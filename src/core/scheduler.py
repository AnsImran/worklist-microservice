"""Background scheduler — the 30-second tick loop.

Orchestrates the entire simulation:
1. Hot-reload JSON configs
2. Generate new studies
3. Advance existing studies through lifecycle
4. Process demand file
5. Persist state to disk
"""

import asyncio
import logging
import random
from typing import Any

from src.config import (
    DEFAULT_ACTIVE_WORKLIST_MAX,
    DEFAULT_STUDIES_PER_TICK_MAX,
    DEFAULT_STUDIES_PER_TICK_MIN,
    DEFAULT_TICK_INTERVAL,
    FIELD_DEFINITIONS_FILE,
    GENERATION_RATES_FILE,
    LIFECYCLE_FILE,
)
from src.core.field_registry import FieldRegistry
from src.core.generator import StudyGenerator
from src.core.hot_reload import HotReloader
from src.core.lifecycle import LifecycleEngine
from src.data.store import DataStore
from src.services.audit_logger import AuditLogger
from src.services.demand_processor import DemandProcessor

logger = logging.getLogger(__name__)


class Scheduler:
    """The main background loop that drives the worklist simulation."""

    def __init__(
        self,
        store: DataStore,
        field_registry: FieldRegistry,
        generator: StudyGenerator,
        lifecycle_engine: LifecycleEngine,
        audit_logger: AuditLogger,
        demand_processor: DemandProcessor,
    ) -> None:
        self.store = store
        self.field_registry = field_registry
        self.generator = generator
        self.lifecycle_engine = lifecycle_engine
        self.audit_logger = audit_logger
        self.demand_processor = demand_processor
        self.hot_reloader = HotReloader()

        # Configurable via generation_rates.json
        self.tick_interval: int = DEFAULT_TICK_INTERVAL
        self.studies_per_tick_min: int = DEFAULT_STUDIES_PER_TICK_MIN
        self.studies_per_tick_max: int = DEFAULT_STUDIES_PER_TICK_MAX
        self.active_max: int = DEFAULT_ACTIVE_WORKLIST_MAX

    async def run(self) -> None:
        """Main loop — runs until cancelled."""
        logger.info("Scheduler started (tick every %d seconds)", self.tick_interval)
        # Do an initial config load
        self._reload_configs()

        while True:
            try:
                self._tick()
            except Exception:
                logger.exception("Error during scheduler tick")
            await asyncio.sleep(self.tick_interval)

    def _tick(self) -> None:
        """A single 30-second tick."""
        # 1. Hot-reload configs
        self._reload_configs()

        # 2. Generate new studies
        self._generate_studies()

        # 3. Advance lifecycle
        self.lifecycle_engine.advance_all()

        # 4. Process demands
        self.demand_processor.process()

        # 5. Persist to disk
        self.store.save_to_disk()

        active = len(self.store.active_studies)
        archived = len(self.store.archived_studies)
        logger.info("Tick complete: %d active, %d archived", active, archived)

    def _reload_configs(self) -> None:
        """Check all config files for changes and reload if needed."""
        results = self.hot_reloader.check_all_configs()

        # Field definitions
        fd_result = results.get("field_definitions.json")
        if fd_result and fd_result[1]:  # changed
            self.field_registry.load(fd_result[0])
            logger.info("Reloaded field definitions")

        # Lifecycle config
        lc_result = results.get("lifecycle.json")
        if lc_result and lc_result[1]:
            self.generator.update_lifecycle_config(lc_result[0])
            logger.info("Reloaded lifecycle config")

        # Generation rates
        gr_result = results.get("generation_rates.json")
        if gr_result and gr_result[1]:
            self._apply_generation_rates(gr_result[0])
            logger.info("Reloaded generation rates")

        # Pool files — update field registry's cached pools
        for filename, (data, changed) in results.items():
            if changed and filename not in (
                "field_definitions.json",
                "lifecycle.json",
                "generation_rates.json",
            ):
                self.field_registry.reload_pool(filename, data)

    def _apply_generation_rates(self, config: dict[str, Any]) -> None:
        """Apply generation rate configuration."""
        tick_cfg = config.get("studies_per_tick", {})
        self.studies_per_tick_min = tick_cfg.get("min", DEFAULT_STUDIES_PER_TICK_MIN)
        self.studies_per_tick_max = tick_cfg.get("max", DEFAULT_STUDIES_PER_TICK_MAX)
        self.active_max = config.get("active_worklist_max_size", DEFAULT_ACTIVE_WORKLIST_MAX)
        self.tick_interval = config.get("tick_interval_seconds", DEFAULT_TICK_INTERVAL)

    def _generate_studies(self) -> None:
        """Generate a batch of new studies if below the max active limit."""
        if len(self.store.active_studies) >= self.active_max:
            return

        count = random.randint(self.studies_per_tick_min, self.studies_per_tick_max)
        # Don't exceed the max
        remaining = self.active_max - len(self.store.active_studies)
        count = min(count, remaining)

        studies = self.generator.generate_batch(count)
        for study in studies:
            self.store.add_study(study)
            self.audit_logger.log_study_created(
                accession=study.accession_number,
                patient=study.patient_name,
                description=study.study_description,
            )

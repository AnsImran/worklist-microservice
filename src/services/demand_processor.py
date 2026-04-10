"""Demand processor — reads demanded_data.json and injects studies into the worklist.

On each tick, this module:
1. Reads demand/demanded_data.json
2. Finds requests where processed == false
3. Creates studies with the specified characteristics
4. Marks requests as processed and writes the file back
"""

import json
import logging
import os

from src.config import DEMAND_FILE
from src.core.generator import StudyGenerator
from src.data.store import DataStore
from src.models.demand import DemandRequest
from src.services.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class DemandProcessor:
    """Processes study injection demands from demanded_data.json."""

    def __init__(
        self,
        store: DataStore,
        generator: "StudyGenerator",
        audit_logger: AuditLogger,
    ) -> None:
        self.store = store
        self.generator = generator
        self.audit_logger = audit_logger

    def process(self) -> None:
        """Check for unprocessed demands and execute them."""
        if not DEMAND_FILE.exists():
            return

        try:
            raw = json.loads(DEMAND_FILE.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to read demand file")
            return

        requests = raw.get("requests", [])
        any_processed = False

        for i, req_data in enumerate(requests):
            try:
                req = DemandRequest.model_validate(req_data)
            except Exception:
                logger.warning("Invalid demand request at index %d, skipping", i)
                continue

            if req.processed:
                continue

            if req.action == "inject_study":
                try:
                    self._inject_study(req)
                except Exception:
                    logger.exception("Failed to inject study for demand %s", req.id)
                    continue  # Don't mark as processed — retry next tick
            else:
                logger.warning("Unknown demand action: %s", req.action)

            # Mark as processed in the raw data (only reached on success)
            requests[i]["processed"] = True
            any_processed = True
            logger.info("Processed demand: %s", req.id)

        if any_processed:
            raw["requests"] = requests
            self._write_demand_file(raw)

    def _inject_study(self, req: DemandRequest) -> None:
        """Create a study from a demand request and add it to the worklist."""
        overrides: dict = {}
        if req.study:
            if req.study.patient_name:
                overrides["patient_name"] = req.study.patient_name
            if req.study.modality:
                overrides["modality"] = req.study.modality
            if req.study.study_description:
                overrides["study_description"] = req.study.study_description
            if req.study.priority is not None:
                overrides["priority"] = req.study.priority
            if req.study.extra_fields:
                overrides["extra_fields"] = req.study.extra_fields

        study = self.generator.generate_one(
            overrides=overrides,
            lifecycle_overrides=req.lifecycle_overrides,
            cancel_at_stage=req.cancel_at_stage,
        )

        self.store.add_study(study)
        self.audit_logger.log_demand_injected(
            accession=study.accession_number,
            patient=study.patient_name,
            demand_id=req.id,
        )

    @staticmethod
    def _write_demand_file(data: dict) -> None:
        """Write demand file back atomically."""
        tmp = DEMAND_FILE.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp, DEMAND_FILE)
        except Exception:
            logger.exception("Failed to write demand file")
            if tmp.exists():
                tmp.unlink()

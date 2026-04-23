"""Study generator — creates new studies using the field registry and lifecycle config.

On each tick, generates a batch of new studies. Each study gets:
1. All field values generated according to field_definitions.json
2. A complete pre-computed lifecycle timeline (all transition timestamps decided at birth)
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from src.core.field_registry import FieldRegistry
from src.data.store import DataStore
from src.models.study import Study, StudyTimeline

logger = logging.getLogger(__name__)


class StudyGenerator:
    """Generates new worklist studies."""

    def __init__(
        self,
        store: DataStore,
        field_registry: FieldRegistry,
        lifecycle_config: dict[str, Any],
    ) -> None:
        self.store = store
        self.field_registry = field_registry
        self.lifecycle_config = lifecycle_config

    def update_lifecycle_config(self, config: dict[str, Any]) -> None:
        self.lifecycle_config = config

    def generate_batch(self, count: int) -> list[Study]:
        """Generate a batch of new studies."""
        studies = []
        for _ in range(count):
            study = self.generate_one()
            studies.append(study)
        return studies

    def generate_one(
        self,
        overrides: dict[str, Any] | None = None,
        lifecycle_overrides: dict[str, int] | None = None,
        cancel_at_stage: str | None = None,
        introduced_at: datetime | None = None,
    ) -> Study:
        """Generate a single new study.

        Args:
            overrides: Field values to use instead of generating. For demand system.
            lifecycle_overrides: Custom transition delays in seconds. For demand system.
            cancel_at_stage: If set, study will be cancelled at this stage.
            introduced_at: Anchor timestamp for when the study enters the worklist.
                           Defaults to now. All timeline transitions are computed relative to this.
        """
        overrides = overrides or {}
        now = introduced_at or datetime.now(timezone.utc)

        # Step 1: Generate all field values using the field registry
        context: dict[str, Any] = {}
        extra_fields: dict[str, Any] = {}

        # Core fields we build the Study model from
        core_field_names = {
            "accession_number", "patient_name", "mrn", "dob", "modality",
            "study_description", "priority", "rvu", "status",
            "study_introduced_at", "assigned_at", "assigned_radiologist",
            "assigned_by",
        }

        for field_def in self.field_registry.fields:
            name = field_def["name"]

            # Use override if provided
            if name in overrides:
                context[name] = overrides[name]
                continue

            # Handle special strategies that need the store
            strategy = field_def.get("generation_strategy", "")

            if strategy == "sequential_prefix":
                prefix = field_def.get("prefix", "ACC")
                zero_pad = field_def.get("zero_pad", 10)
                context[name] = self.store.next_accession_number(prefix, zero_pad)
                continue

            if strategy == "current_time":
                context[name] = now
                continue

            if strategy == "lifecycle_timestamp":
                context[name] = None
                continue

            # Fields with trigger_status are set during lifecycle, not at creation
            if field_def.get("trigger_status"):
                context[name] = None
                continue

            # Generate using field registry
            value = self.field_registry.generate_value(field_def, context)
            context[name] = value

        # Step 2: For patient_name override from demand, look up MRN/DOB if not also overridden
        if "patient_name" in overrides and "mrn" not in overrides:
            for field_def in self.field_registry.fields:
                if field_def["name"] == "mrn":
                    context["mrn"] = self.field_registry.generate_value(field_def, context)
        if "patient_name" in overrides and "dob" not in overrides:
            for field_def in self.field_registry.fields:
                if field_def["name"] == "dob":
                    context["dob"] = self.field_registry.generate_value(field_def, context)

        # Step 3: Compute the full lifecycle timeline
        timeline = self._compute_timeline(now, lifecycle_overrides, cancel_at_stage)

        # Step 4: Separate core fields from extra fields
        for key, value in context.items():
            if key not in core_field_names and value is not None:
                extra_fields[key] = value

        # Step 5: Build the Study object (use `or` to catch both missing keys and None values)
        study = Study(
            accession_number=context.get("accession_number") or "UNKNOWN",
            patient_name=context.get("patient_name") or "Unknown Patient",
            mrn=context.get("mrn") or "UNKNOWN",
            dob=context.get("dob") or "01/01/2000",
            modality=context.get("modality") or "CT",
            study_description=context.get("study_description") or "Unknown Study",
            priority=context.get("priority") or 5,
            rvu=context.get("rvu") or 1.0,
            status="Introduced",
            study_introduced_at=now,
            timeline=timeline,
            lifecycle_overrides=lifecycle_overrides,
            extra_fields=extra_fields,
        )

        return study

    def _compute_timeline(
        self,
        introduced_at: datetime,
        lifecycle_overrides: dict[str, int] | None = None,
        cancel_at_stage: str | None = None,
    ) -> StudyTimeline:
        """Pre-compute the full lifecycle timeline at study creation.

        All transition timestamps are determined now. The lifecycle engine
        just checks if now >= next_timestamp on each tick.
        """
        transitions = self.lifecycle_config.get("transitions", {})
        cancel_prob = self.lifecycle_config.get("cancellation_probability", 0.02)
        overrides = lifecycle_overrides or {}

        def get_delay(transition_key: str) -> int:
            """Get delay in seconds — from override or random within config range."""
            if transition_key in overrides:
                return overrides[transition_key]
            cfg = transitions.get(transition_key, {})
            min_s = cfg.get("min_seconds", 60)
            max_s = cfg.get("max_seconds", 300)
            return random.randint(min_s, max_s)

        # Determine if this study will be cancelled
        will_cancel = cancel_at_stage is not None
        if not will_cancel and random.random() < cancel_prob:
            cancellable = self.lifecycle_config.get(
                "cancellable_stages", ["Introduced", "Assigned", "Dictating", "Pending Approval"]
            )
            cancel_at_stage = random.choice(cancellable)
            will_cancel = True

        # Compute timestamps for each transition
        assigned_at = introduced_at + timedelta(
            seconds=get_delay("Introduced_to_Assigned")
        )
        dictating_at = assigned_at + timedelta(
            seconds=get_delay("Assigned_to_Dictating")
        )
        pending_at = dictating_at + timedelta(
            seconds=get_delay("Dictating_to_Pending_Approval")
        )
        approved_at = pending_at + timedelta(
            seconds=get_delay("Pending_Approval_to_Approved")
        )

        timeline = StudyTimeline(
            will_be_assigned_at=assigned_at,
            will_start_dictating_at=dictating_at,
            will_be_pending_approval_at=pending_at,
            will_be_approved_at=approved_at,
        )

        # If cancellation is scheduled, set the cancellation time
        if will_cancel and cancel_at_stage:
            stage_times = {
                "Introduced": introduced_at + timedelta(
                    seconds=random.randint(10, get_delay("Introduced_to_Assigned") // 2 or 30)
                ),
                "Assigned": assigned_at + timedelta(
                    seconds=random.randint(10, get_delay("Assigned_to_Dictating") // 2 or 15)
                ),
                "Dictating": dictating_at + timedelta(
                    seconds=random.randint(10, get_delay("Dictating_to_Pending_Approval") // 2 or 60)
                ),
                "Pending Approval": pending_at + timedelta(
                    seconds=random.randint(10, get_delay("Pending_Approval_to_Approved") // 2 or 30)
                ),
            }
            cancel_time = stage_times.get(cancel_at_stage, approved_at)
            timeline.will_be_cancelled_at = cancel_time
            timeline.cancel_at_stage = cancel_at_stage

        return timeline

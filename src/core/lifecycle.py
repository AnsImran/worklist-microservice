"""Lifecycle engine — advances studies through status transitions.

On each tick, iterates all active studies and checks if their pre-computed
transition timestamp has been reached. If so, transitions to the next status.

The lifecycle flow is:
  Introduced → Assigned → Reading → Pending Approval → Approved
  (Cancelled can happen at any stage if pre-determined at creation)
"""

import logging
from datetime import datetime, timezone

from src.core.field_registry import FieldRegistry
from src.data.store import DataStore
from src.services.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

# Ordered lifecycle stages
LIFECYCLE_ORDER = ["Introduced", "Assigned", "Reading", "Pending Approval", "Approved"]
TERMINAL_STATUSES = {"Approved", "Cancelled"}


class LifecycleEngine:
    """Advances studies through their pre-computed lifecycle timelines."""

    def __init__(
        self,
        store: DataStore,
        field_registry: FieldRegistry,
        audit_logger: AuditLogger,
    ) -> None:
        self.store = store
        self.field_registry = field_registry
        self.audit_logger = audit_logger

    def advance_all(self) -> None:
        """Check all active studies and advance those whose time has come."""
        now = datetime.now(timezone.utc)
        to_archive: list[str] = []

        for accession, study in list(self.store.active_studies.items()):
            try:
                if study.status in TERMINAL_STATUSES:
                    to_archive.append(accession)
                    continue

                timeline = study.timeline

                # Check for cancellation first
                if (
                    timeline.will_be_cancelled_at
                    and timeline.cancel_at_stage == study.status
                    and now >= timeline.will_be_cancelled_at
                ):
                    old_status = study.status
                    study.status = "Cancelled"
                    self.audit_logger.log_status_change(
                        accession, study.patient_name, old_status, "Cancelled"
                    )
                    to_archive.append(accession)
                    continue

                # Check for normal transitions
                transitioned = True
                while transitioned:
                    transitioned = False

                    if study.status == "Introduced" and timeline.will_be_assigned_at and now >= timeline.will_be_assigned_at:
                        self._transition_to_assigned(study, now)
                        transitioned = True

                    elif study.status == "Assigned" and timeline.will_start_reading_at and now >= timeline.will_start_reading_at:
                        old = study.status
                        study.status = "Reading"
                        self.audit_logger.log_status_change(accession, study.patient_name, old, "Reading")
                        transitioned = True

                    elif study.status == "Reading" and timeline.will_be_pending_approval_at and now >= timeline.will_be_pending_approval_at:
                        old = study.status
                        study.status = "Pending Approval"
                        self.audit_logger.log_status_change(accession, study.patient_name, old, "Pending Approval")
                        transitioned = True

                    elif study.status == "Pending Approval" and timeline.will_be_approved_at and now >= timeline.will_be_approved_at:
                        old = study.status
                        study.status = "Approved"
                        self.audit_logger.log_status_change(accession, study.patient_name, old, "Approved")
                        to_archive.append(accession)
                        transitioned = False  # Terminal — stop

                    # Re-check cancellation after each transition
                    if (
                        transitioned
                        and timeline.will_be_cancelled_at
                        and timeline.cancel_at_stage == study.status
                        and now >= timeline.will_be_cancelled_at
                    ):
                        old = study.status
                        study.status = "Cancelled"
                        self.audit_logger.log_status_change(accession, study.patient_name, old, "Cancelled")
                        to_archive.append(accession)
                        break
            except Exception:
                logger.exception("Error advancing study %s, skipping", accession)

        # Archive terminal studies
        for accession in to_archive:
            self.store.archive_study(accession)

    def _transition_to_assigned(self, study, now: datetime) -> None:
        """Handle the Introduced → Assigned transition (sets radiologist fields)."""
        old = study.status
        study.status = "Assigned"
        study.assigned_at = now

        # Generate radiologist and assigned_by using field registry
        context = {"patient_name": study.patient_name, "modality": study.modality}
        for field_def in self.field_registry.fields:
            if field_def["name"] == "assigned_radiologist":
                study.assigned_radiologist = self.field_registry.generate_value(field_def, context)
                context["assigned_radiologist"] = study.assigned_radiologist
            elif field_def["name"] == "assigned_by":
                study.assigned_by = self.field_registry.generate_value(field_def, context)

        self.audit_logger.log_status_change(
            study.accession_number, study.patient_name, old, "Assigned"
        )
        if study.assigned_radiologist:
            self.audit_logger.log_assignment(
                study.accession_number,
                study.patient_name,
                study.assigned_radiologist,
                study.assigned_by or "Unknown",
            )

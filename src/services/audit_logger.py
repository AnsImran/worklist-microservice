"""Audit logger — records every worklist event to the data store.

Mirrors the real Exa PACS audit log format with columns:
  LOGGED DATE, SCREEN, USER, PATIENT NAME, LOG DESCRIPTION, ACCESSION NUMBER

Screen types used:
  - "New Study"    : A new study was created and added to the worklist
  - "Studies"      : A study's status changed (Assigned, Dictating, Pending Approval, Approved, Cancelled)
  - "Assignment"   : A study was assigned to a radiologist
  - "Demand"       : A study was injected via the demand system
"""

from datetime import datetime, timezone

from src.data.store import DataStore
from src.models.audit import AuditEntry


class AuditLogger:
    """Writes audit log entries to the data store."""

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def log(
        self,
        screen: str,
        accession_number: str,
        patient_name: str,
        description: str,
        user: str = "System (Simulator)",
        logged_date: datetime | None = None,
    ) -> None:
        entry = AuditEntry(
            logged_date=logged_date or datetime.now(timezone.utc),
            screen=screen,
            user=user,
            patient_name=patient_name,
            accession_number=accession_number,
            log_description=description,
        )
        self.store.add_audit_entry(entry)

    def log_study_created(self, accession: str, patient: str, description: str) -> None:
        self.log(
            screen="New Study",
            accession_number=accession,
            patient_name=patient,
            description=f"Add: New Study ({description}) created",
        )

    def log_status_change(
        self,
        accession: str,
        patient: str,
        old_status: str,
        new_status: str,
        logged_date: datetime | None = None,
    ) -> None:
        self.log(
            screen="Studies",
            accession_number=accession,
            patient_name=patient,
            description=f"Status changed from ({old_status}) to ({new_status})",
            logged_date=logged_date,
        )

    def log_assignment(
        self,
        accession: str,
        patient: str,
        radiologist: str,
        assigned_by: str,
        logged_date: datetime | None = None,
    ) -> None:
        self.log(
            screen="Assignment",
            accession_number=accession,
            patient_name=patient,
            description=f"Assigned to ({radiologist}) by ({assigned_by})",
            logged_date=logged_date,
        )

    def log_demand_injected(self, accession: str, patient: str, demand_id: str) -> None:
        self.log(
            screen="Demand",
            accession_number=accession,
            patient_name=patient,
            description=f"Study injected via demand system (demand_id={demand_id})",
        )

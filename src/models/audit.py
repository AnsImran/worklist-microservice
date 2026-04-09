"""Pydantic model for audit log entries."""

from datetime import datetime

from pydantic import BaseModel


class AuditEntry(BaseModel):
    """A single audit log entry tracking a worklist event."""

    logged_date: datetime
    screen: str  # Event category: "New Study", "Studies", "Assignment", etc.
    user: str  # Who performed the action (or "System (Simulator)")
    patient_name: str
    accession_number: str
    log_description: str

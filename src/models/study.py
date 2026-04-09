"""Pydantic models for worklist studies."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StudyTimeline(BaseModel):
    """Pre-computed lifecycle timestamps. Determined at study creation."""

    will_be_assigned_at: datetime | None = None
    will_start_reading_at: datetime | None = None
    will_be_pending_approval_at: datetime | None = None
    will_be_approved_at: datetime | None = None
    will_be_cancelled_at: datetime | None = None
    cancel_at_stage: str | None = None


class Study(BaseModel):
    """A single study/exam in the worklist."""

    # Core identifiers
    accession_number: str
    patient_name: str
    mrn: str
    dob: str

    # Exam details
    modality: str
    study_description: str
    priority: int = Field(ge=1, le=10)
    rvu: float

    # Status & lifecycle
    status: str = "Introduced"
    study_introduced_at: datetime
    assigned_at: datetime | None = None
    assigned_radiologist: str | None = None
    assigned_by: str | None = None

    # Pre-computed timeline (internal — controls when transitions happen)
    timeline: StudyTimeline = Field(default_factory=StudyTimeline)

    # Lifecycle overrides from demand system
    lifecycle_overrides: dict[str, int] | None = None

    # Dynamic fields added via field_definitions.json
    extra_fields: dict[str, Any] = Field(default_factory=dict)

    def to_api_response(self) -> dict[str, Any]:
        """Serialize for API responses — excludes internal timeline, flattens extra_fields."""
        data = self.model_dump(exclude={"timeline", "lifecycle_overrides"})
        extras = data.pop("extra_fields", {})
        data.update(extras)
        return data


class StudyCreate(BaseModel):
    """Request body for manually creating a study via POST /studies."""

    patient_name: str | None = None
    mrn: str | None = None
    modality: str | None = None
    study_description: str | None = None
    priority: int | None = Field(default=None, ge=1, le=10)
    rvu: float | None = None
    extra_fields: dict[str, Any] = Field(default_factory=dict)


class StudyStatusUpdate(BaseModel):
    """Request body for PUT /studies/{accession}/status."""

    status: str

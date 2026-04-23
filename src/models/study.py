"""Pydantic models for worklist studies."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StudyTimeline(BaseModel):
    """Pre-computed lifecycle timestamps. Determined at study creation."""

    will_be_assigned_at: datetime | None = None
    will_start_dictating_at: datetime | None = None
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

    # Status & lifecycle timestamps
    status: str = "Introduced"
    study_introduced_at: datetime
    assigned_at: datetime | None = None
    dictating_started_at: datetime | None = None
    submitted_for_approval_at: datetime | None = None
    approved_at: datetime | None = None

    # Assignment details
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


class StudyReassignment(BaseModel):
    """Manually reassign a study to a different radiologist.

    Only valid when the study is currently in Assigned status. Resets
    `assigned_at` to the current time so the new radiologist's clock
    starts fresh (this is what the notification-system engine reads to
    compute the 2-min nag and 6-min reassignment thresholds). The
    pre-computed timeline (will_start_dictating_at, etc.) is left alone
    so the study's scheduled progression is unaffected.
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"assigned_radiologist": "Jones, Mary M.D.", "assigned_by": "Support Team"},
            ]
        }
    }

    assigned_radiologist: str = Field(
        min_length=1,
        description="New radiologist name. Format: 'Last, First M.D.' or similar.",
        examples=["Jones, Mary M.D."],
    )
    assigned_by: str | None = Field(
        default="Support Team",
        description="Who performed the reassignment. Defaults to 'Support Team' when omitted.",
        examples=["Support Team"],
    )


class StudyStatusUpdate(BaseModel):
    """Manually change a study's status.

    Valid transitions follow the lifecycle order:
      Introduced  -> Assigned  or Cancelled
      Assigned    -> Dictating   or Cancelled
      Dictating     -> Pending Approval or Cancelled
      Pending Approval -> Approved or Cancelled
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"status": "Assigned"},
            ]
        }
    }

    status: str = Field(
        description=(
            "Target status. Valid transitions: "
            "Introduced -> Assigned or Cancelled | "
            "Assigned -> Dictating or Cancelled | "
            "Dictating -> Pending Approval or Cancelled | "
            "Pending Approval -> Approved or Cancelled"
        ),
        examples=["Assigned", "Dictating", "Pending Approval", "Approved", "Cancelled"],
    )

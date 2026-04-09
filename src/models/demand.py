"""Pydantic model for demand system requests."""

from typing import Any

from pydantic import BaseModel


class DemandStudy(BaseModel):
    """Study characteristics specified in a demand request."""

    patient_name: str | None = None
    modality: str | None = None
    study_description: str | None = None
    priority: int | None = None
    extra_fields: dict[str, Any] | None = None


class DemandRequest(BaseModel):
    """A single demand request from demanded_data.json."""

    id: str
    processed: bool = False
    action: str = "inject_study"
    study: DemandStudy | None = None
    lifecycle_overrides: dict[str, int] | None = None
    cancel_at_stage: str | None = None

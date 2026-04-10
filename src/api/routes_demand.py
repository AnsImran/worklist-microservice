"""Demand API route — create studies with full control over characteristics and timing.

Two endpoints:
  POST /demand       — create a single study
  POST /demand/batch — create multiple studies in one call
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import get_field_registry, get_store
from src.core.field_registry import FieldRegistry
from src.core.generator import StudyGenerator
from src.data.store import DataStore
from src.services.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demand", tags=["demand"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class DemandStudyInput(BaseModel):
    """Study characteristics. Every field is optional — omitted fields are randomly generated."""

    patient_name: str | None = Field(
        default=None,
        description="Patient full name in 'Last, First Middle' format.",
        examples=["Garcia, Maria L"],
    )
    mrn: str | None = Field(
        default=None,
        description="Medical record number. Auto-generated if omitted.",
        examples=["SHHD2100392"],
    )
    modality: str | None = Field(
        default=None,
        description="Imaging modality. One of: CT, CR, DX, MR, US, NM.",
        examples=["CT"],
    )
    study_description: str | None = Field(
        default=None,
        description="Short exam description.",
        examples=["CT BRAIN STROKE W/O CONTRAST"],
    )
    priority: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="Priority level from 1 (lowest) to 10 (highest/STAT).",
        examples=[10],
    )
    rvu: float | None = Field(
        default=None,
        description="Relative Value Unit — complexity/reimbursement weight.",
        examples=[3.5],
    )
    extra_fields: dict[str, Any] | None = Field(
        default=None,
        description="Any additional custom key-value fields to attach to the study.",
        examples=[{"study_flag": "ER"}],
    )


class DemandInput(BaseModel):
    """Create a study with specific characteristics and lifecycle timing.

    All fields are optional. Omitted study fields are randomly generated.
    Omitted lifecycle overrides use the default random timing from lifecycle.json.
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "study": {
                        "patient_name": "Garcia, Maria L",
                        "modality": "CT",
                        "study_description": "CT BRAIN STROKE W/O CONTRAST",
                        "priority": 10,
                        "rvu": 3.5,
                    },
                    "study_introduced_at": "2026-04-10T10:00:00Z",
                    "lifecycle_overrides": {
                        "Introduced_to_Assigned": 30,
                        "Assigned_to_Reading": 30,
                        "Reading_to_Pending_Approval": 60,
                        "Pending_Approval_to_Approved": 30,
                    },
                    "cancel_at_stage": None,
                }
            ]
        }
    }

    study: DemandStudyInput | None = Field(
        default=None,
        description="Study characteristics. All fields optional — omitted fields are randomly generated.",
    )
    study_introduced_at: datetime | None = Field(
        default=None,
        description=(
            "Anchor timestamp for when the study enters the worklist. "
            "All lifecycle transitions are computed relative to this time. "
            "Defaults to the current time if omitted."
        ),
        examples=["2026-04-10T10:00:00Z"],
    )
    lifecycle_overrides: dict[str, int] | None = Field(
        default=None,
        description=(
            "Override the random transition delays with exact values in seconds. "
            "Available keys: "
            "Introduced_to_Assigned, "
            "Assigned_to_Reading, "
            "Reading_to_Pending_Approval, "
            "Pending_Approval_to_Approved. "
            "Omitted keys use the default random range from lifecycle.json."
        ),
        examples=[{
            "Introduced_to_Assigned": 30,
            "Assigned_to_Reading": 30,
            "Reading_to_Pending_Approval": 60,
            "Pending_Approval_to_Approved": 30,
        }],
    )
    cancel_at_stage: str | None = Field(
        default=None,
        description=(
            "If set, the study will be cancelled at this stage instead of progressing further. "
            "Valid values: Introduced, Assigned, Reading, Pending Approval."
        ),
        examples=["Reading"],
    )


# ---------------------------------------------------------------------------
# Shared logic
# ---------------------------------------------------------------------------

def _create_one_study(
    body: DemandInput,
    store: DataStore,
    field_registry: FieldRegistry,
) -> dict[str, Any]:
    """Create a single study from a DemandInput and return its API response dict."""
    audit_logger = AuditLogger(store)
    lifecycle_config = getattr(store, "_lifecycle_config", {})
    generator = StudyGenerator(store, field_registry, lifecycle_config)

    overrides: dict[str, Any] = {}
    if body.study:
        if body.study.patient_name:
            overrides["patient_name"] = body.study.patient_name
        if body.study.mrn:
            overrides["mrn"] = body.study.mrn
        if body.study.modality:
            overrides["modality"] = body.study.modality
        if body.study.study_description:
            overrides["study_description"] = body.study.study_description
        if body.study.priority is not None:
            overrides["priority"] = body.study.priority
        if body.study.rvu is not None:
            overrides["rvu"] = body.study.rvu
        if body.study.extra_fields:
            overrides["extra_fields"] = body.study.extra_fields

    study = generator.generate_one(
        overrides=overrides,
        lifecycle_overrides=body.lifecycle_overrides,
        cancel_at_stage=body.cancel_at_stage,
        introduced_at=body.study_introduced_at,
    )
    store.add_study(study)
    audit_logger.log_study_created(
        accession=study.accession_number,
        patient=study.patient_name,
        description=study.study_description,
    )

    return study.to_api_response()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    summary="Create a single study",
    description=(
        "Create a new study in the worklist with full control over its characteristics and lifecycle timing. "
        "All fields are optional — omitted study fields are randomly generated from the configured pools. "
        "Omitted lifecycle overrides use the default random timing from lifecycle.json. "
        "The study is created immediately and appears in the active worklist right away."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "study": {
                            "accession_number": "COCSNV0000000042",
                            "patient_name": "Garcia, Maria L",
                            "mrn": "SHHD2100392",
                            "dob": "04/08/1975",
                            "modality": "CT",
                            "study_description": "CT BRAIN STROKE W/O CONTRAST",
                            "priority": 10,
                            "rvu": 3.5,
                            "status": "Introduced",
                            "study_introduced_at": "2026-04-10T10:00:00Z",
                            "assigned_at": None,
                            "assigned_radiologist": None,
                            "assigned_by": None,
                        },
                        "message": "Study created successfully",
                    }
                }
            }
        }
    },
)
def create_demand(
    body: DemandInput,
    store: DataStore = Depends(get_store),
    field_registry: FieldRegistry = Depends(get_field_registry),
) -> dict[str, Any]:
    try:
        study_data = _create_one_study(body, store, field_registry)
        return {"study": study_data, "message": "Study created successfully"}
    except Exception:
        logger.exception("Error creating study via demand")
        raise HTTPException(status_code=500, detail="Failed to create study")


@router.post(
    "/batch",
    summary="Create multiple studies in one call",
    description=(
        "Create multiple studies in a single API call. Each item in the list follows "
        "the same schema as POST /demand (single study). All studies are created immediately. "
        "Useful for seeding the worklist with test data or simulating a batch of incoming exams."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "studies": [
                            {
                                "accession_number": "COCSNV0000000042",
                                "patient_name": "Garcia, Maria L",
                                "modality": "CT",
                                "priority": 10,
                                "status": "Introduced",
                            },
                            {
                                "accession_number": "COCSNV0000000043",
                                "patient_name": "Smith, John R",
                                "modality": "MR",
                                "priority": 5,
                                "status": "Introduced",
                            },
                        ],
                        "message": "2 studies created successfully",
                    }
                }
            }
        }
    },
)
def create_demand_batch(
    body: list[DemandInput],
    store: DataStore = Depends(get_store),
    field_registry: FieldRegistry = Depends(get_field_registry),
) -> dict[str, Any]:
    try:
        created = [_create_one_study(d, store, field_registry) for d in body]
        return {
            "studies": created,
            "message": f"{len(created)} studies created successfully",
        }
    except Exception:
        logger.exception("Error creating studies via batch demand")
        raise HTTPException(status_code=500, detail="Failed to create studies")

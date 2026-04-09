"""Study management API routes — create and update studies manually."""

from typing import Any

from fastapi import APIRouter, Depends

from src.api.dependencies import get_field_registry, get_store
from src.core.field_registry import FieldRegistry
from src.core.generator import StudyGenerator
from src.data.store import DataStore
from src.models.study import StudyCreate, StudyStatusUpdate
from src.services.audit_logger import AuditLogger

router = APIRouter(prefix="/studies", tags=["studies"])


@router.post("", summary="Manually create a new study")
def create_study(
    body: StudyCreate,
    store: DataStore = Depends(get_store),
    field_registry: FieldRegistry = Depends(get_field_registry),
) -> dict[str, Any]:
    audit_logger = AuditLogger(store)
    lifecycle_config = getattr(store, "_lifecycle_config", {})
    generator = StudyGenerator(store, field_registry, lifecycle_config)

    overrides = {}
    if body.patient_name:
        overrides["patient_name"] = body.patient_name
    if body.mrn:
        overrides["mrn"] = body.mrn
    if body.modality:
        overrides["modality"] = body.modality
    if body.study_description:
        overrides["study_description"] = body.study_description
    if body.priority is not None:
        overrides["priority"] = body.priority
    if body.rvu is not None:
        overrides["rvu"] = body.rvu

    study = generator.generate_one(overrides=overrides)
    store.add_study(study)
    audit_logger.log_study_created(
        accession=study.accession_number,
        patient=study.patient_name,
        description=study.study_description,
    )

    return {"study": study.to_api_response(), "message": "Study created successfully"}


@router.put("/{accession_number}/status", summary="Update a study's status")
def update_study_status(
    accession_number: str,
    body: StudyStatusUpdate,
    store: DataStore = Depends(get_store),
) -> dict[str, Any]:
    study = store.get_study(accession_number)
    if not study:
        return {"error": "Study not found", "accession_number": accession_number}

    valid_transitions = {
        "Introduced": ["Assigned", "Cancelled"],
        "Assigned": ["Reading", "Cancelled"],
        "Reading": ["Pending Approval", "Cancelled"],
        "Pending Approval": ["Approved", "Cancelled"],
    }

    allowed = valid_transitions.get(study.status, [])
    if body.status not in allowed:
        return {
            "error": f"Cannot transition from '{study.status}' to '{body.status}'",
            "allowed_transitions": allowed,
        }

    audit_logger = AuditLogger(store)
    old_status = study.status
    study.status = body.status

    audit_logger.log_status_change(accession_number, study.patient_name, old_status, body.status)

    if body.status in ("Approved", "Cancelled"):
        store.archive_study(accession_number)
        return {"message": f"Study {body.status.lower()}", "accession_number": accession_number}

    return {"study": study.to_api_response(), "message": f"Status updated to {body.status}"}

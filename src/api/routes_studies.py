"""Study management API routes — update study status."""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path

from src.api.dependencies import get_store
from src.data.store import DataStore
from src.models.study import StudyReassignment, StudyStatusUpdate
from src.services.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/studies", tags=["studies"])


@router.put(
    "/{accession_number}/status",
    summary="Update a study's status",
    description=(
        "Manually transition a study to a new lifecycle status. "
        "Only valid transitions are allowed:\n\n"
        "- **Introduced** -> Assigned or Cancelled\n"
        "- **Assigned** -> Dictating or Cancelled\n"
        "- **Dictating** -> Pending Approval or Cancelled\n"
        "- **Pending Approval** -> Approved or Cancelled\n\n"
        "When a study reaches Approved or Cancelled, it is automatically moved to the archive."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "study": {
                            "accession_number": "COCSNV0000000042",
                            "patient_name": "Garcia, Maria L",
                            "status": "Dictating",
                        },
                        "message": "Status updated to Dictating",
                    }
                }
            }
        },
        400: {
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Cannot transition from 'Introduced' to 'Approved'. Allowed: ['Assigned', 'Cancelled']"
                    }
                }
            }
        },
        404: {
            "content": {
                "application/json": {
                    "example": {"detail": "Study COCSNV9999999999 not found"}
                }
            }
        },
    },
)
def update_study_status(
    accession_number: str = Path(
        description="Unique accession number of the study to update.",
        examples=["COCSNV0000000001"],
    ),
    body: StudyStatusUpdate = ...,
    store: DataStore = Depends(get_store),
) -> dict[str, Any]:
    try:
        study = store.get_study(accession_number)
        if not study:
            raise HTTPException(status_code=404, detail=f"Study {accession_number} not found")

        valid_transitions = {
            "Introduced": ["Assigned", "Cancelled"],
            "Assigned": ["Dictating", "Cancelled"],
            "Dictating": ["Pending Approval", "Cancelled"],
            "Pending Approval": ["Approved", "Cancelled"],
        }

        allowed = valid_transitions.get(study.status, [])
        if body.status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from '{study.status}' to '{body.status}'. Allowed: {allowed}",
            )

        audit_logger = AuditLogger(store)
        old_status = study.status
        study.status = body.status

        # Set the corresponding timestamp
        now = datetime.now(timezone.utc)
        if body.status == "Assigned":
            study.assigned_at = now
        elif body.status == "Dictating":
            study.dictating_started_at = now
        elif body.status == "Pending Approval":
            study.submitted_for_approval_at = now
        elif body.status == "Approved":
            study.approved_at = now

        audit_logger.log_status_change(accession_number, study.patient_name, old_status, body.status)

        if body.status in ("Approved", "Cancelled"):
            store.archive_study(accession_number)
            return {"message": f"Study {body.status.lower()}", "accession_number": accession_number}

        return {"study": study.to_api_response(), "message": f"Status updated to {body.status}"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error updating study %s", accession_number)
        raise HTTPException(status_code=500, detail="Failed to update study status")


@router.put(
    "/{accession_number}/assignee",
    summary="Reassign a study to a different radiologist",
    description=(
        "Change the `assigned_radiologist` on a study that is currently in Assigned status. "
        "Resets `assigned_at` to the current time so the new radiologist's assignment clock "
        "starts fresh -- this is what the notification-system engine reads to compute the "
        "2-minute and 6-minute thresholds. The pre-computed internal timeline "
        "(will_start_dictating_at, etc.) is NOT shifted, so the study still progresses to "
        "Dictating at its originally-planned time.\n\n"
        "Rejects if the study is not in Assigned status -- reassignment only makes sense "
        "for a study that already has a radiologist to reassign away from."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "study": {
                            "accession_number": "COCSNV0000000042",
                            "status": "Assigned",
                            "assigned_radiologist": "Jones, Mary M.D.",
                            "assigned_by": "Support Team",
                            "assigned_at": "2026-04-22T08:15:00Z",
                        },
                        "message": "Reassigned to Jones, Mary M.D.",
                        "previous_radiologist": "Wright, Joshua M.D.",
                    }
                }
            }
        },
        400: {
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Cannot reassign study in 'Introduced' status; must be 'Assigned'"
                    }
                }
            }
        },
        404: {
            "content": {
                "application/json": {
                    "example": {"detail": "Study COCSNV9999999999 not found"}
                }
            }
        },
    },
)
def reassign_study(
    accession_number: str = Path(
        description="Unique accession number of the study to reassign.",
        examples=["COCSNV0000000042"],
    ),
    body: StudyReassignment = ...,
    store: DataStore = Depends(get_store),
) -> dict[str, Any]:
    try:
        study = store.get_study(accession_number)
        if not study:
            raise HTTPException(status_code=404, detail=f"Study {accession_number} not found")

        if study.status != "Assigned":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot reassign study in '{study.status}' status; must be 'Assigned'"
                ),
            )

        old_radiologist = study.assigned_radiologist or "Unassigned"
        new_radiologist = body.assigned_radiologist
        assigned_by = body.assigned_by or "Support Team"

        study.assigned_radiologist = new_radiologist
        study.assigned_by = assigned_by
        study.assigned_at = datetime.now(timezone.utc)

        audit_logger = AuditLogger(store)
        audit_logger.log(
            screen="Assignment",
            accession_number=accession_number,
            patient_name=study.patient_name,
            description=(
                f"Reassigned from ({old_radiologist}) to ({new_radiologist}) by ({assigned_by})"
            ),
        )

        return {
            "study": study.to_api_response(),
            "message": f"Reassigned to {new_radiologist}",
            "previous_radiologist": old_radiologist,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error reassigning study %s", accession_number)
        raise HTTPException(status_code=500, detail="Failed to reassign study")

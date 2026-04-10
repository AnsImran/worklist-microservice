"""Study management API routes — update study status."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path

from src.api.dependencies import get_store
from src.data.store import DataStore
from src.models.study import StudyStatusUpdate
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
        "- **Assigned** -> Reading or Cancelled\n"
        "- **Reading** -> Pending Approval or Cancelled\n"
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
                            "status": "Reading",
                        },
                        "message": "Status updated to Reading",
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
            "Assigned": ["Reading", "Cancelled"],
            "Reading": ["Pending Approval", "Cancelled"],
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

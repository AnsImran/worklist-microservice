"""Worklist API routes — live snapshot of active studies."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from src.api.dependencies import get_store
from src.data.store import DataStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/worklist", tags=["worklist"])


@router.get(
    "",
    summary="Get current active worklist",
    description=(
        "Returns all studies currently in the active worklist (not yet archived). "
        "Supports filtering by modality, status, and priority range. "
        "Results are paginated via `limit` and `offset`."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "total": 42,
                        "offset": 0,
                        "limit": 100,
                        "studies": [
                            {
                                "accession_number": "COCSNV0000000001",
                                "patient_name": "Garcia, Maria L",
                                "mrn": "SHHD2100392",
                                "dob": "04/08/1975",
                                "modality": "CT",
                                "study_description": "CT BRAIN STROKE W/O CONTRAST",
                                "priority": 10,
                                "rvu": 3.42,
                                "status": "Reading",
                                "study_introduced_at": "2026-04-10T10:00:00Z",
                                "assigned_at": "2026-04-10T10:02:30Z",
                                "assigned_radiologist": "Wright, Joshua M.D.",
                                "assigned_by": "Wright, Joshua M.D.",
                            }
                        ],
                    }
                }
            }
        }
    },
)
def get_worklist(
    store: DataStore = Depends(get_store),
    accession_number: str | None = Query(
        None,
        description="Filter by accession number (exact match).",
        examples=["COCSNV0000000001"],
    ),
    modality: str | None = Query(
        None,
        description="Filter by imaging modality.",
        examples=["CT", "MR", "CR", "DX", "US", "NM"],
    ),
    status: str | None = Query(
        None,
        description="Filter by current lifecycle status.",
        examples=["Introduced", "Assigned", "Reading", "Pending Approval"],
    ),
    priority_min: int | None = Query(
        None, ge=1, le=10,
        description="Minimum priority (inclusive). 1 = lowest, 10 = STAT.",
        examples=[7],
    ),
    priority_max: int | None = Query(
        None, ge=1, le=10,
        description="Maximum priority (inclusive). 1 = lowest, 10 = STAT.",
        examples=[10],
    ),
    limit: int = Query(
        100, ge=1, le=1000,
        description="Maximum number of results to return (1–1000).",
        examples=[100],
    ),
    offset: int = Query(
        0, ge=0,
        description="Number of results to skip for pagination.",
        examples=[0],
    ),
) -> dict[str, Any]:
    try:
        studies = list(store.active_studies.values())

        if accession_number:
            studies = [s for s in studies if s.accession_number == accession_number]
        if modality:
            studies = [s for s in studies if s.modality == modality]
        if status:
            studies = [s for s in studies if s.status == status]
        if priority_min is not None:
            studies = [s for s in studies if s.priority >= priority_min]
        if priority_max is not None:
            studies = [s for s in studies if s.priority <= priority_max]

        total = len(studies)
        studies = studies[offset : offset + limit]

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "studies": [s.to_api_response() for s in studies],
        }
    except Exception:
        logger.exception("Error fetching worklist")
        raise HTTPException(status_code=500, detail="Failed to retrieve worklist")


@router.get(
    "/{accession_number}",
    summary="Get a single study by accession number",
    description=(
        "Look up a specific study by its unique accession number. "
        "Searches the active worklist first, then the archive."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "study": {
                            "accession_number": "COCSNV0000000001",
                            "patient_name": "Garcia, Maria L",
                            "mrn": "SHHD2100392",
                            "dob": "04/08/1975",
                            "modality": "CT",
                            "study_description": "CT BRAIN STROKE W/O CONTRAST",
                            "priority": 10,
                            "rvu": 3.42,
                            "status": "Reading",
                            "study_introduced_at": "2026-04-10T10:00:00Z",
                            "assigned_at": "2026-04-10T10:02:30Z",
                            "assigned_radiologist": "Wright, Joshua M.D.",
                            "assigned_by": "Wright, Joshua M.D.",
                        },
                        "source": "active",
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
def get_study(
    accession_number: str = Path(
        description="Unique accession number of the study.",
        examples=["COCSNV0000000001"],
    ),
    store: DataStore = Depends(get_store),
) -> dict[str, Any]:
    try:
        study = store.get_study(accession_number)
        if not study:
            for archived in store.archived_studies:
                if archived.get("accession_number") == accession_number:
                    return {"study": archived, "source": "archive"}
            raise HTTPException(status_code=404, detail=f"Study {accession_number} not found")
        return {"study": study.to_api_response(), "source": "active"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching study %s", accession_number)
        raise HTTPException(status_code=500, detail="Failed to retrieve study")

"""History API routes — archived (completed/cancelled) studies."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_store
from src.data.store import DataStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/history", tags=["history"])


@router.get(
    "",
    summary="Get archived studies with optional filters",
    description=(
        "Returns studies that have reached a terminal status (Approved or Cancelled) "
        "and moved to the archive. Supports filtering by modality, final status, "
        "patient name (partial match), and date range. Results are paginated."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "total": 318,
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
                                "status": "Approved",
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
def get_history(
    store: DataStore = Depends(get_store),
    modality: str | None = Query(
        None,
        description="Filter by imaging modality.",
        examples=["CT", "MR", "CR", "DX", "US", "NM"],
    ),
    status: str | None = Query(
        None,
        description="Filter by final status (only terminal statuses exist in archive).",
        examples=["Approved", "Cancelled"],
    ),
    patient_name: str | None = Query(
        None,
        description="Search by patient name (case-insensitive partial match).",
        examples=["Garcia"],
    ),
    date_from: datetime | None = Query(
        None,
        description="Start of date range filter on study_introduced_at (ISO 8601 format).",
        examples=["2026-04-09T00:00:00Z"],
    ),
    date_to: datetime | None = Query(
        None,
        description="End of date range filter on study_introduced_at (ISO 8601 format).",
        examples=["2026-04-10T23:59:59Z"],
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
        studies = list(store.archived_studies)

        if modality:
            studies = [s for s in studies if s.get("modality") == modality]
        if status:
            studies = [s for s in studies if s.get("status") == status]
        if patient_name:
            patient_lower = patient_name.lower()
            studies = [s for s in studies if patient_lower in s.get("patient_name", "").lower()]
        if date_from:
            date_from_str = date_from.isoformat()
            studies = [s for s in studies if s.get("study_introduced_at", "") >= date_from_str]
        if date_to:
            date_to_str = date_to.isoformat()
            studies = [s for s in studies if s.get("study_introduced_at", "") <= date_to_str]

        total = len(studies)
        studies = studies[offset : offset + limit]

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "studies": studies,
        }
    except Exception:
        logger.exception("Error fetching history")
        raise HTTPException(status_code=500, detail="Failed to retrieve history")

"""History API routes — archived (completed/cancelled) studies."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_store
from src.data.store import DataStore

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", summary="Get archived studies with optional filters")
def get_history(
    store: DataStore = Depends(get_store),
    modality: str | None = Query(None, description="Filter by modality"),
    status: str | None = Query(None, description="Filter by final status (Approved/Cancelled)"),
    patient_name: str | None = Query(None, description="Search by patient name (partial match)"),
    date_from: datetime | None = Query(None, description="Start of date range (ISO format)"),
    date_to: datetime | None = Query(None, description="End of date range (ISO format)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
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

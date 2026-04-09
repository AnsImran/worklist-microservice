"""Worklist API routes — live snapshot of active studies."""

from typing import Any

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_store
from src.data.store import DataStore

router = APIRouter(prefix="/worklist", tags=["worklist"])


@router.get("", summary="Get current active worklist")
def get_worklist(
    store: DataStore = Depends(get_store),
    modality: str | None = Query(None, description="Filter by modality (e.g., CT, MR)"),
    status: str | None = Query(None, description="Filter by status"),
    priority_min: int | None = Query(None, ge=1, le=10, description="Minimum priority"),
    priority_max: int | None = Query(None, ge=1, le=10, description="Maximum priority"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    studies = list(store.active_studies.values())

    # Apply filters
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


@router.get("/{accession_number}", summary="Get a single study by accession number")
def get_study(
    accession_number: str,
    store: DataStore = Depends(get_store),
) -> dict[str, Any]:
    study = store.get_study(accession_number)
    if not study:
        # Check archive
        for archived in store.archived_studies:
            if archived.get("accession_number") == accession_number:
                return {"study": archived, "source": "archive"}
        return {"error": "Study not found", "accession_number": accession_number}
    return {"study": study.to_api_response(), "source": "active"}

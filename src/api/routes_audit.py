"""Audit log API routes — event trail for all worklist actions."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_store
from src.data.store import DataStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "",
    summary="Get audit log entries with optional filters",
    description=(
        "Returns the full event log — every study creation, status change, assignment, "
        "and demand injection is recorded here. Supports filtering by event type (screen), "
        "user, accession number, and date range. Results are paginated."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "total": 1205,
                        "offset": 0,
                        "limit": 100,
                        "entries": [
                            {
                                "logged_date": "2026-04-10T10:00:00Z",
                                "screen": "New Study",
                                "user": "System (Worklist)",
                                "patient_name": "Garcia, Maria L",
                                "accession_number": "COCSNV0000000001",
                                "log_description": "New study created: CT BRAIN STROKE W/O CONTRAST",
                            },
                            {
                                "logged_date": "2026-04-10T10:02:30Z",
                                "screen": "Studies",
                                "user": "System (Worklist)",
                                "patient_name": "Garcia, Maria L",
                                "accession_number": "COCSNV0000000001",
                                "log_description": "Status changed from Introduced to Assigned",
                            },
                            {
                                "logged_date": "2026-04-10T10:02:30Z",
                                "screen": "Assignment",
                                "user": "System (Worklist)",
                                "patient_name": "Garcia, Maria L",
                                "accession_number": "COCSNV0000000001",
                                "log_description": "Study assigned to Wright, Joshua M.D. by Wright, Joshua M.D.",
                            },
                        ],
                    }
                }
            }
        }
    },
)
def get_audit_log(
    store: DataStore = Depends(get_store),
    screen: str | None = Query(
        None,
        description="Filter by event type.",
        examples=["New Study", "Studies", "Assignment", "Demand"],
    ),
    user: str | None = Query(
        None,
        description="Filter by user (case-insensitive partial match).",
        examples=["System (Worklist)", "Wright"],
    ),
    accession_number: str | None = Query(
        None,
        description="Filter by accession number to see the full history of one study.",
        examples=["COCSNV0000000001"],
    ),
    date_from: datetime | None = Query(
        None,
        description="Start of date range filter on logged_date (ISO 8601 format).",
        examples=["2026-04-09T00:00:00Z"],
    ),
    date_to: datetime | None = Query(
        None,
        description="End of date range filter on logged_date (ISO 8601 format).",
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
        entries = list(store.audit_entries)

        if screen:
            entries = [e for e in entries if e.get("screen") == screen]
        if user:
            user_lower = user.lower()
            entries = [e for e in entries if user_lower in (e.get("user") or "").lower()]
        if accession_number:
            entries = [e for e in entries if e.get("accession_number") == accession_number]
        if date_from:
            date_from_str = date_from.isoformat()
            entries = [e for e in entries if e.get("logged_date", "") >= date_from_str]
        if date_to:
            date_to_str = date_to.isoformat()
            entries = [e for e in entries if e.get("logged_date", "") <= date_to_str]

        total = len(entries)
        entries = entries[offset : offset + limit]

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "entries": entries,
        }
    except Exception:
        logger.exception("Error fetching audit log")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit log")

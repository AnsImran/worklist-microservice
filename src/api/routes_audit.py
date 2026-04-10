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
                                "screen": "Assignment",
                                "user": "System (Worklist)",
                                "patient_name": "Garcia, Maria L",
                                "accession_number": "COCSNV0000000001",
                                "log_description": "Study assigned to Wright, Joshua M.D. by Wright, Joshua M.D.",
                            },
                            {
                                "logged_date": "2026-04-10T10:02:30Z",
                                "screen": "Studies",
                                "user": "System (Worklist)",
                                "patient_name": "Garcia, Maria L",
                                "accession_number": "COCSNV0000000001",
                                "log_description": "Status changed from Introduced to Assigned",
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
    screen: str | None = Query(None, description="Filter by event type (e.g., 'New Study', 'Studies')"),
    user: str | None = Query(None, description="Filter by user"),
    accession_number: str | None = Query(None, description="Filter by accession number"),
    date_from: datetime | None = Query(None, description="Start of date range (ISO format)"),
    date_to: datetime | None = Query(None, description="End of date range (ISO format)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
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

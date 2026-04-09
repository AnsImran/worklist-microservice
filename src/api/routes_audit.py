"""Audit log API routes — event trail for all worklist actions."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_store
from src.data.store import DataStore

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", summary="Get audit log entries with optional filters")
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
    entries = list(store.audit_entries)

    if screen:
        entries = [e for e in entries if e.get("screen") == screen]
    if user:
        entries = [e for e in entries if user.lower() in e.get("user", "").lower()]
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

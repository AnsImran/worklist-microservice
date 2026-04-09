"""Health and stats API routes."""

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from src.api.dependencies import get_store
from src.data.store import DataStore

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health check")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/stats", summary="Worklist statistics")
def stats(store: DataStore = Depends(get_store)) -> dict[str, Any]:
    active = list(store.active_studies.values())
    status_counts = Counter(s.status for s in active)
    modality_counts = Counter(s.modality for s in active)

    archived_status_counts = Counter(s.get("status", "unknown") for s in store.archived_studies)

    now = datetime.now(timezone.utc)
    uptime = (now - store.startup_time).total_seconds()

    return {
        "active_studies": len(active),
        "archived_studies": len(store.archived_studies),
        "audit_entries": len(store.audit_entries),
        "active_by_status": dict(status_counts),
        "active_by_modality": dict(modality_counts),
        "archived_by_status": dict(archived_status_counts),
        "uptime_seconds": round(uptime),
    }

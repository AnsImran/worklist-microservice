"""Health and stats API routes."""

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_store
from src.data.store import DataStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Service health check",
    description="Returns `{\"status\": \"ok\"}` if the service is running. Use this for uptime monitoring.",
)
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/stats",
    summary="Worklist statistics",
    description=(
        "Returns live aggregate statistics: total active studies, total archived, "
        "total audit entries, breakdowns by status and modality, and service uptime."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "active_studies": 42,
                        "archived_studies": 318,
                        "audit_entries": 1205,
                        "active_by_status": {
                            "Introduced": 8,
                            "Assigned": 12,
                            "Dictating": 15,
                            "Pending Approval": 7,
                        },
                        "active_by_modality": {
                            "CT": 15,
                            "MR": 10,
                            "CR": 8,
                            "DX": 5,
                            "US": 3,
                            "NM": 1,
                        },
                        "archived_by_status": {
                            "Approved": 310,
                            "Cancelled": 8,
                        },
                        "uptime_seconds": 3600,
                    }
                }
            }
        }
    },
)
def stats(store: DataStore = Depends(get_store)) -> dict[str, Any]:
    try:
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
    except Exception:
        logger.exception("Error computing stats")
        raise HTTPException(status_code=500, detail="Failed to compute statistics")

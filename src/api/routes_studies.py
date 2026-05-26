"""Study management API routes — update study status."""

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path

from src.api.dependencies import get_store
from src.data.store import DataStore
from src.models.study import StudyReassignment, StudyStatusUpdate
from src.services.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/studies", tags=["studies"])


def _allow_reverse_transitions() -> bool:
    """Read the env flag fresh on every call (so tests can monkeypatch it).

    When True (set by ``run_all.py --for-e2e``), the mock allows the
    re-dictation cycle that the prod NewVue workflow exposes but the
    mock's forward-only state machine normally rejects:

      * Pending Approval -> Dictating  (rad reworks a draft before signing)
      * Approved         -> Assigned   (signed exam reopened + reassigned)
      * Approved         -> Dictating  (signed exam reopened, same rad)
      * Approved         -> Cancelled  (signed exam cancelled retroactively)

    For the Approved-* paths, the study is un-archived from
    ``store.archived_studies`` back into ``store.active_studies`` so the
    notification engine starts tracking it again. Subsequent forward
    progression (Dictating -> Pending Approval -> Approved) re-archives
    on the second Approved hit. The cycle can repeat any number of times.
    """
    return os.environ.get("ALLOW_REVERSE_TRANSITIONS", "false").lower() == "true"


@router.put(
    "/{accession_number}/status",
    summary="Update a study's status",
    description=(
        "Manually transition a study to a new lifecycle status. "
        "Only valid transitions are allowed:\n\n"
        "- **Introduced** -> Assigned or Cancelled\n"
        "- **Assigned** -> Dictating or Cancelled\n"
        "- **Dictating** -> Pending Approval or Cancelled\n"
        "- **Pending Approval** -> Approved or Cancelled\n\n"
        "When a study reaches Approved or Cancelled, it is automatically moved to the archive.\n\n"
        "**Reverse-transition mode (e2e harness only):** when the mock is launched "
        "with `ALLOW_REVERSE_TRANSITIONS=true`, three extra paths open up to support "
        "the re-dictation cycle exercised by `tests/e2e`:\n\n"
        "- **Pending Approval** -> Dictating (draft rework before signing)\n"
        "- **Approved** -> Assigned (reopen + reassign — un-archives the study)\n"
        "- **Approved** -> Dictating (same rad reopens — un-archives the study)\n"
        "- **Approved** -> Cancelled (signed exam cancelled retroactively)\n\n"
        "When transitioning *out of* Approved the study is moved back from the archive "
        "into the active worklist; the cycle may repeat any number of times."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "study": {
                            "accession_number": "COCSNV0000000042",
                            "patient_name": "Garcia, Maria L",
                            "status": "Dictating",
                        },
                        "message": "Status updated to Dictating",
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
    # Per-study lock so concurrent threadpool handlers can't race on the
    # read-modify-write of this study's status / archive position. See
    # DataStore.study_lock. Different accessions get distinct locks, so
    # parallel PUTs on different studies still run concurrently.
    with store.study_lock(accession_number):
        return _update_study_status_locked(accession_number, body, store)


def _update_study_status_locked(
    accession_number: str,
    body: "StudyStatusUpdate",
    store: DataStore,
) -> dict[str, Any]:
    try:
        reverse_on = _allow_reverse_transitions()

        # Look up the study. When reverse-transitions are enabled, also
        # search the archive so that "Approved -> ..." requests resolve.
        # Note: the archive is searched-only here; the actual un-archive
        # happens after the transition's been validated.
        study = store.get_study(accession_number)
        archived_dict: dict[str, Any] | None = None
        if study is None and reverse_on:
            archived_dict = next(
                (
                    s for s in store.archived_studies
                    if s.get("accession_number") == accession_number
                ),
                None,
            )
        if study is None and archived_dict is None:
            raise HTTPException(
                status_code=404,
                detail=f"Study {accession_number} not found",
            )

        # Determine the current status -- from the active Study object if
        # present, otherwise from the archived dict.
        current_status = study.status if study else archived_dict.get("status", "")

        # Build the allowed-transitions table. Reverse paths are opt-in
        # via the env flag so production-shape mock behaviour is the
        # default.
        valid_transitions: dict[str, list[str]] = {
            "Introduced":       ["Assigned", "Cancelled"],
            "Assigned":         ["Dictating", "Cancelled"],
            "Dictating":        ["Pending Approval", "Cancelled"],
            "Pending Approval": ["Approved", "Cancelled"],
        }
        if reverse_on:
            valid_transitions["Pending Approval"] = (
                valid_transitions["Pending Approval"] + ["Dictating"]
            )
            valid_transitions["Approved"] = ["Assigned", "Dictating", "Cancelled"]

        allowed = valid_transitions.get(current_status, [])
        if body.status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot transition from '{current_status}' to "
                    f"'{body.status}'. Allowed: {allowed}"
                ),
            )

        # If we matched an archived study, un-archive now -- the transition
        # is validated and the Study object becomes the live record.
        if study is None:
            study = store.unarchive_study(accession_number)
            if study is None:
                # Shouldn't be reachable -- we found it above -- but be
                # explicit in case the store mutates between calls.
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to un-archive {accession_number}",
                )

        audit_logger = AuditLogger(store)
        old_status = study.status
        study.status = body.status

        # Update the lifecycle timestamps. Forward transitions stamp the
        # entered-into status. Reverse transitions also CLEAR the
        # timestamps of stages later than the new status, so a subsequent
        # forward progression won't carry stale data from the prior cycle.
        now = datetime.now(timezone.utc)
        if body.status == "Assigned":
            study.assigned_at = now
            study.dictating_started_at = None
            study.submitted_for_approval_at = None
            study.approved_at = None
        elif body.status == "Dictating":
            study.dictating_started_at = now
            study.submitted_for_approval_at = None
            study.approved_at = None
        elif body.status == "Pending Approval":
            study.submitted_for_approval_at = now
            study.approved_at = None
        elif body.status == "Approved":
            study.approved_at = now

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


@router.put(
    "/{accession_number}/assignee",
    summary="Reassign a study to a different radiologist",
    description=(
        "Change the `assigned_radiologist` on a study that is currently in Assigned status. "
        "Resets `assigned_at` to the current time so the new radiologist's assignment clock "
        "starts fresh -- this is what the notification-system engine reads to compute the "
        "2-minute and 6-minute thresholds. The pre-computed internal timeline "
        "(will_start_dictating_at, etc.) is NOT shifted, so the study still progresses to "
        "Dictating at its originally-planned time.\n\n"
        "Rejects if the study is not in Assigned status -- reassignment only makes sense "
        "for a study that already has a radiologist to reassign away from."
    ),
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "study": {
                            "accession_number": "COCSNV0000000042",
                            "status": "Assigned",
                            "assigned_radiologist": "Jones, Mary M.D.",
                            "assigned_by": "Support Team",
                            "assigned_at": "2026-04-22T08:15:00Z",
                        },
                        "message": "Reassigned to Jones, Mary M.D.",
                        "previous_radiologist": "Wright, Joshua M.D.",
                    }
                }
            }
        },
        400: {
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Cannot reassign study in 'Introduced' status; must be 'Assigned'"
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
def reassign_study(
    accession_number: str = Path(
        description="Unique accession number of the study to reassign.",
        examples=["COCSNV0000000042"],
    ),
    body: StudyReassignment = ...,
    store: DataStore = Depends(get_store),
) -> dict[str, Any]:
    # Per-study lock — see update_study_status above. Without this, three
    # concurrent reassigns (e.g. the e2e harness driving 3 cloned studies
    # at the same `at` offset) raced on `study.assigned_radiologist =`
    # and one PUT silently dropped on the way back to the client.
    with store.study_lock(accession_number):
        return _reassign_study_locked(accession_number, body, store)


def _reassign_study_locked(
    accession_number: str,
    body: "StudyReassignment",
    store: DataStore,
) -> dict[str, Any]:
    try:
        study = store.get_study(accession_number)
        if not study:
            raise HTTPException(status_code=404, detail=f"Study {accession_number} not found")

        if study.status != "Assigned":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot reassign study in '{study.status}' status; must be 'Assigned'"
                ),
            )

        old_radiologist = study.assigned_radiologist or "Unassigned"
        new_radiologist = body.assigned_radiologist
        assigned_by = body.assigned_by or "Support Team"

        study.assigned_radiologist = new_radiologist
        study.assigned_by = assigned_by
        study.assigned_at = datetime.now(timezone.utc)

        audit_logger = AuditLogger(store)
        audit_logger.log(
            screen="Assignment",
            accession_number=accession_number,
            patient_name=study.patient_name,
            description=(
                f"Reassigned from ({old_radiologist}) to ({new_radiologist}) by ({assigned_by})"
            ),
        )

        return {
            "study": study.to_api_response(),
            "message": f"Reassigned to {new_radiologist}",
            "previous_radiologist": old_radiologist,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error reassigning study %s", accession_number)
        raise HTTPException(status_code=500, detail="Failed to reassign study")

"""Tests for ``DataStore.unarchive_study()``.

Used by the e2e harness's reverse-transition path: an Approved study
gets pulled back from ``archived_studies`` into ``active_studies`` so
the notification engine starts tracking it again.
"""

from datetime import datetime, timezone

from src.models.study import Study, StudyTimeline


def _make_approved_archived(store, accession: str = "ACC_UNARC_001") -> str:
    """Build an Approved study, archive it, return the accession number."""
    study = Study(
        accession_number=accession,
        patient_name="Doe, John",
        mrn="MRN_X",
        dob="01/01/1990",
        modality="CT",
        study_description="Test",
        priority=5,
        rvu=1.0,
        status="Approved",
        study_introduced_at=datetime.now(timezone.utc),
        approved_at=datetime.now(timezone.utc),
        timeline=StudyTimeline(),
    )
    store.add_study(study)
    store.archive_study(accession)
    return accession


def test_unarchive_unknown_returns_none(store):
    assert store.unarchive_study("NOT_THERE") is None


def test_unarchive_moves_back_to_active(store):
    acc = _make_approved_archived(store)
    assert acc not in store.active_studies
    assert any(s["accession_number"] == acc for s in store.archived_studies)

    out = store.unarchive_study(acc)
    assert out is not None
    assert out.accession_number == acc
    assert acc in store.active_studies
    assert not any(s["accession_number"] == acc for s in store.archived_studies)


def test_unarchive_preserves_core_fields(store):
    acc = _make_approved_archived(store, "ACC_UNARC_002")
    out = store.unarchive_study(acc)
    assert out is not None
    assert out.patient_name      == "Doe, John"
    assert out.mrn               == "MRN_X"
    assert out.modality          == "CT"
    assert out.priority          == 5
    assert out.rvu               == 1.0
    assert out.status            == "Approved"
    assert out.approved_at       is not None


def test_unarchive_then_archive_round_trip(store):
    """Round-tripping should leave the archive consistent and the
    active store empty afterwards."""
    acc = _make_approved_archived(store, "ACC_UNARC_003")

    out = store.unarchive_study(acc)
    assert out is not None

    # Now re-archive (drive it back to Approved + archive).
    store.archive_study(acc)
    assert acc not in store.active_studies
    matches = [s for s in store.archived_studies if s.get("accession_number") == acc]
    assert len(matches) == 1, "archive must hold exactly one entry per accession"

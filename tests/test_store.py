"""Tests for the DataStore — add, get, archive, accession counter."""

from src.models.study import Study, StudyTimeline
from datetime import datetime, timezone


def test_add_and_get_study(store):
    study = Study(
        accession_number="ACC001",
        patient_name="Doe, John",
        mrn="MRN001",
        dob="01/01/1990",
        modality="CT",
        study_description="Test",
        priority=5,
        rvu=1.0,
        study_introduced_at=datetime.now(timezone.utc),
        timeline=StudyTimeline(),
    )
    store.add_study(study)
    assert store.get_study("ACC001") is study


def test_get_nonexistent_returns_none(store):
    assert store.get_study("NONEXISTENT") is None


def test_archive_study(store):
    study = Study(
        accession_number="ACC002",
        patient_name="Doe, Jane",
        mrn="MRN002",
        dob="02/02/1985",
        modality="MR",
        study_description="Test archive",
        priority=7,
        rvu=2.5,
        status="Approved",
        study_introduced_at=datetime.now(timezone.utc),
        timeline=StudyTimeline(),
    )
    store.add_study(study)
    assert store.get_study("ACC002") is not None

    store.archive_study("ACC002")
    assert store.get_study("ACC002") is None
    assert len(store.archived_studies) == 1
    assert store.archived_studies[0]["accession_number"] == "ACC002"


def test_archive_nonexistent_does_nothing(store):
    store.archive_study("NOPE")
    assert len(store.archived_studies) == 0


def test_accession_counter(store):
    a1 = store.next_accession_number("COCSNV", 10)
    a2 = store.next_accession_number("COCSNV", 10)
    a3 = store.next_accession_number("COCSNV", 10)

    assert a1 == "COCSNV0000000001"
    assert a2 == "COCSNV0000000002"
    assert a3 == "COCSNV0000000003"
    assert store.accession_counter == 3


def test_add_audit_entry(store):
    from src.models.audit import AuditEntry

    entry = AuditEntry(
        logged_date=datetime.now(timezone.utc),
        screen="New Study",
        user="System (Simulator)",
        patient_name="Test",
        accession_number="ACC001",
        log_description="Test entry",
    )
    store.add_audit_entry(entry)
    assert len(store.audit_entries) == 1
    assert store.audit_entries[0]["screen"] == "New Study"

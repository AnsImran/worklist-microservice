"""Tests for the StudyGenerator — study creation, overrides, timelines."""

from datetime import datetime, timedelta, timezone


def test_generate_one_default(generator):
    """Default generation produces a valid study with all required fields."""
    study = generator.generate_one()
    assert study.accession_number
    assert study.patient_name
    assert study.mrn
    assert study.dob
    assert study.modality in ("CT", "CR", "DX", "MR", "US", "NM")
    assert study.study_description
    assert 1 <= study.priority <= 10
    assert study.rvu > 0
    assert study.status == "Introduced"
    assert study.study_introduced_at is not None
    assert study.timeline.will_be_assigned_at is not None


def test_generate_one_with_overrides(generator):
    """Overridden fields use the provided values."""
    study = generator.generate_one(overrides={"modality": "NM", "priority": 10})
    assert study.modality == "NM"
    assert study.priority == 10


def test_generate_one_custom_patient(generator):
    """Custom patient name not in pool still gets MRN and DOB."""
    study = generator.generate_one(overrides={"patient_name": "Custom, Person X"})
    assert study.patient_name == "Custom, Person X"
    assert study.mrn != "UNKNOWN"
    assert study.mrn.startswith("SHHD")
    assert study.dob != "01/01/2000"


def test_generate_one_pool_patient(generator):
    """Patient from pool gets their pre-assigned MRN."""
    # Get a known patient name from the pool
    patients = generator.field_registry._pools["patients.json"]["patients"]
    known = patients[0]
    study = generator.generate_one(overrides={"patient_name": known["name"]})
    assert study.patient_name == known["name"]
    assert study.mrn == known["mrn"]
    assert study.dob == known["dob"]


def test_generate_one_lifecycle_overrides(generator):
    """Lifecycle overrides produce exact transition delays."""
    overrides = {
        "Introduced_to_Assigned": 60,
        "Assigned_to_Reading": 120,
        "Reading_to_Pending_Approval": 180,
        "Pending_Approval_to_Approved": 240,
    }
    study = generator.generate_one(lifecycle_overrides=overrides)
    t = study.timeline
    intro = study.study_introduced_at

    assert t.will_be_assigned_at == intro + timedelta(seconds=60)
    assert t.will_start_reading_at == intro + timedelta(seconds=60 + 120)
    assert t.will_be_pending_approval_at == intro + timedelta(seconds=60 + 120 + 180)
    assert t.will_be_approved_at == intro + timedelta(seconds=60 + 120 + 180 + 240)


def test_generate_one_cancel_at_stage(generator):
    """Cancel at a specific stage sets the cancellation timeline."""
    study = generator.generate_one(cancel_at_stage="Reading")
    assert study.timeline.cancel_at_stage == "Reading"
    assert study.timeline.will_be_cancelled_at is not None


def test_generate_one_introduced_at(generator):
    """Custom introduced_at anchors all timeline timestamps."""
    anchor = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    study = generator.generate_one(introduced_at=anchor)
    assert study.study_introduced_at == anchor
    assert study.timeline.will_be_assigned_at > anchor


def test_accession_number_sequential(generator):
    """Each generated study gets a unique sequential accession number."""
    s1 = generator.generate_one()
    s2 = generator.generate_one()
    s3 = generator.generate_one()
    assert s1.accession_number != s2.accession_number
    assert s2.accession_number != s3.accession_number
    # Numbers should be sequential
    n1 = int(s1.accession_number.replace("COCSNV", ""))
    n2 = int(s2.accession_number.replace("COCSNV", ""))
    n3 = int(s3.accession_number.replace("COCSNV", ""))
    assert n2 == n1 + 1
    assert n3 == n2 + 1

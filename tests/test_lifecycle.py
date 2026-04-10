"""Tests for the LifecycleEngine — transitions, timestamps, cancellation."""

from datetime import datetime, timedelta, timezone

from src.core.lifecycle import LifecycleEngine
from src.models.study import StudyTimeline


def test_advance_introduced_to_assigned(store, field_registry, audit_logger, make_study):
    """Study transitions from Introduced to Assigned when time is reached."""
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    study = make_study(
        status="Introduced",
        will_be_assigned_at=past,
        will_start_reading_at=datetime.now(timezone.utc) + timedelta(hours=1),
        will_be_pending_approval_at=datetime.now(timezone.utc) + timedelta(hours=2),
        will_be_approved_at=datetime.now(timezone.utc) + timedelta(hours=3),
    )
    engine = LifecycleEngine(store, field_registry, audit_logger)
    engine.advance_all()

    assert study.status == "Assigned"
    assert study.assigned_at is not None
    assert study.assigned_radiologist is not None


def test_advance_assigned_to_reading(store, field_registry, audit_logger, make_study):
    """Study transitions from Assigned to Reading."""
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    study = make_study(
        status="Assigned",
        will_be_assigned_at=past - timedelta(minutes=5),
        will_start_reading_at=past,
        will_be_pending_approval_at=datetime.now(timezone.utc) + timedelta(hours=1),
        will_be_approved_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    engine = LifecycleEngine(store, field_registry, audit_logger)
    engine.advance_all()

    assert study.status == "Reading"


def test_advance_reading_to_pending(store, field_registry, audit_logger, make_study):
    """Study transitions from Reading to Pending Approval."""
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    study = make_study(
        status="Reading",
        will_be_assigned_at=past - timedelta(minutes=10),
        will_start_reading_at=past - timedelta(minutes=5),
        will_be_pending_approval_at=past,
        will_be_approved_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    engine = LifecycleEngine(store, field_registry, audit_logger)
    engine.advance_all()

    assert study.status == "Pending Approval"


def test_advance_pending_to_approved(store, field_registry, audit_logger, make_study):
    """Study transitions from Pending Approval to Approved and is archived."""
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    study = make_study(
        status="Pending Approval",
        will_be_assigned_at=past - timedelta(minutes=15),
        will_start_reading_at=past - timedelta(minutes=10),
        will_be_pending_approval_at=past - timedelta(minutes=5),
        will_be_approved_at=past,
    )
    acc = study.accession_number
    engine = LifecycleEngine(store, field_registry, audit_logger)
    engine.advance_all()

    # Study should be archived (removed from active)
    assert store.get_study(acc) is None
    assert any(a["accession_number"] == acc for a in store.archived_studies)


def test_cancellation_at_stage(store, field_registry, audit_logger, make_study):
    """Study is cancelled at the specified stage."""
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    study = make_study(
        status="Reading",
        will_be_assigned_at=past - timedelta(minutes=10),
        will_start_reading_at=past - timedelta(minutes=5),
        will_be_pending_approval_at=datetime.now(timezone.utc) + timedelta(hours=1),
        will_be_approved_at=datetime.now(timezone.utc) + timedelta(hours=2),
        will_be_cancelled_at=past,
        cancel_at_stage="Reading",
    )
    acc = study.accession_number
    engine = LifecycleEngine(store, field_registry, audit_logger)
    engine.advance_all()

    assert store.get_study(acc) is None
    archived = [a for a in store.archived_studies if a["accession_number"] == acc]
    assert len(archived) == 1
    assert archived[0]["status"] == "Cancelled"


def test_no_advance_before_time(store, field_registry, audit_logger, make_study):
    """Study stays in current status when transition time hasn't been reached."""
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    study = make_study(
        status="Introduced",
        will_be_assigned_at=future,
        will_start_reading_at=future + timedelta(hours=1),
        will_be_pending_approval_at=future + timedelta(hours=2),
        will_be_approved_at=future + timedelta(hours=3),
    )
    engine = LifecycleEngine(store, field_registry, audit_logger)
    engine.advance_all()

    assert study.status == "Introduced"


def test_audit_log_uses_timeline_timestamps(store, field_registry, audit_logger, make_study):
    """Audit entries use the pre-computed timeline time, not wall-clock time."""
    assigned_time = datetime(2026, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    study = make_study(
        status="Introduced",
        will_be_assigned_at=assigned_time,
        will_start_reading_at=datetime.now(timezone.utc) + timedelta(hours=1),
        will_be_pending_approval_at=datetime.now(timezone.utc) + timedelta(hours=2),
        will_be_approved_at=datetime.now(timezone.utc) + timedelta(hours=3),
    )
    # Manually set will_be_assigned_at to the past so it triggers
    study.timeline.will_be_assigned_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    target_time = study.timeline.will_be_assigned_at

    engine = LifecycleEngine(store, field_registry, audit_logger)
    engine.advance_all()

    # Find the status change audit entry
    status_entries = [e for e in store.audit_entries if e["screen"] == "Studies"]
    assert len(status_entries) >= 1
    logged = datetime.fromisoformat(status_entries[0]["logged_date"])
    # Should match the timeline timestamp, not current wall-clock
    assert abs((logged - target_time).total_seconds()) < 1

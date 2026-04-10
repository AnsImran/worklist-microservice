"""Tests for the AuditLogger — all log methods and logged_date parameter."""

from datetime import datetime, timezone, timedelta


def test_log_study_created(store, audit_logger):
    audit_logger.log_study_created("ACC001", "Doe, John", "CT Brain")
    assert len(store.audit_entries) == 1
    e = store.audit_entries[0]
    assert e["screen"] == "New Study"
    assert e["accession_number"] == "ACC001"
    assert "CT Brain" in e["log_description"]


def test_log_status_change(store, audit_logger):
    audit_logger.log_status_change("ACC001", "Doe, John", "Introduced", "Assigned")
    assert len(store.audit_entries) == 1
    e = store.audit_entries[0]
    assert e["screen"] == "Studies"
    assert "(Introduced)" in e["log_description"]
    assert "(Assigned)" in e["log_description"]


def test_log_status_change_with_logged_date(store, audit_logger):
    custom_time = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    audit_logger.log_status_change(
        "ACC001", "Doe, John", "Assigned", "Reading", logged_date=custom_time
    )
    e = store.audit_entries[0]
    assert e["logged_date"] == "2026-01-15T10:30:00Z"


def test_log_status_change_default_date_is_now(store, audit_logger):
    before = datetime.now(timezone.utc)
    audit_logger.log_status_change("ACC001", "Doe, John", "Reading", "Pending Approval")
    after = datetime.now(timezone.utc)
    logged = datetime.fromisoformat(store.audit_entries[0]["logged_date"])
    assert before <= logged <= after + timedelta(seconds=1)


def test_log_assignment(store, audit_logger):
    audit_logger.log_assignment("ACC001", "Doe, John", "Wright, Joshua M.D.", "Self")
    e = store.audit_entries[0]
    assert e["screen"] == "Assignment"
    assert "Wright, Joshua M.D." in e["log_description"]
    assert "Self" in e["log_description"]


def test_log_assignment_with_logged_date(store, audit_logger):
    custom_time = datetime(2026, 3, 1, 8, 0, 0, tzinfo=timezone.utc)
    audit_logger.log_assignment(
        "ACC001", "Doe, John", "Khan, Abrar M.D.", "Song, Jaemin",
        logged_date=custom_time,
    )
    assert store.audit_entries[0]["logged_date"] == "2026-03-01T08:00:00Z"


def test_log_demand_injected(store, audit_logger):
    audit_logger.log_demand_injected("ACC001", "Doe, John", "demand-abc123")
    e = store.audit_entries[0]
    assert e["screen"] == "Demand"
    assert "demand-abc123" in e["log_description"]

"""Tests for GET /audit — audit log with filters."""


def _create_study(client, **study_fields):
    payload = {"study": study_fields} if study_fields else {}
    resp = client.post("/demand", json=payload)
    return resp.json()["study"]


def test_audit_logs_study_creation(client):
    study = _create_study(client)
    resp = client.get("/audit", params={"accession_number": study["accession_number"]})
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    screens = [e["screen"] for e in entries]
    assert "New Study" in screens


def test_audit_filter_by_screen(client):
    _create_study(client)
    resp = client.get("/audit", params={"screen": "New Study"})
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert all(e["screen"] == "New Study" for e in entries)


def test_audit_filter_by_accession(client):
    study = _create_study(client)
    acc = study["accession_number"]
    resp = client.get("/audit", params={"accession_number": acc})
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert all(e["accession_number"] == acc for e in entries)
    assert len(entries) >= 1


def test_audit_filter_by_user(client):
    _create_study(client)
    resp = client.get("/audit", params={"user": "System"})
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert all("system" in e["user"].lower() for e in entries)

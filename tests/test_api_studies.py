"""Tests for PUT /studies/{accession}/status — status transitions."""


def _create_study(client, **study_fields):
    payload = {"study": study_fields} if study_fields else {}
    resp = client.post("/demand", json=payload)
    assert resp.status_code == 200
    return resp.json()["study"]


def test_valid_transition_introduced_to_assigned(client):
    study = _create_study(client)
    acc = study["accession_number"]

    resp = client.put(f"/studies/{acc}/status", json={"status": "Assigned"})
    assert resp.status_code == 200
    assert resp.json()["study"]["status"] == "Assigned"


def test_valid_transition_to_cancelled(client):
    study = _create_study(client)
    acc = study["accession_number"]

    resp = client.put(f"/studies/{acc}/status", json={"status": "Cancelled"})
    assert resp.status_code == 200
    assert "cancelled" in resp.json()["message"].lower()


def test_invalid_transition_returns_400(client):
    study = _create_study(client)
    acc = study["accession_number"]

    # Introduced -> Approved is not valid (must go through Assigned, Dictating, etc.)
    resp = client.put(f"/studies/{acc}/status", json={"status": "Approved"})
    assert resp.status_code == 400
    assert "Cannot transition" in resp.json()["detail"]


def test_approved_archives_study(client):
    study = _create_study(client)
    acc = study["accession_number"]

    # Walk through the full lifecycle
    client.put(f"/studies/{acc}/status", json={"status": "Assigned"})
    client.put(f"/studies/{acc}/status", json={"status": "Dictating"})
    client.put(f"/studies/{acc}/status", json={"status": "Pending Approval"})
    resp = client.put(f"/studies/{acc}/status", json={"status": "Approved"})
    assert resp.status_code == 200

    # Should no longer be in active worklist
    resp = client.get(f"/worklist/{acc}")
    assert resp.status_code == 200
    assert resp.json()["source"] == "archive"


def test_study_not_found_returns_404(client):
    resp = client.put("/studies/NONEXISTENT/status", json={"status": "Assigned"})
    assert resp.status_code == 404

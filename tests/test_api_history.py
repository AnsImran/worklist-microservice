"""Tests for GET /history — archived studies with filters."""


def _create_and_approve(client, **study_fields):
    """Create a study and walk it through to Approved."""
    payload = {"study": study_fields} if study_fields else {}
    resp = client.post("/demand", json=payload)
    study = resp.json()["study"]
    acc = study["accession_number"]
    client.put(f"/studies/{acc}/status", json={"status": "Assigned"})
    client.put(f"/studies/{acc}/status", json={"status": "Dictating"})
    client.put(f"/studies/{acc}/status", json={"status": "Pending Approval"})
    client.put(f"/studies/{acc}/status", json={"status": "Approved"})
    return study


def _create_and_cancel(client, **study_fields):
    """Create a study and cancel it."""
    payload = {"study": study_fields} if study_fields else {}
    resp = client.post("/demand", json=payload)
    study = resp.json()["study"]
    acc = study["accession_number"]
    client.put(f"/studies/{acc}/status", json={"status": "Cancelled"})
    return study


def test_history_empty(client):
    resp = client.get("/history")
    assert resp.status_code == 200
    # May not be truly empty because the app lifespan generates studies,
    # but the structure should be correct
    data = resp.json()
    assert "total" in data
    assert "studies" in data


def test_history_after_approval(client):
    study = _create_and_approve(client, modality="CT")
    acc = study["accession_number"]
    # Use patient_name filter to find our specific study (accession filter not on history)
    resp = client.get("/history", params={"patient_name": study["patient_name"], "limit": 1000})
    assert resp.status_code == 200
    accessions = [s["accession_number"] for s in resp.json()["studies"]]
    assert acc in accessions


def test_history_filter_by_modality(client):
    _create_and_approve(client, modality="US")
    resp = client.get("/history", params={"modality": "US"})
    assert resp.status_code == 200
    studies = resp.json()["studies"]
    assert all(s["modality"] == "US" for s in studies)


def test_history_filter_by_status(client):
    _create_and_approve(client, modality="CT")
    _create_and_cancel(client, modality="MR")

    approved = client.get("/history", params={"status": "Approved"}).json()["studies"]
    cancelled = client.get("/history", params={"status": "Cancelled"}).json()["studies"]
    assert all(s["status"] == "Approved" for s in approved)
    assert all(s["status"] == "Cancelled" for s in cancelled)


def test_history_filter_by_patient_name(client):
    _create_and_approve(client, patient_name="Uniquename, Testperson")
    resp = client.get("/history", params={"patient_name": "Uniquename"})
    assert resp.status_code == 200
    studies = resp.json()["studies"]
    assert any("Uniquename" in s["patient_name"] for s in studies)

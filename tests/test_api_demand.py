"""Tests for POST /demand and POST /demand/batch."""


def test_create_single_study(client):
    """POST /demand with minimal input creates a study immediately."""
    resp = client.post("/demand", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert "study" in data
    assert "message" in data
    assert data["study"]["status"] == "Introduced"
    assert data["study"]["accession_number"]


def test_create_study_with_overrides(client):
    """Overrides are reflected in the created study."""
    resp = client.post("/demand", json={
        "study": {
            "modality": "NM",
            "priority": 10,
            "patient_name": "Override, Test",
        }
    })
    assert resp.status_code == 200
    study = resp.json()["study"]
    assert study["modality"] == "NM"
    assert study["priority"] == 10
    assert study["patient_name"] == "Override, Test"


def test_create_study_with_lifecycle_overrides(client):
    """Lifecycle overrides are accepted without error."""
    resp = client.post("/demand", json={
        "study": {"modality": "CT"},
        "lifecycle_overrides": {
            "Introduced_to_Assigned": 60,
            "Assigned_to_Reading": 60,
            "Reading_to_Pending_Approval": 60,
            "Pending_Approval_to_Approved": 60,
        },
    })
    assert resp.status_code == 200
    assert resp.json()["study"]["modality"] == "CT"


def test_create_study_with_custom_patient(client):
    """Custom patient name not in pool gets a generated MRN and DOB."""
    resp = client.post("/demand", json={
        "study": {"patient_name": "Unique, Custom Person"}
    })
    assert resp.status_code == 200
    study = resp.json()["study"]
    assert study["patient_name"] == "Unique, Custom Person"
    assert study["mrn"].startswith("SHHD")
    assert study["dob"]  # Not empty


def test_create_study_with_introduced_at(client):
    """Custom introduced_at anchor is used."""
    resp = client.post("/demand", json={
        "study_introduced_at": "2026-01-01T12:00:00Z",
    })
    assert resp.status_code == 200
    study = resp.json()["study"]
    assert study["study_introduced_at"].startswith("2026-01-01T12:00:00")


def test_create_study_with_cancel_at_stage(client):
    """cancel_at_stage is accepted without error."""
    resp = client.post("/demand", json={
        "cancel_at_stage": "Reading",
    })
    assert resp.status_code == 200
    assert resp.json()["study"]["status"] == "Introduced"


def test_batch_create(client):
    """POST /demand/batch creates multiple studies."""
    resp = client.post("/demand/batch", json=[
        {"study": {"modality": "CT", "priority": 9}},
        {"study": {"modality": "MR", "priority": 3}},
        {"study": {"modality": "NM", "priority": 7}},
    ])
    assert resp.status_code == 200
    data = resp.json()
    assert "studies" in data
    assert len(data["studies"]) == 3
    assert "3 studies created" in data["message"]
    modalities = {s["modality"] for s in data["studies"]}
    assert modalities == {"CT", "MR", "NM"}


def test_batch_empty_list(client):
    """Batch with empty list returns 0 studies."""
    resp = client.post("/demand/batch", json=[])
    assert resp.status_code == 200
    data = resp.json()
    assert data["studies"] == []
    assert "0 studies created" in data["message"]

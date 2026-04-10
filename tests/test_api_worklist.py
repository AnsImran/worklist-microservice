"""Tests for GET /worklist and GET /worklist/{accession_number}."""


def _create_study(client, **study_fields):
    """Helper to create a study and return the response."""
    payload = {"study": study_fields} if study_fields else {}
    resp = client.post("/demand", json=payload)
    assert resp.status_code == 200
    return resp.json()["study"]


def test_worklist_returns_created_study(client):
    study = _create_study(client, modality="CT", priority=8)
    acc = study["accession_number"]

    resp = client.get("/worklist", params={"accession_number": acc})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["studies"][0]["accession_number"] == acc


def test_worklist_filter_by_modality(client):
    _create_study(client, modality="NM")
    _create_study(client, modality="CT")

    resp = client.get("/worklist", params={"modality": "NM"})
    assert resp.status_code == 200
    studies = resp.json()["studies"]
    assert all(s["modality"] == "NM" for s in studies)


def test_worklist_filter_by_status(client):
    _create_study(client)

    resp = client.get("/worklist", params={"status": "Introduced"})
    assert resp.status_code == 200
    studies = resp.json()["studies"]
    assert all(s["status"] == "Introduced" for s in studies)


def test_worklist_filter_by_priority_range(client):
    _create_study(client, priority=2)
    _create_study(client, priority=9)

    resp = client.get("/worklist", params={"priority_min": 8, "priority_max": 10})
    assert resp.status_code == 200
    studies = resp.json()["studies"]
    assert all(8 <= s["priority"] <= 10 for s in studies)


def test_worklist_filter_by_accession_number(client):
    study = _create_study(client)
    acc = study["accession_number"]

    resp = client.get("/worklist", params={"accession_number": acc})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["studies"][0]["accession_number"] == acc


def test_worklist_pagination(client):
    for _ in range(5):
        _create_study(client)

    resp = client.get("/worklist", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["studies"]) == 2
    assert data["total"] >= 5


def test_get_study_active(client):
    study = _create_study(client)
    acc = study["accession_number"]

    resp = client.get(f"/worklist/{acc}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "active"
    assert data["study"]["accession_number"] == acc


def test_get_study_not_found(client):
    resp = client.get("/worklist/NONEXISTENT999")
    assert resp.status_code == 404

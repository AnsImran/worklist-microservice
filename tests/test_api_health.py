"""Tests for GET /health and GET /stats."""


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_stats_returns_structure(client):
    resp = client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_studies" in data
    assert "archived_studies" in data
    assert "audit_entries" in data
    assert "active_by_status" in data
    assert "active_by_modality" in data
    assert "archived_by_status" in data
    assert "uptime_seconds" in data
    assert isinstance(data["active_studies"], int)
    assert isinstance(data["uptime_seconds"], int)

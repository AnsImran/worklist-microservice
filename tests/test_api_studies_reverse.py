"""Tests for the reverse-transition path on PUT /studies/{acc}/status.

Reverse transitions are opt-in via the ``ALLOW_REVERSE_TRANSITIONS=true``
environment variable, which the production stack never sets but the e2e
test harness does (via ``run_all.py --for-e2e``). They unlock the
re-dictation cycle the prod NewVue workflow exposes:

  * Pending Approval -> Dictating  (draft rework)
  * Approved         -> Assigned   (reopen + reassign)
  * Approved         -> Dictating  (same rad reopens)
  * Approved         -> Cancelled  (signed exam retroactively cancelled)

Approved-* paths additionally un-archive the study so the notification
engine starts tracking it again.
"""


def _create_and_walk_to_approved(client):
    """Helper: demand a study and walk it forward to Approved."""
    resp = client.post("/demand", json={})
    assert resp.status_code == 200
    acc = resp.json()["study"]["accession_number"]
    for next_status in ("Assigned", "Dictating", "Pending Approval", "Approved"):
        resp = client.put(f"/studies/{acc}/status", json={"status": next_status})
        assert resp.status_code == 200, resp.text
    return acc


# ── Reverse mode OFF (default) ────────────────────────────────────────
def test_reverse_off_rejects_pending_approval_to_dictating(client, monkeypatch):
    """Without the env flag the only allowed move out of Pending Approval is forward."""
    monkeypatch.delenv("ALLOW_REVERSE_TRANSITIONS", raising=False)
    resp = client.post("/demand", json={})
    acc = resp.json()["study"]["accession_number"]
    for status in ("Assigned", "Dictating", "Pending Approval"):
        client.put(f"/studies/{acc}/status", json={"status": status})
    resp = client.put(f"/studies/{acc}/status", json={"status": "Dictating"})
    assert resp.status_code == 400
    assert "Cannot transition" in resp.json()["detail"]


def test_reverse_off_rejects_approved_to_anything(client, monkeypatch):
    monkeypatch.delenv("ALLOW_REVERSE_TRANSITIONS", raising=False)
    acc = _create_and_walk_to_approved(client)
    # Once archived + reverse-off, the route can't even find the study.
    resp = client.put(f"/studies/{acc}/status", json={"status": "Dictating"})
    assert resp.status_code == 404


# ── Reverse mode ON ───────────────────────────────────────────────────
def test_reverse_on_allows_pending_approval_to_dictating(client, monkeypatch):
    monkeypatch.setenv("ALLOW_REVERSE_TRANSITIONS", "true")
    resp = client.post("/demand", json={})
    acc = resp.json()["study"]["accession_number"]
    for status in ("Assigned", "Dictating", "Pending Approval"):
        client.put(f"/studies/{acc}/status", json={"status": status})

    resp = client.put(f"/studies/{acc}/status", json={"status": "Dictating"})
    assert resp.status_code == 200, resp.text
    study = resp.json()["study"]
    assert study["status"] == "Dictating"
    # Reverse path clears the later-stage timestamps so the next forward
    # progression doesn't carry stale "submitted_for_approval_at" data.
    assert study["submitted_for_approval_at"] is None
    assert study["approved_at"] is None


def test_reverse_on_approved_to_assigned_unarchives_and_resets_clock(client, monkeypatch):
    monkeypatch.setenv("ALLOW_REVERSE_TRANSITIONS", "true")
    acc = _create_and_walk_to_approved(client)

    # Confirm it's currently in archive.
    resp = client.get(f"/worklist/{acc}")
    assert resp.json()["source"] == "archive"

    # Reopen via reverse transition Approved -> Assigned.
    resp = client.put(f"/studies/{acc}/status", json={"status": "Assigned"})
    assert resp.status_code == 200, resp.text
    study = resp.json()["study"]
    assert study["status"] == "Assigned"
    # All later-stage timestamps cleared.
    assert study["dictating_started_at"]      is None
    assert study["submitted_for_approval_at"] is None
    assert study["approved_at"]               is None
    # assigned_at re-stamped (just a basic non-null check; precise wall
    # time isn't deterministic in a unit test).
    assert study["assigned_at"] is not None

    # Active worklist now sees it again.
    resp = client.get(f"/worklist/{acc}")
    assert resp.json()["source"] == "active"


def test_reverse_on_approved_to_dictating_unarchives(client, monkeypatch):
    """Same rad reopens the signed exam directly to Dictating."""
    monkeypatch.setenv("ALLOW_REVERSE_TRANSITIONS", "true")
    acc = _create_and_walk_to_approved(client)

    resp = client.put(f"/studies/{acc}/status", json={"status": "Dictating"})
    assert resp.status_code == 200, resp.text
    study = resp.json()["study"]
    assert study["status"]                    == "Dictating"
    assert study["dictating_started_at"]      is not None
    assert study["submitted_for_approval_at"] is None
    assert study["approved_at"]               is None

    resp = client.get(f"/worklist/{acc}")
    assert resp.json()["source"] == "active"


def test_reverse_on_full_re_dictation_cycle_can_repeat(client, monkeypatch):
    """Approved -> Assigned -> Dictating -> Pending Approval -> Approved -> repeat."""
    monkeypatch.setenv("ALLOW_REVERSE_TRANSITIONS", "true")
    acc = _create_and_walk_to_approved(client)

    for cycle in range(3):
        # Reopen.
        resp = client.put(f"/studies/{acc}/status", json={"status": "Assigned"})
        assert resp.status_code == 200, f"cycle {cycle} reopen: {resp.text}"
        # Walk forward again.
        for status in ("Dictating", "Pending Approval", "Approved"):
            resp = client.put(f"/studies/{acc}/status", json={"status": status})
            assert resp.status_code == 200, f"cycle {cycle} -> {status}: {resp.text}"

    # After the final Approved, study is back in archive.
    resp = client.get(f"/worklist/{acc}")
    assert resp.json()["source"] == "archive"


def test_reverse_on_approved_to_cancelled_archives_with_cancelled_status(client, monkeypatch):
    monkeypatch.setenv("ALLOW_REVERSE_TRANSITIONS", "true")
    acc = _create_and_walk_to_approved(client)

    resp = client.put(f"/studies/{acc}/status", json={"status": "Cancelled"})
    assert resp.status_code == 200, resp.text
    assert "cancelled" in resp.json()["message"].lower()

    # Cancelled studies live in archive too.
    resp = client.get(f"/worklist/{acc}")
    assert resp.json()["source"] == "archive"


def test_reverse_on_reassignment_after_reopen(client, monkeypatch):
    """The two-step reopen + reassign flow: status -> Assigned, then assignee swap."""
    monkeypatch.setenv("ALLOW_REVERSE_TRANSITIONS", "true")
    acc = _create_and_walk_to_approved(client)

    client.put(f"/studies/{acc}/status", json={"status": "Assigned"})
    resp = client.put(
        f"/studies/{acc}/assignee",
        json={"assigned_radiologist": "Reassigned, NewRad M.D.", "assigned_by": "Test"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["study"]["assigned_radiologist"] == "Reassigned, NewRad M.D."


def test_reverse_on_unknown_accession_returns_404(client, monkeypatch):
    monkeypatch.setenv("ALLOW_REVERSE_TRANSITIONS", "true")
    resp = client.put(
        "/studies/NEVER_EXISTED/status", json={"status": "Dictating"}
    )
    assert resp.status_code == 404

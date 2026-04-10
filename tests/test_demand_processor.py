"""Tests for the DemandProcessor — file-based demand injection."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.services.demand_processor import DemandProcessor


def test_process_injects_study(store, generator, audit_logger, tmp_path):
    """A valid unprocessed demand creates a study in the store."""
    demand_file = tmp_path / "demanded_data.json"
    demand_file.write_text(json.dumps({
        "requests": [
            {
                "id": "test-001",
                "processed": False,
                "action": "inject_study",
                "study": {"modality": "CT", "priority": 10},
            }
        ]
    }))

    with patch("src.services.demand_processor.DEMAND_FILE", demand_file):
        processor = DemandProcessor(store, generator, audit_logger)
        processor.process()

    assert len(store.active_studies) == 1
    study = list(store.active_studies.values())[0]
    assert study.modality == "CT"
    assert study.priority == 10


def test_process_marks_processed(store, generator, audit_logger, tmp_path):
    """After successful injection, the request is marked processed."""
    demand_file = tmp_path / "demanded_data.json"
    demand_file.write_text(json.dumps({
        "requests": [
            {
                "id": "test-002",
                "processed": False,
                "action": "inject_study",
                "study": {"modality": "MR"},
            }
        ]
    }))

    with patch("src.services.demand_processor.DEMAND_FILE", demand_file):
        processor = DemandProcessor(store, generator, audit_logger)
        processor.process()

    data = json.loads(demand_file.read_text())
    assert data["requests"][0]["processed"] is True


def test_invalid_request_skipped(store, generator, audit_logger, tmp_path):
    """Invalid demand requests are skipped without crashing."""
    demand_file = tmp_path / "demanded_data.json"
    demand_file.write_text(json.dumps({
        "requests": [
            {"garbage": True},  # Invalid — no id, no action
            {
                "id": "test-003",
                "processed": False,
                "action": "inject_study",
                "study": {"modality": "US"},
            },
        ]
    }))

    with patch("src.services.demand_processor.DEMAND_FILE", demand_file):
        processor = DemandProcessor(store, generator, audit_logger)
        processor.process()

    # The valid request should still be processed
    assert len(store.active_studies) == 1


def test_already_processed_skipped(store, generator, audit_logger, tmp_path):
    """Requests already marked processed are not re-injected."""
    demand_file = tmp_path / "demanded_data.json"
    demand_file.write_text(json.dumps({
        "requests": [
            {
                "id": "test-004",
                "processed": True,
                "action": "inject_study",
                "study": {"modality": "CT"},
            }
        ]
    }))

    with patch("src.services.demand_processor.DEMAND_FILE", demand_file):
        processor = DemandProcessor(store, generator, audit_logger)
        processor.process()

    assert len(store.active_studies) == 0


def test_missing_file_no_error(store, generator, audit_logger, tmp_path):
    """Missing demand file is handled gracefully."""
    demand_file = tmp_path / "nonexistent.json"

    with patch("src.services.demand_processor.DEMAND_FILE", demand_file):
        processor = DemandProcessor(store, generator, audit_logger)
        processor.process()  # Should not raise

    assert len(store.active_studies) == 0

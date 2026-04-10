"""Shared pytest fixtures for the worklist microservice tests."""

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.config import LIFECYCLE_FILE
from src.core.field_registry import FieldRegistry
from src.core.generator import StudyGenerator
from src.data.store import DataStore
from src.main import app
from src.models.study import Study, StudyTimeline
from src.services.audit_logger import AuditLogger


@pytest.fixture()
def store():
    """Fresh in-memory data store (no disk state)."""
    return DataStore()


@pytest.fixture()
def field_registry():
    """Field registry loaded from real config files."""
    fr = FieldRegistry()
    fr.load()
    return fr


@pytest.fixture()
def lifecycle_config():
    """Lifecycle config loaded from lifecycle.json."""
    return json.loads(LIFECYCLE_FILE.read_text(encoding="utf-8"))


@pytest.fixture()
def generator(store, field_registry, lifecycle_config):
    """StudyGenerator wired up with fresh store."""
    return StudyGenerator(store, field_registry, lifecycle_config)


@pytest.fixture()
def audit_logger(store):
    """AuditLogger backed by the test store."""
    return AuditLogger(store)


@pytest.fixture()
def sample_study(store, generator):
    """Generate a single study and add it to the store."""
    study = generator.generate_one()
    store.add_study(study)
    return study


@pytest.fixture()
def make_study(store):
    """Factory fixture to create studies with explicit fields for deterministic tests."""
    counter = 0

    def _make(
        accession: str | None = None,
        status: str = "Introduced",
        modality: str = "CT",
        priority: int = 5,
        patient_name: str = "Test, Patient A",
        **timeline_kwargs,
    ) -> Study:
        nonlocal counter
        counter += 1
        now = datetime.now(timezone.utc)
        study = Study(
            accession_number=accession or f"TEST{counter:010d}",
            patient_name=patient_name,
            mrn=f"MRN{counter:06d}",
            dob="01/01/1990",
            modality=modality,
            study_description=f"Test study {counter}",
            priority=priority,
            rvu=2.0,
            status=status,
            study_introduced_at=now,
            timeline=StudyTimeline(**timeline_kwargs),
        )
        store.add_study(study)
        return study

    return _make


@pytest.fixture()
def client():
    """FastAPI TestClient with the full app.

    The app lifespan starts a fresh store and scheduler.
    We disable the background scheduler's sleep to avoid hanging tests.
    """
    with TestClient(app) as c:
        yield c

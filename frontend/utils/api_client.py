"""HTTP client wrapping all FastAPI worklist API calls.

Uses the API_BASE_URL environment variable to determine the API address.
  - Local dev:  API_BASE_URL=http://localhost:8000
  - Docker:     API_BASE_URL=http://worklist-api:8000 (set in docker-compose.yml)
"""

import os
from typing import Any

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
TIMEOUT = 10


def _get(path: str, params: dict | None = None) -> dict[str, Any]:
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        return {"error": f"Cannot connect to API at {API_BASE_URL}"}
    except Exception as e:
        return {"error": str(e)}


def _post(path: str, json_body: dict) -> dict[str, Any]:
    try:
        resp = requests.post(f"{API_BASE_URL}{path}", json=json_body, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        return {"error": f"Cannot connect to API at {API_BASE_URL}"}
    except Exception as e:
        return {"error": str(e)}


def health_check() -> dict:
    return _get("/health")


def get_stats() -> dict:
    return _get("/stats")


def get_worklist(
    modality: str | None = None,
    status: str | None = None,
    priority_min: int | None = None,
    priority_max: int | None = None,
    limit: int = 500,
) -> dict:
    params: dict[str, Any] = {"limit": limit}
    if modality:
        params["modality"] = modality
    if status:
        params["status"] = status
    if priority_min is not None:
        params["priority_min"] = priority_min
    if priority_max is not None:
        params["priority_max"] = priority_max
    return _get("/worklist", params)


def get_audit_log(
    screen: str | None = None,
    user: str | None = None,
    accession_number: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 500,
) -> dict:
    params: dict[str, Any] = {"limit": limit}
    if screen:
        params["screen"] = screen
    if user:
        params["user"] = user
    if accession_number:
        params["accession_number"] = accession_number
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    return _get("/audit", params)


def get_history(
    modality: str | None = None,
    status: str | None = None,
    patient_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 500,
) -> dict:
    params: dict[str, Any] = {"limit": limit}
    if modality:
        params["modality"] = modality
    if status:
        params["status"] = status
    if patient_name:
        params["patient_name"] = patient_name
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    return _get("/history", params)


def create_demand(payload: dict) -> dict:
    return _post("/demand", payload)

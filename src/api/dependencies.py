"""FastAPI dependency injection — provides access to store and field registry."""

from fastapi import Request

from src.core.field_registry import FieldRegistry
from src.data.store import DataStore


def get_store(request: Request) -> DataStore:
    return request.app.state.store


def get_field_registry(request: Request) -> FieldRegistry:
    return request.app.state.field_registry

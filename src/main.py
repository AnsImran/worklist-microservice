"""FastAPI application entry point.

Starts the worklist simulation service with:
- Background scheduler (30-second tick loop)
- REST API endpoints for worklist, history, audit, studies, health
- Hot-reloadable JSON configuration

Run with: uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import logging
import logging.handlers
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.routes_audit import router as audit_router
from src.api.routes_demand import router as demand_router
from src.api.routes_health import router as health_router
from src.api.routes_history import router as history_router
from src.api.routes_studies import router as studies_router
from src.api.routes_worklist import router as worklist_router
from src.config import LIFECYCLE_FILE
from src.core.field_registry import FieldRegistry
from src.core.generator import StudyGenerator
from src.core.lifecycle import LifecycleEngine
from src.core.scheduler import Scheduler
from src.data.store import DataStore
from src.services.audit_logger import AuditLogger
from src.services.demand_processor import DemandProcessor

# Configure logging -- stderr always; rotating file when WLS_LOG_FILE is set
# (Phase-2 observability: Promtail tails the file and ships to Loki).
_LOG_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(level=logging.INFO, format=_LOG_FMT, datefmt=_LOG_DATEFMT)
_log_file = os.environ.get("WLS_LOG_FILE")
if _log_file:
    Path(_log_file).parent.mkdir(parents=True, exist_ok=True)
    _fh = logging.handlers.RotatingFileHandler(
        _log_file, maxBytes=50 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    _fh.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_LOG_DATEFMT))
    logging.getLogger().addHandler(_fh)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — startup and shutdown."""
    logger.info("Starting worklist simulation service...")

    # Initialize components
    store = DataStore()
    store.load_from_disk()

    field_registry = FieldRegistry()
    field_registry.load()

    # Load lifecycle config
    lifecycle_config = {}
    if LIFECYCLE_FILE.exists():
        lifecycle_config = json.loads(LIFECYCLE_FILE.read_text(encoding="utf-8"))

    # Store lifecycle config on the store for manual study creation via API
    store._lifecycle_config = lifecycle_config  # type: ignore[attr-defined]

    audit_logger = AuditLogger(store)
    generator = StudyGenerator(store, field_registry, lifecycle_config)
    lifecycle_engine = LifecycleEngine(store, field_registry, audit_logger)
    demand_processor = DemandProcessor(store, generator, audit_logger)

    scheduler = Scheduler(
        store=store,
        field_registry=field_registry,
        generator=generator,
        lifecycle_engine=lifecycle_engine,
        audit_logger=audit_logger,
        demand_processor=demand_processor,
    )

    # Attach to app state for dependency injection
    app.state.store = store
    app.state.field_registry = field_registry

    # Start background scheduler
    task = asyncio.create_task(scheduler.run())
    logger.info("Worklist simulation service started")

    yield

    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    store.save_to_disk()
    logger.info("Worklist simulation service stopped")


app = FastAPI(
    title="Simulated Radiology Worklist",
    description="A microservice that simulates a hospital PACS radiology worklist. "
    "Generates studies, advances them through lifecycle stages, and provides "
    "REST API access to live worklist, history, and audit log data.",
    version="0.1.0",
    lifespan=lifespan,
)

# Global exception handler — safety net for any unhandled error
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    logger.debug(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )

# Register routers
app.include_router(health_router)
app.include_router(worklist_router)
app.include_router(history_router)
app.include_router(audit_router)
app.include_router(studies_router)
app.include_router(demand_router)


# ---------------------------------------------------------------------------
# Prometheus metrics (§38)
# ---------------------------------------------------------------------------
Instrumentator(
    excluded_handlers=[
        "/metrics",
        ".*/health.*",
        ".*/healthz",
        ".*/readyz",
    ],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

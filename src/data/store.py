"""In-memory data store with JSON file persistence.

The store holds all runtime state:
- Active worklist studies (keyed by accession number)
- Archived studies (completed/cancelled)
- Audit log entries
- Accession number counter

On each tick, state is persisted to JSON files under data/db/.
On startup, state is restored from these files if they exist.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import ARCHIVE_DB_FILE, AUDIT_LOG_DB_FILE, DB_DIR, WORKLIST_DB_FILE
from src.models.audit import AuditEntry
from src.models.study import Study

logger = logging.getLogger(__name__)


class DataStore:
    """Central in-memory data store with JSON persistence."""

    def __init__(self) -> None:
        self.active_studies: dict[str, Study] = {}
        self.archived_studies: list[dict[str, Any]] = []
        self.audit_entries: list[dict[str, Any]] = []
        self.accession_counter: int = 0
        self._startup_time: datetime = datetime.now(timezone.utc)

    @property
    def startup_time(self) -> datetime:
        return self._startup_time

    def next_accession_number(self, prefix: str, zero_pad: int) -> str:
        """Generate the next unique accession number."""
        self.accession_counter += 1
        return f"{prefix}{self.accession_counter:0{zero_pad}d}"

    def add_study(self, study: Study) -> None:
        """Add a new study to the active worklist."""
        self.active_studies[study.accession_number] = study

    def get_study(self, accession_number: str) -> Study | None:
        """Get an active study by accession number."""
        return self.active_studies.get(accession_number)

    def archive_study(self, accession_number: str) -> None:
        """Move a study from active to archive (Approved or Cancelled)."""
        study = self.active_studies.pop(accession_number, None)
        if study:
            self.archived_studies.append(study.to_api_response())

    def add_audit_entry(self, entry: AuditEntry) -> None:
        """Add an audit log entry."""
        self.audit_entries.append(entry.model_dump(mode="json"))

    def load_from_disk(self) -> None:
        """Restore state from JSON files on startup."""
        DB_DIR.mkdir(parents=True, exist_ok=True)

        if WORKLIST_DB_FILE.exists():
            try:
                data = json.loads(WORKLIST_DB_FILE.read_text(encoding="utf-8"))
                self.accession_counter = data.get("accession_counter", 0)
                for study_data in data.get("studies", []):
                    study = Study.model_validate(study_data)
                    self.active_studies[study.accession_number] = study
                logger.info(
                    "Restored %d active studies (counter=%d)",
                    len(self.active_studies),
                    self.accession_counter,
                )
            except Exception:
                logger.exception("Failed to load worklist from disk")

        if ARCHIVE_DB_FILE.exists():
            try:
                data = json.loads(ARCHIVE_DB_FILE.read_text(encoding="utf-8"))
                self.archived_studies = data.get("studies", [])
                logger.info("Restored %d archived studies", len(self.archived_studies))
            except Exception:
                logger.exception("Failed to load archive from disk")

        if AUDIT_LOG_DB_FILE.exists():
            try:
                data = json.loads(AUDIT_LOG_DB_FILE.read_text(encoding="utf-8"))
                self.audit_entries = data.get("entries", [])
                logger.info("Restored %d audit entries", len(self.audit_entries))
            except Exception:
                logger.exception("Failed to load audit log from disk")

    def save_to_disk(self) -> None:
        """Persist all state to JSON files. Uses atomic write (write to .tmp then rename)."""
        DB_DIR.mkdir(parents=True, exist_ok=True)

        self._atomic_write(
            WORKLIST_DB_FILE,
            {
                "accession_counter": self.accession_counter,
                "studies": [s.model_dump(mode="json") for s in self.active_studies.values()],
            },
        )

        self._atomic_write(
            ARCHIVE_DB_FILE,
            {"studies": self.archived_studies},
        )

        self._atomic_write(
            AUDIT_LOG_DB_FILE,
            {"entries": self.audit_entries},
        )

    @staticmethod
    def _atomic_write(path: Path, data: Any) -> None:
        """Write JSON atomically: write to .tmp file, then rename."""
        tmp_path = path.with_suffix(".tmp")
        try:
            tmp_path.write_text(
                json.dumps(data, indent=2, default=str), encoding="utf-8"
            )
            # os.replace is atomic on most operating systems
            os.replace(tmp_path, path)
        except Exception:
            logger.exception("Failed to write %s", path)
            if tmp_path.exists():
                tmp_path.unlink()

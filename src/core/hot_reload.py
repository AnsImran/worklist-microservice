"""Hot-reload watcher for JSON configuration files.

On each 30-second tick, checks file modification times for all JSON files
under data/config/ and data/pools/. If any file changed since the last check,
it triggers a reload of the affected component.

This is lightweight — just os.stat() calls + conditional reads.
"""

import json
import logging
from pathlib import Path
from typing import Any

from src.config import CONFIG_DIR, POOLS_DIR

logger = logging.getLogger(__name__)


class HotReloader:
    """Tracks file modification times and reloads changed JSON configs."""

    def __init__(self) -> None:
        self._mtimes: dict[str, float] = {}
        self._cache: dict[str, Any] = {}

    def check_and_load(self, path: Path) -> tuple[Any, bool]:
        """Check if a file changed since last read. Returns (data, changed).

        If the file hasn't changed, returns the cached data and changed=False.
        If it has changed (or is being read for the first time), reads it,
        updates the cache, and returns changed=True.
        """
        key = str(path)
        try:
            current_mtime = path.stat().st_mtime
        except FileNotFoundError:
            return self._cache.get(key), False

        if key in self._mtimes and self._mtimes[key] == current_mtime:
            return self._cache[key], False

        # File is new or changed — read it
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._mtimes[key] = current_mtime
            self._cache[key] = data
            if key in self._mtimes:
                logger.info("Hot-reloaded: %s", path.name)
            return data, True
        except Exception:
            logger.exception("Failed to read %s", path)
            return self._cache.get(key), False

    def check_all_configs(self) -> dict[str, tuple[Any, bool]]:
        """Check all config and pool files. Returns {filename: (data, changed)}."""
        results = {}
        for directory in [CONFIG_DIR, POOLS_DIR]:
            if not directory.exists():
                continue
            for path in directory.glob("*.json"):
                data, changed = self.check_and_load(path)
                results[path.name] = (data, changed)
        return results

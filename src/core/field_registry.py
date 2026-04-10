"""Field registry — reads field_definitions.json and generates values for each field.

This is the central component that makes the system configurable without code changes.
It parses field definitions, understands generation strategies, and produces values
for new studies.
"""

import json
import logging
import random
from typing import Any

from src.config import FIELD_DEFINITIONS_FILE, POOLS_DIR

logger = logging.getLogger(__name__)


class FieldRegistry:
    """Parses field definitions and generates values for study fields."""

    def __init__(self) -> None:
        self.fields: list[dict[str, Any]] = []
        self._pools: dict[str, Any] = {}
        self._patient_lookup: dict[str, dict[str, str]] = {}

    def load(self, data: dict[str, Any] | None = None) -> None:
        """Load field definitions from data dict or from disk."""
        if data is None:
            data = json.loads(FIELD_DEFINITIONS_FILE.read_text(encoding="utf-8"))
        self.fields = data.get("fields", [])
        self._preload_pools()

    def _preload_pools(self) -> None:
        """Pre-load all referenced pool files into memory."""
        for field in self.fields:
            pool_file = field.get("pool_file")
            if pool_file and pool_file not in self._pools:
                path = POOLS_DIR / pool_file
                if path.exists():
                    self._pools[pool_file] = json.loads(
                        path.read_text(encoding="utf-8")
                    )

        # Build patient name -> record lookup for patient_linked fields
        patients_data = self._pools.get("patients.json", {})
        for patient in patients_data.get("patients", []):
            self._patient_lookup[patient["name"]] = patient

    def reload_pool(self, pool_file: str, data: Any) -> None:
        """Update a specific pool's cached data."""
        self._pools[pool_file] = data
        if pool_file == "patients.json":
            self._patient_lookup.clear()
            for patient in data.get("patients", []):
                self._patient_lookup[patient["name"]] = patient

    def generate_value(
        self, field: dict[str, Any], context: dict[str, Any]
    ) -> Any:
        """Generate a value for a single field based on its generation strategy.

        Args:
            field: The field definition dict from field_definitions.json.
            context: Already-generated values for this study (so fields can
                     reference each other, e.g., study_description needs modality).
        """
        strategy = field.get("generation_strategy", "")

        if strategy == "random_from_pool":
            return self._gen_random_from_pool(field)

        if strategy == "random_from_pool_keyed":
            return self._gen_random_from_pool_keyed(field, context)

        if strategy == "sequential_prefix":
            # Handled externally by the generator (needs store's counter)
            return None

        if strategy == "current_time":
            # Handled externally by the generator
            return None

        if strategy == "lifecycle_timestamp":
            # Starts as None, filled during lifecycle transitions
            return None

        if strategy == "initial_value":
            return field.get("value")

        if strategy == "weighted_random":
            return self._gen_weighted_random(field)

        if strategy == "weighted_random_numeric":
            return self._gen_weighted_random_numeric(field)

        if strategy == "modality_based_range":
            return self._gen_modality_based_range(field, context)

        if strategy == "patient_linked":
            return self._gen_patient_linked(field, context)

        if strategy == "self_or_pool":
            return self._gen_self_or_pool(field, context)

        logger.warning("Unknown generation strategy: %s", strategy)
        return None

    # ---- Strategy implementations ----

    def _gen_random_from_pool(self, field: dict) -> Any:
        pool_file = field.get("pool_file", "")
        pool_key = field.get("pool_key", "")
        pool_data = self._pools.get(pool_file, {})
        items = pool_data.get(pool_key, [])
        if not items:
            return None
        item = random.choice(items)
        # If items are dicts and pool_subkey is set, extract the subkey
        subkey = field.get("pool_subkey")
        if subkey and isinstance(item, dict):
            return item[subkey]
        return item

    def _gen_random_from_pool_keyed(self, field: dict, context: dict) -> Any:
        pool_file = field.get("pool_file", "")
        key_field = field.get("key_field", "")
        key_value = context.get(key_field, "")
        pool_data = self._pools.get(pool_file, {})
        items = pool_data.get(key_value, [])
        if not items:
            return None
        return random.choice(items)

    def _gen_weighted_random(self, field: dict) -> Any:
        values = field.get("possible_values", [])
        weights = field.get("weights", [])
        if not values or not weights:
            return None
        return random.choices(values, weights=weights, k=1)[0]

    def _gen_weighted_random_numeric(self, field: dict) -> int:
        weight_ranges = field.get("weight_ranges", [])
        if not weight_ranges:
            return random.randint(field.get("min", 1), field.get("max", 10))
        # Pick which sub-range, then pick a value within it
        ranges = [wr["range"] for wr in weight_ranges]
        weights = [wr["weight"] for wr in weight_ranges]
        chosen_range = random.choices(ranges, weights=weights, k=1)[0]
        return random.randint(chosen_range[0], chosen_range[1])

    def _gen_modality_based_range(self, field: dict, context: dict) -> float:
        modality = context.get("modality", "CT")
        ranges = field.get("ranges", {})
        r = ranges.get(modality, [1.0, 3.0])
        return round(random.uniform(r[0], r[1]), 2)

    def _gen_patient_linked(self, field: dict, context: dict) -> Any:
        linked_field = field.get("linked_field", "patient_name")
        patient_name = context.get(linked_field)
        if not patient_name:
            return None
        patient = self._patient_lookup.get(patient_name)
        if patient:
            return_key = field.get("pool_return_key", "")
            return patient.get(return_key)
        # Patient not in pool (custom name) — generate a value
        return_key = field.get("pool_return_key", "")
        if return_key == "mrn":
            return f"SHHD{random.randint(2200000, 2999999)}"
        if return_key == "dob":
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            year = random.randint(1940, 2005)
            return f"{month:02d}/{day:02d}/{year}"
        return None

    def _gen_self_or_pool(self, field: dict, context: dict) -> Any:
        self_prob = field.get("self_probability", 0.7)
        self_field = field.get("self_field", "")
        if random.random() < self_prob:
            return context.get(self_field, "Self-Assigned")
        # Fall back to pool
        pool_file = field.get("pool_file", "")
        pool_key = field.get("pool_key", "")
        pool_data = self._pools.get(pool_file, {})
        items = pool_data.get(pool_key, [])
        if items:
            return random.choice(items)
        return "Unknown"

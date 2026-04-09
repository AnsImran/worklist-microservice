"""Application configuration — paths, intervals, constants."""

from pathlib import Path

# Base directory of the project (one level up from src/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Data directories
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = DATA_DIR / "config"
POOLS_DIR = DATA_DIR / "pools"
DB_DIR = DATA_DIR / "db"
DEMAND_DIR = BASE_DIR / "demand"

# Config files (hot-reloadable)
FIELD_DEFINITIONS_FILE = CONFIG_DIR / "field_definitions.json"
LIFECYCLE_FILE = CONFIG_DIR / "lifecycle.json"
GENERATION_RATES_FILE = CONFIG_DIR / "generation_rates.json"

# Pool files
PATIENTS_FILE = POOLS_DIR / "patients.json"
RADIOLOGISTS_FILE = POOLS_DIR / "radiologists.json"
REFERRING_PHYSICIANS_FILE = POOLS_DIR / "referring_physicians.json"
STUDY_DESCRIPTIONS_FILE = POOLS_DIR / "study_descriptions.json"

# Database files (runtime state)
WORKLIST_DB_FILE = DB_DIR / "worklist.json"
ARCHIVE_DB_FILE = DB_DIR / "archive.json"
AUDIT_LOG_DB_FILE = DB_DIR / "audit_log.json"

# Demand file
DEMAND_FILE = DEMAND_DIR / "demanded_data.json"

# Defaults (overridden by generation_rates.json)
DEFAULT_TICK_INTERVAL = 30
DEFAULT_STUDIES_PER_TICK_MIN = 1
DEFAULT_STUDIES_PER_TICK_MAX = 4
DEFAULT_ACTIVE_WORKLIST_MAX = 200

# Accession number counter starting point
ACCESSION_START = 1705200

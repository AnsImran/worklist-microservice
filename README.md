# Simulated Radiology Worklist Microservice

A FastAPI-based microservice that simulates a real hospital radiology worklist (like the ones used in PACS systems such as Konica Exa). It generates fake patient studies, moves them through realistic lifecycle stages, and exposes everything via a REST API.

Other services can connect to this API to get a live, constantly-updating worklist — just like a real hospital would have.

---

## What Does This Do ?

Imagine a hospital radiology department. Patients come in, get imaging exams (CT scans, X-rays, MRIs, etc.), and those exams appear on a **worklist** — a screen that radiologists look at to know what they need to read next.

This microservice **simulates that entire process**:

1. **New exams appear** in the worklist every 30 seconds (just like real patients arriving)
2. **Exams get assigned** to a radiologist (sometimes self-assigned, sometimes by a referring doctor)
3. **The radiologist reads** the exam
4. **The exam goes for approval** and eventually gets **approved** (or occasionally **cancelled**)
5. **Everything is logged** — every status change, every assignment, every event — just like a real audit trail

The data is fake (randomly generated patient names, exam types, etc.), but the **behavior is realistic** and the timing uses real wall-clock seconds.

---

## The Lifecycle of an Exam

Every exam that enters the worklist goes through these stages:

```
 Introduced ──→ Assigned ──→ Dictating ──→ Pending Approval ──→ Approved
      │              │           │               │
      └──────────────┴───────────┴───────────────┘
                            │
                        Cancelled
                   (can happen at any stage)
```

| Stage | What it means |
|---|---|
| **Introduced** | The exam just appeared in the worklist. No one has picked it up yet. |
| **Assigned** | A radiologist has been assigned to read this exam. |
| **Dictating** | The radiologist is actively looking at the images and writing a report. |
| **Pending Approval** | The report is written and waiting for final sign-off. |
| **Approved** | Done. The report is finalized. The exam moves to the archive. |
| **Cancelled** | The exam was cancelled before completion (about 2% of exams). |

When an exam is first created, the system **decides its entire timeline upfront** — it already knows exactly when it will be assigned, when dictating will start, and when it will be approved. This makes the simulation predictable and realistic.

### Reverse transitions (opt-in, for end-to-end testing)

By default the lifecycle is **forward-only** — once an exam reaches
`Approved` or `Cancelled` it is archived and cannot move again. This
mirrors the real worklist.

For end-to-end testing of the notification system's **re-dictation
cycle** (a signed exam reopened, reassigned, dictated, and signed again),
the mock can be launched with the environment variable
`ALLOW_REVERSE_TRANSITIONS=true`. That unlocks four extra paths on
`PUT /studies/{accession_number}/status`:

| From | Extra targets allowed |
|---|---|
| `Pending Approval` | `Dictating` (rework a draft before signing) |
| `Approved` | `Assigned` (reopen + reassign) |
| `Approved` | `Dictating` (same rad reopens) |
| `Approved` | `Cancelled` (signed exam cancelled retroactively) |

When an exam transitions **out of** `Approved`, it is un-archived back
into the active worklist (the store's `unarchive_study`), so the
notification engine starts tracking it again. The cycle can repeat any
number of times. Leaving the variable unset (the default) keeps the
strict forward-only behaviour. The notification system's e2e harness
sets this flag automatically via `run_all.py --for-e2e`.

---

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Install and Run

```bash
# Install dependencies
uv sync

# Start the server
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

The server starts immediately. Within 30 seconds, you will see studies appearing in the worklist. Open your browser and go to:

- **http://localhost:8000/docs** — Interactive API documentation (Swagger UI)
- **http://localhost:8000/health** — Quick health check
- **http://localhost:8000/stats** — Live statistics
- **http://localhost:8000/worklist** — Current active worklist

### Running the Frontend

```bash
# From the repo root (API must be running in another terminal)
set API_BASE_URL=http://localhost:8000&& uv run streamlit run frontend/app.py
```

The frontend opens at **http://localhost:8501**.

### Running Tests

```bash
uv run pytest tests/ -v
```

82 tests covering: API endpoints, study generation, lifecycle transitions (incl. opt-in reverse transitions + un-archive), audit logging, demand processing, data store, and field registry.

---

## API Endpoints

| Method | URL | What it does |
|---|---|---|
| `GET` | `/health` | Returns `{"status": "ok"}` if the service is running |
| `GET` | `/stats` | Live counts — how many exams by status, by modality, total archived |
| `GET` | `/worklist` | All active (in-progress) exams. Supports filters (see below) |
| `GET` | `/worklist/{accession}` | Look up a single exam by its accession number |
| `GET` | `/history` | Archived exams (completed or cancelled). Supports date range filters |
| `GET` | `/audit` | Full event log — every status change, assignment, creation |
| `POST` | `/demand` | Create a new exam immediately with full control over characteristics and lifecycle timing |
| `POST` | `/demand/batch` | Create multiple exams in one call (same schema as `/demand`, but as a list) |
| `PUT` | `/studies/{accession}/status` | Manually change an exam's status |

### Filtering Examples

```
GET /worklist?modality=CT                          — Only CT scans
GET /worklist?status=Dictating                       — Only exams being read right now
GET /worklist?priority_min=7&priority_max=10       — High-priority exams only
GET /worklist?accession_number=COCSNV0000000001    — Find a specific exam in the active worklist
GET /history?date_from=2026-04-09T00:00:00Z        — Archived exams from a specific date
GET /history?status=Cancelled                      — Only cancelled exams
GET /history?patient_name=Garcia                   — Search by patient name (partial match)
GET /audit?accession_number=COCSNV0000000001       — Full history of one specific exam
GET /audit?screen=Assignment                       — Only assignment events
GET /audit?user=Wright                             — Events by a specific user
```

---

## Project Structure

```
microservice_worklist/
│
├── src/                        ← All application code
│   ├── main.py                 ← Entry point — starts the server and background loop
│   ├── config.py               ← File paths and constants
│   ├── models/                 ← Data definitions (what a study looks like, what an audit entry looks like)
│   ├── core/                   ← The engine (generates studies, advances lifecycle, hot-reloads config)
│   ├── data/                   ← In-memory data store with JSON file persistence
│   ├── api/                    ← All REST API endpoints
│   └── services/               ← Audit logger and demand processor
│
├── data/
│   ├── config/                 ← Configuration files (HOT-RELOADABLE — edit while running!)
│   │   ├── field_definitions.json   ← Defines every data field on a study
│   │   ├── lifecycle.json           ← How fast exams move through stages
│   │   └── generation_rates.json    ← How many new exams per tick, max worklist size
│   ├── pools/                  ← Reference data (names, descriptions, etc.)
│   │   ├── patients.json            ← 1000 patient names with unique MRNs
│   │   ├── radiologists.json        ← 10 radiologist names
│   │   ├── referring_physicians.json ← 10 referring doctor names
│   │   └── study_descriptions.json  ← Exam descriptions grouped by modality
│   └── db/                     ← Runtime state (auto-generated, git-ignored)
│       ├── worklist.json            ← Current active studies
│       ├── archive.json             ← Completed/cancelled studies
│       └── audit_log.json           ← Full event history
│
├── frontend/                   ← Streamlit worklist frontend
│   ├── app.py                  ← Entry point (home page)
│   ├── pages/                  ← Worklist, Statistics, Audit Log, History, Demand Injection
│   └── utils/                  ← API client, styling helpers
│
├── tests/                      ← Unit and API tests (pytest)
│   ├── conftest.py             ← Shared fixtures
│   ├── test_api_*.py           ← API endpoint tests (health, worklist, history, audit, demand, studies)
│   ├── test_generator.py       ← Study generation with overrides, custom patients, timelines
│   ├── test_lifecycle.py       ← Lifecycle transitions, timestamps, cancellation
│   ├── test_store.py           ← Data store operations
│   ├── test_audit_logger.py    ← Audit logging with custom timestamps
│   ├── test_field_registry.py  ← Field generation strategies, patient lookup
│   └── test_demand_processor.py ← File-based demand processing
│
├── demand/
│   └── demanded_data.json      ← Inject specific exams with custom timing (see below)
│
└── scripts/
    └── generate_patients.py    ← One-time script that generated the 1000 patient names
```

---

## Hot-Reloadable Configuration

All files under `data/config/` are **hot-reloadable**. This means you can edit them while the server is running, and the changes take effect within 30 seconds — no restart needed.

### generation_rates.json — Control the flow

| Setting | What it controls | Default |
|---|---|---|
| `studies_per_tick.min` | Minimum new exams created every 30 seconds | 0 |
| `studies_per_tick.max` | Maximum new exams created every 30 seconds | 3 |
| `active_worklist_max_size` | Hard cap — stop creating exams if this many are active | 200 |
| `tick_interval_seconds` | How often the background loop runs | 30 |

### lifecycle.json — Control the timing

Each transition has a `min_seconds` and `max_seconds`. When an exam is created, the system picks a random delay within each range to build the exam's full timeline.

| Transition | Default range | What it means |
|---|---|---|
| Introduced → Assigned | 60–300 seconds | 1 to 5 minutes before someone picks it up |
| Assigned → Dictating | 30–120 seconds | 30 seconds to 2 minutes before dictating starts |
| Dictating → Pending Approval | 120–900 seconds | 2 to 15 minutes of dictating time |
| Pending Approval → Approved | 60–600 seconds | 1 to 10 minutes in the approval queue |

`cancellation_probability` controls how many exams get cancelled instead of approved (default: 2%).

### field_definitions.json — Define data fields

This file defines every data field on a study — its name, type, whether it is required, and how its value is generated. The file itself contains detailed instructions on how to add new fields. See the `_README` section at the top of the file for a complete guide.

---

## The Demand System

The demand system lets you **inject specific exams** into the worklist with exact characteristics and timing. This is useful for testing scenarios like:

- "I want a STAT stroke exam that gets assigned in 30 seconds and approved in 2 minutes"
- "I want an MR exam that gets cancelled during dictating"

### How to use it

1. Open `demand/demanded_data.json`
2. Add an entry to the `requests` array
3. Save the file
4. The system picks it up within 30–60 seconds

The file contains detailed instructions and multiple commented-out examples. Here is a quick example:

```json
{
  "requests": [
    {
      "id": "my-test-001",
      "processed": false,
      "action": "inject_study",
      "study": {
        "modality": "CT",
        "study_description": "- CT BRAIN STROKE W/O CONTRAST",
        "priority": 10
      },
      "lifecycle_overrides": {
        "Introduced_to_Assigned": 30,
        "Assigned_to_Dictating": 30,
        "Dictating_to_Pending_Approval": 60,
        "Pending_Approval_to_Approved": 30
      }
    }
  ]
}
```

This creates a high-priority CT stroke exam that moves through the entire lifecycle in about 2.5 minutes.

---

## Data Fields on Each Study

| Field | Description | Example |
|---|---|---|
| `accession_number` | Unique ID for the exam | `COCSNV0000000042` |
| `patient_name` | Patient's name (from pool of 1000) | `Garcia, Maria L` |
| `mrn` | Medical Record Number (unique per patient) | `SHHD2100392` |
| `dob` | Date of birth | `04/08/1975` |
| `modality` | Type of imaging | `CT`, `CR`, `DX`, `MR`, `US`, `NM` |
| `study_description` | What the exam is | `- CT BRAIN STROKE W/O CONTRAST` |
| `priority` | Urgency level, 1–10 (10 = most urgent) | `7` |
| `rvu` | Relative Value Unit (complexity measure) | `3.42` |
| `status` | Current lifecycle stage | `Dictating` |
| `study_introduced_at` | When the exam entered the worklist | `2026-04-09T10:14:44Z` |
| `assigned_at` | When it was assigned to a radiologist | `2026-04-09T10:16:14Z` |
| `assigned_radiologist` | **Identity** of the assigned rad (= email / NewVue username). Stable. Used by the notification system for roster lookup. | `joshua.wright@pacspros.llc` |
| `assigned_radiologist_display` | **Human-readable** name (`"Last, First"`) for the same rad. Used in SMS / Teams / Zoho ticket subjects. Resolved from the same pool entry as `assigned_radiologist`. | `Wright, Joshua` |
| `assigned_by` | Who assigned it (often self-assigned). Carries the email when self-assigned (70%), a referring-physician name from the pool otherwise. | `joshua.wright@pacspros.llc` |

### Why `assigned_radiologist` is the email (and how it pairs with `assigned_radiologist_display`)

The mock previously emitted a single `assigned_radiologist` field that was a display string like `"Wright, Joshua M.D."`. The notification system used that one string for two unrelated jobs: as the **roster key** (look up the rad's phone numbers in `notification_targets.yaml`) and as the **display name** (render into SMS / Teams / Zoho ticket subjects).

We split those two jobs into two separate fields so the mock matches the shape of the real NewVue worklist (and the downstream `worklist_database` data platform's `v_worklist_active` view, which the notification system will eventually read from instead of polling the mock):

- **`assigned_radiologist` is now the radiologist's email** (the NewVue `username`, e.g. `joshua.wright@pacspros.llc`). It is the **stable identity**: it doesn't change if the person is renamed, it can't collide between two people who happen to share a display name, and it matches the same key the data platform uses (`exam_assignedto_username` on `exam_current`). The notification system's roster (`audiences.radiologist` in `notification_targets.yaml`) is keyed by this string.
- **`assigned_radiologist_display`** is the human-readable `"Last, First"` form (e.g. `"Wright, Joshua"`), joined from the picked pool entry's `first_name` + `last_name`. It is used **only** for rendering — every place a human sees the rad's name (SMS body, Teams card, Zoho ticket subject, audit comments). It is **never** used for identity or routing.

The pool that backs both fields lives at [`data/pools/radiologists.json`](data/pools/radiologists.json). Each entry is now an object with three keys:

```json
{
  "radiologists": [
    {
      "email": "joshua.wright@pacspros.llc",
      "first_name": "Joshua",
      "last_name": "Wright"
    }
  ]
}
```

At the `Introduced → Assigned` transition the lifecycle engine picks one entry at random, sets `assigned_radiologist = entry.email`, and resolves `assigned_radiologist_display` from the same entry via `FieldRegistry.display_name_for(email)`. The reassign endpoint (`PUT /studies/{accession}/assignee`) does the same: it accepts an email in the request body and stamps both fields on the study.

### Modalities

| Code | What it is |
|---|---|
| `CT` | Computed Tomography (CT scan) |
| `CR` | Computed Radiography (digital X-ray) |
| `DX` | Digital Radiography |
| `MR` | Magnetic Resonance Imaging (MRI) |
| `US` | Ultrasound |
| `NM` | Nuclear Medicine |

---

## Concurrency

FastAPI serves each request in its own threadpool thread when the handler is a
plain `def`. The two write endpoints (`PUT /studies/{acc}/status` and
`PUT /studies/{acc}/assignee`) do a read–modify–write on the in-memory `Study`
object, and concurrent PUTs to the **same** study would race on
`study.status = …` / `study.assigned_radiologist = …` without coordination —
this surfaced empirically as one of three concurrent reassigns silently
dropping when the e2e harness fired three identical PUTs at the same instant.

The fix is one **per-study reentrant lock**, lazily created by accession and
held only across the read-modify-write block of each handler. Different
accessions get distinct locks, so concurrent PUTs against **different** studies
still run in parallel; only same-study compound mutations are serialised — the
same guarantee a real worklist DB gets for free via row-level locking.

- `DataStore.study_lock(accession)` ([src/data/store.py](src/data/store.py)) —
  returns the per-study `threading.RLock`, lazy-created under a tiny meta-lock
  so two threads racing to create the same accession's lock end up sharing one.
- `update_study_status` / `reassign_study`
  ([src/api/routes_studies.py](src/api/routes_studies.py)) wrap their bodies
  with `with store.study_lock(accession_number):` via a thin wrapper +
  `_*_locked` impl so the existing body needs no re-indent.

---

## Persistence

All runtime state is saved to JSON files under `data/db/` on every tick (every 30 seconds). If you stop and restart the server, it picks up right where it left off — active studies, archive, audit log, and the accession counter all survive restarts.

The `data/db/` folder is git-ignored since it is generated at runtime.

---

## What's Coming Next

- **Dashboard** — A live web UI to view and interact with the worklist (separate container, same repo)
- **Docker** — Containerized deployment for both the API and dashboard

---

## Deployment & observability (EC2)

> Note: this service is the **mock / simulated** worklist used for development and testing. Production worklist data now comes from the separate NewVue worklist parser — this microservice is not in the production data path, but it is deployed and observed identically so the two stay operationally interchangeable.

Production runs as a Docker container on a single EC2 host, deployed by GitHub Actions, observed by a shared Prometheus + Grafana + Tempo + Loki stack. (Local dev still works via the Quick Start instructions above.)

### Containerization
- This repo builds **two images**:
  - **`Dockerfile.api`** → `ghcr.io/ansimran/worklist-microservice/worklist-api:latest` — the FastAPI worklist API.
  - **`Dockerfile.frontend`** → `ghcr.io/ansimran/worklist-microservice/worklist-frontend:latest` — the Streamlit worklist UI.
- Both are `python:3.12-slim`; dependencies installed with `uv sync --frozen --no-dev --no-install-project` from `pyproject.toml` + `uv.lock` (eliminates dep drift between local / CI / prod — this replaced an earlier hand-curated `pip install` list that silently went stale when new deps were added). Only the **API** image has its `CMD` wrapped with `opentelemetry-instrument`, which is inert unless the `OTEL_*` env vars are set, so the image runs fine standalone.
- **`docker-compose.yml`** references the CI-built GHCR images (`worklist-api:latest` and `worklist-frontend:latest`) with `build:` blocks kept as a local fallback.
- **`.dockerignore`** keeps secrets, tests, docs and the `.github/` folder out of the build context.

### CI/CD — `.github/workflows/ci.yml`
On push to `main`: **test** (lint/compile/pytest) → **build-and-push** (images → GHCR, registry-cached) → **deploy** (SSH to EC2, `git reset --hard origin/main`, `docker login ghcr.io`, `docker compose pull`, `docker compose up -d`, health-check). Required GitHub Actions secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `GHCR_USER`, `GHCR_TOKEN` (plus `DEPLOY_GIT_PATH` where used). Docs-only pushes are skipped via `paths-ignore`.

### EC2 topology
The containers join an external Docker network **`observability-net`** so services resolve each other by container name and Prometheus can scrape them. An EC2-side **`docker-compose.override.yml`** (gitignored, not in this repo) injects the `OTEL_*` env vars + a `WLS_LOG_FILE` path and joins that network; the committed compose stays environment-agnostic. The container names on EC2 are **`worklist-api`** (internal port **8000**) and **`worklist-frontend`** (Streamlit, internal port **8501** → host port **8502**).

### Observability
- **Phase 1 — metrics:** `/metrics` exposed via `prometheus-fastapi-instrumentator`; Prometheus scrapes it (scrape job / `OTEL_SERVICE_NAME`: **`worklist`**).
- **Phase 2 — traces + logs:** the `opentelemetry-instrument` CMD wrapper (API image) auto-instruments FastAPI + httpx and ships spans via OTLP to the OTel Collector → **Tempo**. JSON logs go to `WLS_LOG_FILE`, tailed by **Promtail** into **Loki**; `OTEL_PYTHON_LOG_CORRELATION=true` injects `otelTraceID` so Grafana jumps trace ⇄ log. The explicit OTel instrumentor packages (`opentelemetry-instrumentation-fastapi`/`-httpx`/`-logging`) are pinned in `pyproject.toml` because uv-created venvs ship without `pip`, so the usual `opentelemetry-bootstrap -a install` step silently no-ops.

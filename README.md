# Simulated Radiology Worklist Microservice

A FastAPI-based microservice that simulates a real hospital radiology worklist (like the ones used in PACS systems such as Konica Exa). It generates fake patient studies, moves them through realistic lifecycle stages, and exposes everything via a REST API.

Other services can connect to this API to get a live, constantly-updating worklist — just like a real hospital would have.

---

## What Does This Do?

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
 Introduced ──→ Assigned ──→ Reading ──→ Pending Approval ──→ Approved
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
| **Reading** | The radiologist is actively looking at the images and writing a report. |
| **Pending Approval** | The report is written and waiting for final sign-off. |
| **Approved** | Done. The report is finalized. The exam moves to the archive. |
| **Cancelled** | The exam was cancelled before completion (about 2% of exams). |

When an exam is first created, the system **decides its entire timeline upfront** — it already knows exactly when it will be assigned, when reading will start, and when it will be approved. This makes the simulation predictable and realistic.

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
| `POST` | `/demand` | Create a new exam with full control over characteristics and lifecycle timing |
| `PUT` | `/studies/{accession}/status` | Manually change an exam's status |

### Filtering Examples

```
GET /worklist?modality=CT                    — Only CT scans
GET /worklist?status=Reading                 — Only exams being read right now
GET /worklist?priority_min=7&priority_max=10 — High-priority exams only
GET /history?date_from=2026-04-09T00:00:00Z  — Archived exams from a specific date
GET /audit?accession_number=COCSNV0000000001 — Full history of one specific exam
GET /audit?screen=Assignment                 — Only assignment events
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
| Assigned → Reading | 30–120 seconds | 30 seconds to 2 minutes before reading starts |
| Reading → Pending Approval | 120–900 seconds | 2 to 15 minutes of reading time |
| Pending Approval → Approved | 60–600 seconds | 1 to 10 minutes in the approval queue |

`cancellation_probability` controls how many exams get cancelled instead of approved (default: 2%).

### field_definitions.json — Define data fields

This file defines every data field on a study — its name, type, whether it is required, and how its value is generated. The file itself contains detailed instructions on how to add new fields. See the `_README` section at the top of the file for a complete guide.

---

## The Demand System

The demand system lets you **inject specific exams** into the worklist with exact characteristics and timing. This is useful for testing scenarios like:

- "I want a STAT stroke exam that gets assigned in 30 seconds and approved in 2 minutes"
- "I want an MR exam that gets cancelled during reading"

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
        "Assigned_to_Reading": 30,
        "Reading_to_Pending_Approval": 60,
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
| `status` | Current lifecycle stage | `Reading` |
| `study_introduced_at` | When the exam entered the worklist | `2026-04-09T10:14:44Z` |
| `assigned_at` | When it was assigned to a radiologist | `2026-04-09T10:16:14Z` |
| `assigned_radiologist` | Who is reading it | `Wright, Joshua M.D.` |
| `assigned_by` | Who assigned it (often self-assigned) | `Wright, Joshua M.D.` |

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

## Persistence

All runtime state is saved to JSON files under `data/db/` on every tick (every 30 seconds). If you stop and restart the server, it picks up right where it left off — active studies, archive, audit log, and the accession counter all survive restarts.

The `data/db/` folder is git-ignored since it is generated at runtime.

---

## What's Coming Next

- **Dashboard** — A live web UI to view and interact with the worklist (separate container, same repo)
- **Docker** — Containerized deployment for both the API and dashboard

# 🪄 DataGenie — AI-Powered Synthetic Test Data Generator

DataGenie is a full-stack application that generates realistic, compliant synthetic test data from natural language descriptions or uploaded sample files. It infers schema, detects sensitive fields, enforces masking rules, and outputs data in 8 formats — all without your real data ever leaving your environment.

---

## ✨ Features

### Schema Inference
- **Natural language input** — describe your data in plain English (*"50 users with name, email, SSN, and purchase history"*) and DataGenie infers tables, columns, types, volume, and compliance requirements
- **File upload** — upload CSV, TSV, Excel, JSON, XML, or YAML files as a schema template; columns, types, and sample values are auto-extracted
- **Multi-table schema** — infers related tables from context (e.g., `customers → orders → order_items`) with FK relationships and suggested cardinality
- **Semantic type detection** — 100+ field catalog maps column names to real-world types (`email`, `phone`, `ssn`, `iban`, `dob`, `job_title`, `company_name`, etc.)

### Starter Templates
Click a card to instantly load a fully-configured multi-table schema. Templates work with **any LLM provider** (including Demo mode) — use them as a starting point, then refine with natural language or by editing fields directly.

| Card | Schema | Frameworks |
|------|--------|-----------|
| 🛒 **E-Commerce Orders** | `customers → orders → order_items` | PCI, PII, GDPR |
| 🏥 **Healthcare Patients** | `patients → visits + prescriptions` | HIPAA, PII, GDPR |
| 👩‍💼 **HR & Payroll** | `employees → leave_requests` | SOX, PII, GDPR |
| 🎓 **Student Records** | `students → enrollments` | FERPA, PII, GDPR |
| 🏦 **Banking & Accounts** | `customers → accounts → transactions + loans` | PCI, GLBA, SOX, PII |

### Compliance & Masking
- **8 regulatory frameworks** — PII, PCI DSS, HIPAA, GDPR, CCPA, SOX, FERPA, GLBA
- **Per-field masking actions** — `fake_realistic`, `redact`, `hash`, `partial_mask`, `tokenize`, `age_shift`, `generalize`
- **Custom masking rules** — write plain-English rules per field (*"replace with last 4 digits only"*) that are normalised to structured masking ops via LLM
- **Confidence scores** — LLM classifies each field and reports confidence; rule-based catalog is the fallback

### Data Generation
- **Value distributions** — configure exact ratios for enum fields (*80% Active / 15% Inactive / 5% Suspended*)
- **Referential integrity** — FK values in child tables are sampled from parent table PKs
- **Realistic Faker data** — country/city consistency, person names, emails, phone numbers, credit cards, dates, IBANs, SSNs, MRNs, etc.
- **Relationship validation** — enforces no duplicate table pairs, no reverse relationships (A→B blocks B→A)

### Output
- **8 export formats** — CSV, TSV, JSON, JSON Lines, Excel (.xlsx), XML, YAML, Parquet
- **JSON style options** — Array of objects, Nested object, or JSON Lines (one record per line)
- **XML structure options** — configurable root element and row element names
- **Multi-table ZIP** — when schema has multiple tables, all files are bundled in a single ZIP
- **In-app preview** — see sample rows before downloading; preview clears when you edit earlier stages

### Profiles & Persistence
- **Save profiles** — store any generation config (schema + compliance + output settings) with a name
- **Reload instantly** — load a saved profile to re-run or tweak a previous configuration
- **Searchable profile list** — filter by name with relative timestamps

### Reliability
- **Retry logic** — network errors and 5xx responses are automatically retried up to 2× with exponential backoff (handles Render deploy restarts gracefully)
- **LLM warning passthrough** — misconfigured providers surface a clear warning banner rather than silent fallback

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose

### Production (Docker)

```bash
git clone git@github.com:karthik-krishnan/datagenie.git
cd datagenie
docker-compose up --build
```

Open **http://localhost:3001** | API docs: **http://localhost:8000/docs**

> ⚠️ `docker-compose.yml` bakes code into the image — you must `docker-compose build backend && docker-compose up -d backend` after every backend Python change.

### Development (hot reload for both frontend and backend)

Use the dev overlay — backend source is volume-mounted and uvicorn runs with `--reload`, so Python changes are picked up instantly without rebuilding:

```bash
# Start postgres + backend with hot reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# Frontend with Vite HMR (run separately on the host)
cd frontend
npm install
npm run dev        # → http://localhost:3001
```

Or run everything natively without Docker:

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev        # → http://localhost:3001
```

The Vite dev server proxies `/api/*` to `http://localhost:8000` automatically.

---

## 🏗 Architecture

```
datagenie/
├── frontend/                        # React 18 + Vite + Tailwind CSS
│   └── src/
│       ├── api/
│       │   └── client.js            # API client with fetchWithRetry
│       ├── components/
│       │   ├── Stage1_Upload/       # File upload (drag-drop) & context text input
│       │   ├── Stage2_Characteristics/  # Volume input & value distribution editor
│       │   ├── Stage3_Compliance/   # Framework detection & per-field masking rules
│       │   ├── Stage4_Relationships/    # Cross-table FK relationship editor (validated)
│       │   ├── Stage5_Output/       # Format picker, preview table, download button
│       │   ├── Profiles/            # Save / load / search named profiles
│       │   └── Settings/            # LLM provider configuration
│       ├── store/
│       │   └── appStore.js          # Zustand global state
│       └── utils/
│           └── llmStorage.js        # localStorage LLM config persistence
│
├── backend/                         # FastAPI + SQLAlchemy (async)
│   ├── routers/
│   │   ├── schema.py    # POST /infer, GET /demo, POST /normalize-rule
│   │   ├── generate.py  # POST /generate, POST /preview
│   │   ├── profiles.py  # CRUD for saved profiles
│   │   └── settings.py  # LLM settings + test connection
│   └── services/
│       ├── llm_service.py           # Multi-provider LLM abstraction
│       ├── context_extractor.py     # NL → structured schema params
│       ├── compliance_detector.py   # 100+ field catalog, 7 frameworks, LLM batch
│       ├── data_generator.py        # Faker-based synthetic data engine
│       ├── demo_templates.py        # 5 multi-table + 4 single-table canned schemas
│       ├── output_formatter.py      # CSV/TSV/JSON/JSONL/Excel/XML/YAML/Parquet
│       ├── masking.py               # Plain-English rule → structured MaskingOp
│       ├── schema_inferrer.py       # File-based column type + stats inference
│       └── file_parser.py           # CSV/Excel/JSON/XML/YAML → normalised rows
│
├── docker-compose.yml               # Full stack (postgres + backend + frontend/nginx)
└── nginx.conf                       # Reverse proxy: /api → backend, / → frontend
```

---

## 🤖 LLM Configuration

Open **Settings (⚙️)** and choose your provider. Configuration is stored in `localStorage` and sent with every request — no server-side storage required.

| Provider | Notes |
|---|---|
| **Anthropic** | Claude Sonnet 3.5 / Opus — recommended for best schema inference |
| **OpenAI** | GPT-4o / GPT-4 Turbo |
| **Azure OpenAI** | Requires `endpoint` and `deployment` in Extra Config |
| **Google** | Gemini 1.5 Pro / Flash |
| **Ollama** | Local models (e.g. `llama3`), no API key needed |
| **Demo** | No API key — rule-based inference only, no LLM calls |

---

## 📋 The Generation Workflow

| Stage | What happens |
|-------|-------------|
| **1 · Upload & Context** | Upload sample files and/or describe your data in plain English. DataGenie infers column names, types, and volume. |
| **2 · Characteristics** | Review detected entity types; configure exact value distributions for categorical fields (e.g. gender, status). |
| **3 · Compliance** | DataGenie auto-detects sensitive fields across 7 frameworks. Review per-field masking actions; add custom rules in plain English. |
| **4 · Relationships** | Confirm or edit FK relationships between tables. Validation prevents duplicate or contradictory pairs. |
| **5 · Output & Preview** | Pick a format, preview sample rows, then download. Multi-table schemas are bundled in a ZIP. |

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 5, Tailwind CSS 3, Zustand |
| Backend | FastAPI, SQLAlchemy 2 (async), Uvicorn |
| Database | PostgreSQL 15 |
| Data generation | Faker, pandas, openpyxl, pyarrow |
| LLM providers | Anthropic, OpenAI, Azure OpenAI, Google Generative AI, Ollama |
| Containerisation | Docker, Docker Compose, nginx |

---

## 📸 Screenshots

> Screenshots can be found in [`docs/screenshots/`](docs/screenshots/).

| Screen | Description |
|--------|-------------|
| `01-starter-templates.png` | Profile picker with demo starter cards |
| `02-upload-infer.png` | File upload + context text → schema inference |
| `03-compliance.png` | Compliance review with per-field masking actions |
| `04-relationships.png` | Relationship editor with cardinality selector |
| `05-output-preview.png` | Format picker + in-app data preview |
| `06-download-excel.png` | Multi-table Excel / ZIP download |

---

## 🗒 Notes

- **No data leaves your environment** when using Ollama or if you self-host the backend. When using cloud LLM providers, only column names and sample values are sent (never full dataset rows).
- **Starter templates** are available in all modes — load any template and refine it with natural language or manual edits. In Demo mode, inference uses rule-based detection (no LLM calls required).
- The `/api/schema/infer` endpoint **never falls back to demo templates**. Starter cards use a dedicated `/api/schema/demo` endpoint. Free-form text always runs real inference (rule-based when in demo mode, LLM when configured).

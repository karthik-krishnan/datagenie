# 🪄 Datagenia — AI-Powered Synthetic Test Data Generator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Datagenia is a full-stack application that generates realistic, compliant synthetic test data from natural language descriptions or uploaded sample files. It infers schema, detects sensitive fields, enforces masking rules, and outputs data in multiple formats — all without your real data ever leaving your environment.

---

## 📋 Generation Workflow

| # | Name | Description |
|:-:|:-----|:------------|
| 1 | **Upload & Context** | Upload sample files and/or describe your data in plain English. DataGenie infers tables, columns, types, volume, and sensitivity. Edit schema inline using dog-ear tabs. |
| 2 | **Characteristics** | Set total volume, variable child counts per parent (min/max/shape), numeric ranges, and categorical value distributions. |
| 3 | **Compliance** | Auto-detected sensitive fields across 8 frameworks. Review and adjust per-field masking actions; write custom plain-English rules. *(Skipped if compliance is disabled or no sensitive fields detected.)* |
| 4 | **Relationships** | Confirm or edit parent→child FK relationships (1:N, 1:1, N:N). *(Skipped for single-table schemas.)* |
| 5 | **Output & Preview** | Pick a format, preview sample rows in a tabbed view, then download. Multi-table schemas are bundled as a ZIP. |

---

## ✨ Features

### Schema Inference (Stage 1)
- **Natural language input** — describe your data in plain English and DataGenie infers tables, columns, types, volume, and compliance requirements
- **File upload** — upload CSV, TSV, Excel, JSON, XML, or YAML files; columns, types, and sample values are auto-extracted
- **Multi-table schema** — infers related tables from context with FK relationships and cardinality
- **Semantic type detection** — 100+ field catalog maps column names to real-world types (`email`, `phone`, `ssn`, `iban`, `dob`, `job_title`, etc.)
- **Dog-ear tabbed schema editor** — one table visible at a time when multiple tables are present; tabs auto-reset on re-infer
- **Inline column editing** — rename columns, change types, edit enum values, set date formats
- **Type suggestions** — auto-suggests a better type when a column name implies one (e.g. `created_at` → `date`)
- **Unique constraints** — auto-detected for identifiers (email, SSN, passport, IBAN, username, etc.); manually overrideable per column
- **Sensitivity tagging** — click any cell to add/remove compliance framework badges (PII, PCI, HIPAA, GDPR, etc.); auto-detected on column rename
- **PK / FK column ordering** — primary key and foreign key columns are automatically sorted to the front of every table across all stages

---

### Characteristics (Stage 2)
- **Volume control** — set number of root-table rows; child tables scale automatically based on per-parent counts
- **Variable child record counts** — per child table min/max with three distribution shapes:
  - **Fixed** — every parent gets exactly the midpoint count
  - **Uniform** — random count drawn uniformly between min and max
  - **Realistic** — power-law skew toward lower counts (most parents have few children, a tail have many)
- **Numeric ranges** — configure min/max for `integer` and `float` columns
- **Value distributions** — set exact proportions for categorical (`string`/`enum`) columns with visual stacked proportion bar; percentages need not sum to 100
- **Dog-ear tabbed view** — per-table tabs for value distributions and ranges; badge shows count of configured columns
- **Quick mode** — "Let AI decide" toggle hands distribution decisions to the LLM

---

### Compliance & Masking (Stage 3)
- **8 regulatory frameworks** — PII, PCI DSS, HIPAA (all 18 PHI identifiers), GDPR (Art.9 special categories), CCPA, SOX, FERPA, GLBA
- **211-entry DLP field catalog** — rule-based detection covering all HIPAA 18 PHI, GDPR Art.9, PCI SAD, and GLBA fields
- **Per-field masking actions** — `fake_realistic`, `redact`, `hash`, `partial_mask`, `tokenize`, `age_shift`, `generalize`
- **Custom plain-English rules** — write a rule per field (*"replace with last 4 digits only"*) normalised to structured masking ops via LLM
- **Confidence scores** — LLM classifies each field and reports confidence; rule-based catalog is the fallback
- **Feature toggle** — disable the entire compliance feature in Settings for simpler use cases; hides sensitivity column, skips compliance stage entirely

---

### Relationships (Stage 4)
- **Parent→child direction** — relationships expressed as `Parent (1) → Child (N)`, e.g. `customers → orders`
- **Cardinality options** — 1:1, 1:N, N:N
- **Referential integrity** — FK values in child tables are sampled from parent table PKs
- **Duplicate & reverse detection** — prevents adding the same pair twice or contradictory A→B / B→A pairs
- **AI-detected relationships** — cross-file FK relationships auto-detected and pre-filled on infer

---

### Output (Stage 5)
- **7 export formats** — CSV, TSV, JSON, Excel (.xlsx), XML, YAML, Parquet
- **JSON style options** — Array of objects, Nested, or JSON Lines (one record per line)
- **XML structure options** — configurable root element and row element names
- **Multi-table ZIP** — when schema has multiple tables, all files are bundled in a single ZIP
- **Dog-ear tabbed preview** — see sample rows per table before downloading; row count badge on each tab
- **Preview regeneration** — re-run preview after editing any earlier stage
- **Consistent column ordering** — PK and FK columns appear first in the preview table, matching the schema editor order

---

### Settings
- **Sidebar placement** — Settings button consistently at the bottom-left on every screen
- **6 LLM providers** — Anthropic, OpenAI, Azure OpenAI, Google, Ollama, Demo
- **Per-provider key storage** — switching providers restores that provider's previously saved key/model/extras
- **Compliance feature toggle** — turn off regulatory compliance globally for simpler workflows
- **Test connection** — verify API key before saving

---

### App Shell
- **Fixed sidebar, scrollable content** — sidebar stays locked; only the main area scrolls
- **Stage locking** — stages 2–5 are locked until a schema is inferred ("infer schema first" tooltip)
- **Consistent headers** — identical top bar height across all screens

---

### Home Screen & Starter Templates
- **Profile picker home screen** — consistent sidebar layout with Settings pinned at bottom-left
- **4 domain starter templates** — instantly load a fully-configured multi-table schema for a specific domain; works in all modes including Demo
- **Saved profiles** — reload any previous generation config (schema + compliance + output settings) with one click; searchable by name

| Template | Schema | Frameworks |
|----------|--------|------------|
| 🛒 **E-Commerce Orders** | `customers → orders → order_items` | PCI, PII, GDPR |
| 🏥 **Healthcare Patients** | `patients → visits → prescriptions` | HIPAA, PII, GDPR |
| 👩‍💼 **HR & Payroll** | `employees → leave_requests` | SOX, PII, GDPR |
| 🏦 **Banking & Accounts** | `customers → accounts → transactions + loans` | PCI, GLBA, SOX, PII |

---

## 🤖 LLM Configuration

Open **Settings (⚙️)** from the sidebar bottom-left. Config is stored in `localStorage` — no server-side storage.

| Provider | Notes |
|---|---|
| **Anthropic** | Claude Sonnet / Opus — recommended for best schema inference |
| **OpenAI** | GPT-4o / GPT-4 Turbo |
| **Azure OpenAI** | Requires endpoint and deployment name |
| **Google** | Gemini 1.5 Pro / Flash |
| **Ollama** | Local models (e.g. `llama3`), no API key needed |
| **Demo** | No API key — rule-based inference only |

---

## 📸 Screenshots

<details>
<summary>Click to expand screenshots</summary>
<br/>

<table>
  <tr>
    <td align="center"><a href="docs/screenshots/01-starter-templates.png"><img src="docs/screenshots/01-starter-templates.png" width="170"/></a><br/><sub>Starter templates</sub></td>
    <td align="center"><a href="docs/screenshots/02-schema-infer.png"><img src="docs/screenshots/02-schema-infer.png" width="170"/></a><br/><sub>Schema editor</sub></td>
    <td align="center"><a href="docs/screenshots/03-characteristics.png"><img src="docs/screenshots/03-characteristics.png" width="170"/></a><br/><sub>Characteristics</sub></td>
    <td align="center"><a href="docs/screenshots/04-distributions.png"><img src="docs/screenshots/04-distributions.png" width="170"/></a><br/><sub>Value distributions</sub></td>
  </tr>
  <tr>
    <td align="center"><a href="docs/screenshots/05-compliance.png"><img src="docs/screenshots/05-compliance.png" width="170"/></a><br/><sub>Compliance review</sub></td>
    <td align="center"><a href="docs/screenshots/06-relationships.png"><img src="docs/screenshots/06-relationships.png" width="170"/></a><br/><sub>Relationships</sub></td>
    <td align="center"><a href="docs/screenshots/07-preview.png"><img src="docs/screenshots/07-preview.png" width="170"/></a><br/><sub>Output preview</sub></td>
    <td align="center"><a href="docs/screenshots/08-settings.png"><img src="docs/screenshots/08-settings.png" width="170"/></a><br/><sub>Settings</sub></td>
  </tr>
</table>

</details>

---

## 🏗 Project Structure

```
datagenie/
├── frontend/                        # React 18 + Vite + Tailwind CSS
│   └── src/
│       ├── api/client.js            # API client with fetchWithRetry
│       ├── components/
│       │   ├── Stage1_Upload/       # File upload + schema editor (dog-ear tabs, unique, sensitivity)
│       │   ├── Stage2_Characteristics/  # Volume, variable child counts, ranges, distributions
│       │   ├── Stage3_Compliance/   # Framework detection, per-field masking, custom rules
│       │   ├── Stage4_Relationships/    # Parent→child FK editor (1:N, 1:1, N:N)
│       │   ├── Stage5_Output/       # Format picker, tabbed preview, download
│       │   ├── Profiles/            # Save / load / search named profiles
│       │   ├── Settings/            # LLM provider + compliance feature toggle
│       │   └── common/              # StageIndicator, Spinner, ChipSelector
│       ├── store/appStore.js        # Zustand global state + sortColumnsForDisplay utility
│       └── utils/llmStorage.js     # localStorage: LLM config + app settings
│
├── backend/                         # FastAPI + SQLAlchemy (async)
│   ├── app_config.py                # Centralised env-var config (MAX_VOLUME_RECORDS, etc.)
│   ├── routers/
│   │   ├── schema.py    # POST /infer, GET /demo, POST /normalize-rule
│   │   ├── generate.py  # POST /generate, POST /preview (enforces volume cap)
│   │   ├── profiles.py  # CRUD for saved profiles
│   │   └── settings.py  # LLM settings + test connection
│   ├── prompts/                     # LLM prompt templates (one file per concern)
│   │   ├── extraction.py            # Context extraction system + user prompt
│   │   ├── compliance_domain.py     # Domain framework detection prompt
│   │   ├── compliance_batch.py      # Batch column classification system prompt
│   │   └── masking_normalize.py     # Masking rule normalisation prompt
│   └── services/
│       ├── llm_service.py           # Multi-provider LLM abstraction
│       ├── context_extractor.py     # NL → structured schema params
│       ├── compliance_detector.py   # 211-entry DLP catalog, 8 frameworks, LLM batch
│       ├── data_generator.py        # Faker-based engine: FK integrity, unique constraints, variable child counts
│       ├── starter_templates.py     # 4 domain multi-table + 4 single-table canned schemas + demo dataset
│       ├── output_formatter.py      # CSV/TSV/JSON/JSONL/Excel/XML/YAML/Parquet
│       ├── masking.py               # Plain-English rule → structured MaskingOp
│       ├── schema_inferrer.py       # File-based column type + stats inference
│       └── file_parser.py           # CSV/Excel/JSON/XML/YAML → normalised rows
│
├── docker-compose.yml               # Full stack (postgres + backend + frontend/nginx)
└── nginx.conf                       # Reverse proxy: /api → backend, / → frontend
```

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

### Development (hot reload)

```bash
# Start postgres + backend with hot reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# Frontend with Vite HMR (run separately)
cd frontend && npm install && npm run dev   # → http://localhost:3001
```

Or run natively without Docker:

```bash
# Terminal 1 — backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm install && npm run dev   # → http://localhost:3001
```

The Vite dev server proxies `/api/*` to `http://localhost:8000` automatically.

---

## 🗒 Notes

- **No data leaves your environment** when using Ollama or self-hosting. With cloud providers, only column names and sample values are sent — never full dataset rows.
- **Demo mode** works fully without any API key — the app loads a fixed `jobs → applicants → interviews` demo dataset so every stage can be explored immediately. Schema inference uses rule-based detection with no LLM call.
- **Starter templates** (E-Commerce, Healthcare, HR & Payroll, Banking) are only loaded when a user explicitly picks one from the home screen — they are never silently selected based on what you type in the description box.
- **Compliance is optional** — disable it in Settings to skip sensitivity tagging and the compliance stage entirely.
- Starter card schemas use a dedicated `/api/schema/demo?keyword=` endpoint; the main `/api/schema/infer` endpoint is always used for user-supplied descriptions and uploaded files.
- **Volume cap** — the UI limits root-entity volume to 10,000 records by default to keep generation responsive. Exceeding the limit is blocked both in the UI and server-side. Configure the cap via the `MAX_VOLUME_RECORDS` environment variable (see `docker-compose.yml` or `.env.example`). Child table rows scale with the per-parent multiplier on top of the root cap.

---

## 🔭 Future Capabilities

Features on the roadmap — not yet available but planned as the project grows:

| Capability | Description |
|:-----------|:------------|
| **Composite primary keys** | Tables where the PK spans multiple columns (e.g. `order_id + product_id`). FK resolution would enforce the combined tuple, not just individual columns. |
| **Higher-volume generation** | Server-side streaming or chunked generation to support millions of rows without browser memory constraints. |
| **Circular / self-referential FKs** | Tables with a `parent_id` pointing back to the same table (hierarchies, org charts, category trees). |
| **Many-to-many uniqueness enforcement** | Junction tables where the FK pair `(a_id, b_id)` must be unique across all rows. |
| **Custom data providers** | Plug in domain-specific generators (e.g. realistic product names, medical codes, postal addresses by country) beyond the built-in Faker pool. |
| **Saved profiles with versioning** | Track schema evolution over time and diff two profile versions. |
| **Incremental / delta generation** | Generate only the new rows needed to top up an existing dataset, preserving existing PKs. |
| **SQL DDL export** | Export schema as `CREATE TABLE` DDL alongside the data, with FK constraints and indexes. |
| **Direct database seeding** | Push generated data directly to a connected PostgreSQL / MySQL / SQLite instance instead of downloading a file. |

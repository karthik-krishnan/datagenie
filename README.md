# 🪄 DataGenie — AI Assisted Intelligent Test Data Generator

DataGenie is a full-stack application that generates realistic, compliant synthetic test data from natural language descriptions or uploaded sample files. No real data ever leaves your environment.

## Features

- **Natural language schema inference** — describe your data in plain English ("50 users with name, email, SSN, gender") and DataGenie infers the schema, volume, distributions, and compliance requirements
- **File upload** — upload CSV, JSON, Excel, XML or Parquet files as a schema template
- **Multi-framework compliance** — automatically detects and handles PII, PCI DSS, HIPAA, GDPR, CCPA, SOX, and FERPA fields with configurable masking/redaction
- **Value distributions** — specify exactly how values should be distributed (e.g. 80% Male / 10% Female / 10% Not specified)
- **Relationship mapping** — referential integrity across multiple related tables
- **Multiple output formats** — CSV, JSON, XML with configurable structure and packaging
- **Profile system** — save and reload generation configurations for repeatable datasets
- **Multiple LLM providers** — Anthropic Claude, OpenAI GPT-4, Azure OpenAI, Google Gemini, Ollama (local), or Demo mode (no API key required)

## Quick Start

### Prerequisites
- Docker & Docker Compose

### Run (production mode)

```bash
git clone git@github.com:karthik-krishnan/datagenie.git
cd datagenie
docker-compose up --build
```

Open **http://localhost:3000**

### Run (development mode — hot reload)

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

- Frontend (Vite HMR): **http://localhost:3001**
- Backend API: **http://localhost:8000**
- API docs: **http://localhost:8000/docs**

## Architecture

```
datagenie/
├── frontend/          # React + Vite + Tailwind CSS
│   └── src/
│       ├── components/
│       │   ├── Stage1_Upload/          # File upload & context input
│       │   ├── Stage2_Characteristics/ # Volume & distributions
│       │   ├── Stage3_Compliance/      # Framework selection & masking
│       │   ├── Stage4_Relationships/   # Cross-table relationships
│       │   ├── Stage5_Output/          # Format picker & preview
│       │   ├── Profiles/               # Save/load profiles
│       │   └── Settings/               # LLM provider configuration
│       └── store/                      # Zustand state management
│
├── backend/           # FastAPI + SQLAlchemy (async)
│   ├── routers/       # API endpoints (schema, generate, profiles, settings)
│   └── services/
│       ├── llm_service.py          # Multi-provider LLM abstraction
│       ├── context_extractor.py    # NL → structured params (LLM + regex fallback)
│       ├── compliance_detector.py  # 100+ field catalog, 7 frameworks
│       ├── data_generator.py       # Faker-based synthetic data generation
│       ├── demo_templates.py       # Pre-built schemas for demo mode
│       └── output_formatter.py     # CSV / JSON / XML formatting
│
├── docker-compose.yml      # Production setup
└── docker-compose.dev.yml  # Development overrides (hot reload)
```

## LLM Configuration

Open **Settings (⚙️)** in the app and select your provider:

| Provider | Notes |
|---|---|
| **Anthropic** | Claude Sonnet / Opus — recommended |
| **OpenAI** | GPT-4o / GPT-4 Turbo |
| **Azure OpenAI** | Requires endpoint + deployment name |
| **Google** | Gemini 1.5 Pro / Flash |
| **Ollama** | Local models, no API key needed |
| **Demo** | No API key — uses pre-built sample schemas |

## The Generation Workflow

1. **Upload & Context** — upload sample files and/or describe your data in natural language
2. **Characteristics** — confirm volume and configure value distributions
3. **Compliance** — select applicable regulatory frameworks; DataGenie shows only the fields that need decisions
4. **Relationships** — confirm or edit detected relationships between tables
5. **Output & Preview** — pick format (CSV/JSON/XML), preview rows, then download

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Zustand |
| Backend | FastAPI, SQLAlchemy (async), Uvicorn |
| Database | PostgreSQL 15 |
| Data generation | Faker, pandas |
| Containerisation | Docker, Docker Compose, nginx |

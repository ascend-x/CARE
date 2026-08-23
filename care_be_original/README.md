# CARE EMR — Complete Deployment & Architecture Guide

> **Version**: Dev Stage | **Last Updated**: March 2026  
> This document covers full system deployment, architecture deep-dive, and component documentation for the CARE Electronic Medical Records system.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [System Architecture](#system-architecture)
3. [Backend — Deep Dive](#backend--deep-dive)
4. [Frontend — Deep Dive](#frontend--deep-dive)
5. [How Frontend ↔ Backend Work Together](#how-frontend--backend-work-together)
6. [MedGemma AI Plugin](#medgemma-ai-plugin)
7. [Infrastructure Services](#infrastructure-services)
8. [Deployment Guide — Full Setup](#deployment-guide--full-setup)
9. [Deployment Guide — Dev-Lite (No Redis/Celery)](#deployment-guide--dev-lite-no-rediscelery)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

| Tool        | Version     | Purpose                          |
|-------------|-------------|----------------------------------|
| Docker      | 24+         | Container runtime                |
| Docker Compose | v2+      | Multi-container orchestration    |
| Node.js     | 22+         | Frontend build/dev               |
| npm         | 10+         | Frontend package manager         |
| Git         | 2.x+        | Version control                  |

### Option A: Full Setup (Standard)

```bash
# 1. Clone the repository
git clone <repo-url> CARE && cd CARE

# 2. Start backend (Postgres + Redis + MinIO + Celery + Django)
cd care_be
make up

# 3. Load initial data (admin accounts, fixtures)
make load-fixtures

# 4. Load CARE patient data (Dr. Shivani + Devaganesh + reports → MinIO)
make load-care-fixtures

# 5. Start frontend
cd ../care_fe
npm install
npm run dev
```

- **Backend API**: http://localhost:9000
- **Frontend UI**: http://localhost:4000
- **MinIO Console**: http://localhost:9001 (user: `minioadmin` / pass: `minioadmin`)

### Option B: Dev-Lite Setup (No Redis, No Celery)

```bash
cd care_be
make up-lite          # Starts only: Postgres + MinIO + Backend
make load-fixtures    # Load accounts & seed data
make load-care-fixtures  # Load Dr. Shivani + Devaganesh + 28 reports → MinIO

cd ../care_fe
npm install
npm run dev
```

> **What changes?** Celery tasks execute inline (synchronously). Cache uses in-memory instead of Redis. Fewer containers = ~400MB less RAM.

### Default Login Credentials

| User | Username | Password | Role |
|------|----------|----------|------|
| Admin | `admin` | `admin` | Superuser |
| Doctor | `dr-shivani` | `Coronasafe@123` | Doctor |
| Dev Admin | `devdistrictadmin` | `Coronasafe@123` | District Admin |

### Test Patient

| Field | Value |
|-------|-------|
| Name | Devaganesh S |
| ABHA ID | `91-1234-5678-9012` |
| DOB | 1998-03-15 |
| Blood Group | O+ |
| Reports | 27 PDFs + 1 JPEG (uploaded to MinIO) |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER BROWSER                         │
│                   http://localhost:4000                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/REST (JSON)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    CARE FRONTEND (Vite + React)              │
│  • TailwindCSS + Radix UI components                        │
│  • TanStack React Query (data fetching + caching)           │
│  • Jotai (client state)                                     │
│  • Raviger (routing)                                        │
│  • i18next (internationalization)                           │
└──────────────────────────┬──────────────────────────────────┘
                           │ API calls to /api/v1/*
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              CARE BACKEND (Django REST Framework)            │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐         │
│  │  care.emr     │  │ care.    │  │ care.         │         │
│  │  (Clinical)   │  │ users    │  │ facility      │         │
│  ├──────────────┤  ├──────────┤  ├───────────────┤         │
│  │  care.        │  │ care.    │  │ Plugins       │         │
│  │  security     │  │ audit_log│  │ (MedGemma)    │         │
│  └──────────────┘  └──────────┘  └───────────────┘         │
│  Auth: JWT (SimpleJWT) + OIDC (JWKS)                        │
│  Permissions: Role-based (CareAuthentication)               │
└────┬──────────────┬──────────────┬──────────────────────────┘
     │              │              │
     ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐
│ Postgres │  │  Redis   │  │   MinIO    │  │ Celery   │
│ (DB)     │  │ (Cache/  │  │   (S3)     │  │ (Async   │
│ :5433    │  │  Broker) │  │ :9100/:9001│  │  Tasks)  │
│          │  │ :6380    │  │            │  │          │
└─────────┘  └──────────┘  └────────────┘  └──────────┘
```

### Data Flow Summary

1. **User** loads the React app from Vite dev server (`:4000`)
2. **Frontend** authenticates via `/api/v1/auth/login/` → receives JWT token pair
3. **Frontend** makes REST API calls with `Authorization: Bearer <token>`
4. **Backend** validates JWT, checks role permissions, processes request
5. **Backend** reads/writes to **Postgres** for data persistence
6. **Backend** uses **Redis** for caching (sessions, rate limiting, locks)
7. **Backend** uses **MinIO** for file/image storage (patient documents, facility images)
8. **Backend** uses **Celery** for async tasks (report generation, cleanup, email)

---

## Backend — Deep Dive

### Technology Stack

| Component           | Technology                              |
|--------------------|-----------------------------------------|
| Framework          | Django 5.x + Django REST Framework      |
| Database           | PostgreSQL 16 (Alpine)                  |
| Cache/Broker       | Redis 8 (Alpine)                        |
| Object Storage     | MinIO (S3-compatible)                   |
| Task Queue         | Celery 5.x                             |
| Auth               | SimpleJWT + OIDC (JWKS)                |
| API Docs           | drf-spectacular (OpenAPI 3.0)           |
| Password Hashing   | Argon2id                               |
| Python Runtime     | 3.13 (slim-bookworm)                   |

### Django Apps

#### `care.emr` — Electronic Medical Records (Core)

The primary clinical data module. Contains:

- **Patient management** — registration, demographics, identifiers
- **Encounters** — clinical visits, admissions, discharges
- **Observations** — vitals, lab results, clinical measurements
- **Medications** — prescriptions, dispensing, drug interactions
- **Appointments** — scheduling, token management, queues
- **Questionnaires** — dynamic clinical forms (FHIR-compatible)
- **File uploads** — patient documents, scans, reports (via MinIO)
- **Resource categories** — SNOMED CT value sets
- **Billing** — invoices, payments, tax configuration

Key models: `Patient`, `Encounter`, `Observation`, `Medication`, `Appointment`, `Questionnaire`, `FileUpload`

#### `care.users` — User Management

- User accounts with role-based access (Doctor, Nurse, Admin, State Admin, etc.)
- Password management with Argon2 hashing
- TOTP-based 2FA (Two-Factor Authentication)
- OTP-based patient login
- User-facility assignments

#### `care.facility` — Healthcare Facility Management

- Facility registration and metadata
- Location hierarchy (wards, beds, rooms)
- Organization structure (departments, teams)
- Facility-level settings and configuration

#### `care.security` — Permission & Access Control

- Role-based permission system (`CareAuthentication`)
- Permission matrix syncing (`sync_permissions_roles`)
- Fine-grained object-level access control
- Security middleware

#### `care.audit_log` — Audit Logging

- Tracks all data mutations for compliance
- Model-level change tracking
- Configurable inclusion/exclusion rules
- Patient data field masking

### Celery Tasks (Background Processing)

| Task                                | Module                              | Purpose                                    |
|-------------------------------------|-------------------------------------|--------------------------------------------|
| `sync_valueset`                     | `care.emr.models.resource_category` | Sync SNOMED CT value sets                  |
| `report_generation`                 | `care.emr.tasks.report_generation`  | Generate patient reports                   |
| `cleanup_incomplete_file_uploads`   | `care.emr.tasks.cleanup_*`          | Remove stale uploads after 24h             |
| `cleanup_expired_token_slots`       | `care.emr.tasks.cleanup_*`          | Clean expired appointment tokens           |
| `send_totp_email`/`send_totp_sms`  | `care.emr.tasks.totp`               | Deliver 2FA codes                          |
| `expire_consents` (plugin)         | `care_medgemma.tasks`               | Mark expired consent records               |
| `run_medgemma_analysis` (plugin)   | `care_medgemma.tasks`               | Async AI analysis                          |

> **Dev-Lite Mode**: All tasks execute inline via `CELERY_TASK_ALWAYS_EAGER=True`.

### Plugin System

Plugins are installable Django apps registered via `plug_config.py`:

```python
# care_be/plug_config.py
from plugs.manager import PlugManager
plugs = []                        # Add Plug(...) entries here
manager = PlugManager(plugs)
```

Plugins are installed via `ADDITIONAL_PLUGS` build arg in Docker. The `install_plugins.py` script handles pip installation.

### Middleware Stack (Request Processing Order)

1. `SecurityMiddleware` — HTTPS enforcement, HSTS
2. `CorsMiddleware` — Cross-origin request handling
3. `WhiteNoiseMiddleware` — Static file serving
4. `SessionMiddleware` — Session management
5. `LocaleMiddleware` — Language detection
6. `CommonMiddleware` — URL normalization
7. `CsrfViewMiddleware` — CSRF protection
8. `AuthenticationMiddleware` — User authentication
9. `MessageMiddleware` — Flash messages
10. `BrokenLinkEmailsMiddleware` — 404 notifications
11. `XFrameOptionsMiddleware` — Clickjacking protection
12. `MaintenanceModeMiddleware` — Maintenance page
13. `AuditLogMiddleware` — Request/response audit logging

### Authentication Flow

```
Login Request → /api/v1/auth/login/
    ↓
CustomJWTAuthentication validates credentials
    ↓
SimpleJWT generates token pair:
  • Access Token (10 min TTL)
  • Refresh Token (30 min TTL, rotated)
    ↓
Frontend stores tokens, sends via Authorization header
    ↓
On expiry: POST /api/v1/auth/token/refresh/
    ↓
OIDC/JWKS also supported for federated identity
```

### Key Configuration Files

| File                            | Purpose                                     |
|--------------------------------|---------------------------------------------|
| `config/settings/base.py`      | Core Django settings (DB, cache, auth, etc.)|
| `config/settings/local.py`     | Development overrides                       |
| `config/settings/deployment.py`| Production/staging settings                 |
| `config/settings/test.py`      | Test runner settings                        |
| `config/celery_app.py`         | Celery configuration                        |
| `config/api_router.py`         | REST API URL routing (16KB!)                |
| `config/authentication.py`     | Custom JWT + Basic auth classes             |
| `config/caches.py`             | Custom cache backends (LocMemCache)         |
| `docker/.local.env`            | Docker dev environment variables            |
| `docker/.dev-lite.env`         | Docker dev-lite env (no Redis/Celery)       |

---

## Frontend — Deep Dive

### Technology Stack

| Component          | Technology                           |
|-------------------|--------------------------------------|
| Framework         | React 19 + TypeScript                |
| Build Tool        | Vite 6                              |
| Styling           | TailwindCSS 4 + Radix UI            |
| State Management  | Jotai (client) + TanStack React Query (server) |
| Routing           | Raviger                             |
| Forms             | React Hook Form + Zod validation    |
| Charts            | Recharts                            |
| i18n              | i18next (en, hi, ta, ml, mr, kn)    |
| Animations        | Framer Motion                        |
| PDF               | react-pdf + jsPDF                    |
| Testing           | Playwright (E2E)                     |

### Source Structure

```
care_fe/src/
├── App.tsx                 # Root component with providers
├── index.tsx               # Entry point, mounts React app
├── components/             # Feature components
│   ├── Auth/               # Login, password reset
│   ├── Billing/            # Invoices, payments
│   ├── Encounter/          # Clinical encounters
│   ├── Facility/           # Facility management
│   ├── Medication/         # Prescriptions
│   ├── Patient/            # Patient management
│   ├── Questionnaire/      # Dynamic forms
│   ├── Schedule/           # Appointments
│   ├── Users/              # User management
│   ├── ui/                 # Shared UI primitives (Radix-based)
│   └── ...                 # 20+ feature modules
├── Routers/                # Route definitions
├── hooks/                  # Custom React hooks
├── types/                  # TypeScript type definitions
├── Providers/              # Context providers
├── Integrations/           # External service integrations
├── Utils/                  # Utility functions
├── style/                  # Global CSS
├── Locale/                 # Translation files
└── config/                 # App configuration
```

### Key Frontend Patterns

**Data Fetching**: All API calls go through TanStack React Query:
```typescript
// Automatic caching, deduplication, background refetching
const { data } = useQuery({
  queryKey: ["patient", patientId],
  queryFn: () => api.getPatient(patientId),
});
```

**State Management**: Client state via Jotai atoms, server state via React Query.

**Component Pattern**: Radix UI primitives + TailwindCSS + class-variance-authority (CVA) for variant-based styling.

**Plugin System**: Frontend supports remote micro-frontends via `@originjs/vite-plugin-federation`. Plugins are registered via `REACT_ENABLED_APPS` env var.

### Key Configuration

| File               | Purpose                                          |
|-------------------|--------------------------------------------------|
| `care.config.ts`  | Central app configuration (reads env vars)       |
| `.env`            | Environment variables (API URL, features, etc.)  |
| `vite.config.mts` | Vite build config (plugins, proxy, etc.)         |
| `tailwind.config.js` | TailwindCSS theme customization               |
| `package.json`    | Dependencies and scripts                         |

### Important Environment Variables

| Variable               | Default                | Purpose                          |
|------------------------|------------------------|----------------------------------|
| `REACT_CARE_API_URL`   | `http://localhost:9000`| Backend API base URL             |
| `REACT_RECAPTCHA_SITE_KEY` | (empty)           | Google reCAPTCHA for login       |
| `REACT_ENABLED_APPS`   | (empty)               | Remote plugin apps               |
| `REACT_ALLOWED_LOCALES`| `en,hi,ta,ml,mr,kn`   | Available languages              |

---

## How Frontend ↔ Backend Work Together

### API Contract

The frontend communicates with the backend exclusively through REST API endpoints under `/api/v1/`. The backend exposes a comprehensive API defined in `config/api_router.py`.

```
Frontend (React)                     Backend (Django)
     │                                    │
     │──── POST /api/v1/auth/login/ ────→│ Returns JWT tokens
     │←── { access, refresh } ──────────│
     │                                    │
     │──── GET /api/v1/patient/ ────────→│ List patients
     │     Authorization: Bearer <jwt>    │ (paginated, filtered)
     │←── { results: [...], count } ────│
     │                                    │
     │──── POST /api/v1/encounter/ ─────→│ Create encounter
     │←── { id, external_id, ... } ─────│
     │                                    │
     │──── PUT /api/v1/.../upload/ ─────→│ Get presigned URL
     │     (file metadata)                │
     │←── { presigned_url } ────────────│
     │                                    │
     │──── PUT presigned_url ───────────→│ Direct to MinIO
     │     (file binary)                  │ (S3-compatible)
```

### Authentication Flow (JWT)

1. User enters credentials in the React login form
2. Frontend POSTs to `/api/v1/auth/login/`
3. Backend validates credentials, generates JWT pair (access + refresh)
4. Frontend stores tokens in memory (Jotai atom)
5. Every API request includes `Authorization: Bearer <access_token>`
6. When access token expires (10 min), frontend auto-refreshes via `/api/v1/auth/token/refresh/`
7. If refresh token also expired (30 min), user is redirected to login

### File Uploads (MinIO Flow)

1. Frontend requests a pre-signed upload URL from backend
2. Backend generates a pre-signed S3 URL (MinIO)
3. Frontend uploads the file directly to MinIO using the pre-signed URL
4. Backend records the file reference in Postgres
5. For downloads, backend generates a pre-signed download URL

### CORS Configuration

- **Dev mode**: `CORS_ORIGIN_ALLOW_ALL = True` (set in `local.py`)
- **Production**: Configure `CORS_ALLOWED_ORIGINS` or `CORS_ALLOWED_ORIGIN_REGEXES`

### Pagination

Backend uses `CareLimitOffsetPagination` (default page size: 14). Frontend uses React Query's pagination hooks for infinite scroll or page-based navigation.

---

## MedGemma AI Plugin

The `care_medgemma` plugin adds AI-powered clinical analysis to CARE.

### Architecture

```
care_medgemma/
├── __init__.py
├── apps.py              # Django app configuration
├── admin.py             # Admin panel registration
├── settings.py          # Plugin settings (MEDGEMMA_MOCK_MODE, etc.)
├── urls.py              # REST API router
├── tasks.py             # Celery tasks (consent expiry, async analysis)
├── fhir_utils.py        # FHIR R5 bundle generation
├── mock_medgemma.py     # Mock analysis engine
├── real_medgemma.py     # Real Ollama/MedGemma integration
├── models/
│   ├── medgemma.py      # MedGemmaAnalysis model
│   ├── consent.py       # ConsentRecord model
│   └── audit_log.py     # AuditLogEntry model
├── serializers/
│   └── medgemma.py      # Request/response serializers
└── viewsets/
    ├── medgemma.py      # AI analysis endpoints (ABHA → MinIO → Ollama)
    ├── fhir_export.py   # FHIR R5 data export
    ├── consent.py       # Patient consent management
    └── audit_log.py     # Audit trail viewing
```

### ABHA → MinIO → MedGemma Pipeline

The main analysis pipeline works as follows:

```
  User enters ABHA ID (91-1234-5678-9012)
       │
       ▼
  _resolve_patient()  →  Lookup by ABHA / UUID / Name
       │
       ▼
  _pull_patient_files()  →  Query FileUpload records
       │                     Download from MinIO (S3)
       ▼
  _extract_text_from_pdf()  →  PyPDF2 text extraction
  base64 encode images      →  Image encoding
       │
       ▼
  Build Ollama prompt  →  System prompt (preset) +
       │                   Patient info + All file contents
       ▼
  Ollama /api/chat  →  Local AI inference (no cloud egress)
       │
       ▼
  Structured response  →  Parse into summary, flags,
                           findings, SOAP, trends, etc.
```

**Supported file types for analysis:**
- Documents: PDF, TXT, CSV, DOC, XLS, XLSX, RTF, ODT
- Images: JPEG, PNG, GIF, BMP, WebP, TIFF
- All file types are handled — unknown types are read as text

### How to Test MedGemma

```bash
# 1. Ensure fixtures are loaded
cd care_be
make load-fixtures
make load-care-fixtures    # Uploads 28 patient reports to MinIO

# 2. Open MedGemma in browser
# http://localhost:4000/medgemma

# 3. Enter ABHA ID: 91-1234-5678-9012
# 4. Select a preset (e.g., Comprehensive)
# 5. Click "Run Analysis"
```

The system will pull all 28 reports from MinIO, extract text from PDFs, and feed everything to the AI engine.

### API Endpoints

| Endpoint                                 | Method | Purpose                           |
|------------------------------------------|--------|-----------------------------------|
| `/api/v1/medgemma/`                      | GET    | List analysis records             |
| `/api/v1/medgemma/{id}/`                 | GET    | Retrieve analysis details         |
| `/api/v1/medgemma/analyze/`              | POST   | Submit data for AI analysis       |
| `/api/v1/fhir/export/{patient_id}/`      | GET    | Export patient data as FHIR R5    |
| `/api/v1/consent/`                       | GET/POST| Manage patient consent records   |
| `/api/v1/audit/`                         | GET    | View audit log                    |

### Analyze Request Body

```json
{
  "analysis_type": "comprehensive",
  "patient_id": "91-1234-5678-9012",
  "preset": "comprehensive",
  "encounter_id": "",
  "input_data": {}
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `analysis_type` | Yes | One of: `comprehensive`, `summary`, `critical`, `timeline`, `report_summary`, `trend_analysis`, `ddi_check`, `differential_diagnosis`, `soap_autofill` |
| `patient_id` | No | ABHA ID, patient UUID, or patient name. Triggers MinIO file pull. |
| `preset` | No | Overrides the prompt template. Options: `comprehensive`, `summary`, `critical`, `timeline` |
| `encounter_id` | No | Links analysis to a specific clinical encounter |
| `input_data` | No | Additional JSON clinical data to include in analysis |

### Analysis Types

| Type                  | Description                                        |
|-----------------------|----------------------------------------------------|
| `comprehensive`       | Full clinical analysis with ICD codes & care plan   |
| `summary`             | Quick high-level clinical overview                  |
| `critical`            | Red flags, contraindications, emergency action plan |
| `timeline`            | Chronological medical history extraction            |
| `report_summary`      | Structured lab report analysis                      |
| `trend_analysis`      | Longitudinal parameter trending                     |
| `ddi_check`           | Drug-drug interaction check                         |
| `differential_diagnosis` | Differential diagnosis suggestions               |
| `soap_autofill`       | SOAP note auto-generation                           |

### Mock vs Real Mode

- **`MEDGEMMA_MOCK_MODE=True`** (default): Returns hardcoded clinical analysis. No external dependencies.
- **`MEDGEMMA_MOCK_MODE=False`**: Connects to local Ollama server running MedGemma/CareAnalyzer model. Responses come from local AI inference — **no cloud egress**, fully private pipeline.

### MedGemma Environment Variables

| Variable | Default | Purpose |
|----------|---------|--------|
| `MEDGEMMA_MOCK_MODE` | `True` | Use mock or real Ollama engine |
| `MEDGEMMA_OLLAMA_HOST` | `http://172.19.127.189:11434/api/chat` | Ollama server URL |
| `MEDGEMMA_OLLAMA_MODEL` | `CareAnalyzer` | Ollama model name |
| `MEDGEMMA_REQUEST_TIMEOUT` | `120` | Ollama request timeout (seconds) |

---

## Infrastructure Services

### PostgreSQL (Database)

- **Image**: `postgres:alpine`
- **Port**: `5433` (host) → `5432` (container)
- **Data Volume**: `postgres-data` (named Docker volume)
- **Default Credentials**: `postgres` / `postgres` / `care`

### Redis (Cache + Message Broker)

- **Image**: `redis:8-alpine`
- **Port**: `6380` (host) → `6379` (container)
- **Data Volume**: `redis-data`
- **Used By**: Django cache, Celery broker, rate limiting, distributed locks
- **Dev-Lite**: Not used — replaced by LocMemCache + eager Celery

### MinIO (S3-Compatible Object Storage)

- **Image**: `minio/minio:latest`
- **Ports**: `9100` (S3 API), `9001` (Web Console)
- **Credentials**: `minioadmin` / `minioadmin`
- **Buckets**: `patient-bucket` (uploads), `facility-bucket` (facility assets)

### Celery (Async Task Worker)

- **Image**: Same as backend (`care_local`)
- **Script**: `scripts/celery-dev.sh`
- **Includes**: Worker + Beat (periodic task scheduler)
- **Monitors**: Auto-restart on code changes via `watchmedo`
- **Dev-Lite**: Not used — tasks execute inline

---

## Deployment Guide — Full Setup

### 1. Prerequisites

```bash
# Verify Docker
docker --version    # Must be 24+
docker compose version  # Must be v2+

# Verify Node.js
node --version      # Must be 22+
npm --version       # Must be 10+
```

### 2. Backend Setup

```bash
cd care_be

# Copy environment files (optional — Docker uses docker/.local.env)
cp .env.example .env

# Build and start all services
make build          # Build Docker images
make up             # Start: db + redis + minio + celery + backend

# Wait for health checks to pass (~30s)
make list           # Shows container status

# Run database migrations and load seed data
make load-fixtures       # Creates admin account (admin/admin)
make load-care-fixtures  # Creates Dr. Shivani + Devaganesh + uploads 28 reports to MinIO
```

### 3. Frontend Setup

```bash
cd care_fe

# Install dependencies
npm install

# Start dev server
npm run dev
```

The dev server starts at http://localhost:4000. It proxies API requests to http://localhost:9000 (configured in `.env`).

### 4. Login

- **URL**: http://localhost:4000
- **Doctor**: `dr-shivani` / `Coronasafe@123`
- **Admin**: `devdistrictadmin` / `Coronasafe@123`

### 5. Test MedGemma (AI Analysis)

```bash
# Navigate to: http://localhost:4000/medgemma
# Enter ABHA ID: 91-1234-5678-9012
# Select "Comprehensive" → Click "Run Analysis"
# System pulls 28 patient reports from MinIO → AI analysis
```

### 6. Verify

```bash
# Backend health
curl http://localhost:9000/ping/

# Check services
cd care_be && make list
```

---

## Deployment Guide — Dev-Lite (No Redis/Celery)

This mode removes Redis and Celery containers, reducing resource usage by ~400MB RAM.

### How It Works

| Standard Mode            | Dev-Lite Mode                         |
|--------------------------|---------------------------------------|
| Redis for caching        | Django LocMemCache (in-process)       |
| Redis as Celery broker   | Celery `ALWAYS_EAGER` (inline tasks)  |
| Celery worker container  | No separate container                 |
| 5 containers total       | 3 containers total                    |

### Setup

```bash
cd care_be

# Build (same image, first time only)
make build

# Start in dev-lite mode
make up-lite        # Starts: db + minio + backend (no redis, no celery)

# Load seed data (migrations run automatically in start-dev-lite.sh)
make load-fixtures
make load-care-fixtures  # Dr. Shivani + Devaganesh + 28 reports → MinIO

# Frontend (same as standard)
cd ../care_fe
npm install
npm run dev
```

### Switching Between Modes

```bash
# Stop lite mode
make down-lite

# Start standard mode
make up

# Or vice versa
make down
make up-lite
```

### Limitations of Dev-Lite Mode

- **No real caching**: LocMemCache doesn't persist across server restarts
- **No distributed locking**: Concurrent request coordination is limited
- **Synchronous tasks**: Long-running Celery tasks block the request until complete
- **No periodic tasks**: Celery Beat doesn't run — scheduled cleanup tasks won't execute automatically

> For development and testing, these limitations are generally acceptable.

---

## Troubleshooting

### Backend won't start

```bash
# Check logs
cd care_be
docker compose -f docker-compose.yaml -f docker-compose.dev-lite.yaml logs backend

# Common: Database not ready
# Fix: The start script waits for DB, but if timing out, restart:
make down-lite && make up-lite
```

### Frontend can't connect to API

```bash
# Verify backend is running
curl http://localhost:9000/ping/

# Check .env in care_fe
cat care_fe/.env | grep REACT_CARE_API_URL
# Must be: http://localhost:9000
```

### MinIO buckets not created

```bash
# MinIO auto-creates buckets on first start via entrypoint.sh
# If buckets are missing, restart minio:
docker compose restart minio
```

### Port conflicts

| Service   | Default Port | Alternative                              |
|-----------|-------------|------------------------------------------|
| Backend   | 9000        | Change in `docker-compose.dev-lite.yaml` |
| Postgres  | 5433        | Change in `docker-compose.yaml`          |
| Redis     | 6380        | N/A in dev-lite                          |
| MinIO API | 9100        | Change in `docker-compose.yaml`          |
| MinIO UI  | 9001        | Change in `docker-compose.yaml`          |
| Frontend  | 4000        | `npm run dev -- --port 3000`             |

### Reset everything

```bash
cd care_be
make teardown       # Remove all containers AND volumes
make build          # Rebuild images
make up             # or make up-lite
make load-fixtures  # Re-seed data
make load-care-fixtures  # Re-load Dr. Shivani + Devaganesh + reports
```

### Makefile Reference

| Command | Description |
|---------|-------------|
| `make up` | Start full stack (db + redis + minio + celery + backend) |
| `make up-lite` | Start dev-lite (db + minio + backend, no Redis/Celery) |
| `make down` | Stop full stack |
| `make down-lite` | Stop dev-lite stack |
| `make build` | Build Docker images |
| `make load-fixtures` | Load base seed data (admin, roles, questionnaires) |
| `make load-care-fixtures` | Load Dr. Shivani + patient Devaganesh + 28 reports → MinIO |
| `make list` | Show running container status |
| `make teardown` | Remove all containers AND volumes (full reset) |
| `make logs` | Tail container logs |

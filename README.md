# AI Reconciliation Worker

> AI-assisted reconciliation worker for payment gateway, bank, and invoice data.  
> **AI prepares the reconciliation. Finance users approve only the exceptions.**

## What it does

Connects Stripe, Razorpay, Chargebee, bank statements, and invoice exports.  
Normalizes messy data, matches records deterministically, explains exceptions with AI, and produces an accountant-ready XLSX report.

```
Auth → Upload → Parse → Map → Normalize → Reconcile → Explain → Review → Export
```

---

## Tech Stack

| Concern | Technology |
|---|---|
| Language | Python 3.11+ |
| API | FastAPI |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Database | PostgreSQL 16 |
| Queue | Redis + RQ |
| Parsing | pandas + openpyxl |
| Validation | Pydantic v2 |
| Storage | LocalStack (local) / AWS S3 (prod) |
| Auth | Google OAuth + JWT |
| AI | Anthropic Claude |
| Testing | pytest |

---

## Local Setup

### Prerequisites

- Docker + Docker Compose
- Python 3.11+
- `make`

### 1. Clone and configure

```bash
git clone <repo>
cd recon

# Copy env file and configure
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY, optionally GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
```

### 2. Install Python dependencies (for local dev outside Docker)

```bash
pip install -e ".[dev]"
```

### 3. First-time setup (start services + migrate + create bucket)

```bash
make setup
```

This runs:
1. `docker compose up -d` (postgres, redis, localstack, backend)
2. `alembic upgrade head` (run migrations)
3. `python scripts/create_localstack_bucket.py` (create S3 bucket)

### 4. Verify health

```bash
curl http://localhost:8000/health
# → {"status": "ok", "service": "ai-reconciliation-worker"}

curl http://localhost:8000/ready
# → {"status": "ready", "checks": {"database": true, "redis": true, "storage": true}}
```

### 5. API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Common Commands

```bash
make up             # Start all Docker services
make down           # Stop all services
make logs           # Follow all logs
make migrate        # Run pending migrations
make migrate-new MSG="add column"  # Create new migration
make test           # Run all tests
make test-unit      # Unit tests only
make lint           # Lint with ruff
make dev            # Run API server locally (no Docker)
make demo-load      # Load sample data
make demo-run       # Run sample reconciliation
```

---

## Development Login (Local Only)

When `APP_ENV=local`, a dev-login endpoint is available (no Google OAuth needed):

```bash
POST http://localhost:8000/api/auth/dev-login
Content-Type: application/json

{
  "email": "dev@example.com",
  "full_name": "Dev User"
}
```

Returns a JWT token you can use in `Authorization: Bearer <token>` headers.

---

## Project Structure

```
recon/
├── docker-compose.yml           # Postgres, Redis, LocalStack, Backend
├── Makefile                     # Dev commands
├── .env.example                 # Environment variables template
├── pyproject.toml               # Python project config
├── samples/                     # Sample CSV/XLSX files for demo
│   ├── stripe/
│   ├── razorpay/
│   ├── chargebee/
│   ├── bank/
│   └── invoices/
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── alembic.ini
    ├── alembic/                 # Database migrations
    └── app/
        ├── main.py              # FastAPI app
        ├── config.py            # Settings
        ├── database.py          # DB engine
        ├── dependencies.py      # FastAPI dependencies
        ├── core/                # JWT, errors, money, dates, security
        ├── auth/                # Google OAuth, CurrentUserContext
        ├── api/                 # Routes
        ├── domain/              # Enums, models, schemas, repos, services
        ├── integrations/        # S3, parsers, payment provider clients
        ├── ai/                  # Anthropic AI layer
        ├── workers/             # Redis + RQ background jobs
        ├── seed/                # Sample data loader
        └── tests/               # Unit + integration tests
```

---

## API Endpoints

### Health
```
GET  /health          # Liveness
GET  /ready           # Readiness (DB + Redis + S3)
```

### Auth
```
GET  /api/auth/google/login      # Redirect to Google OAuth
GET  /api/auth/google/callback   # OAuth callback
POST /api/auth/logout
GET  /api/auth/me
POST /api/auth/dev-login         # LOCAL ONLY
```

### Workspaces
```
GET   /api/workspaces
POST  /api/workspaces
GET   /api/workspaces/{id}
GET   /api/workspaces/{id}/members
POST  /api/workspaces/{id}/members/invite
```

### Upload & Parse
```
POST   /api/uploads                      # Upload CSV/XLSX
GET    /api/uploads                      # List uploads
GET    /api/uploads/{id}                 # Get upload details
GET    /api/uploads/{id}/preview         # Preview parsed rows
DELETE /api/uploads/{id}
```

### Column Mapping & Normalization
```
POST /api/uploads/{id}/suggest-mapping   # AI-suggested mapping
GET  /api/uploads/{id}/mapping
PUT  /api/uploads/{id}/mapping
POST /api/uploads/{id}/normalize
```

### Reconciliation
```
POST /api/reconciliation-runs
GET  /api/reconciliation-runs
GET  /api/reconciliation-runs/{id}
POST /api/reconciliation-runs/{id}/run
GET  /api/reconciliation-runs/{id}/summary
GET  /api/reconciliation-runs/{id}/matches
GET  /api/reconciliation-runs/{id}/exceptions
```

### Review
```
POST /api/matches/{id}/approve
POST /api/matches/{id}/reject
GET  /api/exceptions/{id}
POST /api/exceptions/{id}/explain
POST /api/exceptions/{id}/resolve
POST /api/exceptions/{id}/ignore
POST /api/exceptions/{id}/note
```

### Export
```
POST /api/reconciliation-runs/{id}/export
GET  /api/exports/{id}
GET  /api/exports/{id}/download
```

### Demo
```
POST /api/demo/load-sample-data
POST /api/demo/run-sample-reconciliation
GET  /api/demo/status
```

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `JWT_SECRET_KEY` | JWT signing key (change in production) |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `S3_ENDPOINT_URL` | LocalStack endpoint (local) or AWS S3 (prod) |
| `S3_BUCKET_NAME` | Storage bucket name |

---

## Testing

```bash
make test           # All tests
make test-unit      # Unit tests (money, dates, parsing, matching logic)
make test-cov       # With coverage report
```

---

## Deployment (Production)

| Local | Production |
|---|---|
| LocalStack S3 | AWS S3 / Cloudflare R2 |
| Local Postgres | Neon / Supabase / RDS |
| Local Redis | Upstash / Managed Redis |
| Local FastAPI | Render / Railway / Fly.io / ECS |

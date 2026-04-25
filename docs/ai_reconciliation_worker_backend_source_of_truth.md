# AI Reconciliation Worker — Backend Engineering Source of Truth

**Document type:** Engineering implementation guide  
**Audience:** Antigravity / AI coding agent / backend developer  
**Goal:** Build a clean, backend-first MVP that is demo-ready, extensible, and not over-engineered.  
**Product promise:** AI prepares reconciliation. Finance users approve exceptions.  
**Current priority:** Backend only. Frontend comes later.

---

## 1. Product Architecture Summary

The MVP must support this exact workflow:

```text
Google Login / Signup
        ↓
User + Workspace Context
        ↓
Upload CSV/XLSX files
        ↓
Store file in LocalStack S3
        ↓
Parse rows into source_records
        ↓
AI-assisted column mapping
        ↓
Manual mapping fallback
        ↓
Normalize into canonical records
        ↓
Run deterministic reconciliation
        ↓
Generate matches + exceptions
        ↓
AI explains exceptions
        ↓
User reviews / approves / rejects
        ↓
Export XLSX reconciliation report
```

### Core business outcome

A finance/accounting user should upload Stripe, Razorpay, Chargebee, bank, and invoice files and receive:

- matched records
- unmatched records
- exception report
- source evidence
- accountant summary
- downloadable XLSX report

### Product boundary

This is **not**:

- an accounting platform
- a full ledger
- a tax filing tool
- a billing system
- a dashboard-only product
- a Chargebee replacement
- a payment gateway

This is:

> **An AI-assisted reconciliation worker across payment, billing, bank, and invoice data.**

---

## 2. Non-Negotiable Engineering Rules

### Build only this MVP flow first

```text
Auth → Upload → Parse → Map → Normalize → Reconcile → Review → Export
```

### Do not build now

Avoid these until the MVP is working:

- frontend dashboard
- advanced analytics
- OCR/scanned PDF processing
- direct bank APIs
- accounting write-back
- GST/tax filing
- journal posting
- SAP/NetSuite integration
- SSO/SAML
- complex RBAC
- AI chat assistant
- workflow builder
- generic accounting features

### Architecture rules

1. API routes must be thin.
2. Business logic must live in services.
3. Reconciliation logic must be deterministic first.
4. AI must be isolated under `app/ai`.
5. Do not send full files to LLMs.
6. Every business query must be workspace-scoped.
7. Every core table must have audit columns.
8. Money must use `Decimal`, never `float`.
9. Financial outputs must have evidence.
10. Ambiguous matches require human approval.

---

## 3. Tech Stack

### Backend stack

| Concern | Technology |
|---|---|
| Language | Python 3.11+ |
| API framework | FastAPI |
| ORM | SQLAlchemy 2.x |
| DB migrations | Alembic |
| Database | PostgreSQL |
| Queue | Redis + RQ |
| File parsing | pandas + openpyxl |
| Validation | Pydantic v2 |
| Storage | S3-compatible storage |
| Local storage emulator | LocalStack |
| Auth | Google OAuth first |
| Token | JWT access token |
| Testing | pytest |
| Logging | Python logging / structlog optional |
| API docs | FastAPI OpenAPI / Swagger |

### Local development stack

Use Docker Compose:

```text
backend-api
postgres
redis
localstack
```

### LocalStack usage

Use LocalStack for local S3-compatible object storage.

Local bucket:

```text
recon-worker-local-files
```

### Future production equivalents

| Local | Production |
|---|---|
| LocalStack S3 | AWS S3 / Cloudflare R2 |
| local Postgres | Neon / Supabase / RDS |
| local Redis | Upstash / managed Redis |
| local FastAPI | Render / Railway / Fly.io / ECS |

---

## 4. Complete Repository Structure

Use this exact backend-first structure.

```text
ai-reconciliation-worker/
  README.md
  .env.example
  docker-compose.yml
  Makefile
  pyproject.toml

  samples/
    stripe/
      stripe_payout_report_sample.csv
    razorpay/
      razorpay_settlement_report_sample.csv
    chargebee/
      chargebee_invoices_sample.csv
      chargebee_transactions_sample.csv
    bank/
      bank_statement_sample.csv
    invoices/
      invoice_export_sample.csv

  backend/
    README.md
    alembic.ini

    alembic/
      env.py
      script.py.mako
      versions/
        0001_create_auth_workspace_tables.py
        0002_create_file_ingestion_tables.py
        0003_create_canonical_record_tables.py
        0004_create_reconciliation_tables.py
        0005_create_integration_tables.py

    app/
      __init__.py
      main.py
      config.py
      logging_config.py
      database.py
      dependencies.py

      core/
        __init__.py
        security.py
        jwt.py
        errors.py
        pagination.py
        money.py
        dates.py
        constants.py

      auth/
        __init__.py
        google_oauth.py
        current_user.py
        auth_service.py
        auth_schemas.py

      api/
        __init__.py
        router.py

        routes/
          __init__.py
          auth_routes.py
          workspace_routes.py
          upload_routes.py
          column_mapping_routes.py
          normalization_routes.py
          reconciliation_routes.py
          match_routes.py
          exception_routes.py
          export_routes.py
          demo_routes.py
          health_routes.py

      domain/
        __init__.py

        enums/
          __init__.py
          auth_enums.py
          file_enums.py
          mapping_enums.py
          provider_enums.py
          reconciliation_enums.py
          exception_enums.py
          export_enums.py
          integration_enums.py
          audit_enums.py

        models/
          __init__.py
          base.py
          user.py
          workspace.py
          workspace_member.py
          user_session.py
          audit_event.py

          uploaded_file.py
          source_record.py
          column_mapping.py

          payment_record.py
          settlement_record.py
          bank_record.py
          invoice_record.py
          billing_transaction_record.py

          reconciliation_run.py
          reconciliation_run_file.py
          match_candidate.py
          exception_item.py
          review_action.py
          export_job.py

          integration_connection.py
          integration_credential.py
          integration_sync_run.py

        schemas/
          __init__.py
          common_schemas.py
          auth_schemas.py
          workspace_schemas.py
          upload_schemas.py
          mapping_schemas.py
          normalization_schemas.py
          reconciliation_schemas.py
          match_schemas.py
          exception_schemas.py
          export_schemas.py
          demo_schemas.py

        repositories/
          __init__.py
          user_repository.py
          workspace_repository.py
          uploaded_file_repository.py
          source_record_repository.py
          column_mapping_repository.py
          canonical_record_repository.py
          reconciliation_repository.py
          exception_repository.py
          export_repository.py
          audit_repository.py

        services/
          __init__.py
          workspace_service.py
          audit_service.py
          file_storage_service.py
          file_ingestion_service.py
          parsing_service.py
          column_mapping_service.py
          normalization_service.py
          reconciliation_service.py
          matching_engine.py
          exception_service.py
          review_service.py
          export_service.py
          demo_service.py

      integrations/
        __init__.py
        storage/
          __init__.py
          s3_client.py
          localstack_client.py

        parsers/
          __init__.py
          base_parser.py
          csv_parser.py
          xlsx_parser.py
          stripe_parser.py
          razorpay_parser.py
          chargebee_parser.py
          bank_parser.py
          invoice_parser.py

        providers/
          __init__.py
          stripe_client.py
          razorpay_client.py
          chargebee_client.py

      ai/
        __init__.py
        ai_client.py
        ai_config.py

        prompts/
          __init__.py
          column_mapping_prompt.py
          exception_explanation_prompt.py
          accountant_summary_prompt.py

        schemas/
          __init__.py
          ai_column_mapping_schema.py
          ai_exception_schema.py
          ai_summary_schema.py

        services/
          __init__.py
          ai_column_mapping_service.py
          ai_exception_explanation_service.py
          ai_summary_service.py

      workers/
        __init__.py
        queue.py
        jobs.py
        reconciliation_worker.py
        normalization_worker.py
        export_worker.py

      seed/
        __init__.py
        sample_data_loader.py

      tests/
        __init__.py
        conftest.py

        unit/
          test_money.py
          test_dates.py
          test_parsing_service.py
          test_column_mapping_service.py
          test_normalization_service.py
          test_matching_engine.py
          test_exception_service.py
          test_export_service.py

        integration/
          test_auth_flow.py
          test_upload_flow.py
          test_reconciliation_flow.py
          test_export_flow.py
          test_workspace_isolation.py

    scripts/
      create_localstack_bucket.py
      load_sample_data.py
      run_demo_reconciliation.py
```

---

## 5. File Responsibilities

### App entry files

#### `main.py`

Responsibilities:

- create FastAPI app
- include root router
- configure middleware
- configure exception handlers
- configure startup/shutdown events

#### `config.py`

Responsibilities:

- load environment variables
- expose typed settings
- define app, DB, Redis, S3, OAuth, AI config

#### `database.py`

Responsibilities:

- create SQLAlchemy engine
- create session factory
- provide DB session dependency

#### `dependencies.py`

Responsibilities:

- provide common dependencies:
  - DB session
  - current user context
  - workspace access guard

---

## 6. Environment Variables

Create `.env.example`.

```env
# App
APP_NAME=AI Reconciliation Worker
APP_ENV=local
APP_DEBUG=true
API_BASE_URL=http://localhost:8000
FRONTEND_BASE_URL=http://localhost:3000

# Database
DATABASE_URL=postgresql+psycopg://recon:recon@localhost:5432/recon_worker

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=change-me-local-only
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback

# S3 / LocalStack
S3_ENDPOINT_URL=http://localhost:4566
S3_ACCESS_KEY_ID=test
S3_SECRET_ACCESS_KEY=test
S3_REGION=us-east-1
S3_BUCKET_NAME=recon-worker-local-files
S3_FORCE_PATH_STYLE=true

# AI Provider
AI_PROVIDER=openai
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
AI_MODEL_COLUMN_MAPPING=gpt-4.1-mini
AI_MODEL_EXPLANATION=gpt-4.1-mini
AI_MODEL_SUMMARY=gpt-4.1-mini
AI_REQUEST_TIMEOUT_SECONDS=30

# File Upload
MAX_UPLOAD_SIZE_MB=25
ALLOWED_FILE_TYPES=.csv,.xlsx

# Logging
LOG_LEVEL=INFO

# Security
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

---

## 7. Auth Flow

### MVP auth method

Start with:

```text
Google login and signup
```

Do not build email/password now.

### Auth endpoints

```text
GET  /api/auth/google/login
GET  /api/auth/google/callback
POST /api/auth/logout
GET  /api/auth/me
```

### Google signup/login flow

```text
User opens /api/auth/google/login
        ↓
Backend redirects to Google OAuth consent
        ↓
Google redirects to /api/auth/google/callback
        ↓
Backend exchanges code for Google token
        ↓
Backend fetches Google user profile
        ↓
Find or create user by provider_subject/email
        ↓
If new user, create default workspace
        ↓
Create workspace_members OWNER row
        ↓
Issue JWT access token
        ↓
Return token or redirect to frontend later
```

### First-login behavior

When a new Google user signs in:

1. Create `users`.
2. Create `workspaces`.
3. Create `workspace_members` with role `OWNER`.
4. Log audit event:
   - `USER_SIGNED_IN`
   - `WORKSPACE_CREATED`

### JWT claims

```json
{
  "sub": "user_uuid",
  "email": "user@example.com",
  "active_workspace_id": "workspace_uuid",
  "role": "OWNER",
  "exp": 1234567890
}
```

---

## 8. Current User and Workspace Context

### CurrentUserContext object

Create file:

```text
backend/app/auth/current_user.py
```

Schema:

```python
class CurrentUserContext(BaseModel):
    user_id: UUID
    email: str
    active_workspace_id: UUID
    role: WorkspaceRole
```

### Dependency behavior

Every protected API must use current context.

Example:

```python
@router.get("/api/uploads")
def list_uploads(
    ctx: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db)
):
    return upload_service.list_uploads(
        workspace_id=ctx.active_workspace_id,
        user_id=ctx.user_id,
    )
```

### Workspace safety rule

Bad:

```python
get_upload(upload_id)
```

Good:

```python
get_upload(workspace_id, upload_id)
```

Every query must include `workspace_id`.

---

## 9. Authorization Model

### Roles

```text
OWNER
ADMIN
MEMBER
ACCOUNTANT
VIEWER
```

### MVP role permissions

| Action | OWNER | ADMIN | MEMBER | ACCOUNTANT | VIEWER |
|---|---:|---:|---:|---:|---:|
| Upload files | Yes | Yes | Yes | Yes | No |
| Normalize files | Yes | Yes | Yes | Yes | No |
| Run reconciliation | Yes | Yes | Yes | Yes | No |
| Approve/reject matches | Yes | Yes | Yes | Yes | No |
| Resolve exceptions | Yes | Yes | Yes | Yes | No |
| Export reports | Yes | Yes | Yes | Yes | Yes |
| Manage members | Yes | Yes | No | No | No |

For MVP, implement a simple role guard utility.

---

## 10. Audit Columns Standard

Every business table must include:

```text
id UUID PRIMARY KEY
workspace_id UUID NOT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
created_by_user_id UUID
updated_by_user_id UUID
```

Tables that support deletion should also include:

```text
deleted_at TIMESTAMPTZ
deleted_by_user_id UUID
```

### Base model files

#### `domain/models/base.py`

Include:

- UUID ID mixin
- timestamp mixin
- workspace mixin
- user audit mixin
- soft delete mixin

Suggested classes:

```text
UUIDPrimaryKeyMixin
TimestampMixin
WorkspaceScopedMixin
UserAuditMixin
SoftDeleteMixin
Base
```

---

## 11. Enums

Create enums as Python `StrEnum` or string enum.

### `auth_enums.py`

```text
AuthProvider
  GOOGLE

UserStatus
  ACTIVE
  DISABLED
  DELETED

WorkspaceStatus
  ACTIVE
  SUSPENDED
  DELETED

WorkspaceRole
  OWNER
  ADMIN
  MEMBER
  ACCOUNTANT
  VIEWER
```

### `file_enums.py`

```text
FileCategory
  STRIPE_REPORT
  RAZORPAY_REPORT
  CHARGEBEE_INVOICE_EXPORT
  CHARGEBEE_TRANSACTION_EXPORT
  BANK_STATEMENT
  INVOICE_EXPORT

UploadedFileStatus
  UPLOADED
  PARSING
  PARSED
  PARSE_FAILED
  NORMALIZING
  NORMALIZED
  NORMALIZE_FAILED
  ARCHIVED

SourceRecordStatus
  PARSED
  INVALID
```

### `mapping_enums.py`

```text
MappingSource
  AI
  MANUAL
  TEMPLATE

ColumnMappingStatus
  ACTIVE
  ARCHIVED
```

### `provider_enums.py`

```text
PaymentProvider
  STRIPE
  RAZORPAY
  CASHFREE
  PAYU
  PAYPAL
  UNKNOWN

BillingSystem
  CHARGEBEE
  STRIPE_BILLING
  RAZORPAY_SUBSCRIPTIONS
  ZOHO
  CUSTOM
  UNKNOWN
```

### `reconciliation_enums.py`

```text
ReconciliationRunStatus
  PENDING
  RUNNING
  COMPLETED
  FAILED
  CANCELLED

MatchStatus
  SUGGESTED
  AUTO_MATCHED
  APPROVED
  REJECTED

RecordType
  PAYMENT
  SETTLEMENT
  BANK
  INVOICE
  BILLING_TRANSACTION

MatchingRule
  EXACT_ID
  UTR
  AMOUNT_AND_DATE
  NET_SETTLEMENT
  FUZZY_REFERENCE
  AI_SUGGESTED
```

### `exception_enums.py`

```text
ExceptionType
  MISSING_INVOICE
  MISSING_PAYMENT
  MISSING_SETTLEMENT
  MISSING_BANK_CREDIT
  AMOUNT_MISMATCH
  FEE_MISMATCH
  TAX_MISMATCH
  REFUND_MISMATCH
  DUPLICATE_PAYMENT
  DELAYED_SETTLEMENT
  UNKNOWN_BANK_CREDIT
  OFFLINE_PAYMENT_CANDIDATE
  CHARGEBACK_OR_DISPUTE
  CURRENCY_MISMATCH
  NEEDS_MANUAL_REVIEW

ExceptionSeverity
  LOW
  MEDIUM
  HIGH
  CRITICAL

ExceptionStatus
  OPEN
  APPROVED
  REJECTED
  RESOLVED
  IGNORED
```

### `export_enums.py`

```text
ExportType
  XLSX_RECONCILIATION_REPORT
  CSV_MATCHED_RECORDS
  CSV_EXCEPTIONS
  ACCOUNTANT_SUMMARY

ExportStatus
  PENDING
  RUNNING
  COMPLETED
  FAILED
```

### `audit_enums.py`

```text
AuditEventType
  USER_SIGNED_IN
  WORKSPACE_CREATED
  FILE_UPLOADED
  FILE_PARSED
  COLUMN_MAPPING_SUGGESTED
  COLUMN_MAPPING_CONFIRMED
  NORMALIZATION_COMPLETED
  RECONCILIATION_STARTED
  RECONCILIATION_COMPLETED
  MATCH_APPROVED
  MATCH_REJECTED
  EXCEPTION_RESOLVED
  REPORT_EXPORTED
```

---

## 12. Database Models

## 12.1 Auth and workspace models

### `user.py`

Table: `users`

Fields:

```text
id UUID PK
email VARCHAR UNIQUE NOT NULL
full_name VARCHAR
avatar_url TEXT
auth_provider VARCHAR NOT NULL
provider_subject VARCHAR NOT NULL
status VARCHAR NOT NULL
last_login_at TIMESTAMPTZ
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

Unique:

```text
(email)
(auth_provider, provider_subject)
```

---

### `workspace.py`

Table: `workspaces`

Fields:

```text
id UUID PK
name VARCHAR NOT NULL
slug VARCHAR UNIQUE
status VARCHAR NOT NULL
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

---

### `workspace_member.py`

Table: `workspace_members`

Fields:

```text
id UUID PK
workspace_id UUID FK
user_id UUID FK
role VARCHAR NOT NULL
status VARCHAR NOT NULL
invited_by_user_id UUID FK
joined_at TIMESTAMPTZ
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

Unique:

```text
(workspace_id, user_id)
```

---

### `user_session.py`

Table: `user_sessions`

Optional but useful.

Fields:

```text
id UUID PK
user_id UUID FK
refresh_token_hash TEXT
expires_at TIMESTAMPTZ
revoked_at TIMESTAMPTZ
ip_address VARCHAR
user_agent TEXT
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

---

### `audit_event.py`

Table: `audit_events`

Fields:

```text
id UUID PK
workspace_id UUID
actor_user_id UUID
event_type VARCHAR NOT NULL
entity_type VARCHAR
entity_id UUID
metadata_json JSONB
ip_address VARCHAR
user_agent TEXT
created_at TIMESTAMPTZ
```

---

## 12.2 File ingestion models

### `uploaded_file.py`

Table: `uploaded_files`

Fields:

```text
id UUID PK
workspace_id UUID FK
file_name VARCHAR NOT NULL
file_category VARCHAR NOT NULL
storage_bucket VARCHAR NOT NULL
storage_key TEXT NOT NULL
mime_type VARCHAR
file_size_bytes BIGINT
checksum_sha256 VARCHAR
status VARCHAR NOT NULL
row_count INTEGER
parse_error TEXT
uploaded_by_user_id UUID FK
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
deleted_at TIMESTAMPTZ
deleted_by_user_id UUID
```

---

### `source_record.py`

Table: `source_records`

Fields:

```text
id UUID PK
workspace_id UUID FK
uploaded_file_id UUID FK
row_number INTEGER NOT NULL
raw_data_json JSONB NOT NULL
parse_status VARCHAR NOT NULL
parse_error TEXT
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

Index:

```text
(workspace_id, uploaded_file_id)
```

---

### `column_mapping.py`

Table: `column_mappings`

Fields:

```text
id UUID PK
workspace_id UUID FK
uploaded_file_id UUID FK
source_column VARCHAR NOT NULL
canonical_field VARCHAR NOT NULL
confidence NUMERIC(5, 2)
mapping_source VARCHAR NOT NULL
status VARCHAR NOT NULL
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

Unique:

```text
(uploaded_file_id, source_column)
```

---

## 12.3 Canonical record models

### `payment_record.py`

Table: `payment_records`

Fields:

```text
id UUID PK
workspace_id UUID FK
source_record_id UUID FK
provider VARCHAR
provider_payment_id VARCHAR
provider_order_id VARCHAR
billing_invoice_id VARCHAR
customer_reference VARCHAR
gross_amount NUMERIC(18, 6)
currency VARCHAR(3)
payment_status VARCHAR
payment_date TIMESTAMPTZ
raw_payload_json JSONB
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

Indexes:

```text
(workspace_id, provider, provider_payment_id)
(workspace_id, billing_invoice_id)
(workspace_id, payment_date)
```

---

### `settlement_record.py`

Table: `settlement_records`

Fields:

```text
id UUID PK
workspace_id UUID FK
source_record_id UUID FK
provider VARCHAR
provider_settlement_id VARCHAR
provider_payout_id VARCHAR
utr VARCHAR
gross_amount NUMERIC(18, 6)
fee_amount NUMERIC(18, 6)
tax_amount NUMERIC(18, 6)
refund_amount NUMERIC(18, 6)
adjustment_amount NUMERIC(18, 6)
net_settlement_amount NUMERIC(18, 6)
currency VARCHAR(3)
settlement_date TIMESTAMPTZ
status VARCHAR
raw_payload_json JSONB
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

Indexes:

```text
(workspace_id, provider, provider_settlement_id)
(workspace_id, provider_payout_id)
(workspace_id, utr)
(workspace_id, settlement_date)
```

---

### `bank_record.py`

Table: `bank_records`

Fields:

```text
id UUID PK
workspace_id UUID FK
source_record_id UUID FK
bank_account_reference VARCHAR
narration TEXT
utr VARCHAR
credit_amount NUMERIC(18, 6)
debit_amount NUMERIC(18, 6)
currency VARCHAR(3)
transaction_date TIMESTAMPTZ
raw_payload_json JSONB
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

Indexes:

```text
(workspace_id, utr)
(workspace_id, transaction_date)
```

---

### `invoice_record.py`

Table: `invoice_records`

Fields:

```text
id UUID PK
workspace_id UUID FK
source_record_id UUID FK
invoice_id VARCHAR
customer_reference VARCHAR
invoice_amount NUMERIC(18, 6)
paid_amount NUMERIC(18, 6)
currency VARCHAR(3)
invoice_status VARCHAR
invoice_date TIMESTAMPTZ
due_date TIMESTAMPTZ
raw_payload_json JSONB
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

Indexes:

```text
(workspace_id, invoice_id)
(workspace_id, customer_reference)
```

---

### `billing_transaction_record.py`

Table: `billing_transaction_records`

Used mainly for Chargebee transaction exports.

Fields:

```text
id UUID PK
workspace_id UUID FK
source_record_id UUID FK
billing_system VARCHAR
billing_transaction_id VARCHAR
billing_invoice_id VARCHAR
billing_customer_id VARCHAR
billing_subscription_id VARCHAR
gateway VARCHAR
gateway_transaction_id VARCHAR
amount NUMERIC(18, 6)
currency VARCHAR(3)
transaction_status VARCHAR
transaction_date TIMESTAMPTZ
raw_payload_json JSONB
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

Indexes:

```text
(workspace_id, billing_system, billing_transaction_id)
(workspace_id, billing_invoice_id)
(workspace_id, gateway, gateway_transaction_id)
```

---

## 12.4 Reconciliation models

### `reconciliation_run.py`

Table: `reconciliation_runs`

Fields:

```text
id UUID PK
workspace_id UUID FK
name VARCHAR NOT NULL
status VARCHAR NOT NULL
started_at TIMESTAMPTZ
completed_at TIMESTAMPTZ
total_records INTEGER DEFAULT 0
matched_count INTEGER DEFAULT 0
exception_count INTEGER DEFAULT 0
matched_amount NUMERIC(18, 6)
unmatched_amount NUMERIC(18, 6)
error_message TEXT
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

---

### `reconciliation_run_file.py`

Table: `reconciliation_run_files`

Fields:

```text
id UUID PK
workspace_id UUID FK
reconciliation_run_id UUID FK
uploaded_file_id UUID FK
created_at TIMESTAMPTZ
created_by_user_id UUID
```

Unique:

```text
(reconciliation_run_id, uploaded_file_id)
```

---

### `match_candidate.py`

Table: `match_candidates`

Fields:

```text
id UUID PK
workspace_id UUID FK
reconciliation_run_id UUID FK
source_type VARCHAR NOT NULL
source_record_id UUID NOT NULL
target_type VARCHAR NOT NULL
target_record_id UUID NOT NULL
confidence_score NUMERIC(5, 2)
matching_rule VARCHAR
status VARCHAR NOT NULL
explanation TEXT
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

---

### `exception_item.py`

Table: `exception_items`

Fields:

```text
id UUID PK
workspace_id UUID FK
reconciliation_run_id UUID FK
exception_type VARCHAR NOT NULL
severity VARCHAR NOT NULL
related_record_refs JSONB
amount NUMERIC(18, 6)
currency VARCHAR(3)
explanation TEXT
suggested_action TEXT
status VARCHAR NOT NULL
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

---

### `review_action.py`

Table: `review_actions`

Fields:

```text
id UUID PK
workspace_id UUID FK
reconciliation_run_id UUID FK
actor_user_id UUID FK
action_type VARCHAR NOT NULL
target_type VARCHAR NOT NULL
target_id UUID NOT NULL
note TEXT
created_at TIMESTAMPTZ
```

---

### `export_job.py`

Table: `export_jobs`

Fields:

```text
id UUID PK
workspace_id UUID FK
reconciliation_run_id UUID FK
export_type VARCHAR NOT NULL
status VARCHAR NOT NULL
storage_bucket VARCHAR
storage_key TEXT
error_message TEXT
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

---

## 12.5 Future integration models

Create these tables now only if low effort. They are useful for future, but do not implement sync logic in MVP.

### `integration_connection.py`

Table: `integration_connections`

Fields:

```text
id UUID PK
workspace_id UUID FK
provider VARCHAR NOT NULL
status VARCHAR NOT NULL
display_name VARCHAR
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

Providers:

```text
STRIPE
RAZORPAY
CHARGEBEE
CASHFREE
PAYU
ZOHO_BOOKS
TALLY
QUICKBOOKS
XERO
```

### `integration_credential.py`

Table: `integration_credentials`

Fields:

```text
id UUID PK
workspace_id UUID FK
integration_connection_id UUID FK
credential_type VARCHAR
encrypted_payload TEXT
status VARCHAR
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
created_by_user_id UUID
updated_by_user_id UUID
```

Never store plain secrets.

### `integration_sync_run.py`

Table: `integration_sync_runs`

Fields:

```text
id UUID PK
workspace_id UUID FK
integration_connection_id UUID FK
sync_type VARCHAR
status VARCHAR
started_at TIMESTAMPTZ
completed_at TIMESTAMPTZ
records_synced INTEGER
error_message TEXT
created_at TIMESTAMPTZ
```

---

## 13. Complete API List

## 13.1 Health APIs

```text
GET /health
GET /ready
```

### Purpose

- `/health`: API is alive.
- `/ready`: DB/Redis/S3 checks pass.

---

## 13.2 Auth APIs

```text
GET  /api/auth/google/login
GET  /api/auth/google/callback
POST /api/auth/logout
GET  /api/auth/me
```

### `GET /api/auth/me`

Response:

```json
{
  "data": {
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "full_name": "Girish"
    },
    "active_workspace": {
      "id": "uuid",
      "name": "Girish Workspace",
      "role": "OWNER"
    }
  }
}
```

---

## 13.3 Workspace APIs

```text
GET  /api/workspaces
POST /api/workspaces
GET  /api/workspaces/{workspace_id}
GET  /api/workspaces/{workspace_id}/members
POST /api/workspaces/{workspace_id}/members/invite
PATCH /api/workspaces/{workspace_id}/members/{member_id}/role
```

For MVP, invite/member update can be basic or placeholder.

---

## 13.4 Upload APIs

```text
POST   /api/uploads
GET    /api/uploads
GET    /api/uploads/{upload_id}
GET    /api/uploads/{upload_id}/preview
DELETE /api/uploads/{upload_id}
```

### `POST /api/uploads`

Form data:

```text
file
file_category
```

Accepted categories:

```text
STRIPE_REPORT
RAZORPAY_REPORT
CHARGEBEE_INVOICE_EXPORT
CHARGEBEE_TRANSACTION_EXPORT
BANK_STATEMENT
INVOICE_EXPORT
```

---

## 13.5 Column Mapping APIs

```text
POST /api/uploads/{upload_id}/suggest-mapping
GET  /api/uploads/{upload_id}/mapping
PUT  /api/uploads/{upload_id}/mapping
POST /api/uploads/{upload_id}/normalize
```

### AI mapping rule

Only send:

- column names
- 5 sample rows maximum
- file category

Never send full file to AI.

---

## 13.6 Reconciliation APIs

```text
POST /api/reconciliation-runs
GET  /api/reconciliation-runs
GET  /api/reconciliation-runs/{run_id}
POST /api/reconciliation-runs/{run_id}/run
GET  /api/reconciliation-runs/{run_id}/summary
GET  /api/reconciliation-runs/{run_id}/matches
GET  /api/reconciliation-runs/{run_id}/exceptions
```

### `POST /api/reconciliation-runs`

Request:

```json
{
  "name": "March 2026 Reconciliation",
  "uploaded_file_ids": ["uuid1", "uuid2"]
}
```

---

## 13.7 Match Review APIs

```text
POST /api/matches/{match_id}/approve
POST /api/matches/{match_id}/reject
```

Request:

```json
{
  "note": "Looks correct based on UTR and settlement amount."
}
```

---

## 13.8 Exception APIs

```text
GET  /api/exceptions/{exception_id}
POST /api/exceptions/{exception_id}/explain
POST /api/exceptions/{exception_id}/resolve
POST /api/exceptions/{exception_id}/ignore
POST /api/exceptions/{exception_id}/note
```

---

## 13.9 Export APIs

```text
POST /api/reconciliation-runs/{run_id}/export
GET  /api/exports/{export_id}
GET  /api/exports/{export_id}/download
```

### Export output

XLSX with sheets:

```text
Summary
Matched Records
Exceptions
Source Evidence
Review Actions
```

---

## 13.10 Demo APIs

```text
POST /api/demo/load-sample-data
POST /api/demo/run-sample-reconciliation
GET  /api/demo/status
```

These are important before frontend exists.

---

## 14. Service Layer

## 14.1 Auth services

### `AuthService`

File:

```text
app/auth/auth_service.py
```

Responsibilities:

- handle Google profile
- find/create user
- create default workspace
- create workspace member
- issue JWT
- update last_login_at

---

## 14.2 Workspace services

### `WorkspaceService`

Responsibilities:

- create workspace
- get current workspace
- list user workspaces
- validate membership
- manage members later

---

## 14.3 File services

### `FileStorageService`

Responsibilities:

- upload file to S3/LocalStack
- download file from storage
- generate storage key
- compute checksum
- create download URL later

### `FileIngestionService`

Responsibilities:

- create UploadedFile
- call FileStorageService
- call ParsingService
- save SourceRecord rows
- update file status

### `ParsingService`

Responsibilities:

- parse CSV
- parse XLSX
- return rows as dicts
- validate row count
- handle parse errors

---

## 14.4 Mapping and normalization services

### `ColumnMappingService`

Responsibilities:

- get file columns/sample rows
- call AI mapping service
- save suggested mappings
- save manual mappings
- validate canonical fields

### `NormalizationService`

Responsibilities:

- read source records
- apply mappings
- create canonical records based on file category
- parse money/date fields safely
- track invalid rows

---

## 14.5 Reconciliation services

### `ReconciliationService`

Responsibilities:

- create reconciliation run
- attach uploaded files to run
- orchestrate matching
- update run status and counts

### `MatchingEngine`

Responsibilities:

- match invoice to payment/billing transaction
- match payment/billing transaction to settlement
- match settlement to bank
- create match candidates
- calculate confidence
- create exception items

### `ExceptionService`

Responsibilities:

- create exceptions
- classify exception severity
- retrieve/filter exceptions
- update exception status

### `ReviewService`

Responsibilities:

- approve match
- reject match
- resolve exception
- ignore exception
- add review note
- create ReviewAction
- create AuditEvent

---

## 14.6 Export services

### `ExportService`

Responsibilities:

- create export job
- generate XLSX
- upload export to S3/LocalStack
- return download info

---

## 14.7 Demo service

### `DemoService`

Responsibilities:

- load sample files
- parse and normalize sample data
- create demo reconciliation run
- run demo reconciliation
- create demo export

---

## 15. AI Layer

## 15.1 AI files

```text
app/ai/
  ai_client.py
  ai_config.py

  prompts/
    column_mapping_prompt.py
    exception_explanation_prompt.py
    accountant_summary_prompt.py

  schemas/
    ai_column_mapping_schema.py
    ai_exception_schema.py
    ai_summary_schema.py

  services/
    ai_column_mapping_service.py
    ai_exception_explanation_service.py
    ai_summary_service.py
```

## 15.2 AIClient

Responsibilities:

- call configured provider
- support OpenAI first
- return structured JSON
- handle timeout
- log usage
- no business logic

## 15.3 AI tasks

### Column mapping

Input:

```json
{
  "file_category": "RAZORPAY_REPORT",
  "columns": ["payment_id", "settlement_id", "amount", "fee", "tax"],
  "sample_rows": []
}
```

Output:

```json
{
  "mappings": [
    {
      "source_column": "payment_id",
      "canonical_field": "provider_payment_id",
      "confidence": 0.98
    }
  ]
}
```

### Exception explanation

Input:

```json
{
  "exception_type": "REFUND_MISMATCH",
  "related_records": [],
  "amount": "500.00",
  "currency": "INR"
}
```

Output:

```json
{
  "explanation": "The settlement is lower because a refund appears to have been deducted from this payout cycle.",
  "suggested_action": "Verify refund transaction and confirm it belongs to this settlement period."
}
```

### Accountant summary

Input:

```json
{
  "total_records": 1200,
  "matched_count": 1140,
  "exception_count": 60,
  "top_exception_types": []
}
```

Output:

```json
{
  "summary": "Processed 1,200 records. 1,140 matched automatically. 60 require review."
}
```

## 15.4 AI safety rules

- AI never approves matches.
- AI never changes financial records silently.
- AI never posts to accounting systems.
- AI output must be validated with Pydantic.
- AI failure must not break core reconciliation.
- AI explanation is advisory only.

---

## 16. Worker Layer

Use Redis + RQ for MVP.

### Files

```text
workers/
  queue.py
  jobs.py
  normalization_worker.py
  reconciliation_worker.py
  export_worker.py
```

### `queue.py`

Responsibilities:

- configure Redis connection
- create queues:
  - `default`
  - `normalization`
  - `reconciliation`
  - `exports`

### Worker jobs

#### Normalize file job

```text
normalize_uploaded_file(uploaded_file_id, workspace_id, user_id)
```

#### Run reconciliation job

```text
run_reconciliation(reconciliation_run_id, workspace_id, user_id)
```

#### Export report job

```text
generate_export(export_job_id, workspace_id, user_id)
```

### MVP shortcut

For first implementation, jobs can run synchronously behind APIs.  
But keep worker structure ready so async can be added without rewriting services.

---

## 17. Reconciliation Logic

### Matching levels

```text
Level 1: Invoice ↔ Payment / Billing Transaction
Level 2: Payment / Billing Transaction ↔ Settlement / Payout
Level 3: Settlement / Payout ↔ Bank Credit
Level 4: Approved Results ↔ Export Report
```

### Matching priority

1. Exact ID match
2. UTR match
3. Amount + date window
4. Net settlement formula
5. Fuzzy reference candidate
6. AI-suggested explanation only

### Net settlement formula

```text
net_settlement_amount =
  gross_amount
  - fee_amount
  - tax_amount
  - refund_amount
  + adjustment_amount
```

### Confidence score

```text
100 = exact ID + amount + date match
90-99 = exact ID + amount match
75-89 = amount/date + strong reference match
50-74 = fuzzy candidate, manual review required
<50 = no reliable match, create exception
```

---

## 18. Antigravity Phase Plan

## Phase 0 — Project skeleton and local infra

### Goal

Create backend skeleton with Docker Compose.

### Prompt

```text
Create a backend-first FastAPI project for an AI reconciliation worker.

Use:
- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis + RQ
- LocalStack for S3
- Pydantic v2
- pytest

Create:
- exact folder structure from the engineering document
- docker-compose.yml for backend, postgres, redis, localstack
- .env.example
- Makefile
- /health and /ready endpoints
- README with local setup

Do not implement business logic yet.
Do not build frontend.
```

### Acceptance

- `docker compose up` works
- `/health` works
- DB connection works
- LocalStack bucket creation script works

---

## Phase 1 — Auth, workspace, context, audit foundation

### Prompt

```text
Implement Google OAuth auth and workspace context.

Build:
- users
- workspaces
- workspace_members
- user_sessions optional
- audit_events
- Google login/callback
- create user on first login
- create default workspace on first login
- assign OWNER role
- issue JWT
- GET /api/auth/me
- CurrentUserContext dependency
- workspace-scoped auth guard

Rules:
- no email/password
- every protected endpoint must use CurrentUserContext
- log USER_SIGNED_IN and WORKSPACE_CREATED audit events
- add tests for auth and workspace isolation
```

### Acceptance

- Google signup/login works
- default workspace is created
- JWT contains active workspace context
- `/api/auth/me` works
- audit events are created

---

## Phase 2 — File upload, storage, parsing

### Prompt

```text
Implement file upload and parsing.

Build:
- uploaded_files
- source_records
- POST /api/uploads
- GET /api/uploads
- GET /api/uploads/{id}
- GET /api/uploads/{id}/preview
- DELETE /api/uploads/{id}

Support:
- CSV
- XLSX

File categories:
- STRIPE_REPORT
- RAZORPAY_REPORT
- CHARGEBEE_INVOICE_EXPORT
- CHARGEBEE_TRANSACTION_EXPORT
- BANK_STATEMENT
- INVOICE_EXPORT

Use LocalStack S3 for file storage.
Parse rows using pandas/openpyxl.
Save rows as source_records.raw_data_json.
Do not build normalization yet.
```

### Acceptance

- upload works
- file stored in LocalStack
- source records created
- preview endpoint returns rows
- workspace isolation tested

---

## Phase 3 — Column mapping and normalization

### Prompt

```text
Implement column mapping and normalization.

Build:
- column_mappings
- POST /api/uploads/{id}/suggest-mapping
- GET /api/uploads/{id}/mapping
- PUT /api/uploads/{id}/mapping
- POST /api/uploads/{id}/normalize

Build canonical tables:
- payment_records
- settlement_records
- bank_records
- invoice_records
- billing_transaction_records

AI mapping:
- send only headers and 5 sample rows
- return structured JSON
- validate with Pydantic
- allow manual override

Use Decimal for money.
Use timezone-aware dates.
Every canonical record links to source_record_id.
```

### Acceptance

- mapping can be suggested
- mapping can be saved manually
- records normalize into canonical tables
- invalid rows handled cleanly

---

## Phase 4 — Reconciliation engine

### Prompt

```text
Implement deterministic reconciliation engine.

Build:
- reconciliation_runs
- reconciliation_run_files
- match_candidates
- exception_items

APIs:
- POST /api/reconciliation-runs
- GET /api/reconciliation-runs
- GET /api/reconciliation-runs/{id}
- POST /api/reconciliation-runs/{id}/run
- GET /api/reconciliation-runs/{id}/summary
- GET /api/reconciliation-runs/{id}/matches
- GET /api/reconciliation-runs/{id}/exceptions

Matching:
1. invoice to payment/billing transaction
2. billing transaction to gateway payment
3. payment to settlement/payout
4. settlement/payout to bank record

Use:
- exact IDs
- UTR
- amount/date window
- net settlement formula
- fuzzy candidate generation

Do not use LLM for deterministic matching.
```

### Acceptance

- sample reconciliation produces matches and exceptions
- counts stored on run
- tests for matching cases pass

---

## Phase 5 — Review actions and AI explanations

### Prompt

```text
Implement review actions and AI explanations.

Build:
- review_actions
- POST /api/matches/{id}/approve
- POST /api/matches/{id}/reject
- GET /api/exceptions/{id}
- POST /api/exceptions/{id}/explain
- POST /api/exceptions/{id}/resolve
- POST /api/exceptions/{id}/ignore
- POST /api/exceptions/{id}/note

AI:
- explain exceptions
- generate suggested action
- generate accountant summary

Rules:
- AI never approves matches
- all user actions create review_actions
- all important actions create audit_events
```

### Acceptance

- matches can be approved/rejected
- exceptions can be resolved/ignored/noted
- AI explanation works
- audit trail exists

---

## Phase 6 — XLSX export

### Prompt

```text
Implement XLSX export.

Build:
- export_jobs
- POST /api/reconciliation-runs/{id}/export
- GET /api/exports/{id}
- GET /api/exports/{id}/download

XLSX sheets:
- Summary
- Matched Records
- Exceptions
- Source Evidence
- Review Actions

Store export in LocalStack S3.
Create REPORT_EXPORTED audit event.
```

### Acceptance

- export file generated
- download works
- report is useful for accountant review

---

## Phase 7 — Demo backend

### Prompt

```text
Implement demo backend flow.

Build:
- sample files under /samples
- POST /api/demo/load-sample-data
- POST /api/demo/run-sample-reconciliation
- GET /api/demo/status

Demo must include:
- Stripe report
- Razorpay report
- Chargebee invoice export
- Chargebee transaction export
- bank statement
- invoice export

Demo exceptions:
- missing invoice
- missing bank credit
- refund mismatch
- fee mismatch
- offline payment candidate
- amount mismatch

Create Postman collection and README demo flow.
```

### Acceptance

- demo can run without frontend
- exported XLSX proves product value
- Postman can show full flow

---

## 19. API Response Format

### Success

```json
{
  "data": {},
  "request_id": "req_123"
}
```

### Error

```json
{
  "error": {
    "code": "FILE_PARSE_FAILED",
    "message": "Could not parse uploaded file.",
    "details": {}
  },
  "request_id": "req_123"
}
```

### Error rules

- no stack traces in API responses
- actionable user-facing messages
- detailed logs server-side
- request_id included

---

## 20. Testing Requirements

### Unit tests

Must cover:

- money parsing
- date parsing
- CSV parsing
- XLSX parsing
- AI mapping output validation
- normalization
- exact matching
- UTR matching
- net settlement formula
- refund mismatch
- fee mismatch
- tax mismatch
- missing invoice
- missing bank credit
- export generation

### Integration tests

Must cover:

- auth flow
- workspace isolation
- upload flow
- mapping flow
- normalization flow
- reconciliation flow
- review action flow
- export flow

### Demo test

A script should:

```text
load sample files
normalize records
run reconciliation
generate exceptions
export XLSX
```

---

## 21. Definition of Done

The backend MVP is complete when:

1. Local Docker setup works.
2. Google auth works.
3. User and workspace context works.
4. Upload to LocalStack works.
5. CSV/XLSX parsing works.
6. AI column mapping works.
7. Manual mapping works.
8. Normalization works.
9. Reconciliation run works.
10. Match candidates are created.
11. Exceptions are created.
12. AI explanations work.
13. Review actions work.
14. XLSX export works.
15. Demo API works.
16. Audit events are created.
17. Workspace isolation is tested.
18. Postman collection proves full workflow.

---

## 22. Final Instruction for Antigravity

Build this like a mature backend product, but do not over-engineer.

The only product flow that matters now:

```text
Auth → Upload → Parse → Map → Normalize → Reconcile → Explain → Review → Export
```

The business output that matters:

> A finance/accounting user gets an accountant-ready reconciliation report with exceptions and source evidence.

Everything else is later.
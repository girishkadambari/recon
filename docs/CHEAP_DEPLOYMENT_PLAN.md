# SettleProof Cheap Deployment Plan

This document outlines the cheapest possible MVP validation deployment for SettleProof. The goal is to run a controlled MVP demo at near-zero cost until a real customer, design partner, or strong potential lead is acquired.

## 1. Cheapest Architecture

The deployment leverages completely free or heavily credited tiers.

*   **Frontend**: Cloudflare Pages (Free tier, generous bandwidth and fast global edge CDN for static Vite builds).
*   **Backend**: Render Free Web Service (or Railway Trial). It runs the Dockerized FastAPI application.
*   **Database**: Neon Free Postgres (0$ Serverless Postgres, generous storage limits for demo files).
*   **Storage**: AWS S3 (Free-tier limits cover basic demo file sizes).
*   **Queue**: AWS SQS (Optional, entirely avoided for the first demo).

## 2. Deployment Modes

### Mode A: Free Demo Mode (Current State)
*   **Execution**: Synchronous processing (`JOB_MODE=sync` effectively, though natively hardcoded as sync).
*   **Worker**: **No required background worker.**
*   **Behavior**: Normalization, Reconciliation Runs, and Exports run synchronously. This is limited by the maximum HTTP timeout of the hosting provider (e.g., Render limits).
*   **Use Case**: Ideal for controlled demos with small sample files (<5k rows) and early validation sales calls.

### Mode B: Pilot Mode (Future Upgrade)
*   **Execution**: Asynchronous background queue (`JOB_MODE=sqs`).
*   **Worker**: Background worker enabled and consuming tasks.
*   **Behavior**: Normalization and heavy reconciliation offload to the queue, avoiding HTTP timeouts on large real-world files.
*   **Use Case**: Deploy only when a customer or pilot appears with massive multi-gigabyte financial ledgers.

## 3. Required Code/Config Check

**Validation Result from Codebase Review:**
The SettleProof backend **already natively executes synchronously.**
*   Routes like `execute_run` in `reconciliation_run_routes.py` and the parsing services bypass background queues inside the API endpoints.
*   The worker scaffolding (`workers/jobs.py` and `workers/queue.py` utilizing `rq`) exists but is not hooked into the active API routes.
*   There is no mandatory URL configuration required for SQS or Redis to execute a standard web request.
*   **Safety Warning**: Because it runs synchronously, massive files (10MB+) could hit Render's 100-second request timeout limit. Demo users must utilize tightly controlled, small CSV files to avoid 504 Gateway errors.

## 4. Free-Tier Deployment Checklist

### Frontend (Cloudflare Pages)
- [ ] Connect Github repository to Cloudflare Pages.
- [ ] Build command: `npm run build`
- [ ] Output directory: `dist`
- [ ] Set Environment Variable: `VITE_API_BASE_URL` to your Render backend URL.

### Backend (Render Free Web Service)
- [ ] Connect Github repository / configure Docker runtime.
- [ ] Set production environment variables (`DATABASE_URL`, `JWT_SECRET_KEY`, `CORS_ALLOWED_ORIGINS`).
- [ ] Disable worker startup commands.
- [ ] Run Alembic migrations manually via Render shell or local CLI against the Neon instance.
- [ ] Verify `/health` and `/ready` endpoints respond successfully.

### Database (Neon Free)
- [ ] Create a Neon Free tier project.
- [ ] Copy the provided pooled connection string (`DATABASE_URL`).
- [ ] Apply Alembic migrations locally targeting this remote URL.

### AWS Storage
- [ ] Create an AWS account (Free Tier).
- [ ] Establish a private S3 bucket.
- [ ] Create an IAM User with exclusively S3 Read/Write permissions.
- [ ] Add `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` to Render backend env vars.
- [ ] Leave SQS configurations empty.

## 5. What to Avoid Now

To guarantee zero runaway costs, strictly **aviod**:
*   **No Kubernetes**, No ECS/Fargate, No heavy Terraform orchestration.
*   **No AWS RDS** (Avoid minimum instance fees, stick to Neon serverless).
*   **No Paid Redis / Paid Worker Services** (Run sync mode until HTTP boundaries are broken by a paying client).
*   **No Rate Limiting Infra** (A single demo user does not necessitate API gateway throttling).

## 6. Cost Expectation

Expected Monthly Overhead:
*   **Frontend**: ₹0 (Cloudflare Pages Free Tier)
*   **Backend**: ₹0 (Render Free Tier). *Note: Instance will sleep after 15 minutes of inactivity; initial login might take up to 45 seconds during cold starts.*
*   **Database**: ₹0 (Neon Free Tier)
*   **S3**: ₹0 (Under free tier of 5GB/20000 GET requests).
*   **Domain**: Standard yearly registration cost (approx ₹800 - ₹1200/year).

## 7. Upgrade Trigger

Do not upgrade this setup or implement robust asynchronous architecture unless:
*   A design partner shares real, massive ledgers that crash the 100-second HTTP timeout.
*   Demo usage frequency requires avoiding Render's web service cold-start delays.
*   You secure funding or paid commitments necessitating production SLA guarantees.

## 8. Production Warnings

**This architecture is strictly for controlled demos, founder-led sales motions, and early validation.**
It is *not* meant for broad public production SaaS usage. Concurrent reconciliation runs from multiple public users will paralyze the synchronous single-threaded free web service. Do not distribute access widely without migrating to Pilot Mode limits.

# SettleProof Deployment Environment Variables

This document catalogs the exact environment variables required to securely launch SettleProof onto compute instances effectively decoupled from local development stubs.

> **CRITICAL WARNING:** NEVER commit raw secrets or production database connection strings into source control. Always inject these natively via rendering host secrets managers or environment runtime layers.

## Backend Application Runtime

The FastAPI backend natively absorbs specific schema mappings. Set these upon provisioning the compute layer:

*   `APP_ENV`: Must equal `production`.
*   `API_BASE_URL`: The public-facing internal map endpoint (`https://cloud.settleproof.app`).
*   `FRONTEND_BASE_URL`: The explicit resolution route the backend throws OAuth requests towards (`https://cloud.settleproof.app/ui`).
*   `CORS_ALLOWED_ORIGINS`: Restrict rigidly to your top-level domain (`https://cloud.settleproof.app`).
*   `DATABASE_URL`: Your managed string. When using Neon Free Postgres, use the pooled endpoint structure: `postgresql://USER:PASSWORD@HOST/DB?sslmode=require`. Apply schema bindings locally before activating: run `alembic upgrade head` targeting this remote connection string individually.
*   `JWT_SECRET_KEY`: Random generated cryptographic token string ensuring session tokens cannot be independently forged.
*   `LOG_LEVEL`: Set to `info` normally; raise to `debug` only when investigating cold start anomalies.
*   `JOB_MODE`: Setting heavily emphasizing architecture path. **Set to `sync` for immediate MVP evaluations.** *(Set to `sqs` only when explicitly moving off single-thread executions.)*

### Integrated Services Mapping

*   `GOOGLE_CLIENT_ID`: OAuth Provider application identity marker.
*   `GOOGLE_CLIENT_SECRET`: Strict secret pair for handshake generation.
*   `GOOGLE_REDIRECT_URI`: Where Google sends the validated ticket. Map strictly to `https://cloud.settleproof.app/api/auth/google/callback`.

### AWS Infrastructure Abstractions

*   `AWS_REGION`: Physical boundary identifier (e.g. `us-east-1` or `ap-south-1`).
*   `AWS_ACCESS_KEY_ID`: Bound rigidly to a specific, scoped S3 IAM instance.
*   `AWS_SECRET_ACCESS_KEY`: Strict secret pair.
*   `S3_BUCKET_NAME`: Standard uniquely named bucket target preventing file bleed.
*   *(Omissible Variable)* `SQS_QUEUE_URL`: Leave blank / abstract entire existence during MVP Phase evaluating strictly `JOB_MODE=sync`. Do not enforce presence checks until Pilot mode.

## Frontend Application Compilation

When triggering Vite builds explicitly targeted toward the single-domain alias logic, you inject context during build compilation, NOT runtime.

*   `VITE_API_BASE_URL`: Resolves browser REST client targets strictly back natively (`https://cloud.settleproof.app`). 
*   `VITE_APP_BASE_PATH`: Resolves TanStack router subpath navigation mapping perfectly into the Apache SPA directory (`/ui`).

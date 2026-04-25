"""
API Router — assembles all route modules.
"""
from fastapi import APIRouter

from app.api.routes.health_routes import router as health_router
from app.api.routes.auth_routes import router as auth_router
from app.api.routes.workspace_routes import router as workspace_router
from app.api.routes.upload_routes import router as upload_router
from app.api.routes.column_mapping_routes import router as column_mapping_router
from app.api.routes.reconciliation_routes import router as reconciliation_router
from app.api.routes.explanation_routes import router as explanation_router
from app.api.routes.export_routes import router as export_router

api_router = APIRouter()

# Health (no prefix, publicly accessible)
api_router.include_router(health_router, tags=["health"])

# Phase 1 — Auth & Workspaces
api_router.include_router(auth_router)
api_router.include_router(workspace_router)

# Phase 2 — Uploads
api_router.include_router(upload_router)

# Phase 3 — Column Mapping & Normalization
api_router.include_router(column_mapping_router)

# Phase 4 — Reconciliation Engine
api_router.include_router(reconciliation_router)

# Phase 5 — AI Explanations & Run Summary
api_router.include_router(explanation_router)

# Phase 6 — XLSX Export
api_router.include_router(export_router)

# Demo in Phase 7

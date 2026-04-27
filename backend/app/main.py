"""
AI Reconciliation Worker — Backend Application Entry Point
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.logging_config import configure_logging
from app.api.router import api_router
from app.core.errors import ReconError

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    configure_logging()
    logger.info(
        "Starting AI Reconciliation Worker",
        env=settings.APP_ENV,
        debug=settings.APP_DEBUG,
    )
    yield
    logger.info("Shutting down AI Reconciliation Worker")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="AI-assisted reconciliation worker for payment gateway, bank, and invoice data.",
        version="0.3.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ────────────────────────────────────────────────────────
    origins = [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request ID middleware ────────────────────────────────────────
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        import uuid
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Global exception handlers ────────────────────────────────────
    @app.exception_handler(ReconError)
    async def recon_error_handler(request: Request, exc: ReconError):
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "Business error",
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details or {},
                },
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled exception", request_id=request_id, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred. Please try again.",
                    "details": {},
                },
                "request_id": request_id,
            },
        )

    # ── Routers ──────────────────────────────────────────────────────
    app.include_router(api_router)

    return app


app = create_app()

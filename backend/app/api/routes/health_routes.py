"""
Health check routes.

GET /health — API is alive
GET /ready  — DB, Redis, and S3 are reachable
"""
import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.database import check_db_connection

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/health", summary="Liveness check")
def health() -> JSONResponse:
    """Returns 200 if the API process is running."""
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "service": "ai-reconciliation-worker"},
    )


@router.get("/ready", summary="Readiness check")
def ready() -> JSONResponse:
    """
    Returns 200 if all downstream dependencies are reachable.
    Returns 503 if any dependency is unavailable.
    """
    checks: dict[str, bool] = {}

    # DB check
    checks["database"] = check_db_connection()

    # Redis check
    try:
        from app.config import get_settings
        import redis as redis_lib

        settings = get_settings()
        r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = True
    except Exception as exc:
        logger.warning("Redis readiness check failed", error=str(exc))
        checks["redis"] = False

    # LocalStack / S3 check
    try:
        from app.config import get_settings
        import boto3
        from botocore.config import Config

        settings = get_settings()
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
            config=Config(connect_timeout=2, retries={"max_attempts": 0}),
        )
        s3.list_buckets()
        checks["storage"] = True
    except Exception as exc:
        logger.warning("S3/LocalStack readiness check failed", error=str(exc))
        checks["storage"] = False

    all_ok = all(checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ok else "degraded",
            "checks": checks,
        },
    )

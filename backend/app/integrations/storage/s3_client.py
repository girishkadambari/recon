"""
S3 / LocalStack storage client.
All file I/O goes through this module.
"""
from typing import Optional
import hashlib
import io
import mimetypes
from typing import BinaryIO

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import get_settings
from app.core.errors import StorageError

logger = structlog.get_logger(__name__)


def _get_s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
        config=Config(retries={"max_attempts": 3}),
    )


def upload_file(
    file_bytes: bytes,
    storage_key: str,
    content_type: Optional[str] = None,
) -> str:
    """
    Upload bytes to S3 at the given storage_key.
    Returns the storage_key on success.
    Raises StorageError on failure.
    """
    settings = get_settings()
    bucket = settings.S3_BUCKET_NAME

    if not content_type:
        guessed, _ = mimetypes.guess_type(storage_key)
        content_type = guessed or "application/octet-stream"

    try:
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=bucket,
            Key=storage_key,
            Body=file_bytes,
            ContentType=content_type,
        )
        logger.info("File uploaded to S3", key=storage_key, size=len(file_bytes))
        return storage_key
    except ClientError as exc:
        logger.error("S3 upload failed", key=storage_key, error=str(exc))
        raise StorageError(f"Failed to upload file to storage: {exc}") from exc


def download_file(storage_key: str) -> bytes:
    """
    Download file bytes from S3.
    Raises StorageError on failure.
    """
    settings = get_settings()
    bucket = settings.S3_BUCKET_NAME
    try:
        s3 = _get_s3_client()
        response = s3.get_object(Bucket=bucket, Key=storage_key)
        return response["Body"].read()
    except ClientError as exc:
        logger.error("S3 download failed", key=storage_key, error=str(exc))
        raise StorageError(f"Failed to download file from storage: {exc}") from exc


def generate_presigned_url(storage_key: str, expires_in: int = 3600) -> str:
    """
    Generate a presigned URL for downloading the file (for exports / client previews).
    """
    settings = get_settings()
    bucket = settings.S3_BUCKET_NAME
    try:
        s3 = _get_s3_client()
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": storage_key},
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as exc:
        raise StorageError(f"Failed to generate presigned URL: {exc}") from exc


def delete_file(storage_key: str) -> None:
    """Delete a file from S3."""
    settings = get_settings()
    bucket = settings.S3_BUCKET_NAME
    try:
        s3 = _get_s3_client()
        s3.delete_object(Bucket=bucket, Key=storage_key)
        logger.info("File deleted from S3", key=storage_key)
    except ClientError as exc:
        logger.error("S3 delete failed", key=storage_key, error=str(exc))
        raise StorageError(f"Failed to delete file from storage: {exc}") from exc


def compute_sha256(file_bytes: bytes) -> str:
    """Compute SHA-256 checksum for deduplication and integrity checks."""
    return hashlib.sha256(file_bytes).hexdigest()


def build_storage_key(workspace_id: str, file_id: str, file_name: str) -> str:
    """
    Build a deterministic S3 key.
    Pattern: uploads/{workspace_id}/{file_id}/{file_name}
    """
    # Sanitize file_name to avoid path traversal
    safe_name = file_name.replace("..", "").replace("/", "_").replace("\\", "_")
    return f"uploads/{workspace_id}/{file_id}/{safe_name}"
"""
FileIngestionService — orchestrates upload → parse → store source records.
Business logic only. No HTTP concerns.
"""
from __future__ import annotations
from typing import Optional
import uuid

import structlog
from sqlalchemy.orm import Session

from app.core.errors import FileTooLargeError, FileParseError, NotFoundError, UnsupportedFileTypeError
from app.domain.enums.audit_enums import AuditEventType
from app.domain.enums.file_enums import UploadedFileStatus
from app.domain.models.uploaded_file import UploadedFile
from app.domain.repositories.uploaded_file_repository import UploadedFileRepository
from app.domain.repositories.source_record_repository import SourceRecordRepository
from app.domain.services.audit_service import AuditService
from app.integrations.parsers.base_parser import ParseResult
from app.integrations.parsers.parser_factory import get_parser
from app.integrations.storage.s3_client import (
    build_storage_key,
    compute_sha256,
    download_file,
    upload_file,
)
from app.config import get_settings

logger = structlog.get_logger(__name__)

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class FileIngestionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.file_repo = UploadedFileRepository(db)
        self.source_repo = SourceRecordRepository(db)
        self.audit_svc = AuditService(db)

    def ingest_file(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        file_name: str,
        file_bytes: bytes,
        file_category: str,
        mime_type: Optional[str] = None,
    ) -> UploadedFile:
        """
        Full ingestion pipeline:
          1. Validate size + extension
          2. Upload to S3
          3. Create UploadedFile record (status=UPLOADING)
          4. Parse file into rows
          5. Bulk insert SourceRecord rows
          6. Update UploadedFile status to PARSED (or PARSE_FAILED)
          7. Log audit event
          8. Commit
        """
        settings = get_settings()

        # ── 1. Validate ─────────────────────────────────────────────
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise FileTooLargeError(
                f"File '{file_name}' is {len(file_bytes) // (1024*1024)}MB"
                f" — max allowed is 50MB."
            )
        # Validate parser exists (raises UnsupportedFileTypeError if not)
        get_parser(file_name, mime_type)

        # ── 2. Compute checksum & build storage key ──────────────────
        checksum = compute_sha256(file_bytes)
        file_id = uuid.uuid4()
        storage_key = build_storage_key(str(workspace_id), str(file_id), file_name)

        # ── 3. Upload to S3 ────────────────────────────────────────
        upload_file(file_bytes, storage_key, content_type=mime_type)

        # ── 4. Create UploadedFile record ──────────────────────────
        uploaded_file = self.file_repo.create(
            workspace_id=workspace_id,
            file_name=file_name,
            file_category=file_category,
            storage_bucket=settings.S3_BUCKET_NAME,
            storage_key=storage_key,
            mime_type=mime_type,
            file_size_bytes=len(file_bytes),
            checksum_sha256=checksum,
            uploaded_by_user_id=user_id,
            file_id_override=file_id,
        )
        self.db.flush()

        # ── 5. Parse ───────────────────────────────────────────────
        self.file_repo.update_status(uploaded_file, UploadedFileStatus.PARSING)
        self.db.flush()

        try:
            parser = get_parser(file_name, mime_type)
            result: ParseResult = parser.parse(file_bytes, file_name)
        except Exception as exc:
            self.file_repo.update_status(
                uploaded_file,
                UploadedFileStatus.PARSE_FAILED,
                parse_error=str(exc),
            )
            self.db.commit()
            raise FileParseError(f"Failed to parse '{file_name}': {exc}") from exc

        if not result.rows:
            parse_err = "; ".join(result.parse_errors) if result.parse_errors else "File is empty."
            self.file_repo.update_status(
                uploaded_file,
                UploadedFileStatus.PARSE_FAILED,
                parse_error=parse_err,
            )
            self.db.commit()
            raise FileParseError(f"'{file_name}' contains no parseable data. {parse_err}")

        # ── 6. Bulk insert source records ──────────────────────────
        inserted = self.source_repo.bulk_create(
            workspace_id=workspace_id,
            uploaded_file_id=uploaded_file.id,
            rows=result.rows,
            created_by_user_id=user_id,
        )

        # ── 7. Update status → PARSED ──────────────────────────────
        self.file_repo.update_status(
            uploaded_file,
            UploadedFileStatus.PARSED,
            row_count=inserted,
        )

        # ── 8. Audit ───────────────────────────────────────────────
        self.audit_svc.log(
            event_type=AuditEventType.FILE_UPLOADED,
            actor_user_id=user_id,
            workspace_id=workspace_id,
            entity_type="uploaded_file",
            entity_id=uploaded_file.id,
            metadata={
                "file_name": file_name,
                "file_category": file_category,
                "row_count": inserted,
                "size_bytes": len(file_bytes),
            },
        )
        self.audit_svc.log(
            event_type=AuditEventType.FILE_PARSED,
            actor_user_id=user_id,
            workspace_id=workspace_id,
            entity_type="uploaded_file",
            entity_id=uploaded_file.id,
            metadata={"row_count": inserted, "parse_warnings": result.parse_errors},
        )

        self.db.commit()

        logger.info(
            "File ingested",
            file_id=str(uploaded_file.id),
            file_name=file_name,
            rows=inserted,
            workspace_id=str(workspace_id),
        )
        return uploaded_file

    def get_file(self, workspace_id: uuid.UUID, file_id: uuid.UUID) -> UploadedFile:
        uf = self.file_repo.get_by_id(file_id, workspace_id)
        if not uf:
            raise NotFoundError(f"File {file_id} not found.")
        return uf

    def list_files(
        self,
        workspace_id: uuid.UUID,
        file_category: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[UploadedFile], int]:
        offset = (page - 1) * page_size
        return self.file_repo.list_for_workspace(
            workspace_id=workspace_id,
            file_category=file_category,
            limit=page_size,
            offset=offset,
        )

    def get_preview_rows(
        self,
        workspace_id: uuid.UUID,
        file_id: uuid.UUID,
        n: int = 20,
    ) -> list[dict]:
        uf = self.get_file(workspace_id, file_id)
        return self.source_repo.list_for_file(
            workspace_id=workspace_id,
            uploaded_file_id=uf.id,
            limit=n,
        )

    def delete_file(self, workspace_id: uuid.UUID, file_id: uuid.UUID, user_id: uuid.UUID) -> None:
        uf = self.get_file(workspace_id, file_id)
        self.file_repo.soft_delete(uf, deleted_by=user_id)
        self.db.commit()
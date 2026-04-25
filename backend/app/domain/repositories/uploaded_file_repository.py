"""
UploadedFile repository.
"""
import uuid
from typing import List

from sqlalchemy.orm import Session

from app.domain.models.uploaded_file import UploadedFile
from app.domain.enums.file_enums import UploadedFileStatus


class UploadedFileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, file_id: uuid.UUID, workspace_id: uuid.UUID) -> UploadedFile | None:
        return (
            self.db.query(UploadedFile)
            .filter(
                UploadedFile.id == file_id,
                UploadedFile.workspace_id == workspace_id,
                UploadedFile.deleted_at.is_(None),
            )
            .first()
        )

    def list_for_workspace(
        self,
        workspace_id: uuid.UUID,
        file_category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[UploadedFile], int]:
        q = self.db.query(UploadedFile).filter(
            UploadedFile.workspace_id == workspace_id,
            UploadedFile.deleted_at.is_(None),
        )
        if file_category:
            q = q.filter(UploadedFile.file_category == file_category)
        total = q.count()
        rows = q.order_by(UploadedFile.created_at.desc()).offset(offset).limit(limit).all()
        return rows, total

    def create(
        self,
        workspace_id: uuid.UUID,
        file_name: str,
        file_category: str,
        storage_bucket: str,
        storage_key: str,
        mime_type: str | None,
        file_size_bytes: int | None,
        checksum_sha256: str | None,
        uploaded_by_user_id: uuid.UUID,
        file_id_override: uuid.UUID | None = None,
    ) -> UploadedFile:
        uf = UploadedFile(
            workspace_id=workspace_id,
            file_name=file_name,
            file_category=file_category,
            storage_bucket=storage_bucket,
            storage_key=storage_key,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            checksum_sha256=checksum_sha256,
            status=UploadedFileStatus.UPLOADED,
            uploaded_by_user_id=uploaded_by_user_id,
            created_by_user_id=uploaded_by_user_id,
            updated_by_user_id=uploaded_by_user_id,
        )
        if file_id_override:
            uf.id = file_id_override
        self.db.add(uf)
        self.db.flush()
        return uf

    def update_status(
        self,
        uploaded_file: UploadedFile,
        status: UploadedFileStatus,
        row_count: int | None = None,
        parse_error: str | None = None,
    ) -> UploadedFile:
        from app.core.dates import utcnow

        uploaded_file.status = status
        if row_count is not None:
            uploaded_file.row_count = row_count
        if parse_error is not None:
            uploaded_file.parse_error = parse_error
        uploaded_file.updated_at = utcnow()
        self.db.flush()
        return uploaded_file

    def soft_delete(self, uploaded_file: UploadedFile, deleted_by: uuid.UUID) -> None:
        from app.core.dates import utcnow

        uploaded_file.deleted_at = utcnow()
        uploaded_file.deleted_by_user_id = deleted_by
        self.db.flush()

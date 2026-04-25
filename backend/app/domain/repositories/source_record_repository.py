"""
SourceRecord repository — bulk insert only; records are read-only after parsing.
"""
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.models.source_record import SourceRecord
from app.domain.enums.file_enums import SourceRecordStatus


class SourceRecordRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def bulk_create(
        self,
        workspace_id: uuid.UUID,
        uploaded_file_id: uuid.UUID,
        rows: list[dict],
        created_by_user_id: uuid.UUID,
    ) -> int:
        """
        Bulk-insert source records.
        Returns the number of records inserted.
        """
        if not rows:
            return 0

        from app.core.dates import utcnow
        now = utcnow()
        import uuid as uuid_lib

        records = [
            {
                "id": uuid_lib.uuid4(),
                "workspace_id": workspace_id,
                "uploaded_file_id": uploaded_file_id,
                "row_number": i + 1,
                "raw_data_json": row,
                "parse_status": SourceRecordStatus.PARSED,
                "parse_error": None,
                "created_at": now,
                "updated_at": now,
                "created_by_user_id": created_by_user_id,
                "updated_by_user_id": created_by_user_id,
            }
            for i, row in enumerate(rows)
        ]
        self.db.bulk_insert_mappings(SourceRecord, records)
        self.db.flush()
        return len(records)

    def list_for_file(
        self,
        workspace_id: uuid.UUID,
        uploaded_file_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SourceRecord]:
        return (
            self.db.query(SourceRecord)
            .filter(
                SourceRecord.workspace_id == workspace_id,
                SourceRecord.uploaded_file_id == uploaded_file_id,
            )
            .order_by(SourceRecord.row_number)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_for_file(self, workspace_id: uuid.UUID, uploaded_file_id: uuid.UUID) -> int:
        return (
            self.db.query(SourceRecord)
            .filter(
                SourceRecord.workspace_id == workspace_id,
                SourceRecord.uploaded_file_id == uploaded_file_id,
            )
            .count()
        )

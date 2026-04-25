"""
Worker job function signatures.
For Phase 0, these are stubs. Full implementations added in later phases.
Each job calls the appropriate service.
"""
from uuid import UUID


def normalize_uploaded_file(
    uploaded_file_id: str,
    workspace_id: str,
    user_id: str,
) -> None:
    """
    Normalize an uploaded file into canonical records.
    Enqueued to the 'normalization' queue.
    """
    # Phase 3: will call NormalizationService
    raise NotImplementedError("Normalization worker not yet implemented.")


def run_reconciliation(
    reconciliation_run_id: str,
    workspace_id: str,
    user_id: str,
) -> None:
    """
    Execute a reconciliation run.
    Enqueued to the 'reconciliation' queue.
    """
    # Phase 4: will call ReconciliationService + MatchingEngine
    raise NotImplementedError("Reconciliation worker not yet implemented.")


def generate_export(
    export_job_id: str,
    workspace_id: str,
    user_id: str,
) -> None:
    """
    Generate an XLSX export and upload to S3.
    Enqueued to the 'exports' queue.
    """
    # Phase 6: will call ExportService
    raise NotImplementedError("Export worker not yet implemented.")

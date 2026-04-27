"""
CSV parser — uses pandas for robust CSV parsing.
Handles BOM, different encodings, various delimiters.
"""
from typing import Optional
import io
import structlog

import pandas as pd

from app.integrations.parsers.base_parser import BaseParser, ParseResult

logger = structlog.get_logger(__name__)

ENCODINGS_TO_TRY = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
DELIMITERS_TO_TRY = [",", ";", "\t", "|"]


class CSVParser(BaseParser):
    def parse(self, file_bytes: bytes, file_name: str = "") -> ParseResult:
        errors: list[str] = []
        df: Optional[pd.DataFrame] = None

        for encoding in ENCODINGS_TO_TRY:
            for delimiter in DELIMITERS_TO_TRY:
                try:
                    df = pd.read_csv(
                        io.BytesIO(file_bytes),
                        delimiter=delimiter,
                        encoding=encoding,
                        dtype=str,          # always read as strings — normalization decides types
                        keep_default_na=False,
                        na_values=[""],
                        on_bad_lines="warn",
                        engine="python",
                    )
                    if df is not None and len(df.columns) > 1:
                        logger.info(
                            "CSV parsed",
                            file=file_name,
                            rows=len(df),
                            cols=len(df.columns),
                            encoding=encoding,
                            delimiter=repr(delimiter),
                        )
                        break
                except Exception as exc:
                    errors.append(f"encoding={encoding} delimiter={repr(delimiter)}: {exc}")
                    df = None
            if df is not None and len(df.columns) > 1:
                break

        if df is None or df.empty:
            return ParseResult(
                rows=[],
                column_names=[],
                parse_errors=errors or ["No data parsed from CSV file."],
            )

        if len(df) > self.MAX_ROWS:
            df = df.iloc[: self.MAX_ROWS]
            errors.append(f"File truncated to {self.MAX_ROWS} rows for safety.")

        # Normalise column names (strip whitespace, deduplicate)
        df.columns = [str(c).strip() for c in df.columns]

        # Replace Pandas NA with None for clean JSON
        # We also convert to object to allow None values alongside strings
        df = df.astype(object).where(pd.notna(df), None)

        # Final safety check: convert any remaining float NaN to None
        rows = []
        for r in df.to_dict(orient="records"):
            # Ensure no float('nan') slips through
            rows.append({k: (None if pd.isna(v) else v) for k, v in r.items()})

        return ParseResult(
            rows=rows,
            column_names=list(df.columns),
            parse_errors=errors,
        )
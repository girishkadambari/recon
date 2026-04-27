from typing import Union
"""
Excel (XLSX/XLS) parser — uses openpyxl via pandas.
Reads the first sheet by default; can specify sheet_name.
"""
import io
import structlog

import pandas as pd

from app.integrations.parsers.base_parser import BaseParser, ParseResult

logger = structlog.get_logger(__name__)


class XLSXParser(BaseParser):
    def __init__(self, sheet_name: Union[int, str] = 0) -> None:
        self.sheet_name = sheet_name

    def parse(self, file_bytes: bytes, file_name: str = "") -> ParseResult:
        errors: list[str] = []
        try:
            df = pd.read_excel(
                io.BytesIO(file_bytes),
                sheet_name=self.sheet_name,
                dtype=str,           # read everything as string — normalization decides types
                keep_default_na=False,
                na_values=[""],
                engine="openpyxl",
            )
        except Exception as exc:
            logger.warning("XLSX parse failed, trying xlrd-compatible fallback", error=str(exc))
            try:
                df = pd.read_excel(
                    io.BytesIO(file_bytes),
                    sheet_name=self.sheet_name,
                    dtype=str,
                    keep_default_na=False,
                    na_values=[""],
                )
            except Exception as exc2:
                return ParseResult(
                    rows=[],
                    column_names=[],
                    parse_errors=[f"Cannot parse Excel file: {exc2}"],
                )

        if df is None or df.empty:
            return ParseResult(
                rows=[],
                column_names=[],
                parse_errors=["No data found in Excel file."],
            )

        if len(df) > self.MAX_ROWS:
            df = df.iloc[: self.MAX_ROWS]
            errors.append(f"File truncated to {self.MAX_ROWS} rows for safety.")

        # Normalise column names
        df.columns = [str(c).strip() for c in df.columns]

        # Replace Pandas NA with None
        df = df.where(pd.notna(df), None)

        rows = df.to_dict(orient="records")

        logger.info(
            "XLSX parsed",
            file=file_name,
            rows=len(rows),
            cols=len(df.columns),
        )

        return ParseResult(
            rows=rows,
            column_names=list(df.columns),
            parse_errors=errors,
        )

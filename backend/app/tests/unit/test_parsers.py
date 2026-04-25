"""
Unit tests: parsers.

Tests CSV and XLSX parsing with real sample data.
No database required.
"""
import io
import pytest

from app.integrations.parsers.csv_parser import CSVParser
from app.integrations.parsers.xlsx_parser import XLSXParser
from app.integrations.parsers.parser_factory import get_parser, is_supported
from app.core.errors import UnsupportedFileTypeError


SAMPLE_CSV = b"""payment_id,amount,currency,status
pay_001,5000.00,INR,succeeded
pay_002,12000.00,INR,succeeded
pay_003,3500.00,INR,failed
"""

SAMPLE_CSV_WITH_BOM = b"\xef\xbb\xbf" + SAMPLE_CSV  # UTF-8 BOM

SAMPLE_CSV_SEMICOLON = b"""payment_id;amount;currency;status
pay_001;5000.00;INR;succeeded
pay_002;12000.00;INR;succeeded
"""


class TestCSVParser:
    def test_parses_standard_csv(self):
        parser = CSVParser()
        result = parser.parse(SAMPLE_CSV, "test.csv")
        assert result.row_count == 3
        assert "payment_id" in result.column_names
        assert result.rows[0]["payment_id"] == "pay_001"
        assert result.rows[0]["amount"] == "5000.00"  # must be string
        assert not result.parse_errors or all("truncated" not in e.lower() for e in result.parse_errors)

    def test_parses_csv_with_bom(self):
        parser = CSVParser()
        result = parser.parse(SAMPLE_CSV_WITH_BOM, "test_bom.csv")
        assert result.row_count == 3
        assert "payment_id" in result.column_names  # BOM stripped

    def test_parses_semicolon_delimited(self):
        parser = CSVParser()
        result = parser.parse(SAMPLE_CSV_SEMICOLON, "test_semi.csv")
        assert result.row_count == 2
        assert "amount" in result.column_names

    def test_empty_csv_returns_empty(self):
        parser = CSVParser()
        result = parser.parse(b"", "empty.csv")
        assert result.row_count == 0
        assert len(result.parse_errors) > 0

    def test_all_values_are_strings(self):
        """Normalization phase converts types — parser must return strings only."""
        parser = CSVParser()
        result = parser.parse(SAMPLE_CSV, "test.csv")
        for row in result.rows:
            for v in row.values():
                assert v is None or isinstance(v, str), f"Expected str, got {type(v)}: {v}"

    def test_preview_limits_rows(self):
        parser = CSVParser()
        result = parser.preview_rows(SAMPLE_CSV, "test.csv", n=2)
        assert len(result.rows) == 2


class TestXLSXParser:
    def _make_xlsx(self) -> bytes:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(["payment_id", "amount", "currency", "status"])
        ws.append(["pay_001", "5000.00", "INR", "succeeded"])
        ws.append(["pay_002", "12000.00", "INR", "succeeded"])
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_parses_xlsx(self):
        parser = XLSXParser()
        result = parser.parse(self._make_xlsx(), "test.xlsx")
        assert result.row_count == 2
        assert "payment_id" in result.column_names

    def test_empty_xlsx_returns_empty(self):
        parser = XLSXParser()
        result = parser.parse(b"not-valid-xlsx", "bad.xlsx")
        assert result.row_count == 0
        assert result.parse_errors


class TestParserFactory:
    def test_returns_csv_parser_for_csv(self):
        parser = get_parser("file.csv")
        assert isinstance(parser, CSVParser)

    def test_returns_xlsx_parser_for_xlsx(self):
        parser = get_parser("file.xlsx")
        assert isinstance(parser, XLSXParser)

    def test_returns_xlsx_parser_for_xls(self):
        parser = get_parser("file.xls")
        assert isinstance(parser, XLSXParser)

    def test_raises_for_unsupported(self):
        with pytest.raises(UnsupportedFileTypeError):
            get_parser("file.pdf")

    def test_is_supported_csv(self):
        assert is_supported("data.csv") is True

    def test_is_supported_xlsx(self):
        assert is_supported("report.xlsx") is True

    def test_is_not_supported_pdf(self):
        assert is_supported("report.pdf") is False

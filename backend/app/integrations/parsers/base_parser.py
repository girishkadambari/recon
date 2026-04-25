"""
Base parser — shared contract for all file format parsers.
"""
import abc
import io
from dataclasses import dataclass, field


@dataclass
class ParseResult:
    """Output of a parse operation."""
    rows: list[dict]            # each dict is a raw row (str → Any)
    column_names: list[str]     # header column names as parsed
    row_count: int = 0
    parse_errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.row_count = len(self.rows)


class BaseParser(abc.ABC):
    """Abstract base class for file parsers."""

    MAX_ROWS = 100_000  # safety ceiling

    @abc.abstractmethod
    def parse(self, file_bytes: bytes, file_name: str = "") -> ParseResult:
        """
        Parse bytes into a ParseResult.
        Must not raise — capture errors in ParseResult.parse_errors instead.
        """
        ...

    def preview_rows(self, file_bytes: bytes, file_name: str = "", n: int = 20) -> ParseResult:
        """Parse and return only the first N rows (for preview endpoint)."""
        result = self.parse(file_bytes, file_name)
        result.rows = result.rows[:n]
        return result

"""
MatchingEngine — pure, deterministic reconciliation logic.
No database access. No AI. Takes two lists of dicts and returns matches + exceptions.

Strategies (applied in order, highest confidence first):
  1. EXACT_ID     — transaction_id or UTR exact match → 100
  2. AMOUNT_DATE  — exact gross_amount + date within SETTLEMENT_DATE_WINDOW_DAYS → 92
  3. AMOUNT_ONLY  — exact gross_amount, date absent or beyond window → 78
  4. FUZZY_AMOUNT — amount within AMOUNT_TOLERANCE_PCT tolerance → 62
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any
import uuid

from app.core.constants import (
    CONFIDENCE_EXACT,
    CONFIDENCE_HIGH_MIN,
    CONFIDENCE_MEDIUM_MIN,
    CONFIDENCE_LOW_MIN,
    CONFIDENCE_EXCEPTION_THRESHOLD,
    SETTLEMENT_DATE_WINDOW_DAYS,
)
from app.domain.enums.reconciliation_enums import (
    ExceptionReason,
    ExceptionStatus,
    FileRole,
    MatchStatus,
    MatchStrategy,
)

# Amount tolerance for fuzzy matching (5%)
AMOUNT_TOLERANCE_PCT = Decimal("0.05")

# Auto-confirm threshold
AUTO_CONFIRM_THRESHOLD = CONFIDENCE_HIGH_MIN


@dataclass
class MatchResult:
    source_record_id: uuid.UUID
    source_table: str
    target_record_id: uuid.UUID
    target_table: str
    confidence_score: int
    match_strategy: str
    status: str
    amount_delta: Decimal | None = None
    date_delta_days: int | None = None


@dataclass
class ExceptionResult:
    record_id: uuid.UUID
    record_table: str
    file_role: str
    reason: str
    amount: Decimal | None = None
    currency: str = "INR"
    details_json: dict[str, Any] | None = None


@dataclass
class EngineOutput:
    matches: list[MatchResult] = field(default_factory=list)
    exceptions: list[ExceptionResult] = field(default_factory=list)
    total_source: int = 0
    total_target: int = 0
    matched_count: int = 0
    exception_count: int = 0
    match_rate_pct: int = 0


class MatchingEngine:
    """
    Stateless reconciliation engine.
    Input: two lists of dicts (source_records, target_records).
    Each dict must have an 'id' key (UUID) and canonical field names.
    """

    def run(
        self,
        source_records: list[dict[str, Any]],
        target_records: list[dict[str, Any]],
        source_table: str,
        target_table: str,
    ) -> EngineOutput:
        output = EngineOutput(
            total_source=len(source_records),
            total_target=len(target_records),
        )

        if not source_records or not target_records:
            # All SOURCE rows are exceptions
            for rec in source_records:
                output.exceptions.append(ExceptionResult(
                    record_id=rec["id"],
                    record_table=source_table,
                    file_role=FileRole.SOURCE,
                    reason=ExceptionReason.UNMATCHED_SOURCE,
                    amount=rec.get("gross_amount") or rec.get("credit_amount"),
                    currency=rec.get("currency", "INR"),
                    details_json=_safe_details(rec),
                ))
            # All TARGET rows are exceptions
            for rec in target_records:
                output.exceptions.append(ExceptionResult(
                    record_id=rec["id"],
                    record_table=target_table,
                    file_role=FileRole.TARGET,
                    reason=ExceptionReason.UNMATCHED_TARGET,
                    amount=rec.get("gross_amount") or rec.get("credit_amount"),
                    currency=rec.get("currency", "INR"),
                    details_json=_safe_details(rec),
                ))
            output.exception_count = len(output.exceptions)
            return output

        # Track which records have been consumed
        matched_source_ids: set[uuid.UUID] = set()
        matched_target_ids: set[uuid.UUID] = set()

        # Build lookup indexes
        target_by_id = _index_by_id_fields(target_records)
        source_by_id = _index_by_id_fields(source_records)
        target_by_amount = _index_by_amount(target_records)

        # ── Strategy 1: EXACT_ID ─────────────────────────────────────
        for rec in source_records:
            src_id = rec["id"]
            if src_id in matched_source_ids:
                continue
            match_ids = _get_record_ids(rec)
            for mid in match_ids:
                if mid in target_by_id:
                    tgt = target_by_id[mid]
                    tgt_id = tgt["id"]
                    if tgt_id in matched_target_ids:
                        continue
                    amount_delta = _amount_delta(rec, tgt)
                    date_delta = _date_delta_days(rec, tgt)
                    output.matches.append(MatchResult(
                        source_record_id=src_id,
                        source_table=source_table,
                        target_record_id=tgt_id,
                        target_table=target_table,
                        confidence_score=CONFIDENCE_EXACT,
                        match_strategy=MatchStrategy.EXACT_ID,
                        status=MatchStatus.MATCHED,
                        amount_delta=amount_delta,
                        date_delta_days=date_delta,
                    ))
                    matched_source_ids.add(src_id)
                    matched_target_ids.add(tgt_id)
                    break

        # ── Strategy 2: AMOUNT_DATE ──────────────────────────────────
        for rec in source_records:
            src_id = rec["id"]
            if src_id in matched_source_ids:
                continue
            src_amount = _primary_amount(rec)
            if src_amount is None:
                continue
            candidates = target_by_amount.get(src_amount, [])
            best = _find_best_date_match(rec, candidates, matched_target_ids)
            if best:
                date_delta = _date_delta_days(rec, best)
                output.matches.append(MatchResult(
                    source_record_id=src_id,
                    source_table=source_table,
                    target_record_id=best["id"],
                    target_table=target_table,
                    confidence_score=92,
                    match_strategy=MatchStrategy.AMOUNT_DATE,
                    status=MatchStatus.MATCHED,
                    amount_delta=Decimal("0"),
                    date_delta_days=date_delta,
                ))
                matched_source_ids.add(src_id)
                matched_target_ids.add(best["id"])

        # ── Strategy 3: AMOUNT_ONLY ──────────────────────────────────
        for rec in source_records:
            src_id = rec["id"]
            if src_id in matched_source_ids:
                continue
            src_amount = _primary_amount(rec)
            if src_amount is None:
                continue
            candidates = [
                t for t in target_by_amount.get(src_amount, [])
                if t["id"] not in matched_target_ids
            ]
            if candidates:
                tgt = candidates[0]
                output.matches.append(MatchResult(
                    source_record_id=src_id,
                    source_table=source_table,
                    target_record_id=tgt["id"],
                    target_table=target_table,
                    confidence_score=78,
                    match_strategy=MatchStrategy.AMOUNT_ONLY,
                    status=MatchStatus.PENDING_REVIEW,
                    amount_delta=Decimal("0"),
                    date_delta_days=_date_delta_days(rec, tgt),
                ))
                matched_source_ids.add(src_id)
                matched_target_ids.add(tgt["id"])

        # ── Strategy 4: FUZZY_AMOUNT ─────────────────────────────────
        for rec in source_records:
            src_id = rec["id"]
            if src_id in matched_source_ids:
                continue
            src_amount = _primary_amount(rec)
            if src_amount is None:
                continue
            best_fuzzy = _find_fuzzy_amount_match(rec, target_records, matched_target_ids)
            if best_fuzzy:
                tgt, delta = best_fuzzy
                output.matches.append(MatchResult(
                    source_record_id=src_id,
                    source_table=source_table,
                    target_record_id=tgt["id"],
                    target_table=target_table,
                    confidence_score=62,
                    match_strategy=MatchStrategy.FUZZY_AMOUNT,
                    status=MatchStatus.PENDING_REVIEW,
                    amount_delta=delta,
                    date_delta_days=_date_delta_days(rec, tgt),
                ))
                matched_source_ids.add(src_id)
                matched_target_ids.add(tgt["id"])

        # ── Exceptions: unmatched source ─────────────────────────────
        for rec in source_records:
            src_id = rec["id"]
            if src_id not in matched_source_ids:
                output.exceptions.append(ExceptionResult(
                    record_id=src_id,
                    record_table=source_table,
                    file_role=FileRole.SOURCE,
                    reason=ExceptionReason.UNMATCHED_SOURCE,
                    amount=_primary_amount(rec),
                    currency=rec.get("currency", "INR"),
                    details_json=_safe_details(rec),
                ))

        # ── Exceptions: unmatched target ─────────────────────────────
        for rec in target_records:
            tgt_id = rec["id"]
            if tgt_id not in matched_target_ids:
                output.exceptions.append(ExceptionResult(
                    record_id=tgt_id,
                    record_table=target_table,
                    file_role=FileRole.TARGET,
                    reason=ExceptionReason.UNMATCHED_TARGET,
                    amount=_primary_amount(rec),
                    currency=rec.get("currency", "INR"),
                    details_json=_safe_details(rec),
                ))

        output.matched_count = len(output.matches)
        output.exception_count = len(output.exceptions)
        total = output.total_source + output.total_target
        if total > 0:
            output.match_rate_pct = int(
                (output.matched_count * 2 / total) * 100
            )
        return output


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_record_ids(rec: dict) -> list[str]:
    """Extract all ID values that might match a target record."""
    candidates = []
    for field in ("transaction_id", "payment_id", "settlement_id", "payout_id", "utr", "gateway_txn_id", "invoice_id", "reference"):
        val = rec.get(field)
        if val and str(val).strip():
            candidates.append(str(val).strip().lower())
    return candidates


def _index_by_id_fields(records: list[dict]) -> dict[str, dict]:
    """Build a lookup: id_value → record."""
    index: dict[str, dict] = {}
    for rec in records:
        for val in _get_record_ids(rec):
            if val not in index:
                index[val] = rec
    return index


def _primary_amount(rec: dict) -> Decimal | None:
    """Return the primary monetary amount for matching purposes."""
    for field in ("gross_amount", "net_amount", "credit_amount", "debit_amount"):
        val = rec.get(field)
        if val is not None:
            try:
                return Decimal(str(val))
            except Exception:
                pass
    return None


def _index_by_amount(records: list[dict]) -> dict[Decimal, list[dict]]:
    """Build a lookup: rounded_amount → [records]."""
    index: dict[Decimal, list[dict]] = {}
    for rec in records:
        amt = _primary_amount(rec)
        if amt is not None:
            index.setdefault(amt, []).append(rec)
    return index


def _find_best_date_match(
    source: dict,
    candidates: list[dict],
    matched_ids: set[uuid.UUID],
) -> dict | None:
    """Find the best date-proximate match from candidates."""
    src_date = _primary_date(source)
    best = None
    best_delta = None
    for tgt in candidates:
        if tgt["id"] in matched_ids:
            continue
        tgt_date = _primary_date(tgt)
        if src_date and tgt_date:
            delta = abs((src_date - tgt_date).days)
            if delta <= SETTLEMENT_DATE_WINDOW_DAYS:
                if best is None or delta < best_delta:
                    best = tgt
                    best_delta = delta
        elif src_date is None and tgt_date is None:
            # No dates available — take first
            if best is None:
                best = tgt
    return best


def _find_fuzzy_amount_match(
    source: dict,
    all_targets: list[dict],
    matched_ids: set[uuid.UUID],
) -> tuple[dict, Decimal] | None:
    """Find a target whose amount is within AMOUNT_TOLERANCE_PCT of source amount."""
    src_amt = _primary_amount(source)
    if src_amt is None or src_amt == 0:
        return None
    tolerance = src_amt * AMOUNT_TOLERANCE_PCT
    best = None
    best_delta = None
    for tgt in all_targets:
        if tgt["id"] in matched_ids:
            continue
        tgt_amt = _primary_amount(tgt)
        if tgt_amt is None:
            continue
        delta = abs(src_amt - tgt_amt)
        if delta <= tolerance:
            if best is None or delta < best_delta:
                best = tgt
                best_delta = delta
    if best is None:
        return None
    return best, best_delta


def _primary_date(rec: dict) -> datetime | None:
    for field in ("transaction_date", "settlement_date", "invoice_date"):
        val = rec.get(field)
        if val is not None:
            if isinstance(val, datetime):
                return val
            try:
                dt = datetime.fromisoformat(str(val))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                pass
    return None


def _date_delta_days(source: dict, target: dict) -> int | None:
    src_dt = _primary_date(source)
    tgt_dt = _primary_date(target)
    if src_dt and tgt_dt:
        return abs((src_dt - tgt_dt).days)
    return None


def _amount_delta(source: dict, target: dict) -> Decimal | None:
    src = _primary_amount(source)
    tgt = _primary_amount(target)
    if src is not None and tgt is not None:
        return abs(src - tgt)
    return None


def _safe_details(rec: dict) -> dict:
    """Return a JSON-safe subset of a record for exception context."""
    result = {}
    for k, v in rec.items():
        if k == "id":
            result[k] = str(v)
        elif isinstance(v, Decimal):
            result[k] = str(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, uuid.UUID):
            result[k] = str(v)
        elif isinstance(v, (str, int, float, bool, type(None))):
            result[k] = v
    return result

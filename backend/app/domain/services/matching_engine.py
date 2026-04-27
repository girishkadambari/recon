"""
MatchingEngine — pure, deterministic reconciliation logic.
No database access. No AI. Takes two lists of dicts and returns matches + exceptions.

Strategies (applied in order, highest confidence first):
    1. EXACT_ID      — transaction_id or UTR exact match → 100
    1.5 UTR          — Specific UTR field match (finance specific) → 98
    2. AMOUNT_DATE   — exact amount + date within SETTLEMENT_DATE_WINDOW_DAYS → 92
    2.5 SETTLEMENT_BATCH — Aggregate payment matching to settlement batch → 90
    3. AMOUNT_ONLY   — exact amount, date absent or beyond window → 75
    4. FUZZY_AMOUNT  — amount within AMOUNT_TOLERANCE_PCT tolerance → 62 (Requires PENDING_REVIEW)
"""
from __future__ import annotations
from typing import Optional
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
    FileRole,
    MatchStatus,
    MatchStrategy,
)
from app.domain.enums.exception_enums import ExceptionType

# Amount tolerance for fuzzy matching (5%)
AMOUNT_TOLERANCE_PCT = Decimal("0.05")


@dataclass
class MatchResult:
    source_record_id: uuid.UUID
    source_table: str
    target_record_id: uuid.UUID
    target_table: str
    confidence_score: int
    match_strategy: str
    status: str
    amount_delta: Optional[Decimal] = None
    date_delta_days: Optional[int] = None


@dataclass
class ExceptionResult:
    record_id: uuid.UUID
    record_table: str
    file_role: str
    reason: str
    amount: Optional[Decimal] = None
    currency: str = "INR"
    details_json: dict = field(default_factory=dict)
    severity: str = "MEDIUM"


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
    def run(
        self,
        source_records: list[dict],
        target_records: list[dict],
        source_table: str,
        target_table: str,
        phase: str = "GENERIC"
    ) -> EngineOutput:
        output = EngineOutput(
            total_source=len(source_records),
            total_target=len(target_records),
        )
        if not source_records and not target_records:
            return output

        src_role = _detect_role(source_table)
        tgt_role = _detect_role(target_table)

        matched_source_ids: set[uuid.UUID] = set()
        matched_target_ids: set[uuid.UUID] = set()

        # ── Strategy 0: Settlement Batching (Hierarchical) ──────────
        if src_role == "PAYMENT" and tgt_role == "SETTLEMENT":
            _handle_settlement_batch_matching(
                source_records, target_records, 
                matched_source_ids, matched_target_ids, 
                output, source_table, target_table
            )

        target_by_id = _index_by_id_fields(target_records, phase)

        # ── Strategy 1: EXACT_ID & UTR ──────────────────────────
        for rec in source_records:
            src_id = rec["id"]
            if not _is_settleable(rec, src_role): 
                continue
                
            # --- Strategy 1: EXPLICIT ID PAIRING Rules ---
            id_matched = False
            
            # Phase-specific pairing rules
            pairs = []
            if phase == "BILLING_TO_PAYMENT":
                pairs = [("order_id", "order_id"), ("invoice_id", "invoice_id"), ("invoice_id", "order_id")]
            elif phase == "PAYMENT_TO_SETTLEMENT":
                pairs = [("settlement_id", "settlement_id"), ("payout_id", "payout_id")]
            elif phase == "SETTLEMENT_TO_BANK":
                pairs = [("utr", "utr"), ("utr", "reference")]
            else:
                # Generic fallback: same-field matching
                fields = ("transaction_id", "payment_id", "settlement_id", "payout_id", "utr", "invoice_id", "order_id", "reference")
                pairs = [(f, f) for f in fields]

            for src_f, tgt_f in pairs:
                val = rec.get(src_f)
                if not val or not str(val).strip():
                    continue
                clean_val = str(val).strip().lower()
                
                # Field-aware lookup in target index
                tgt = target_by_id.get((tgt_f, clean_val))
                if tgt and tgt["id"] not in matched_target_ids:
                    if not _is_settleable(tgt, tgt_role):
                        continue
                        
                    # Directional Filter: If target is BANK, ensure it's a CREDIT for payments
                    if tgt_role == "BANK" and src_role == "PAYMENT" and _is_bank_debit(tgt):
                        continue
                        
                    src_amt = _get_match_amount(rec, src_role, tgt_role, phase)
                    tgt_amt = _get_match_amount(tgt, tgt_role, src_role, phase)
                    
                    strategy = MatchStrategy.UTR if src_f == "utr" else MatchStrategy.EXACT_ID
                    
                    if src_amt == tgt_amt:
                        status = MatchStatus.APPROVED # Exact ID + Amount = High Confidence
                        delta = Decimal("0")
                    else:
                        status = MatchStatus.PENDING_REVIEW
                        delta = (src_amt or 0) - (tgt_amt or 0)
                        reason = _detect_mismatch_reason(rec, tgt, src_role, tgt_role, phase)
                        output.exceptions.append(ExceptionResult(
                            record_id=src_id, record_table=source_table, file_role=FileRole.SOURCE,
                            reason=reason, amount=src_amt,
                            details_json={
                                "source_record": _safe_details(rec),
                                "target_record": _safe_details(tgt),
                                "match_strategy": strategy,
                                "expected_amount": str(src_amt),
                                "actual_amount": str(tgt_amt),
                                "delta_amount": str(delta)
                            },
                        ))
                    
                    output.matches.append(MatchResult(
                        source_record_id=src_id, source_table=source_table,
                        target_record_id=tgt["id"], target_table=target_table,
                        confidence_score=100 if status == MatchStatus.APPROVED else 95,
                        match_strategy=strategy, status=status, amount_delta=delta,
                    ))
                    matched_source_ids.add(src_id)
                    matched_target_ids.add(tgt["id"])
                    id_matched = True
                    break
            
            if id_matched: continue
        
        # ── Strategy 1.5: Substring UTR Match (Narration/Description) ──
        if phase == "SETTLEMENT_TO_BANK":
            for rec in source_records:
                if rec["id"] in matched_source_ids: continue
                utr = str(rec.get("utr") or "").strip().lower()
                if not utr: continue
                
                # Normalize UTR for robust searching (remove common separators)
                clean_utr = utr.replace("-", "").replace(" ", "").replace("/", "")
                if not clean_utr: continue
                
                for tgt in target_records:
                    if tgt["id"] in matched_target_ids: continue
                    narration = str(tgt.get("narration") or "").lower()
                    description = str(tgt.get("description") or "").lower()
                    
                    # Search for clean UTR in normalized narration/description
                    if clean_utr in narration.replace("-", "").replace(" ", "").replace("/", "") or \
                       clean_utr in description.replace("-", "").replace(" ", "").replace("/", ""):
                        
                        src_amt = _get_match_amount(rec, src_role, tgt_role, phase)
                        tgt_amt = _get_match_amount(tgt, tgt_role, src_role, phase)
                        
                        if src_amt == tgt_amt:
                            status = MatchStatus.APPROVED
                            delta = Decimal("0")
                        else:
                            status = MatchStatus.PENDING_REVIEW
                            delta = (src_amt or 0) - (tgt_amt or 0)
                            output.exceptions.append(ExceptionResult(
                                record_id=rec["id"], record_table=source_table, file_role=FileRole.SOURCE,
                                reason=ExceptionType.NET_SETTLEMENT_DIFF, amount=src_amt,
                                details_json={"expected": str(src_amt), "actual": str(tgt_amt), "delta": str(delta)}
                            ))

                        output.matches.append(MatchResult(
                            source_record_id=rec["id"], source_table=source_table,
                            target_record_id=tgt["id"], target_table=target_table,
                            confidence_score=98, match_strategy=MatchStrategy.UTR, status=status, amount_delta=delta
                        ))
                        matched_source_ids.add(rec["id"])
                        matched_target_ids.add(tgt["id"])
                        break

        # ── Strategy 2 & 3: AMOUNT Based (Date Window & Only) ────────
        # Pre-index by role-aware amount
        target_by_match_amount = {}
        for tgt in target_records:
            if tgt["id"] in matched_target_ids or not _is_settleable(tgt, tgt_role):
                continue
            amt = _get_match_amount(tgt, tgt_role, src_role, phase)
            if amt is not None:
                target_by_match_amount.setdefault(amt, []).append(tgt)

        for rec in source_records:
            src_id = rec["id"]
            if src_id in matched_source_ids or not _is_settleable(rec, src_role):
                continue
            src_amt = _get_match_amount(rec, src_role, tgt_role, phase)
            if src_amt is None: continue
            
            candidates = target_by_match_amount.get(src_amt, [])
            
            # Filter candidates: if both have phase-specific IDs, they MUST match or we skip amount matching
            src_ids = {v for _, v in _get_record_ids(rec, phase)}
            filtered_candidates = []
            for t in candidates:
                t_ids = {v for _, v in _get_record_ids(t, phase)}
                if src_ids and t_ids:
                    # Both have IDs but no intersection? Skip.
                    if not (src_ids & t_ids):
                        continue
                filtered_candidates.append(t)
            
            candidates = filtered_candidates

            # Strategy 2: Date Match
            date_candidates = [t for t in candidates if t["id"] not in matched_target_ids and _date_delta_days(rec, t) is not None and _date_delta_days(rec, t) <= SETTLEMENT_DATE_WINDOW_DAYS]
            if date_candidates:
                best = min(date_candidates, key=lambda t: _date_delta_days(rec, t))
                is_unique = len(date_candidates) == 1
                status = MatchStatus.MATCHED if is_unique else MatchStatus.PENDING_REVIEW
                
                output.matches.append(MatchResult(
                    source_record_id=src_id, source_table=source_table,
                    target_record_id=best["id"], target_table=target_table,
                    confidence_score=92, match_strategy=MatchStrategy.AMOUNT_DATE,
                    status=status, amount_delta=Decimal("0"),
                    date_delta_days=_date_delta_days(rec, best),
                ))
                matched_source_ids.add(src_id)
                matched_target_ids.add(best["id"])
                continue
            
            # Strategy 3: Amount Only (if date window fails)
            for tgt in candidates:
                if tgt["id"] not in matched_target_ids:
                    output.matches.append(MatchResult(
                        source_record_id=src_id, source_table=source_table,
                        target_record_id=tgt["id"], target_table=target_table,
                        confidence_score=75, match_strategy=MatchStrategy.AMOUNT_ONLY,
                        status=MatchStatus.PENDING_REVIEW, amount_delta=Decimal("0"),
                    ))
                    matched_source_ids.add(src_id)
                    matched_target_ids.add(tgt["id"])
                    break

        # ── Strategy 3.5: NET_SETTLEMENT (Formulas) ──────────────────
        if src_role == "PAYMENT" and tgt_role == "BANK":
            for rec in source_records:
                if rec["id"] in matched_source_ids or not _is_settleable(rec, src_role):
                    continue
                net_src = _net_settlement_amount(rec)
                if net_src == 0: continue
                # Look for bank record with exact net. Strategy 3.5 is redundant if Strategy 2 used net.
                # But here we allow cross-check.

        # ── Strategy 4: FUZZY_AMOUNT ─────────────────────────────────
        for rec in source_records:
            if rec["id"] in matched_source_ids or not _is_settleable(rec, src_role):
                continue
            res = _find_fuzzy_match(rec, target_records, matched_target_ids, src_role, tgt_role, phase)
            if res:
                tgt, delta = res
                output.matches.append(MatchResult(
                    source_record_id=rec["id"], source_table=source_table,
                    target_record_id=tgt["id"], target_table=target_table,
                    confidence_score=62, match_strategy=MatchStrategy.FUZZY_AMOUNT,
                    status=MatchStatus.PENDING_REVIEW, amount_delta=delta,
                ))
                matched_source_ids.add(rec["id"])
                matched_target_ids.add(tgt["id"])

        # ── Exceptions: Unmatched ────────────────────────────────────
        for rec in source_records:
            if rec["id"] not in matched_source_ids:
                if not _is_settleable(rec, src_role): continue
                reason = _classify_unmatched(rec, src_role, phase, is_source=True)
                output.exceptions.append(ExceptionResult(
                    record_id=rec["id"], record_table=source_table, file_role=FileRole.SOURCE,
                    reason=reason, amount=_get_match_amount(rec, src_role, tgt_role, phase),
                    details_json={**_safe_details(rec), "role": src_role, "phase": phase},
                    severity="HIGH" if src_role == "BANK" else "MEDIUM",
                ))

        for rec in target_records:
            if rec["id"] not in matched_target_ids:
                if not _is_settleable(rec, tgt_role): continue
                if tgt_role == "BANK" and _is_bank_debit(rec): continue
                
                reason = _classify_unmatched(rec, tgt_role, phase, is_source=False)
                if tgt_role == "BANK" and _is_potential_offline(rec):
                    reason = ExceptionType.OFFLINE_PAYMENT_CANDIDATE
                
                output.exceptions.append(ExceptionResult(
                    record_id=rec["id"], record_table=target_table, file_role=FileRole.TARGET,
                    reason=reason, amount=_get_match_amount(rec, tgt_role, src_role, phase),
                    details_json={**_safe_details(rec), "role": tgt_role, "phase": phase},
                ))

        output.matched_count = len(output.matches)
        output.exception_count = len(output.exceptions)
        total = output.total_source + output.total_target
        if total > 0:
            output.match_rate_pct = int((output.matched_count * 2 / total) * 100)
        return output


# ── Private helpers ───────────────────────────────────────────────────────────

def _detect_role(table_name: str) -> str:
    name = table_name.lower()
    if any(k in name for k in ("billing", "invoice", "sales")): return "BILLING"
    if any(k in name for k in ("settlement", "payout")): return "SETTLEMENT"
    if any(k in name for k in ("stripe", "razorpay", "gateway", "payment")): return "PAYMENT"
    if "bank" in name: return "BANK"
    return "SOURCE"

def _is_settleable(rec: dict, role: str) -> bool:
    if role != "PAYMENT": return True
    status = _normalize_status(rec)
    if status in ("failed", "failure", "cancelled", "canceled", "void", "voided", "expired", "disputed", "refunded"):
        return False
    if status == "authorized" and not rec.get("captured"):
        return False
    return True

def _normalize_status(rec: dict) -> str:
    for field in ("status", "payment_status", "transaction_status"):
        val = rec.get(field)
        if val: return str(val).strip().lower()
    return "captured"

def _get_match_amount(rec: dict, role: str, other_role: Optional[str] = None, phase: str = "GENERIC") -> Optional[Decimal]:
    if phase == "BILLING_TO_PAYMENT":
        if role == "BILLING": return _billing_amount(rec)
        if role == "PAYMENT": return _payment_gross_amount(rec)
    
    if phase == "PAYMENT_TO_SETTLEMENT":
        if role == "PAYMENT": return _payment_net_amount(rec)
        if role == "SETTLEMENT": return _settlement_amount(rec)
        
    if phase == "SETTLEMENT_TO_BANK":
        if role == "SETTLEMENT": return _settlement_amount(rec)
        if role == "BANK": return _bank_credit_amount(rec)
        
    if phase == "PAYMENT_TO_BANK_DIRECT":
        if role == "PAYMENT": return _payment_net_amount(rec)
        if role == "BANK": return _bank_credit_amount(rec)

    # Fallbacks for generic or unknown phases
    if role == "SETTLEMENT": return _settlement_amount(rec)
    if role == "PAYMENT": return _payment_net_amount(rec)
    if role == "BANK": return _bank_credit_amount(rec)
    return _primary_amount(rec)

def _billing_amount(rec: dict) -> Optional[Decimal]:
    return _primary_amount(rec)

def _payment_gross_amount(rec: dict) -> Optional[Decimal]:
    return _primary_amount(rec)

def _payment_net_amount(rec: dict) -> Optional[Decimal]:
    # Prefer explicit provider net_amount if present
    net = rec.get("net_amount")
    if net is not None:
        try: return Decimal(str(net))
        except: pass
    return _calculate_net_settlement(rec)

def _settlement_amount(rec: dict) -> Optional[Decimal]:
    for f in ("settlement_amount", "net_amount", "amount", "credit_amount", "gross_amount"):
        val = rec.get(f)
        if val is not None:
            try: return Decimal(str(val))
            except: pass
    return None

def _bank_credit_amount(rec: dict) -> Optional[Decimal]:
    credit = rec.get("credit_amount")
    if credit is not None: return Decimal(str(credit))
    # Fallback if only 'amount' field exists and it's positive
    amt = _primary_amount(rec)
    return amt if amt and amt > 0 else None

def _calculate_net_settlement(rec: dict) -> Decimal:
    gross = _primary_amount(rec) or Decimal("0")
    fee = Decimal(str(rec.get("fee_amount") or "0"))
    tax = Decimal(str(rec.get("tax_amount") or "0"))
    refund = Decimal(str(rec.get("refund_amount") or "0"))
    adj = Decimal(str(rec.get("adjustment_amount") or "0"))
    return (gross - fee - tax - refund + adj).quantize(Decimal("0.01"))

def _is_bank_debit(rec: dict) -> bool:
    debit = rec.get("debit_amount")
    if debit and Decimal(str(debit)) > 0: return True
    amt = _primary_amount(rec)
    return bool(amt and amt < 0)

def _detect_mismatch_reason(src: dict, tgt: dict, src_role: str, tgt_role: str, phase: str) -> str:
    if phase == "SETTLEMENT_TO_BANK":
        return ExceptionType.NET_SETTLEMENT_DIFF
    if src_role == "PAYMENT" and tgt_role == "BANK":
        return ExceptionType.NET_SETTLEMENT_DIFF
    return ExceptionType.AMOUNT_MISMATCH

def _classify_unmatched(rec: dict, role: str, phase: str, is_source: bool) -> str:
    if phase == "BILLING_TO_PAYMENT":
        return ExceptionType.MISSING_PAYMENT if is_source else ExceptionType.MISSING_INVOICE
    
    if phase == "PAYMENT_TO_SETTLEMENT":
        if is_source:
            sid = rec.get("settlement_id")
            return ExceptionType.MISSING_SETTLEMENT if sid else ExceptionType.UNSETTLED_PAYMENT
        return ExceptionType.UNKNOWN_SETTLEMENT
    
    if phase == "SETTLEMENT_TO_BANK":
        return ExceptionType.MISSING_BANK_CREDIT if is_source else ExceptionType.UNKNOWN_BANK_CREDIT
        
    if phase == "PAYMENT_TO_BANK_DIRECT":
        return ExceptionType.MISSING_BANK_CREDIT if is_source else ExceptionType.UNKNOWN_BANK_CREDIT

    # Default fallbacks
    if role == "BILLING": return ExceptionType.MISSING_PAYMENT
    if role == "PAYMENT": return ExceptionType.MISSING_BANK_CREDIT
    if role == "BANK": return ExceptionType.UNKNOWN_BANK_CREDIT
    return ExceptionType.NEEDS_MANUAL_REVIEW

def _is_potential_offline(rec: dict) -> bool:
    narration = str(rec.get("narration") or "").upper()
    description = str(rec.get("description") or "").upper()
    combined = f"{narration} {description}"
    keywords = (
        "CHEQUE", "CHQ", "CASH", "OFFLINE", "DEPOSIT", 
        "NEFT", "IMPS", "RTGS", "UPI", "TRANSFER", "CASH DEP"
    )
    return any(kw in combined for kw in keywords)

def _handle_settlement_batch_matching(
    source_records: list[dict],
    target_records: list[dict],
    matched_source_ids: set[uuid.UUID],
    matched_target_ids: set[uuid.UUID],
    output: EngineOutput,
    source_table: str,
    target_table: str
):
    """
    Groups payments by settlement_id and matches them to settlement records.
    """
    # Group unmatched source payments by settlement_id
    src_groups = {}
    for rec in source_records:
        if rec["id"] in matched_source_ids: continue
        sid = rec.get("settlement_id")
        if sid:
            src_groups.setdefault(str(sid).strip().lower(), []).append(rec)
            
    # Index unmatched targets by settlement_id
    tgt_map = {}
    for rec in target_records:
        if rec["id"] in matched_target_ids: continue
        sid = rec.get("settlement_id")
        if sid:
            tgt_map[str(sid).strip().lower()] = rec
            
    for sid, payments in src_groups.items():
        tgt = tgt_map.get(sid)
        if not tgt: continue
        
        # In a settlement batch, we match all payments to this settlement record
        sum_net = sum(_net_settlement_amount(p) for p in payments)
        tgt_net = _settlement_amount(tgt) or Decimal("0")
        
        # Determine status based on amount match
        if sum_net == tgt_net:
            status = MatchStatus.APPROVED
            delta = Decimal("0")
        else:
            status = MatchStatus.PENDING_REVIEW
            delta = sum_net - tgt_net
            # Log variance exception at settlement level
            output.exceptions.append(ExceptionResult(
                record_id=tgt["id"], record_table=target_table, file_role=FileRole.TARGET,
                reason=ExceptionType.SETTLEMENT_BATCH_AMOUNT_DIFF, amount=delta,
                details_json={
                    "variance_type": "SETTLEMENT_BATCH_AMOUNT_DIFF",
                    "sum_payments_net": str(sum_net), 
                    "settlement_net": str(tgt_net),
                    "delta": str(delta)
                }
            ))
            
        for p in payments:
            output.matches.append(MatchResult(
                source_record_id=p["id"], source_table=source_table,
                target_record_id=tgt["id"], target_table=target_table,
                confidence_score=100 if status == MatchStatus.APPROVED else 90,
                match_strategy=MatchStrategy.SETTLEMENT_BATCH,
                status=status, amount_delta=Decimal("0") # Do not distribute delta across children
            ))
            matched_source_ids.add(p["id"])
        
        matched_target_ids.add(tgt["id"])

def _get_record_ids(rec: dict, phase: str = "GENERIC") -> list[tuple[str, str]]:
    candidates = []
    
    # Phase-specific allowed identifiers to prevent cross-field false matches
    if phase == "BILLING_TO_PAYMENT":
        fields = ("order_id", "invoice_id")
    elif phase == "PAYMENT_TO_SETTLEMENT":
        fields = ("settlement_id", "payout_id")
    elif phase == "SETTLEMENT_TO_BANK":
        fields = ("utr", "reference")
    else:
        fields = ("transaction_id", "payment_id", "settlement_id", "payout_id", "utr", "gateway_txn_id", "invoice_id", "order_id", "reference")
        
    for f in fields:
        val = rec.get(f)
        if val and str(val).strip():
            candidates.append((f, str(val).strip().lower()))
    return candidates

def _index_by_id_fields(records: list[dict], phase: str = "GENERIC") -> dict[tuple[str, str], dict]:
    index = {}
    for rec in records:
        # Field-aware indexing: we map (field_name, value) -> record
        for field_name, val in _get_record_ids(rec, phase):
            # Special case for SETTLEMENT_TO_BANK: source.utr matches target.reference
            if phase == "SETTLEMENT_TO_BANK" and field_name == "reference":
                 # If target has reference, we also index it as 'utr' to allow direct lookup
                 index[("utr", val)] = rec
            
            index[(field_name, val)] = rec
    return index

def _find_best_date_match(source: dict, candidates: list[dict], matched_ids: set[uuid.UUID]) -> Optional[dict]:
    src_date = _primary_date(source)
    best, best_delta = None, None
    for tgt in candidates:
        if tgt["id"] in matched_ids: continue
        tgt_date = _primary_date(tgt)
        if src_date and tgt_date:
            delta = abs((src_date - tgt_date).days)
            if delta <= SETTLEMENT_DATE_WINDOW_DAYS:
                if best is None or delta < best_delta:
                    best, best_delta = tgt, delta
    return best

def _find_fuzzy_match(source: dict, targets: list[dict], matched_ids: set[uuid.UUID], src_role: str, tgt_role: str, phase: str = "GENERIC") -> Optional[tuple[dict, Decimal]]:
    src_amt = _get_match_amount(source, src_role, tgt_role, phase)
    if src_amt is None: return None
    tol = src_amt * AMOUNT_TOLERANCE_PCT
    best, best_delta = None, None
    for tgt in targets:
        if tgt["id"] in matched_ids or not _is_settleable(tgt, tgt_role): continue
        tgt_amt = _get_match_amount(tgt, tgt_role, src_role, phase)
        if tgt_amt is None: continue
        delta = abs(src_amt - tgt_amt)
        if delta <= tol:
            if best is None or delta < best_delta:
                best, best_delta = tgt, delta
    return (best, best_delta) if best else None

def _primary_date(rec: dict) -> Optional[datetime]:
    for f in ("transaction_date", "settlement_date", "invoice_date", "created_at", "date"):
        val = rec.get(f)
        if val:
            if isinstance(val, datetime): return val
            try:
                dt = datetime.fromisoformat(str(val))
                if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except: pass
    return None

def _primary_amount(rec: dict) -> Optional[Decimal]:
    # Removed 'balance' as per requirement
    for f in ("gross_amount", "net_amount", "credit_amount", "debit_amount", "amount"):
        val = rec.get(f)
        if val is not None:
            try: return Decimal(str(val))
            except: pass
    return None

def _net_settlement_amount(rec: dict) -> Decimal:
    # Use the helper defined above
    return _payment_net_amount(rec) or Decimal("0")

def _date_delta_days(source: dict, target: dict) -> Optional[int]:
    s, t = _primary_date(source), _primary_date(target)
    return abs((s - t).days) if s and t else None

def _safe_details(rec: dict) -> dict:
    res = {}
    for k, v in rec.items():
        if k == "id": res[k] = str(v)
        elif isinstance(v, Decimal): res[k] = str(v)
        elif isinstance(v, datetime): res[k] = v.isoformat()
        elif isinstance(v, uuid.UUID): res[k] = str(v)
        elif isinstance(v, (str, int, float, bool, type(None))): res[k] = v
    return res
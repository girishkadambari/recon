"""
Money utilities — all monetary values must use Decimal, never float.
"""
from typing import Optional
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any


ZERO = Decimal("0")
MONEY_QUANTIZE = Decimal("0.000001")  # 6 decimal places (NUMERIC 18,6)


def parse_decimal(value: Any, field_name: str = "amount") -> Decimal:
    """
    Safely parse a value to Decimal.
    Raises ValueError if the value cannot be converted.
    """
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        # Strip common formatting (commas, currency symbols, whitespace)
        cleaned = value.strip().replace(",", "").replace("₹", "").replace("$", "").replace("£", "")
        if not cleaned or cleaned == "-":
            return ZERO
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            raise ValueError(f"Cannot parse '{value}' as a decimal for field '{field_name}'")
    raise ValueError(f"Unsupported type {type(value).__name__} for field '{field_name}'")


def parse_decimal_or_none(value: Any, field_name: str = "amount") -> Optional[Decimal]:
    """Returns None if the value is None or empty, otherwise parses to Decimal."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return parse_decimal(value, field_name)


def round_money(value: Decimal, places: int = 2) -> Decimal:
    """Round a Decimal to N decimal places using ROUND_HALF_UP."""
    quantize_str = Decimal("0." + "0" * places) if places > 0 else Decimal("1")
    return value.quantize(quantize_str, rounding=ROUND_HALF_UP)


def is_amount_match(
    a: Decimal,
    b: Decimal,
    tolerance: Decimal = Decimal("0.01"),
) -> bool:
    """
    Returns True if two amounts are within tolerance of each other.
    Default tolerance is 0.01 (1 paisa / 1 cent).
    """
    return abs(a - b) <= tolerance


def net_settlement_formula(
    gross_amount: Decimal,
    fee_amount: Decimal = ZERO,
    tax_amount: Decimal = ZERO,
    refund_amount: Decimal = ZERO,
    adjustment_amount: Decimal = ZERO,
) -> Decimal:
    """
    Calculate net settlement amount per the standard formula:
        net = gross - fee - tax - refunds + adjustments
    """
    return gross_amount - fee_amount - tax_amount - refund_amount + adjustment_amount
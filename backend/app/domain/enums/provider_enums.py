"""
Payment provider enums.
"""
from enum import StrEnum


class PaymentProvider(StrEnum):
    STRIPE = "STRIPE"
    RAZORPAY = "RAZORPAY"
    CHARGEBEE = "CHARGEBEE"
    UNKNOWN = "UNKNOWN"

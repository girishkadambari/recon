"""
Payment provider enums.
"""
from enum import Enum


class PaymentProvider(str, Enum):
    STRIPE = "STRIPE"
    RAZORPAY = "RAZORPAY"
    CHARGEBEE = "CHARGEBEE"
    UNKNOWN = "UNKNOWN"

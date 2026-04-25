"""
Application-wide constants.
"""

# Confidence score thresholds (see reconciliation logic section)
CONFIDENCE_EXACT = 100
CONFIDENCE_HIGH_MIN = 90
CONFIDENCE_MEDIUM_MIN = 75
CONFIDENCE_LOW_MIN = 50
CONFIDENCE_EXCEPTION_THRESHOLD = 50  # below this, create exception

# Date window for settlement-to-bank matching (days)
SETTLEMENT_DATE_WINDOW_DAYS = 5

# Max sample rows to send to AI for column mapping
AI_COLUMN_MAPPING_SAMPLE_ROWS = 5

# Default workspace role for the first user
DEFAULT_WORKSPACE_ROLE = "OWNER"

# Audit event entity types
ENTITY_TYPE_USER = "user"
ENTITY_TYPE_WORKSPACE = "workspace"
ENTITY_TYPE_UPLOADED_FILE = "uploaded_file"
ENTITY_TYPE_RECONCILIATION_RUN = "reconciliation_run"
ENTITY_TYPE_MATCH_CANDIDATE = "match_candidate"
ENTITY_TYPE_EXCEPTION_ITEM = "exception_item"
ENTITY_TYPE_EXPORT_JOB = "export_job"

# File constraints
MAX_PREVIEW_ROWS = 20

# Currency defaults
DEFAULT_CURRENCY = "INR"

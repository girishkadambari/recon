"""
AI Column Mapping Service.
Uses Claude to suggest canonical field mappings for raw CSV/XLSX columns.
"""
import json
import os
from pathlib import Path
from typing import Any

import structlog

from app.ai.services.ai_client import complete_json, DEFAULT_MODEL
from app.core.errors import AIServiceError
from app.domain.enums.mapping_enums import CanonicalField

logger = structlog.get_logger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "column_mapping_prompt.md"
VALID_CANONICAL_FIELDS = {f.value for f in CanonicalField}


def suggest_column_mapping(
    file_category: str,
    column_names: list[str],
    sample_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Ask Claude to suggest a column mapping.

    Returns:
        {
            "mapping": {"raw_col": "canonical_field", ...},
            "confidence_score": 87,
            "notes": "..."
        }

    The mapping is advisory — user must confirm it before normalization runs.
    """
    if not column_names:
        raise AIServiceError("No column names provided for mapping suggestion.")

    # Load and fill prompt template
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")

    # Format sample rows as JSON string (capped at 5 rows)
    sample_str = json.dumps(sample_rows[:5], default=str, indent=2, ensure_ascii=False)

    prompt = prompt_template.format(
        file_category=file_category,
        column_names=json.dumps(column_names, ensure_ascii=False),
        sample_rows=sample_str,
    )

    system_prompt = (
        "You are a financial data expert. Always respond with valid JSON only. "
        "Never include explanatory text outside the JSON object."
    )

    logger.info(
        "Requesting AI column mapping suggestion",
        file_category=file_category,
        column_count=len(column_names),
    )

    result = complete_json(
        prompt=prompt,
        system=system_prompt,
        max_tokens=1024,
    )

    # Validate the response
    mapping = result.get("mapping", {})
    confidence = result.get("confidence_score", 0)

    # Ensure all suggested canonical fields are valid; default to "ignore" if not
    validated_mapping: dict[str, str] = {}
    for raw_col in column_names:
        suggested = mapping.get(raw_col, "ignore")
        if suggested not in VALID_CANONICAL_FIELDS:
            logger.warning(
                "AI suggested invalid canonical field — defaulting to ignore",
                raw_col=raw_col,
                suggested=suggested,
            )
            suggested = CanonicalField.IGNORE
        validated_mapping[raw_col] = suggested

    logger.info(
        "AI column mapping complete",
        confidence_score=confidence,
        mapped_fields=len([v for v in validated_mapping.values() if v != "ignore"]),
    )

    return {
        "mapping": validated_mapping,
        "confidence_score": min(max(int(confidence), 0), 100),
        "notes": result.get("notes", ""),
    }

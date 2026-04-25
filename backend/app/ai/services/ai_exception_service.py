"""
AI Exception Explanation Service.
Calls Claude to explain why a specific reconciliation exception occurred.
"""
import json
from pathlib import Path
from typing import Any

import structlog

from app.ai.services.ai_client import complete_json, DEFAULT_MODEL
from app.core.errors import AIServiceError

logger = structlog.get_logger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "exception_explanation_prompt.md"
SUMMARY_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "run_summary_prompt.md"

SYSTEM_PROMPT = (
    "You are a financial reconciliation expert. "
    "Always respond with valid JSON only. "
    "Use clear, professional language suitable for a finance team."
)


def explain_exception(
    run_name: str,
    source_category: str,
    target_category: str,
    match_rate_pct: int,
    file_role: str,
    reason_code: str,
    amount: str,
    currency: str,
    record_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Ask Claude to explain why a specific exception occurred.

    Returns:
        {
            "explanation": str,
            "probable_cause": str,
            "recommended_action": str,
            "confidence": "HIGH" | "MEDIUM" | "LOW"
        }
    """
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")

    replacements = {
        "{run_name}": run_name,
        "{source_category}": source_category,
        "{target_category}": target_category,
        "{match_rate_pct}": str(match_rate_pct),
        "{file_role}": file_role,
        "{reason_code}": reason_code,
        "{amount}": amount,
        "{currency}": currency,
        "{record_data}": json.dumps(record_data, default=str, indent=2, ensure_ascii=False),
    }
    prompt = prompt_template
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)

    logger.info(
        "Requesting AI exception explanation",
        run_name=run_name,
        reason_code=reason_code,
        amount=amount,
    )

    result = complete_json(prompt=prompt, system=SYSTEM_PROMPT, max_tokens=512)

    # Ensure required fields are present
    explanation = result.get("explanation", "Unable to generate explanation.")
    cause = result.get("probable_cause", "Unknown")
    action = result.get("recommended_action", "Manual review required.")
    confidence = result.get("confidence", "LOW")

    if confidence not in ("HIGH", "MEDIUM", "LOW"):
        confidence = "LOW"

    return {
        "explanation": explanation,
        "probable_cause": cause,
        "recommended_action": action,
        "confidence": confidence,
    }


def generate_run_summary(
    run_name: str,
    completed_at: str,
    source_category: str,
    target_category: str,
    total_source_rows: int,
    total_target_rows: int,
    matched_count: int,
    match_rate_pct: int,
    exception_count: int,
    exception_breakdown: dict[str, int],
    strategy_breakdown: dict[str, int],
) -> dict[str, Any]:
    """
    Ask Claude to generate a run-level executive summary.

    Returns:
        {
            "headline": str,
            "summary": str,
            "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
            "key_findings": [str],
            "recommended_actions": [str],
            "requires_immediate_attention": bool
        }
    """
    prompt_template = SUMMARY_PROMPT_PATH.read_text(encoding="utf-8")

    # Format breakdowns as readable strings
    exc_breakdown_str = "\n".join(
        f"- {reason}: {count} record(s)"
        for reason, count in exception_breakdown.items()
    ) or "No exceptions."

    strategy_breakdown_str = "\n".join(
        f"- {strategy}: {count} match(es)"
        for strategy, count in strategy_breakdown.items()
    ) or "No matches found."

    replacements = {
        "{run_name}": run_name,
        "{completed_at}": completed_at,
        "{source_category}": source_category,
        "{target_category}": target_category,
        "{total_source_rows}": str(total_source_rows),
        "{total_target_rows}": str(total_target_rows),
        "{matched_count}": str(matched_count),
        "{match_rate_pct}": str(match_rate_pct),
        "{exception_count}": str(exception_count),
        "{exception_breakdown}": exc_breakdown_str,
        "{strategy_breakdown}": strategy_breakdown_str,
    }
    prompt = prompt_template
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)

    logger.info(
        "Requesting AI run summary",
        run_name=run_name,
        match_rate_pct=match_rate_pct,
        exceptions=exception_count,
    )

    result = complete_json(prompt=prompt, system=SYSTEM_PROMPT, max_tokens=1024)

    return {
        "headline": result.get("headline", f"{run_name} — Reconciliation Complete"),
        "summary": result.get("summary", ""),
        "risk_level": result.get("risk_level", "MEDIUM"),
        "key_findings": result.get("key_findings", []),
        "recommended_actions": result.get("recommended_actions", []),
        "requires_immediate_attention": result.get("requires_immediate_attention", False),
    }

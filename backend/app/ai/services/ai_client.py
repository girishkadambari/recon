"""
Anthropic AI client — thin wrapper around the Anthropic Python SDK.
Isolated from all business logic. All AI calls go through this module.
"""
import json
import os
import re
import structlog
from typing import Any

import anthropic

from app.config import get_settings
from app.core.errors import AIServiceError

logger = structlog.get_logger(__name__)
settings = get_settings()

# Default model — claude-3-5-haiku is fast and cheap for structured tasks
DEFAULT_MODEL = "claude-3-5-haiku-20241022"
# For high-stakes explanation tasks
EXPLANATION_MODEL = "claude-3-5-sonnet-20241022"


def _get_client() -> anthropic.Anthropic:
    """Return a configured Anthropic client."""
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        raise AIServiceError(
            "ANTHROPIC_API_KEY is not configured. "
            "Set it in your .env file to use AI features."
        )
    return anthropic.Anthropic(api_key=api_key)


def complete(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    system: str | None = None,
) -> str:
    """
    Send a prompt to Claude and return the raw text response.
    Raises AIServiceError on failure.
    """
    client = _get_client()
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    try:
        response = client.messages.create(**kwargs)
        text = response.content[0].text
        logger.info(
            "AI response received",
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return text
    except anthropic.APIStatusError as exc:
        logger.error("Anthropic API error", status=exc.status_code, error=str(exc))
        raise AIServiceError(f"AI service error ({exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        logger.error("Anthropic connection error", error=str(exc))
        raise AIServiceError("Could not connect to AI service. Check your network.") from exc


def complete_json(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    system: str | None = None,
) -> dict[str, Any]:
    """
    Same as complete() but parses and returns the JSON response.
    Raises AIServiceError if the response is not valid JSON.
    """
    raw = complete(prompt, model=model, max_tokens=max_tokens, system=system)
    return _extract_json(raw)


def _extract_json(text: str) -> dict[str, Any]:
    """
    Extract a JSON object from model output.
    Handles markdown code fences: ```json ... ```
    """
    # Strip markdown code fences
    stripped = re.sub(r"```(?:json)?\s*", "", text).strip()
    stripped = stripped.rstrip("```").strip()

    # Find the first { ... } block
    start = stripped.find("{")
    end = stripped.rfind("}") + 1
    if start == -1 or end == 0:
        raise AIServiceError(
            f"AI response did not contain a JSON object. "
            f"Raw response: {text[:300]}"
        )
    try:
        return json.loads(stripped[start:end])
    except json.JSONDecodeError as exc:
        raise AIServiceError(
            f"AI response is not valid JSON: {exc}. "
            f"Raw response: {text[:300]}"
        ) from exc

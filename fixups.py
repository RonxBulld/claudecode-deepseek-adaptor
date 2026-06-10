"""
Provider-specific fixups for API request/response bodies.

These fixups handle incompatibilities between what Claude Code sends
(Anthropic API format) and what specific backend providers accept.
"""

from typing import Any


def fix_thinking_reasoning_effort_conflict(body: dict[str, Any]) -> dict[str, Any]:
    """
    DeepSeek rejects `thinking.type=disabled` when `reasoning_effort` is also set.

    Error: "400 thinking options type cannot be disabled when reasoning_effort is set"

    Fix: When thinking is explicitly disabled, remove reasoning_effort entirely.
    The user's intent is to disable thinking mode, so reasoning_effort is irrelevant.
    """
    thinking = body.get("thinking")
    if thinking and isinstance(thinking, dict) and thinking.get("type") == "disabled":
        if "reasoning_effort" in body:
            body = body.copy()
            del body["reasoning_effort"]
    return body


def fix_thinking_budget_tokens(body: dict[str, Any]) -> dict[str, Any]:
    """
    DeepSeek's `thinking` object doesn't use `budget_tokens` (Anthropic-specific).
    Strip it to avoid potential 400 errors.
    """
    thinking = body.get("thinking")
    if thinking and isinstance(thinking, dict) and "budget_tokens" in thinking:
        body = body.copy()
        thinking = thinking.copy()
        del thinking["budget_tokens"]
        if not thinking:  # empty dict after stripping
            del body["thinking"]
        else:
            body["thinking"] = thinking
    return body


def apply_all(body: dict[str, Any]) -> dict[str, Any]:
    """Apply all DeepSeek-specific fixups."""
    body = fix_thinking_reasoning_effort_conflict(body)
    body = fix_thinking_budget_tokens(body)
    return body

"""
Provider-specific fixups for API request/response bodies.

These fixups handle incompatibilities between what Claude Code sends
(Anthropic API format) and what specific backend providers accept.

Currently targets DeepSeek's /anthropic endpoint.
"""

from typing import Any

# Sampling parameters that DeepSeek thinking mode ignores (or Anthropic Opus 4.7+ rejects).
_SAMPLING_PARAMS = {"temperature", "top_p", "top_k"}

# output_config keys that DeepSeek supports.
_SUPPORTED_OUTPUT_CONFIG_KEYS = {"effort"}


def fix_thinking_adaptive(body: dict[str, Any]) -> dict[str, Any]:
    """
    Convert `thinking.type = "adaptive"` to `"enabled"`.

    DeepSeek's /anthropic endpoint only documents ``"enabled"`` and
    ``"disabled"`` for ``thinking.type``.  Claude Code (Opus 4.6+) sends
    ``"adaptive"`` — convert it to ``"enabled"``, letting
    ``output_config.effort`` control thinking depth.
    """
    thinking = body.get("thinking")
    if thinking and isinstance(thinking, dict) and thinking.get("type") == "adaptive":
        body = body.copy()
        body["thinking"] = {**thinking, "type": "enabled"}
    return body


def fix_thinking_display(body: dict[str, Any]) -> dict[str, Any]:
    """
    Strip ``display`` from the ``thinking`` object.

    Anthropic Opus 4.7+ supports ``thinking.display`` (``"summarized"`` |
    ``"omitted"``) — DeepSeek does not document this field.  Remove it so
    it doesn't cause a 400 error.  If ``thinking`` becomes empty after
    stripping, remove it entirely.
    """
    thinking = body.get("thinking")
    if thinking and isinstance(thinking, dict) and "display" in thinking:
        body = body.copy()
        thinking = thinking.copy()
        del thinking["display"]
        if not thinking:
            del body["thinking"]
        else:
            body["thinking"] = thinking
    return body


def fix_thinking_budget_tokens(body: dict[str, Any]) -> dict[str, Any]:
    """
    Strip Anthropic-specific ``budget_tokens`` from the ``thinking`` object.

    DeepSeek's docs state that ``budget_tokens`` is ignored, but stripping
    it avoids potential 400s and keeps the request clean.

    Also handles degenerate cases:
    - ``thinking: {}`` (empty dict) → removed
    - ``thinking: None`` → left alone (thinking not set)
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


def fix_thinking_sampling_params(body: dict[str, Any]) -> dict[str, Any]:
    """
    Strip ``temperature``, ``top_p``, and ``top_k`` when thinking is active.

    DeepSeek's thinking mode ignores these sampling parameters.  Anthropic
    Opus 4.7+ rejects them outright (400).  Remove them whenever the
    ``thinking`` object indicates thinking is *not* explicitly disabled.
    """
    thinking = body.get("thinking")
    if thinking and isinstance(thinking, dict) and thinking.get("type") != "disabled":
        keys_to_remove = _SAMPLING_PARAMS & body.keys()
        if keys_to_remove:
            body = body.copy()
            for key in keys_to_remove:
                del body[key]
    return body


def fix_thinking_reasoning_effort_conflict(body: dict[str, Any]) -> dict[str, Any]:
    """
    DeepSeek rejects ``thinking.type=disabled`` when ``reasoning_effort`` is also set.

    Error: "400 thinking options type cannot be disabled when reasoning_effort is set"

    Fix: When thinking is effectively disabled, remove reasoning_effort entirely.
    This covers:
    - ``thinking: {"type": "disabled"}`` (explicit)
    - ``thinking: {}`` (empty dict — no thinking features enabled)
    - Non-dict, non-None values (e.g. boolean False, string — non-standard but
      effectively disabled)
    - ``thinking`` absent (was removed mid-chain by earlier fixups → reasoning_effort
      alone is valid; this case is handled correctly by the logic below since
      ``body.get("thinking")`` returns None and we only strip when thinking is
      effectively *disabled*, not when it's absent)

    Must run BEFORE ``fix_thinking_empty`` so empty dicts are still visible.
    """
    thinking = body.get("thinking")

    # Is thinking effectively disabled?
    thinking_is_disabled = False

    if isinstance(thinking, dict):
        # Explicitly disabled: {"type": "disabled"}
        if thinking.get("type") == "disabled":
            thinking_is_disabled = True
        # Empty dict {} — no thinking features enabled, effectively disabled
        elif not thinking:
            thinking_is_disabled = True
    elif thinking is not None:
        # Non-dict, non-None value (e.g. bool False, string) — treat as
        # effectively disabled since it doesn't enable any thinking features.
        thinking_is_disabled = True

    if thinking_is_disabled and "reasoning_effort" in body:
        body = body.copy()
        del body["reasoning_effort"]

    return body


def fix_thinking_empty(body: dict[str, Any]) -> dict[str, Any]:
    """
    Remove an empty ``thinking`` dict ``{}`` from the body.

    Empty thinking dicts can slip through when the original request has
    ``thinking: {}`` (all earlier fixups already handle the case where a
    dict *becomes* empty after stripping, but a dict that starts empty
    passes through untouched).  An empty thinking dict is effectively
    "disabled" and can trigger the disabled+reasoning_effort conflict.
    """
    thinking = body.get("thinking")
    if isinstance(thinking, dict) and not thinking:
        body = body.copy()
        del body["thinking"]
    return body


def fix_output_config(body: dict[str, Any]) -> dict[str, Any]:
    """
    Keep only ``effort`` inside ``output_config``.

    DeepSeek only supports ``output_config.effort``.  Claude Code may also
    send ``output_config.task_budget`` (beta) or ``output_config.format``
    (structured outputs) — strip everything except ``effort``.  If
    ``output_config`` becomes empty after stripping, remove it entirely.
    """
    output_config = body.get("output_config")
    if output_config and isinstance(output_config, dict):
        extra_keys = output_config.keys() - _SUPPORTED_OUTPUT_CONFIG_KEYS
        if extra_keys:
            body = body.copy()
            output_config = {
                k: v
                for k, v in output_config.items()
                if k in _SUPPORTED_OUTPUT_CONFIG_KEYS
            }
            if output_config:
                body["output_config"] = output_config
            else:
                del body["output_config"]
    return body


def apply_all(body: dict[str, Any]) -> dict[str, Any]:
    """
    Apply all DeepSeek-specific fixups in order.

    Order matters — each fixup's output is the next fixup's input:

    1. Convert ``"adaptive"`` → ``"enabled"``
    2. Strip unsupported ``display`` field
    3. Strip Anthropic-specific ``budget_tokens``
    4. Strip ``temperature/top_p/top_k`` when thinking is active
    5. Remove empty ``thinking`` dicts (effectively disabled)
    6. Resolve ``disabled`` + ``reasoning_effort`` conflict
    7. Keep only ``effort`` in ``output_config``
    """
    body = fix_thinking_adaptive(body)
    body = fix_thinking_display(body)
    body = fix_thinking_budget_tokens(body)
    body = fix_thinking_sampling_params(body)
    body = fix_thinking_reasoning_effort_conflict(body)  # must be BEFORE fix_thinking_empty
    body = fix_thinking_empty(body)
    body = fix_output_config(body)
    return body

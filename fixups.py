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


def fix_thinking_disabled_remove(body: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve all conflicts around ``thinking: {type: "disabled"}``.

    DeepSeek rejects this parameter combination in multiple scenarios:
    - ``thinking.type=disabled`` + ``reasoning_effort`` (explicit conflict)
    - ``thinking.type=disabled`` on models that don't support thinking at all
      (misleading 400: "thinking options type cannot be disabled when
      reasoning_effort is set" — even when reasoning_effort is absent)

    Fix (model-agnostic):
    - Strip ``thinking`` entirely when its type is ``"disabled"`` —
      semantically equivalent to not sending thinking at all.
    - Strip ``reasoning_effort`` so it doesn't implicitly re-enable thinking
      and counteract the user's intent.
    - Clean up ``thinking: {}`` (empty dict, also effectively disabled).
    - Non-dict/non-None thinking values (boolean False, string — non-standard
      but seen in practice) are also treated as disabled.
    """
    thinking = body.get("thinking")

    # Determine if thinking is effectively disabled.
    thinking_disabled = False
    thinking_present = thinking is not None

    if isinstance(thinking, dict):
        if thinking.get("type") == "disabled" or not thinking:
            thinking_disabled = True
    elif thinking_present:
        # Non-dict, non-None (e.g. False, "disabled") — treat as disabled
        thinking_disabled = True

    if not thinking_disabled:
        return body

    # Strip both thinking and reasoning_effort
    body = body.copy()
    if isinstance(thinking, dict):
        del body["thinking"]
    elif thinking_present and "thinking" in body:
        del body["thinking"]
    if "reasoning_effort" in body:
        del body["reasoning_effort"]

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
    5. Resolve ``thinking=disabled`` conflicts (model-agnostic)
    6. Keep only ``effort`` in ``output_config``
    """
    body = fix_thinking_adaptive(body)
    body = fix_thinking_display(body)
    body = fix_thinking_budget_tokens(body)
    body = fix_thinking_sampling_params(body)
    body = fix_thinking_disabled_remove(body)
    body = fix_output_config(body)
    return body

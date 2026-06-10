"""
Unit tests for ccadaptor fixups.
Uses only Python standard library (unittest).
"""

import unittest

from fixups import (
    apply_all as apply_fixups,
    fix_output_config,
    fix_thinking_adaptive,
    fix_thinking_budget_tokens,
    fix_thinking_display,
    fix_thinking_reasoning_effort_conflict,
    fix_thinking_sampling_params,
)


class TestFixThinkingAdaptive(unittest.TestCase):
    """fix_thinking_adaptive — converts type: "adaptive" → "enabled"."""

    def test_adaptive_to_enabled(self):
        body = {"thinking": {"type": "adaptive"}}
        result = fix_thinking_adaptive(body)
        self.assertEqual(result["thinking"]["type"], "enabled")

    def test_enabled_unchanged(self):
        body = {"thinking": {"type": "enabled"}}
        result = fix_thinking_adaptive(body)
        self.assertEqual(result["thinking"]["type"], "enabled")

    def test_disabled_unchanged(self):
        body = {"thinking": {"type": "disabled"}}
        result = fix_thinking_adaptive(body)
        self.assertEqual(result["thinking"]["type"], "disabled")

    def test_no_thinking_unchanged(self):
        body = {"model": "x"}
        result = fix_thinking_adaptive(body)
        self.assertNotIn("thinking", result)
        self.assertIs(result, body)

    def test_preserves_other_thinking_fields(self):
        body = {"thinking": {"type": "adaptive", "budget_tokens": 4000}}
        result = fix_thinking_adaptive(body)
        self.assertEqual(result["thinking"]["type"], "enabled")
        self.assertEqual(result["thinking"]["budget_tokens"], 4000)


class TestFixThinkingDisplay(unittest.TestCase):
    """fix_thinking_display — strips ``display`` from thinking object."""

    def test_strips_display(self):
        body = {"thinking": {"type": "enabled", "display": "omitted"}}
        result = fix_thinking_display(body)
        self.assertNotIn("display", result["thinking"])
        self.assertEqual(result["thinking"]["type"], "enabled")

    def test_removes_thinking_when_only_display(self):
        body = {"thinking": {"display": "summarized"}}
        result = fix_thinking_display(body)
        self.assertNotIn("thinking", result)

    def test_no_display_unchanged(self):
        body = {"thinking": {"type": "enabled"}}
        result = fix_thinking_display(body)
        self.assertEqual(result["thinking"], {"type": "enabled"})
        self.assertIs(result, body)

    def test_no_thinking_unchanged(self):
        body = {"model": "x"}
        result = fix_thinking_display(body)
        self.assertIs(result, body)


class TestFixThinkingBudgetTokens(unittest.TestCase):
    """fix_thinking_budget_tokens — existing fixup, regression tests."""

    def test_strips_budget_tokens(self):
        body = {"thinking": {"type": "enabled", "budget_tokens": 4000}}
        result = fix_thinking_budget_tokens(body)
        self.assertNotIn("budget_tokens", result["thinking"])
        self.assertEqual(result["thinking"]["type"], "enabled")

    def test_removes_thinking_if_empty_after_budget_strip(self):
        body = {"thinking": {"budget_tokens": 4000}}
        result = fix_thinking_budget_tokens(body)
        self.assertNotIn("thinking", result)

    def test_no_thinking_unchanged(self):
        body = {"model": "x"}
        result = fix_thinking_budget_tokens(body)
        self.assertIs(result, body)

    def test_disabled_no_budget_unchanged(self):
        body = {"thinking": {"type": "disabled"}}
        result = fix_thinking_budget_tokens(body)
        self.assertEqual(result["thinking"], {"type": "disabled"})
        self.assertIs(result, body)


class TestFixThinkingSamplingParams(unittest.TestCase):
    """fix_thinking_sampling_params — strips temperature/top_p/top_k."""

    def test_strips_temperature_when_thinking_enabled(self):
        body = {
            "thinking": {"type": "enabled"},
            "temperature": 0.7,
        }
        result = fix_thinking_sampling_params(body)
        self.assertNotIn("temperature", result)
        self.assertEqual(result["thinking"], {"type": "enabled"})

    def test_keeps_temperature_when_thinking_disabled(self):
        body = {
            "thinking": {"type": "disabled"},
            "temperature": 0.7,
        }
        result = fix_thinking_sampling_params(body)
        self.assertIn("temperature", result)
        self.assertEqual(result["temperature"], 0.7)

    def test_keeps_temperature_when_no_thinking(self):
        body = {"temperature": 0.7}
        result = fix_thinking_sampling_params(body)
        self.assertIn("temperature", result)
        self.assertIs(result, body)

    def test_strips_multiple_sampling_params(self):
        body = {
            "thinking": {"type": "enabled"},
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 50,
        }
        result = fix_thinking_sampling_params(body)
        self.assertNotIn("temperature", result)
        self.assertNotIn("top_p", result)
        self.assertNotIn("top_k", result)

    def test_adaptive_treated_as_enabled(self):
        """Adaptive thinking is active; sampling params should be stripped."""
        body = {
            "thinking": {"type": "adaptive"},
            "temperature": 0.5,
        }
        result = fix_thinking_sampling_params(body)
        self.assertNotIn("temperature", result)


class TestFixThinkingReasoningEffortConflict(unittest.TestCase):
    """fix_thinking_reasoning_effort_conflict — existing fixup, regression tests."""

    def test_strips_reasoning_effort_when_thinking_disabled(self):
        body = {
            "model": "deepseek-v4-pro",
            "thinking": {"type": "disabled"},
            "reasoning_effort": "max",
        }
        result = fix_thinking_reasoning_effort_conflict(body)
        self.assertNotIn("reasoning_effort", result)
        self.assertEqual(result["thinking"], {"type": "disabled"})

    def test_keeps_reasoning_effort_when_thinking_enabled(self):
        body = {
            "model": "deepseek-v4-pro",
            "thinking": {"type": "enabled"},
            "reasoning_effort": "max",
        }
        result = fix_thinking_reasoning_effort_conflict(body)
        self.assertIn("reasoning_effort", result)
        self.assertEqual(result["reasoning_effort"], "max")

    def test_keeps_reasoning_effort_when_no_thinking(self):
        body = {
            "model": "deepseek-v4-pro",
            "reasoning_effort": "max",
        }
        result = fix_thinking_reasoning_effort_conflict(body)
        self.assertIn("reasoning_effort", result)


class TestFixOutputConfig(unittest.TestCase):
    """fix_output_config — keep only ``effort`` in output_config."""

    def test_keeps_effort(self):
        body = {"output_config": {"effort": "high"}}
        result = fix_output_config(body)
        self.assertEqual(result["output_config"], {"effort": "high"})
        self.assertIs(result, body)

    def test_strips_task_budget(self):
        body = {
            "output_config": {
                "effort": "high",
                "task_budget": {"type": "tokens", "total": 100000},
            }
        }
        result = fix_output_config(body)
        self.assertEqual(result["output_config"], {"effort": "high"})
        self.assertNotIn("task_budget", result["output_config"])

    def test_strips_format(self):
        body = {
            "output_config": {
                "effort": "high",
                "format": {"type": "json_schema", "schema": {}},
            }
        }
        result = fix_output_config(body)
        self.assertEqual(result["output_config"], {"effort": "high"})
        self.assertNotIn("format", result["output_config"])

    def test_removes_output_config_when_empty(self):
        body = {
            "output_config": {
                "task_budget": {"type": "tokens", "total": 100000},
                "format": {"type": "json_schema", "schema": {}},
            }
        }
        result = fix_output_config(body)
        self.assertNotIn("output_config", result)

    def test_no_output_config_unchanged(self):
        body = {"model": "x"}
        result = fix_output_config(body)
        self.assertIs(result, body)

    def test_strips_all_unsupported_keeps_effort_only(self):
        body = {
            "output_config": {
                "effort": "max",
                "task_budget": {"type": "tokens", "total": 128000},
                "format": {"type": "json_schema", "schema": {}},
            }
        }
        result = fix_output_config(body)
        self.assertEqual(result["output_config"], {"effort": "max"})


class TestCombinedFixups(unittest.TestCase):
    """End-to-end tests exercising apply_all with multiple fixups."""

    def test_adaptive_display_budget_output_config(self):
        """Full Claude Code Opus 4.8 request with all Anthropic extras."""
        body = {
            "model": "deepseek-v4-pro",
            "max_tokens": 16000,
            "thinking": {
                "type": "adaptive",
                "display": "omitted",
                "budget_tokens": 8000,
            },
            "output_config": {
                "effort": "xhigh",
                "task_budget": {"type": "tokens", "total": 128000},
                "format": {"type": "json_schema", "schema": {}},
            },
            "temperature": 0.7,
            "top_p": 0.9,
            "messages": [{"role": "user", "content": "hello"}],
        }
        result = apply_fixups(body)
        # adaptive → enabled
        self.assertEqual(result["thinking"]["type"], "enabled")
        # display stripped
        self.assertNotIn("display", result["thinking"])
        # budget_tokens stripped
        self.assertNotIn("budget_tokens", result["thinking"])
        # sampling params stripped (thinking is active)
        self.assertNotIn("temperature", result)
        self.assertNotIn("top_p", result)
        # output_config: only effort remains
        self.assertEqual(result["output_config"], {"effort": "xhigh"})
        # messages untouched
        self.assertIn("messages", result)

    def test_disabled_with_reasoning_effort_and_budget(self):
        """Sub-agent pattern: disabled thinking + reasoning_effort + budget_tokens."""
        body = {
            "thinking": {"type": "disabled", "budget_tokens": 4000},
            "reasoning_effort": "max",
        }
        result = apply_fixups(body)
        # reasoning_effort stripped (disabled conflict)
        self.assertNotIn("reasoning_effort", result)
        # budget_tokens stripped
        self.assertNotIn("budget_tokens", result.get("thinking", {}))
        self.assertEqual(result["thinking"], {"type": "disabled"})

    def test_adaptive_with_sampling_and_output_config(self):
        """Enabled thinking with sampling params to strip."""
        body = {
            "thinking": {"type": "adaptive"},
            "temperature": 1.0,
            "top_k": 40,
            "output_config": {
                "effort": "max",
                "format": {"type": "json_schema", "schema": {}},
            },
        }
        result = apply_fixups(body)
        self.assertEqual(result["thinking"]["type"], "enabled")
        self.assertNotIn("temperature", result)
        self.assertNotIn("top_k", result)
        self.assertEqual(result["output_config"], {"effort": "max"})

    def test_idempotent_on_clean_body(self):
        """A body with no Anthropic extras passes through unchanged."""
        body = {
            "model": "deepseek-v4-pro",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "hi"}],
        }
        result = apply_fixups(body)
        self.assertEqual(result, body)

    def test_disabled_removes_reasoning_effort_but_keeps_temperature(self):
        """When thinking is disabled: strip reasoning_effort, keep sampling params."""
        body = {
            "thinking": {"type": "disabled"},
            "reasoning_effort": "max",
            "temperature": 0.3,
        }
        result = apply_fixups(body)
        self.assertNotIn("reasoning_effort", result)
        self.assertIn("temperature", result)  # sampling params kept for disabled


if __name__ == "__main__":
    unittest.main(verbosity=2)

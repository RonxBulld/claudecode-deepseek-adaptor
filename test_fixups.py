"""
Unit tests for ccadaptor fixups.
Uses only Python standard library (unittest).
"""

import unittest

from fixups import (
    apply_all as apply_fixups,
    fix_thinking_budget_tokens,
    fix_thinking_reasoning_effort_conflict,
)


class TestThinkingFixups(unittest.TestCase):
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

    def test_strips_budget_tokens_from_thinking(self):
        body = {
            "thinking": {"type": "enabled", "budget_tokens": 4000},
        }
        result = fix_thinking_budget_tokens(body)
        self.assertNotIn("budget_tokens", result["thinking"])
        self.assertEqual(result["thinking"]["type"], "enabled")

    def test_removes_thinking_if_empty_after_budget_strip(self):
        body = {
            "thinking": {"budget_tokens": 4000},
        }
        result = fix_thinking_budget_tokens(body)
        self.assertNotIn("thinking", result)

    def test_combined_fixup_disabled_thinking_with_effort(self):
        body = {
            "thinking": {"type": "disabled", "budget_tokens": 4000},
            "reasoning_effort": "max",
        }
        result = apply_fixups(body)
        self.assertNotIn("reasoning_effort", result)
        self.assertNotIn("budget_tokens", result.get("thinking", {}))
        self.assertEqual(result["thinking"], {"type": "disabled"})


if __name__ == "__main__":
    unittest.main(verbosity=2)

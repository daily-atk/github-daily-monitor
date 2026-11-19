"""LLM 适配器测试（不发真实请求）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from enrich import build_prompt, estimate_cost, estimate_tokens, parse_items
from helpers import make_scored


class PromptTests(unittest.TestCase):
    def test_prompt_contains_project_data(self):
        candidates = [
            make_scored("ok/app", description="A budget app", topics=["budget", "finance"]),
            make_scored("ok/two", description="A habit tracker", topics=["habit"]),
        ]
        prompt = build_prompt(candidates, max_candidates=1)
        self.assertIn("ok/app", prompt)
        self.assertNotIn("ok/two", prompt)
        self.assertIn("budget", prompt)
        self.assertIn("full_name", prompt)

    def test_token_and_cost_estimate(self):
        self.assertEqual(estimate_tokens("a" * 4000), 1000)
        cost = estimate_cost("a" * 4000, 1000, 1.0, 2.0)
        self.assertAlmostEqual(cost, 0.003, places=6)


class ParseTests(unittest.TestCase):
    def test_parse_code_fence(self):
        content = """```json
{"items":[{"full_name":"ok/app","features":"功能","audience":"人群",
"value":"价值","difficulty":"低","notes":"注意"}]}
```"""
        items = parse_items(content)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["full_name"], "ok/app")

    def test_invalid_items_dropped_and_difficulty_normalized(self):
        content = '{"items":[{"full_name":"ok/app","features":"f","audience":"a",' \
                  '"value":"v","difficulty":"easy","notes":"n"},' \
                  '{"full_name":"ok/missing","features":"f"}]}'
        items = parse_items(content)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["difficulty"], "中")

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            parse_items("not json")


if __name__ == "__main__":
    unittest.main()
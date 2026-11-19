"""报告生成与增强数据校验测试。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config
from lib.reporter import (
    _first_sentence, build_report_data, display_name, render_html,
    render_markdown, validate_enriched,
)
from helpers import make_scored

CFG = load_config(ROOT / "config.json")


class DisplayNameTests(unittest.TestCase):
    def test_product_name_from_description(self):
        self.assertEqual(display_name({
            "name": "xbmc", "owner": "xbmc", "full_name": "xbmc/xbmc",
            "description": "Kodi is an award-winning free and open source home theater software.",
        }), "Kodi")

    def test_multi_word_product_name(self):
        self.assertEqual(display_name({
            "name": "super-productivity", "owner": "super-productivity",
            "full_name": "super-productivity/super-productivity",
            "description": "Super Productivity is an advanced todo list app.",
        }), "Super Productivity")

    def test_generic_name_uses_full_name(self):
        self.assertEqual(display_name({
            "name": "android", "owner": "home-assistant",
            "full_name": "home-assistant/android",
            "description": "Home Assistant Companion for Android",
        }), "home-assistant/android")

    def test_owner_repo_name_falls_back_to_name(self):
        self.assertEqual(display_name({
            "name": "wealthfolio", "owner": "wealthfolio",
            "full_name": "wealthfolio/wealthfolio",
            "description": "A beautiful, private, local-first personal finance tracker.",
        }), "wealthfolio")


class FallbackTests(unittest.TestCase):
    def test_fallback_text_differs(self):
        fitness = make_scored("a/one",
                              description="A fitness tracker app for daily workouts",
                              topics=["fitness", "tracker"])
        budget = make_scored("b/two",
                             description="A budget app to track expenses",
                             topics=["budget", "finance"])
        a = build_report_data([fitness], CFG, "2026-11-19")["items"][0]
        b = build_report_data([budget], CFG, "2026-11-19")["items"][0]
        self.assertNotEqual(a["audience"], b["audience"])
        self.assertNotEqual(a["value"], b["value"])

    def test_first_sentence_truncates_cleanly(self):
        text = "word " * 60
        result = _first_sentence(text, limit=50)
        self.assertTrue(result.endswith("…"))
        self.assertLessEqual(len(result), 51)


class ReportRenderTests(unittest.TestCase):
    def test_render_contains_new_fields_and_anchor(self):
        data = build_report_data([make_scored("ok/app")], CFG, "2026-11-19")
        md = render_markdown(data)
        html_out = render_html(data)
        for token in ("平台", "最近更新", "许可证"):
            self.assertIn(token, md)
        self.assertIn('id="1"', html_out)
        self.assertIn(f'{CFG["dedup"]["cooldown_days"]} 天内不重复', html_out)

    def test_enriched_overrides_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "enriched.json"
            p.write_text(json.dumps({
                "date": "2026-11-19",
                "items": [{
                    "full_name": "ok/app",
                    "features": "自定义功能",
                    "audience": "自定义人群",
                    "value": "自定义价值",
                    "difficulty": "中",
                    "notes": "自定义注意",
                }],
            }, ensure_ascii=False), encoding="utf-8")
            data = build_report_data([make_scored("ok/app")], CFG, "2026-11-19", p)
            item = data["items"][0]
            self.assertEqual(item["features"], "自定义功能")
            self.assertEqual(item["audience"], "自定义人群")
            self.assertEqual(item["difficulty"], "中")


class ValidateEnrichedTests(unittest.TestCase):
    def test_reports_problems(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text(json.dumps({
                "date": "1999-01-01",
                "items": [{"full_name": "nope/nope", "features": ""}],
            }, ensure_ascii=False), encoding="utf-8")
            issues = validate_enriched(p, "2026-11-19", {"a/b"})
            self.assertTrue(any("日期" in i for i in issues))
            self.assertTrue(any("不在当日候选" in i for i in issues))
            self.assertTrue(any("缺少字段" in i for i in issues))

    def test_example_file_is_well_formed(self):
        example = ROOT / "data" / "enriched_latest.example.json"
        payload = json.loads(example.read_text(encoding="utf-8"))
        names = {x["full_name"] for x in payload["items"]}
        self.assertEqual(validate_enriched(example, payload["date"], names), [])


if __name__ == "__main__":
    unittest.main()
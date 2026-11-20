"""资料库同步工具测试（不访问数据库）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.sync_library import cn_highlight, tech_highlight, to_record


class HighlightTests(unittest.TestCase):
    def test_cn_highlight_prefers_chinese_features(self):
        item = {"features": "习惯追踪工具", "description": "habit tracker",
                "topics": [], "category_label": "🏠 生活", "language": "C#"}
        self.assertEqual(cn_highlight(item), "习惯追踪工具")

    def test_tech_highlight_contains_growth(self):
        item = {"language": "Python", "license": "MIT", "topics": ["ai"],
                "stars_growth": 1349, "growth_period": "daily"}
        text = tech_highlight(item)
        self.assertIn("Python", text)
        self.assertIn("MIT", text)
        self.assertIn("1,349", text)
        self.assertIn("今日", text)


class RecordTests(unittest.TestCase):
    def test_to_record_maps_core_fields(self):
        item = {
            "rank": 1, "full_name": "a/b", "url": "https://github.com/a/b",
            "homepage": "", "description": "x", "topics": [], "language": "Python",
            "stars": 100, "stars_growth": 10, "growth_period": "daily",
            "license": "MIT", "category_label": "🔥 Trending", "difficulty": "中",
            "audience": "", "value": "", "notes": "n", "features": "f",
        }
        rec = to_record("2026-11-20", "程序员热度榜", item)
        self.assertEqual(rec["榜单"]["select"], "程序员热度榜")
        self.assertEqual(rec["排名"]["number"], 1)
        self.assertEqual(rec["今日新增Star"]["number"], 10)
        self.assertEqual(rec["项目"]["text"], "a/b")


if __name__ == "__main__":
    unittest.main()
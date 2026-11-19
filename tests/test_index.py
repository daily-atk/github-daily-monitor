"""历史归档索引页测试。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.build_index import build_index, find_reports


class BuildIndexTests(unittest.TestCase):
    def test_lists_reports_newest_first_and_ignores_other_files(self):
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)
            (site / "github-daily-2026-11-18.html").write_text("<html></html>", encoding="utf-8")
            (site / "github-daily-2026-11-19.html").write_text("<html></html>", encoding="utf-8")
            (site / "other.html").write_text("x", encoding="utf-8")

            reports = find_reports(site)
            self.assertEqual([date for date, _ in reports], ["2026-11-19", "2026-11-18"])

            out = build_index(site, "https://github.com/example/repo")
            text = out.read_text(encoding="utf-8")
            self.assertIn("2026-11-19", text)
            self.assertIn("2026-11-18", text)
            self.assertNotIn("other.html", text)
            self.assertIn("https://github.com/example/repo", text)
            self.assertLess(text.index("2026-11-19"), text.index("2026-11-18"))

    def test_empty_site(self):
        with tempfile.TemporaryDirectory() as d:
            out = build_index(d)
            text = out.read_text(encoding="utf-8")
            self.assertIn("还没有日报", text)

    def test_unsafe_repo_url_is_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            out = build_index(d, "javascript:alert(1)")
            self.assertNotIn("javascript:", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
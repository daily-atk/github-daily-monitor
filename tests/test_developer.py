"""程序员排行榜版（profile=dev）测试：Trending 解析、反转打分、配置隔离、双版报告。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.config import load_config
from lib.pipeline import score_repo_dev, dedup_and_select
from lib.reporter import build_report_data, render_markdown, render_html
from lib.trending import parse_trending
from tools.build_index import build_index, build_all, find_reports


# 一个最小的程序员版配置（避免依赖真实 config-dev.json 的内容变动）
def dev_cfg(tmp: Path | None = None) -> dict:
    return {
        "mode": "developer",
        "scoring": {"min_score": 0, "top_n": 10, "max_per_domain": 0,
                    "fresh_bonus_days": 7},
        "dedup": {"cooldown_days": 14, "seen_cooldown_days": 3,
                  "history_file": "data-dev/history.json"},
        "output": {"formats": ["md", "html"], "reports_dir": "reports-dev",
                   "candidates_file": "data-dev/candidates_latest.json",
                   "enriched_file": "data-dev/enriched_latest.json",
                   "file_prefix": "dev-daily"},
        "trending": {"period": "daily"},
        "analytics": {"provider": "off"},
    }


class TrendingParseTests(unittest.TestCase):
    HTML = """
    <article>
      <h2><a href="/foo/bar">foo/bar</a></h2>
      <p class="col-9 color-fg-muted my-1 pr-4">A developer tool for testing things.</p>
      <span itemprop="programmingLanguage">Python</span>
      <a href="/foo/bar/stargazers">12,345</a>
      <a href="/foo/bar/forks">1,234</a>
      <span class="d-inline-block float-sm-right">1,200 stars today</span>
    </article>
    <article><h2><a href="/spam/eggs">spam/eggs</a></h2></article>
    """

    def test_parses_fields(self):
        repos = parse_trending(self.HTML, "daily")
        self.assertEqual(len(repos), 2)
        r = repos[0]
        self.assertEqual(r["full_name"], "foo/bar")
        self.assertEqual(r["description"], "A developer tool for testing things.")
        self.assertEqual(r["language"], "Python")
        self.assertEqual(r["stargazers_count"], 12345)
        self.assertEqual(r["forks_count"], 1234)
        self.assertEqual(r["stars_growth"], 1200)
        self.assertEqual(r["growth_period"], "daily")

    def test_weekly_label(self):
        html = self.HTML.replace("1,200 stars today", "900 stars this week")
        r = parse_trending(html, "weekly")[0]
        self.assertEqual(r["stars_growth"], 900)


class DevScoringTests(unittest.TestCase):
    def test_growth_dominates(self):
        cfg = dev_cfg()
        base = {"full_name": "a/b", "name": "b", "description": "A useful tool.",
                "stargazers_count": 1000, "topics": ["tool"], "license": "MIT",
                "pushed_at": "2026-11-18T00:00:00Z"}
        hot = score_repo_dev({**base, "stars_growth": 2000, "growth_period": "daily"},
                             "Trending", cfg)
        cold = score_repo_dev({**base, "stars_growth": 5, "growth_period": "daily"},
                              "Trending", cfg)
        self.assertGreater(hot["score"], cold["score"])
        self.assertEqual(hot["stars_growth"], 2000)

    def test_license_and_activity_bonus(self):
        cfg = dev_cfg()
        base = {"full_name": "a/b", "name": "b", "description": "A framework for apps.",
                "stargazers_count": 500, "topics": ["framework"], "stars_growth": 100,
                "growth_period": "daily"}
        good = score_repo_dev({**base, "license": "MIT", "pushed_at": "2026-11-19T00:00:00Z"},
                              "框架/库", cfg)
        bad = score_repo_dev({**base, "license": "", "pushed_at": "2020-01-01T00:00:00Z"},
                             "框架/库", cfg)
        self.assertGreater(good["score"], bad["score"])
        self.assertEqual(good["category_label"], "🧩 框架/库")

    def test_dedup_by_growth(self):
        cfg = dev_cfg()
        a = {"full_name": "a/b", "score": 60, "stars": 1000, "stars_growth": 50, "category": "Trending"}
        b = {"full_name": "c/d", "score": 90, "stars": 5000, "stars_growth": 500, "category": "Trending"}
        top, stats = dedup_and_select([a, b], cfg, {"records": {}}, by_growth=True)
        self.assertEqual(top[0]["full_name"], "c/d")  # 增长高的排前，即便分数低


class ProfileIsolationTests(unittest.TestCase):
    def test_paths_are_isolated(self):
        consumer = load_config(profile="consumer")
        dev = load_config(profile="dev")
        self.assertNotEqual(consumer["output"]["reports_dir"], dev["output"]["reports_dir"])
        self.assertNotEqual(consumer["dedup"]["history_file"], dev["dedup"]["history_file"])
        self.assertNotEqual(consumer["output"]["candidates_file"], dev["output"]["candidates_file"])
        self.assertEqual(dev["mode"], "developer")


class DevReportTests(unittest.TestCase):
    def _sample(self):
        item = {"full_name": "foo/bar", "name": "bar", "url": "https://github.com/foo/bar",
                "homepage": "", "description": "A fast developer tool.", "stars": 12000,
                "forks": 800, "language": "Rust", "license": "MIT", "platforms": "",
                "topics": ["rust", "cli"], "created_at": "2026-11-15T00:00:00Z",
                "pushed_at": "2026-11-19T00:00:00Z", "category": "开发工具",
                "category_label": "🛠️ 开发工具", "difficulty": "中", "score": 88.0,
                "stars_growth": 1500, "growth_period": "daily", "source": "trending"}
        data = build_report_data([item], dev_cfg(), "2026-11-20", None)
        return data

    def test_markdown_shows_growth(self):
        md = render_markdown(self._sample())
        self.assertIn("程序员热度榜", md)
        self.assertIn("今日新增", md)
        self.assertIn("+1,500", md)
        self.assertNotIn("适合人群", md)  # 程序员版不展示普通人维度

    def test_html_dev_theme(self):
        h = render_html(self._sample())
        self.assertIn("程序员热度榜", h)
        self.assertIn("--bg:#0d1117", h)  # 深色主题
        self.assertIn("+1,500", h)


class DevIndexTests(unittest.TestCase):
    def test_finds_dev_reports_only(self):
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)
            (site / "github-daily-2026-11-19.html").write_text("<html></html>", encoding="utf-8")
            (site / "dev").mkdir()
            (site / "dev" / "dev-daily-2026-11-20.html").write_text("<html></html>", encoding="utf-8")
            consumer = find_reports(site, "consumer")
            dev = find_reports(site / "dev", "dev")
            self.assertEqual([x[0] for x in consumer], ["2026-11-19"])
            self.assertEqual([x[0] for x in dev], ["2026-11-20"])

    def test_build_all_has_nav(self):
        with tempfile.TemporaryDirectory() as d:
            consumer, dev = build_all(d, "https://github.com/example/repo")
            ctext = consumer.read_text(encoding="utf-8")
            dtext = dev.read_text(encoding="utf-8")
            self.assertIn("普通人日报", ctext)
            self.assertIn("程序员热度榜", ctext)
            self.assertIn('href="dev/index.html"', ctext)
            self.assertIn('href="../index.html"', dtext)


if __name__ == "__main__":
    unittest.main()

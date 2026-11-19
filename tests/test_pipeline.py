"""流水线测试：过滤、打分、去重、历史迁移。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config
from lib.pipeline import (
    _hits, _matches_terms, build_queries, dedup_and_select, filter_low_quality,
    normalize_history, score_repo,
)
from helpers import history_record, make_repo, make_scored

CFG = load_config(ROOT / "config.json")


class HitsTests(unittest.TestCase):
    def test_word_boundaries(self):
        self.assertEqual(_hits("capital rapid apple web3", {"api", "app", "web"}), 0)
        self.assertEqual(_hits("api app web apps", {"api", "app", "web"}), 3)

    def test_chinese_substring(self):
        self.assertEqual(_hits("这是一个提醒工具", {"提醒", "工具"}), 2)


class QueryTests(unittest.TestCase):
    def test_query_count(self):
        active = [k for k, v in CFG["keywords"].items() if not k.startswith("_") and v]
        expected = min(len(active) * 2, CFG["search"]["max_queries_per_run"])
        self.assertEqual(len(build_queries(CFG)), expected)

    def test_every_query_has_known_category(self):
        for query, category, terms in build_queries(CFG):
            self.assertTrue(query)
            self.assertIn(category, CFG["keywords"])
            self.assertGreaterEqual(len(terms), 1)

    def test_required_terms_skip_generic_words(self):
        for _, _, terms in build_queries(CFG):
            self.assertNotIn("app", terms)
            self.assertNotIn("tool", terms)

    def test_matches_terms_rejects_false_positive(self):
        tracker = {"name": "streak", "full_name": "InlitX/streak",
                   "description": "A habit tracker app", "topics": ["habit-tracking"]}
        habitat = {"name": "habitat", "full_name": "habitat-sh/habitat",
                   "description": "Build applications", "topics": []}
        self.assertTrue(_matches_terms(tracker, ["habit", "tracker"]))
        self.assertFalse(_matches_terms(habitat, ["habit", "tracker"]))


class FilterTests(unittest.TestCase):
    def test_filters_low_quality(self):
        repos = [
            make_repo("ok/good"),
            make_repo("ok/no-desc", description=""),
            make_repo("ok/short", description="short"),
            make_repo("ok/awesome-list"),
            make_repo("ok/archived", archived=True),
            make_repo("ok/low-stars", stargazers_count=10),
            make_repo("ok/forky", stargazers_count=1000, forks_count=900),
            make_repo("ok/tiny", size=10),
        ]
        kept, stats = filter_low_quality(repos, CFG)

        self.assertEqual([r["full_name"] for r in kept], ["ok/good"])
        self.assertEqual(stats["by_no_desc"], 1)
        self.assertEqual(stats["by_short_desc"], 1)
        self.assertEqual(stats["by_exclude_name"], 1)
        self.assertEqual(stats["by_archived"], 1)
        self.assertEqual(stats["by_stars"], 1)
        self.assertEqual(stats["by_fork_ratio"], 1)
        self.assertEqual(stats["by_size"], 1)


class ScoreTests(unittest.TestCase):
    def test_missing_license_is_penalized(self):
        base = make_repo("ok/app", description="A simple todo app for daily planning",
                         topics=["app", "todo"])
        no_license = make_repo("ok/app", description="A simple todo app for daily planning",
                               topics=["app", "todo"], license=None)
        with_license_score = score_repo(base, "效率", CFG)
        no_license_score = score_repo(no_license, "效率", CFG)
        weight = CFG["scoring"]["domain_weight"].get("效率", 1.0)
        self.assertAlmostEqual(
            with_license_score["score"] - no_license_score["score"],
            round(6.0 * weight, 1), places=1,
        )
        self.assertEqual(with_license_score["license"], "MIT")
        self.assertEqual(no_license_score["license"], "")

    def test_infra_name_is_penalized(self):
        normal = make_repo("ok/app", description="A simple personal finance app for daily budgeting",
                           topics=["finance"])
        infra = make_repo("ok/webkit", description="A simple personal finance app for daily budgeting",
                          topics=["finance"])
        self.assertLess(score_repo(infra, "财务", CFG)["score"],
                        score_repo(normal, "财务", CFG)["score"])

    def test_difficulty(self):
        easy = make_repo("ok/easy", description="A browser extension for daily planning",
                         topics=["browser-extension"])
        hard = make_repo("ok/hard", description="Self-hosted server with docker and command line deployment",
                         topics=["self-hosted"])
        self.assertEqual(score_repo(easy, "效率", CFG)["difficulty"], "低")
        self.assertEqual(score_repo(hard, "效率", CFG)["difficulty"], "高")


class DedupTests(unittest.TestCase):
    def test_cooldowns_and_same_day(self):
        history = {"records": {
            "a/recent-seen": history_record(seen_days=1),
            "b/old-seen": history_record(seen_days=10),
            "c/recent-rec": history_record(seen_days=5, recommended_days=5, times=1),
            "d/old-rec": history_record(seen_days=40, recommended_days=40, times=1),
            "e/legacy": {"times_recommended": 0,
                         "first_seen": history_record(first_days=1)["first_seen"],
                         "last_recommended": None},
            "f/same-day": history_record(seen_days=0),
        }}
        pool = [make_scored(fn) for fn in history["records"]]
        selected, stats = dedup_and_select(pool, CFG, history)
        names = {x["full_name"] for x in selected}

        self.assertNotIn("a/recent-seen", names)
        self.assertNotIn("c/recent-rec", names)
        self.assertNotIn("e/legacy", names)
        self.assertIn("b/old-seen", names)
        self.assertIn("d/old-rec", names)
        self.assertIn("f/same-day", names)
        self.assertEqual(stats["in_cooldown"], 1)
        self.assertEqual(stats["recent_seen"], 2)

    def test_domain_cap(self):
        pool = [make_scored(f"x{i}/repo{i}", category="生活", score=90 - i) for i in range(10)]
        selected, _ = dedup_and_select(pool, CFG, {"records": {}})
        self.assertEqual(len(selected), CFG["scoring"]["max_per_domain"])

    def test_normalize_history(self):
        history = {"records": {"x/y": {
            "times_recommended": 0,
            "first_seen": "2026-11-01T00:00:00+00:00",
            "last_recommended": None,
        }}}
        self.assertTrue(normalize_history(history))
        self.assertEqual(history["records"]["x/y"]["last_seen"],
                         "2026-11-01T00:00:00+00:00")
        self.assertFalse(normalize_history(history))


if __name__ == "__main__":
    unittest.main()
"""配置加载与校验测试。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.config import ConfigError, load_config, strip_notes, validate_config


class ConfigTests(unittest.TestCase):
    def test_project_config_is_valid(self):
        cfg = load_config(ROOT / "config.json")
        self.assertIn("keywords", cfg)
        active = [k for k, v in cfg["keywords"].items() if not k.startswith("_") and v]
        self.assertGreaterEqual(len(active), 5)

    def test_missing_keywords_rejected(self):
        cfg = {"search": {}, "keywords": {}, "filters": {},
               "scoring": {}, "dedup": {}, "output": {}}
        with self.assertRaises(ConfigError) as ctx:
            validate_config(cfg)
        self.assertIn("keywords", str(ctx.exception))

    def test_bad_json_reports_line_and_column(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text('{"search": {}, "keywords": {}, }', encoding="utf-8")
            with self.assertRaises(ConfigError) as ctx:
                load_config(p)
            msg = str(ctx.exception)
            self.assertIn("第", msg)
            self.assertIn("行", msg)
            self.assertIn("列", msg)

    def test_bad_output_format_rejected(self):
        cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        cfg["output"]["formats"] = ["pdf"]
        with self.assertRaises(ConfigError) as ctx:
            validate_config(cfg)
        self.assertIn("formats", str(ctx.exception))

    def test_strip_notes(self):
        self.assertEqual(
            strip_notes({"_x": 1, "a": {"_y": 2, "b": 3}}),
            {"a": {"b": 3}},
        )


if __name__ == "__main__":
    unittest.main()
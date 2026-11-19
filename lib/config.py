"""配置加载与路径工具。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else ROOT / "config.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def root_path(rel: str) -> Path:
    return ROOT / rel


def strip_notes(obj):
    """递归去掉以 _ 开头的说明键。"""
    if isinstance(obj, dict):
        return {k: strip_notes(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_notes(v) for v in obj]
    return obj

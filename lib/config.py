"""配置加载、校验与路径工具。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ConfigError(ValueError):
    """配置文件有误（中文提示，方便非技术用户排查）。"""


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else ROOT / "config.json"
    if not p.exists():
        raise ConfigError(f"找不到配置文件：{p}")
    try:
        with open(p, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(
            f"config.json 第 {e.lineno} 行第 {e.colno} 列格式有误：{e.msg}。\n"
            "常见原因：少了或多了英文逗号、用了中文引号“”，或最后一项后面多了逗号。"
        ) from e
    validate_config(cfg)
    return cfg


def _check_int(errors: list[str], obj: dict, key: str,
               minimum: int | None = None, maximum: int | None = None,
               where: str = "") -> None:
    if key not in obj:
        return
    v = obj.get(key)
    if isinstance(v, bool) or not isinstance(v, int):
        errors.append(f"{where}.{key} 必须是整数，当前是 {type(v).__name__}")
        return
    if minimum is not None and v < minimum:
        errors.append(f"{where}.{key} 不能小于 {minimum}，当前是 {v}")
    if maximum is not None and v > maximum:
        errors.append(f"{where}.{key} 不能大于 {maximum}，当前是 {v}")


def validate_config(cfg: dict) -> None:
    """在真正运行前检查配置，尽量用中文说清哪里错了。"""
    if not isinstance(cfg, dict):
        raise ConfigError("config.json 最外层必须是一个 { ... } 对象。")

    errors: list[str] = []
    for key in ("search", "keywords", "filters", "scoring", "dedup", "output"):
        if key not in cfg:
            errors.append(f"缺少必需的配置段：{key}")

    s = cfg.get("search") or {}
    if isinstance(s, dict):
        _check_int(errors, s, "lookback_days", minimum=1, where="search")
        _check_int(errors, s, "updated_lookback_days", minimum=1, where="search")
        _check_int(errors, s, "min_stars", minimum=0, where="search")
        _check_int(errors, s, "max_stars", minimum=0, where="search")
        _check_int(errors, s, "results_per_query", minimum=1, maximum=100, where="search")
        _check_int(errors, s, "max_queries_per_run", minimum=1, maximum=30, where="search")
        delay = s.get("request_delay_seconds")
        if not isinstance(delay, (int, float)) or isinstance(delay, bool) or delay < 1:
            errors.append("search.request_delay_seconds 必须是 >=1 的数字（匿名额度建议 7）")
        if isinstance(s.get("min_stars"), int) and isinstance(s.get("max_stars"), int):
            if s["max_stars"] < s["min_stars"]:
                errors.append("search.max_stars 不能小于 min_stars")
    elif s is not None:
        errors.append("search 必须是一个 { ... } 对象")

    kw = cfg.get("keywords")
    if isinstance(kw, dict):
        active = [k for k, v in kw.items() if not k.startswith("_") and v]
        if not active:
            errors.append("keywords 至少要有一个领域，且每个领域的词表不能为空")
        for k, v in kw.items():
            if k.startswith("_"):
                continue
            if not isinstance(v, list) or not v:
                errors.append(f"keywords.{k} 必须是非空列表，例如 [\"todo app\"]")
            elif not all(isinstance(x, str) and x.strip() for x in v):
                errors.append(f"keywords.{k} 里只能是文字（英文词效果最好）")
    elif kw is not None:
        errors.append("keywords 必须是一个 { 领域: [关键词...] } 的对象")

    sc = cfg.get("scoring") or {}
    if isinstance(sc, dict):
        _check_int(errors, sc, "top_n", minimum=1, maximum=50, where="scoring")
        _check_int(errors, sc, "min_score", minimum=0, maximum=100, where="scoring")
        _check_int(errors, sc, "max_per_domain", minimum=0, maximum=50, where="scoring")
        dw = sc.get("domain_weight")
        if dw is not None and not isinstance(dw, dict):
            errors.append("scoring.domain_weight 必须是 { 领域: 数字 } 的对象")
    elif sc is not None:
        errors.append("scoring 必须是一个 { ... } 对象")

    dd = cfg.get("dedup") or {}
    if isinstance(dd, dict):
        _check_int(errors, dd, "cooldown_days", minimum=0, maximum=3650, where="dedup")
        _check_int(errors, dd, "seen_cooldown_days", minimum=0, maximum=3650, where="dedup")
    elif dd is not None:
        errors.append("dedup 必须是一个 { ... } 对象")

    out = cfg.get("output") or {}
    if isinstance(out, dict):
        fmts = out.get("formats")
        if not isinstance(fmts, list) or not fmts:
            errors.append("output.formats 必须是非空列表，可选 \"md\" / \"html\"")
        else:
            bad = [x for x in fmts if x not in ("md", "html")]
            if bad:
                errors.append(f"output.formats 里有不认识的值：{bad}（只支持 md / html）")
    elif out is not None:
        errors.append("output 必须是一个 { ... } 对象")

    if errors:
        raise ConfigError("config.json 配置有问题：\n- " + "\n- ".join(errors))


def root_path(rel: str) -> Path:
    return ROOT / rel


def strip_notes(obj):
    """递归去掉以 _ 开头的说明键。"""
    if isinstance(obj, dict):
        return {k: strip_notes(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_notes(v) for v in obj]
    return obj
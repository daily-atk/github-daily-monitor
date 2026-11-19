#!/usr/bin/env python3
"""每日 GitHub 实用项目监测助手 —— 主入口。

用法：
    python monitor.py collect   # 采集候选（写 data/candidates_latest.json）
    python monitor.py report    # 依据候选/AI增强数据生成 Markdown+HTML 报告
    python monitor.py run       # 采集 + 报告一步到位（自动化每天调用这个）
    python monitor.py stats     # 查看历史去重库统计
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from lib.config import load_config, root_path, strip_notes
from lib.github_client import GitHubClient
from lib.pipeline import (
    build_queries, filter_low_quality, score_repo, dedup_and_select, update_history,
)
from lib.reporter import build_report_data, save_reports


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_history() -> dict:
    p = root_path("data/history.json")
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"records": {}, "updated_at": None, "total_tracked": 0}


def save_history(h: dict):
    p = root_path("data/history.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")


def write_json(rel: str, data):
    p = root_path(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def do_collect(cfg: dict, verbose: bool = True) -> dict:
    s = strip_notes(cfg["search"])
    client = GitHubClient(
        token=cfg.get("github_token_env") and __import__("os").environ.get(cfg["github_token_env"]),
        delay=s["request_delay_seconds"],
    )
    queries = build_queries(cfg)
    if verbose:
        print(f"[采集] 共 {len(queries)} 个搜索式，匿名限流间隔 {s['request_delay_seconds']}s，"
              f"{'已检测到 Token' if client.token else '未配置 Token（额度较低）'}")

    all_repos: list[dict] = []
    categories: dict[str, str] = {}
    for i, (q, cat) in enumerate(queries, 1):
        if verbose:
            print(f"  ({i}/{len(queries)}) [{cat}] {q[:70]}...")
        items = client.search_repos(q, sort="stars", order="desc", per_page=s["results_per_query"])
        for it in items:
            categories.setdefault(it["full_name"], cat)
        all_repos.extend(items)

    # 二次捞取"近期重要更新"：对已收集到的仓库按 pushed 排序再补一点
    if verbose:
        print(f"[采集] 原始 {len(all_repos)} 条，实际 API 请求 {client.request_count} 次，缓存命中 {client.cache_hits} 次")

    kept, fstats = filter_low_quality(all_repos, cfg)
    if verbose:
        print(f"[过滤] 原始 {fstats['total_raw']} → 保留 {fstats['kept']} "
              f"(无描述 {fstats['by_no_desc']}, 排除词 {fstats['by_exclude_name']+fstats['by_exclude_desc']}, "
              f"星标 {fstats['by_stars']}, fork比 {fstats['by_fork_ratio']})")

    scored = [score_repo(r, categories.get(r["full_name"], "综合"), cfg) for r in kept]
    history = load_history()
    selected, dstats = dedup_and_select(scored, cfg, history)
    if verbose:
        print(f"[去重] 冷却期跳过 {dstats['in_cooldown']}，最终入选 {dstats['selected']}")

    payload = {
        "date": today_str(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "filter_stats": fstats,
        "dedup_stats": dstats,
        "candidates": selected,
        "all_seen": list({r["full_name"] for r in all_repos}),
    }
    write_json(cfg["output"]["candidates_file"], payload)
    if verbose and selected:
        print("[候选] Top 列表：")
        for it in selected:
            print(f"   #{it['score']:>5} [{it['category']}] {it['full_name']} ⭐{it['stars']}")

    # 把本次见到的项目记入历史（即使未入选，避免明天重复出现在候选池）
    if cfg["dedup"].get("persist_since_first_seen", True):
        update_history(history, selected, payload["all_seen"])
        save_history(history)
    return payload


def do_report(cfg: dict, verbose: bool = True) -> list[Path]:
    cp = root_path(cfg["output"]["candidates_file"])
    if not cp.exists():
        print("[报告] 没有找到候选文件，请先运行 collect", file=sys.stderr)
        return []
    payload = json.loads(cp.read_text(encoding="utf-8"))
    enriched = root_path(cfg["output"]["enriched_file"])
    data = build_report_data(payload["candidates"], cfg, payload["date"], enriched)
    files = save_reports(data, cfg)
    if verbose:
        for f in files:
            print(f"[报告] 已生成 {f}")
    return files


def do_stats(cfg: dict):
    h = load_history()
    recs = h.get("records", {})
    recommended = sum(1 for r in recs.values() if r.get("times_recommended", 0) > 0)
    print(f"历史库共追踪 {len(recs)} 个项目，其中已推荐过 {recommended} 个")
    print(f"最后更新：{h.get('updated_at')}")
    for fn, rec in list(recs.items())[:10]:
        print(f"  {fn}: 推荐 {rec.get('times_recommended',0)} 次, 最近 {rec.get('last_recommended')}")


def main():
    ap = argparse.ArgumentParser(description="每日 GitHub 实用项目监测助手")
    ap.add_argument("cmd", choices=["collect", "report", "run", "stats"])
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    v = not args.quiet

    if args.cmd == "collect":
        do_collect(cfg, v)
    elif args.cmd == "report":
        do_report(cfg, v)
    elif args.cmd == "run":
        do_collect(cfg, v)
        print("---")
        do_report(cfg, v)
    elif args.cmd == "stats":
        do_stats(cfg)


if __name__ == "__main__":
    main()

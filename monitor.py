#!/usr/bin/env python3
"""每日 GitHub 实用项目监测助手 —— 主入口。

用法：
    python monitor.py collect   # 采集候选（写 data/candidates_latest.json）
    python monitor.py report    # 依据候选/AI增强数据生成 Markdown+HTML 报告
    python monitor.py run       # 采集 + 报告一步到位（自动化每天调用这个）
    python monitor.py stats     # 查看历史去重库统计
    python monitor.py validate  # 校验 AI 增强数据（enriched_latest.json）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from lib.config import ConfigError, load_config, root_path
from lib.github_client import GitHubClient
from lib.pipeline import (
    build_queries, filter_low_quality, score_repo, dedup_and_select,
    update_history, normalize_history,
)
from lib.reporter import build_report_data, save_reports, validate_enriched

LOG_MAX_BYTES = 1_000_000


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def log(msg: str) -> None:
    """把运行过程写进 data/run.log，方便排查定时任务失败。"""
    try:
        p = root_path("data/run.log")
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists() and p.stat().st_size > LOG_MAX_BYTES:
            backup = p.with_suffix(".log.1")
            try:
                if backup.exists():
                    backup.unlink()
                p.replace(backup)
            except Exception:
                pass
        with p.open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except Exception:
        # 日志失败不能影响主流程
        pass


def load_history() -> dict:
    p = root_path("data/history.json")
    history = {"records": {}, "updated_at": None, "total_tracked": 0}
    if p.exists():
        try:
            history = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[警告] 历史文件读取失败，将重新开始：{e}", file=sys.stderr)
            log(f"history load failed: {e}")
    if normalize_history(history):
        save_history(history)
        log("history normalized: added last_seen for old records")
    return history


def save_history(h: dict) -> None:
    p = root_path("data/history.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")


def write_json(rel: str, data) -> None:
    p = root_path(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def do_collect(cfg: dict, verbose: bool = True, force: bool = False) -> dict:
    date_today = today_str()
    cp = root_path(cfg["output"]["candidates_file"])

    # 同一天已经采集过且候选非空时直接复用，避免定时任务和手动运行重复消耗候选池。
    if not force and cp.exists():
        try:
            existing = json.loads(cp.read_text(encoding="utf-8"))
            if existing.get("date") == date_today and existing.get("candidates"):
                if verbose:
                    print(f"[跳过] 今天已有 {len(existing['candidates'])} 个候选，"
                          f"本次不重复采集（如需强制刷新请加 --force）")
                log("collect skipped: same-day candidates already exist")
                return existing
        except Exception:
            pass

    s = cfg["search"]
    token = os.environ.get(cfg.get("github_token_env") or "GITHUB_TOKEN") or ""
    client = GitHubClient(token=token, delay=s["request_delay_seconds"])
    queries = build_queries(cfg)
    log(f"collect start: {len(queries)} queries, token={'yes' if client.token else 'no'}")
    if verbose:
        print(f"[采集] 共 {len(queries)} 个搜索式，请求间隔 {s['request_delay_seconds']}s，"
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

    if verbose:
        print(f"[采集] 原始 {len(all_repos)} 条，实际 API 请求 {client.request_count} 次，"
              f"缓存命中 {client.cache_hits} 次")

    kept, fstats = filter_low_quality(all_repos, cfg)
    if verbose:
        print(f"[过滤] 原始 {fstats['total_raw']} → 保留 {fstats['kept']} "
              f"(无描述 {fstats['by_no_desc']}, 排除词 {fstats['by_exclude_name'] + fstats['by_exclude_desc']}, "
              f"星标 {fstats['by_stars']}, 体积 {fstats['by_size']}, fork比 {fstats['by_fork_ratio']})")

    scored = [score_repo(r, categories.get(r["full_name"], "综合"), cfg) for r in kept]
    history = load_history()
    selected, dstats = dedup_and_select(scored, cfg, history)
    if verbose:
        print(f"[去重] 推荐冷却跳过 {dstats['in_cooldown']}，近期见过 {dstats['recent_seen']}，"
              f"最终入选 {dstats['selected']}")

    # 同一天重复运行时，如果本次没有新候选，保留当天已生成的非空候选，
    # 避免定时任务把白天已经生成的报告覆盖成空榜单。
    cp = root_path(cfg["output"]["candidates_file"])
    if not selected and not force and cp.exists():
        try:
            existing = json.loads(cp.read_text(encoding="utf-8"))
            if existing.get("date") == date_today and existing.get("candidates"):
                if verbose:
                    print(f"[去重] 本次没有新增候选，保留当天已有的 "
                          f"{len(existing['candidates'])} 个候选（不覆盖；如需强制刷新请加 --force）")
                log("collect skipped overwrite: no new candidates, kept existing same-day candidates")
                return existing
        except Exception:
            pass

    payload = {
        "date": date_today,
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

    # 把本次见到的项目记入历史（只在首次见到时记录，避免每天重复出现在候选池）
    if cfg["dedup"].get("persist_since_first_seen", True):
        update_history(history, selected, payload["all_seen"])
        save_history(history)

    log(f"collect done: raw={fstats['total_raw']} kept={fstats['kept']} "
        f"selected={dstats['selected']} requests={client.request_count} cache={client.cache_hits}")
    return payload


def do_report(cfg: dict, verbose: bool = True) -> list[Path]:
    cp = root_path(cfg["output"]["candidates_file"])
    if not cp.exists():
        print("[报告] 没有找到候选文件，请先运行 collect", file=sys.stderr)
        return []
    payload = json.loads(cp.read_text(encoding="utf-8"))
    ep = root_path(cfg["output"]["enriched_file"])

    # 有 AI 增强数据时先校验，问题只提示、不阻断
    issues = validate_enriched(ep, payload.get("date"),
                               {c["full_name"] for c in payload.get("candidates", [])})
    for issue in issues:
        print(f"[校验] {issue}", file=sys.stderr)
        log(f"enriched warning: {issue}")

    data = build_report_data(payload["candidates"], cfg, payload["date"], ep)
    files = save_reports(data, cfg)
    if verbose:
        for f in files:
            print(f"[报告] 已生成 {f}")
    log(f"report done: {len(files)} files, {data['count']} items, date={data['date']}")
    return files


def do_stats(cfg: dict) -> None:
    h = load_history()
    recs = h.get("records", {})
    recommended = sum(1 for r in recs.values() if isinstance(r, dict) and r.get("times_recommended", 0) > 0)
    print(f"历史库共追踪 {len(recs)} 个项目，其中已推荐过 {recommended} 个")
    print(f"最后更新：{h.get('updated_at')}")
    for fn, rec in list(recs.items())[:10]:
        if isinstance(rec, dict):
            print(f"  {fn}: 推荐 {rec.get('times_recommended', 0)} 次, 最近 {rec.get('last_recommended')}")


def do_validate(cfg: dict, verbose: bool = True) -> int:
    cp = root_path(cfg["output"]["candidates_file"])
    if not cp.exists():
        print("[校验] 还没有候选数据，请先运行 python monitor.py collect", file=sys.stderr)
        return 1
    payload = json.loads(cp.read_text(encoding="utf-8"))
    ep = root_path(cfg["output"]["enriched_file"])
    if not ep.exists():
        print("[校验] 尚未生成 enriched_latest.json（这是可选的；没有它时报告会使用脚本兜底文案）")
        return 0
    issues = validate_enriched(ep, payload.get("date"),
                               {c["full_name"] for c in payload.get("candidates", [])})
    if not issues:
        print("[校验] 通过：enriched_latest.json 与当日候选一致")
        return 0
    for issue in issues:
        print(f"[校验] {issue}")
    return 1


def main() -> None:
    ap = argparse.ArgumentParser(description="每日 GitHub 实用项目监测助手")
    ap.add_argument("cmd", choices=["collect", "report", "run", "stats", "validate"])
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="即使今天已有非空候选也重新采集并覆盖")
    args = ap.parse_args()
    log(f"=== start {args.cmd} ===")

    try:
        cfg = load_config()
        verbose = not args.quiet
        if args.cmd == "collect":
            do_collect(cfg, verbose, force=args.force)
        elif args.cmd == "report":
            do_report(cfg, verbose)
        elif args.cmd == "run":
            do_collect(cfg, verbose, force=args.force)
            print("---")
            do_report(cfg, verbose)
        elif args.cmd == "stats":
            do_stats(cfg)
        elif args.cmd == "validate":
            sys.exit(do_validate(cfg, verbose))
        log(f"=== done {args.cmd} ===")
    except ConfigError as e:
        log(f"config error: {e}")
        print(f"\n[配置错误] {e}\n", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[已取消]", file=sys.stderr)
        sys.exit(130)
    except Exception:
        tb = traceback.format_exc()
        log("ERROR\n" + tb)
        print("\n[运行出错] 详细信息已写入 data/run.log，可把最后 20 行发给维护者。\n",
              file=sys.stderr)
        print(tb, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
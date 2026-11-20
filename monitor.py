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
    update_history, normalize_history, _matches_terms,
    score_repo_dev, build_queries_dev,
)
from lib.trending import TrendingClient
from lib.reporter import build_report_data, save_reports, validate_enriched

LOG_MAX_BYTES = 1_000_000
# 当前 profile 的运行日志路径（由 main() 根据配置设置）
_LOG_PATH = "data/run.log"


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def log(msg: str) -> None:
    """把运行过程写进运行日志，方便排查定时任务失败。"""
    try:
        p = root_path(_LOG_PATH)
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


def load_history(cfg: dict) -> dict:
    p = root_path(cfg["dedup"]["history_file"])
    history = {"records": {}, "updated_at": None, "total_tracked": 0}
    if p.exists():
        try:
            history = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[警告] 历史文件读取失败，将重新开始：{e}", file=sys.stderr)
            log(f"history load failed: {e}")
    if normalize_history(history):
        save_history(history, cfg)
        log("history normalized: added last_seen for old records")
    return history


def save_history(h: dict, cfg: dict) -> None:
    p = root_path(cfg["dedup"]["history_file"])
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
    is_dev = cfg.get("mode") == "developer"
    all_repos: list[dict] = []
    categories: dict[str, str] = {}

    # 程序员版：Trending 榜单是主数据源（真实的今日/本周新增 star）
    if is_dev and cfg.get("trending", {}).get("enabled"):
        tr = cfg["trending"]
        tc = TrendingClient(
            period=tr.get("period", "daily"), delay=tr.get("request_delay_seconds", 2),
            token=token, enrich_with_api=tr.get("enrich_with_api", True),
        )
        if verbose:
            print(f"[采集] GitHub Trending {tr.get('period','daily')} 榜，抓取 {tr.get('count',25)} 条...")
        trending = tc.fetch(count=tr.get("count", 25))
        for it in trending:
            categories.setdefault(it["full_name"], "Trending")
            all_repos.append(it)
        if verbose:
            print(f"[采集] Trending 拿到 {len(trending)} 条（API 补元数据 {tc.request_count} 次，"
                  f"缓存 {tc.cache_hits} 次）")
        log(f"trending fetched={len(trending)} requests={tc.request_count} cache={tc.cache_hits}")

    client = GitHubClient(token=token, delay=s["request_delay_seconds"])
    queries = build_queries_dev(cfg) if is_dev else build_queries(cfg)
    log(f"collect start: {len(queries)} queries, token={'yes' if client.token else 'no'}, dev={is_dev}")
    if verbose:
        print(f"[采集] 共 {len(queries)} 个搜索式，请求间隔 {s['request_delay_seconds']}s，"
              f"{'已检测到 Token' if client.token else '未配置 Token（额度较低）'}")

    for i, (q, cat, required) in enumerate(queries, 1):
        if verbose:
            print(f"  ({i}/{len(queries)}) [{cat}] {q[:70]}...")
        items = client.search_repos(q, sort="stars", order="desc", per_page=s["results_per_query"])
        if required:
            items = [it for it in items if _matches_terms(it, required)]
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

    scorer = score_repo_dev if is_dev else score_repo
    scored = [scorer(r, categories.get(r["full_name"], "Trending" if is_dev else "综合"), cfg)
              for r in kept]
    # 程序员榜按热度（新增 star）优先排序，而不是普通人版的价值分
    if is_dev:
        scored.sort(key=lambda x: (-(x.get("stars_growth") or 0), -x["score"], -x["stars"]))

    history = load_history(cfg)
    selected, dstats = dedup_and_select(scored, cfg, history, by_growth=is_dev)
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
            if is_dev:
                print(f"   +{it.get('stars_growth',0):>5}/{'日' if it.get('growth_period')=='daily' else '周'} "
                      f"[{it['category']}] {it['full_name']} ⭐{it['stars']}")
            else:
                print(f"   #{it['score']:>5} [{it['category']}] {it['full_name']} ⭐{it['stars']}")

    # 把本次见到的项目记入历史（只在首次见到时记录，避免每天重复出现在候选池）
    if cfg["dedup"].get("persist_since_first_seen", True):
        update_history(history, selected, payload["all_seen"])
        save_history(history, cfg)

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
    h = load_history(cfg)
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
    ap.add_argument("--profile", default="consumer", choices=["consumer", "dev"],
                    help="consumer=普通人版(默认), dev=程序员排行榜版")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="即使今天已有非空候选也重新采集并覆盖")
    args = ap.parse_args()

    global _LOG_PATH
    try:
        cfg = load_config(profile=args.profile)
        _LOG_PATH = cfg.get("run_log_file") or (
            "data-dev/run.log" if args.profile == "dev" else "data/run.log"
        )
        log(f"=== start {args.cmd} (profile={args.profile}) ===")
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
        print(f"\n[运行出错] 详细信息已写入 {_LOG_PATH}，可把最后 20 行发给维护者。\n",
              file=sys.stderr)
        print(tb, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
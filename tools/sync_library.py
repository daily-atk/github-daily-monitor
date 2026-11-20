#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把普通人榜 + 程序员热度榜的前三名同步到 WorkBuddy 资料库表格。

流程：
  1. 读取两版最新候选数据 + AI 增强数据，复现报告 final 排序，各取前 3；
  2. 生成资料库记录（6 条），落盘到 data/top3_for_library.json 供查阅/手动导入；
  3. 若探测到 WorkBuddy 资料库技能脚本，按「日期 + 榜单」幂等写入表格并回读验证；
  4. 结果以单行 JSON 打印到 stdout，日志走 stderr。

零第三方依赖。找不到资料库脚本时以「仅导出」模式结束（不算失败），
此时可用 WorkBuddy 资料库能力把 data/top3_for_library.json 里的 records 追加到表格。

用法：
  python tools/sync_library.py
  python tools/sync_library.py --database-id <id> --library-dir <dir>
  python tools/sync_library.py --dry-run        # 只导出，不写入
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.config import load_config  # noqa: E402
from lib.reporter import build_report_data  # noqa: E402

DEFAULT_DATABASE_ID = "xX25PIiOQbZsat3exiY0oT"
OUT_FILE = ROOT / "data" / "top3_for_library.json"

BOARD_CONSUMER = "普通人版"
BOARD_DEV = "程序员热度榜"

# 表格字段（与资料库表格保持一致）
LIB_SCRIPT = "batch_add_database_records.py"
QUERY_SCRIPT = "query_database_record.py"


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def find_library_db_dir(explicit: str | None) -> str | None:
    """定位资料库 database 脚本目录；找不到返回 None。"""
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    for env in ("WORKBUDDY_LIBRARY_SKILL_DIR", "CODEBUDDY_SKILL_DIR"):
        val = os.environ.get(env, "").strip()
        if val:
            candidates.append(val if val.replace("\\", "/").lower().endswith("/database")
                               else os.path.join(val, "database"))
    rel = "resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library/database"
    for drive in ("D:/workbuddy", "D:/WorkBuddy", "C:/workbuddy", "C:/WorkBuddy"):
        candidates.append(os.path.join(drive, rel))
    candidates.append(os.path.join(os.path.expanduser("~"), ".workbuddy", "skills", "library", "database"))

    seen = set()
    for c in candidates:
        norm = os.path.normcase(os.path.abspath(c)) if c else ""
        if not c or norm in seen:
            continue
        seen.add(norm)
        if os.path.isfile(os.path.join(c, LIB_SCRIPT)):
            return c
    return None


def load_board(profile: str) -> tuple[str, list[dict]]:
    """复现某版报告的最终 items，返回 (date_str, items)。"""
    cfg = load_config(profile=profile)
    out = cfg.get("output", {}) or {}
    cand_path = ROOT / out.get("candidates_file", "")
    if not cand_path.is_file():
        log(f"[{profile}] 找不到候选文件：{cand_path}（先运行采集）")
        return "", []
    try:
        cand_data = json.loads(cand_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log(f"[{profile}] 候选文件读取失败：{exc}")
        return "", []

    date_str = str(cand_data.get("date", ""))
    candidates = cand_data.get("candidates", []) or []

    enrich_path = ROOT / out.get("enriched_file", "") if out.get("enriched_file") else None
    data = build_report_data(candidates, cfg, date_str, enriched_path=enrich_path)
    return date_str, data.get("items", [])[:3]


# 英文用途关键词 -> 中文短语，用于生成看不懂英文时的中文看点
_PURPOSE_MAP = [
    (("habit", "tracker", "routine"), "习惯打卡与追踪"),
    (("notepad", "notes", "note-taking", "markdown"), "笔记记录"),
    (("launcher", "home screen"), "桌面启动器"),
    (("budget", "expense", "finance", "money", "invoice", "accounting"), "记账与预算"),
    (("fitness", "workout", "exercise", "gym"), "健身训练"),
    (("sleep", "meditation", "relax"), "睡眠与冥想"),
    (("task", "todo", "kanban", "planner"), "任务与待办管理"),
    (("focus", "pomodoro", "timer"), "专注与计时"),
    (("calendar", "schedule", "reminder"), "日程与提醒"),
    (("password", "vault", "security", "encrypt"), "密码与安全"),
    (("photo", "image", "gallery"), "照片与图片管理"),
    (("weather",), "天气查询"),
    (("reader", "reading", "rss", "book"), "阅读与资讯"),
    (("translation", "translate", "dictionary"), "翻译与词典"),
    (("music", "audio", "podcast"), "音乐与音频"),
    (("video", "player", "stream"), "视频播放"),
    (("self-host", "selfhost", "docker", "server"), "可自托管"),
    (("browser",), "浏览器工具"),
    (("weather", "dashboard", "homepage"), "个人主页/仪表盘"),
    (("agent", "claude", "copilot", "assistant"), "AI 助手/Agent"),
    (("skill", "prompt", "slash-command"), "AI 技能包"),
    (("research", "deep-research", "search"), "资料检索与研究"),
    (("cli", "terminal", "command-line"), "命令行工具"),
    (("security", "bug", "red-team", "vulnerability"), "安全测试"),
    (("database", "sql", "storage"), "数据库与存储"),
    (("framework", "library", "sdk"), "开发框架/库"),
    (("deploy", "devops", "kubernetes", "ci-cd"), "部署与运维"),
]


def cn_highlight(item: dict) -> str:
    """生成一句中文看点：用途 + 平台/语言；AI 增强过的 features 优先。"""
    features = str(item.get("features") or "").strip()
    # AI 增强文件里的 features 是中文（含汉字）时，直接用它
    if features and any("\u4e00" <= ch <= "\u9fff" for ch in features):
        return features[:200]

    desc = str(item.get("description") or "").lower()
    topics = " ".join(str(t).lower() for t in (item.get("topics") or []))
    text = f"{desc} {topics}"
    purposes: list[str] = []
    for keys, cn in _PURPOSE_MAP:
        if any(k in text for k in keys):
            if cn not in purposes:
                purposes.append(cn)
        if len(purposes) >= 2:
            break

    cat = str(item.get("category_label") or "").strip("- ")
    lang = str(item.get("language") or "").strip()
    parts: list[str] = []
    if purposes:
        joined = "、".join(purposes)
        parts.append(joined if joined.endswith(("工具", "包", "库", "框架")) else joined + "类项目")
    elif cat:
        parts.append(f"{cat}类项目")
    else:
        parts.append("开源项目")
    if lang:
        parts.append(f"{lang} 实现")
    highlight = "，".join(parts) + "。"
    # 附一句原始描述（截断），保留忠实度但避免过长
    if desc:
        highlight += f" 原描述：{str(item.get('description') or '')[:110]}"
    return highlight[:400]


def tech_highlight(item: dict) -> str:
    """程序员榜：技术栈 + 话题方向 + 新增 star 说明。"""
    lang = str(item.get("language") or "未标注语言")
    lic = str(item.get("license") or "未标注许可证")
    topics = [str(t) for t in (item.get("topics") or [])][:3]
    topic_text = "、".join(topics) if topics else lang
    growth = int(item.get("stars_growth") or 0)
    period = "今日" if str(item.get("growth_period", "daily")) == "daily" else "本周"
    return f"{lang} · {lic}；话题集中在 {topic_text}；{period}新增 {growth:,} star。"[:400]


def to_record(date_str: str, board: str, item: dict) -> dict:
    is_dev = board == BOARD_DEV
    homepage = str(item.get("homepage") or "").strip()
    return {
        "日期": {"date": date_str},
        "榜单": {"select": board},
        "排名": {"number": int(item.get("rank", 0))},
        "项目": {"text": str(item.get("full_name", ""))},
        "链接": {"url": {"text": "GitHub", "link": str(item.get("url", ""))}},
        "一句话看点": {"text": cn_highlight(item)},
        "语言": {"text": str(item.get("language") or "")},
        "总Star": {"number": int(item.get("stars") or 0)},
        "今日新增Star": {"number": int(item.get("stars_growth") or 0)},
        "适合人群": {"text": str(item.get("audience") or "").strip()[:400]},
        "实用价值": {"text": str(item.get("value") or "").strip()[:400]},
        "上手难度": {"select": str(item.get("difficulty") or "中").strip()},
        "注意事项": {"text": str(item.get("notes") or "").strip()[:400]},
        "方向分类": {"text": str(item.get("category_label") or "").strip()[:60]},
        "许可证": {"text": str(item.get("license") or "").strip()[:60]},
        "项目主页": {"url": {"text": "主页", "link": homepage}} if homepage else {"url": {"text": "", "link": ""}},
        "技术亮点": {"text": tech_highlight(item) if is_dev else ""},
    }


def call_lib(db_dir: str, script: str, payload: dict | None, args: list[str]) -> dict:
    cmd = [sys.executable, os.path.join(db_dir, script)] + args
    stdin_data = json.dumps(payload, ensure_ascii=False) if payload is not None else None
    proc = subprocess.run(cmd, input=stdin_data, text=True, capture_output=True,
                          encoding="utf-8", errors="replace", timeout=60)
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"_error": (proc.stdout or proc.stderr or "无输出").strip()[:400]}


def existing_rows(db_dir: str, database_id: str) -> dict[tuple[str, str, int], dict]:
    """已入库记录映射：唯一键(日期+榜单+排名) -> {record_id, 项目}。"""
    res = call_lib(db_dir, QUERY_SCRIPT, None,
                   ["--database-id", database_id, "--page-size", "500"])
    rows: dict[tuple[str, str, int], dict] = {}
    for row in res.get("results", []) or []:
        d = row.get("日期")
        b = row.get("榜单")
        r = row.get("排名")
        if isinstance(d, str) and isinstance(b, str):
            try:
                rank = int(r) if r is not None else 0
            except (TypeError, ValueError):
                rank = 0
            rows[(d[:10], b, rank)] = {
                "record_id": row.get("record_id", ""),
                "项目": row.get("项目", ""),
            }
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--database-id", default=DEFAULT_DATABASE_ID)
    parser.add_argument("--library-dir", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-update", action="store_true",
                        help="项目相同也强制用最新数据覆盖（用于回填新增字段）")
    args, _ = parser.parse_known_args()

    consumer_date, consumer_items = load_board("consumer")
    dev_date, dev_items = load_board("dev")

    records: list[dict] = []
    if consumer_items:
        records += [to_record(consumer_date, BOARD_CONSUMER, it) for it in consumer_items]
    if dev_items:
        records += [to_record(dev_date, BOARD_DEV, it) for it in dev_items]

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps({"database_id": args.database_id, "boards": [
            {"board": BOARD_CONSUMER, "date": consumer_date, "count": len(consumer_items)},
            {"board": BOARD_DEV, "date": dev_date, "count": len(dev_items)},
        ], "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(f"已导出 {len(records)} 条记录到 {OUT_FILE}")

    result = {
        "ok": bool(records),
        "exported": len(records),
        "out_file": str(OUT_FILE),
        "consumer": {"date": consumer_date, "count": len(consumer_items)},
        "dev": {"date": dev_date, "count": len(dev_items)},
        "database_id": args.database_id,
        "mode": "export-only",
        "written": 0,
        "skipped": [],
    }
    if not records:
        print(json.dumps(result, ensure_ascii=False))
        return

    db_dir = find_library_db_dir(args.library_dir or None)
    if args.dry_run or not db_dir:
        result["note"] = ("dry-run" if args.dry_run else
                          "未找到资料库脚本目录，仅导出；可用资料库能力导入 top3_for_library.json")
        log(result["note"])
        print(json.dumps(result, ensure_ascii=False))
        return

    result["mode"] = "write"
    try:
        seen = existing_rows(db_dir, args.database_id)
    except subprocess.TimeoutExpired:
        result["note"] = "查询已有记录超时，未写入以避免重复"
        print(json.dumps(result, ensure_ascii=False))
        return

    to_write: list[dict] = []
    to_update: list[dict] = []
    for rec in records:
        key = (str(rec["日期"]["date"])[:10], str(rec["榜单"]["select"]),
               int(rec["排名"]["number"]))
        old = seen.get(key)
        if old is None:
            to_write.append(rec)
        elif args.force_update or str(old.get("项目", "")) != str(rec["项目"]["text"]):
            # 项目变了（榜单刷新）或强制回填：更新该行而非重复插入
            to_update.append({"record_id": old["record_id"], "properties": rec})
        else:
            result["skipped"].append({"date": key[0], "board": key[1],
                                      "rank": key[2], "reason": "已有相同记录"})

    if to_write:
        add_res = call_lib(db_dir, LIB_SCRIPT, None,
                           ["--database-id", args.database_id,
                            "--records", json.dumps(to_write, ensure_ascii=False)])
        row_results = add_res.get("results", []) or []
        success_ids = [r.get("id") for r in row_results if isinstance(r, dict) and r.get("success")]
        verified = 0
        for rid in success_ids:
            got = call_lib(db_dir, "get_database_record.py", None,
                           ["--database-id", args.database_id, "--record-id", rid])
            if got.get("record_id") or got.get("fields"):
                verified += 1
        result["written"] = len(success_ids)
        result["verified"] = verified
        if add_res.get("_error"):
            result["write_error"] = add_res["_error"]
        failed = [r for r in row_results if isinstance(r, dict) and not r.get("success")]
        if failed:
            result["failed"] = len(failed)

    if to_update:
        upd_res = call_lib(db_dir, "batch_update_database_records.py", None,
                           ["--database-id", args.database_id,
                            "--records", json.dumps(to_update, ensure_ascii=False)])
        upd_rows = upd_res.get("results", []) or []
        result["updated"] = sum(1 for r in upd_rows if isinstance(r, dict) and r.get("success"))
        if upd_res.get("_error"):
            result["update_error"] = upd_res["_error"]

    if not to_write and not to_update:
        result["note"] = "当天两版前三名均已入库且无变化，跳过"

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

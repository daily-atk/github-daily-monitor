"""采集 → 过滤 → 去重 → 普通人价值打分 → 排序 的核心流水线。"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import strip_notes

# 面向"普通人"的消费级信号词（命中即加分）
CONSUMER_WORDS = {
    "app", "application", "tool", "dashboard", "browser", "extension", "desktop",
    "mobile", "ios", "android", "web", "self-hosted", "selfhosted", "no-code",
    "one-click", "simple", "easy", "personal", "everyday", "daily", "planner",
    "tracker", "manager", "reminder", "organizer", "应用", "工具", "软件", "插件",
    "简单", "一键", "个人", "日常", "管理", "追踪", "提醒",
}
# 开发者向信号词（命中即扣分）
DEVELOPER_WORDS = {
    "sdk", "library", "framework", "api", "cli", "database", "kernel", "compiler",
    "package", "npm", "pip", "docker image", "kubernetes", "devops", "middleware",
    "open-source alternative to", "programming language", "library for",
}
# 上手难度推断：低/中/高
EASY_WORDS = {"browser extension", "web app", "online", "desktop app", "ios", "android",
              "chrome extension", "mobile app", "website", "no install", "一键", "网页", "插件"}
HARD_WORDS = {"self-hosted", "docker", "server", "terminal", "cli", "command line",
              "kubernetes", "requirements.txt", "自建", "服务器", "命令行", "部署"}
# 纯开发者基础设施信号：命中即判定为"对普通人无直接价值"，重罚
DEV_INFRA_WORDS = {
    "webkit", "browser engine", "rendering engine", "kernel", "database engine",
    "media center", "operating system", "linux distribution", "compiler", "runtime",
    "framework for", "sdk for", "api server", "orm", "query engine", "search engine library",
    "kubernetes", "container runtime", "package manager", "build system", "monorepo",
    "paradedb", "postgresql extension", "elasticsearch",
}
# 这些 topic 表示是给开发者用的基础设施，而非消费级应用
DEV_INFRA_TOPICS = {
    "browser-engine", "database", "compiler", "operating-system", "kernel", "sdk",
    "framework", "library", "orm", "kubernetes", "devops", "backend", "api",
    "javascript-library", "python-library", "programming-language",
}

CATEGORY_LABEL = {
    "学习": "📚 学习", "生活": "🏠 生活", "效率": "⚡ 效率",
    "健康": "💪 健康", "财务": "💰 财务", "综合": "🧰 综合",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(days_ago: int) -> str:
    return (_now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def build_queries(cfg: dict) -> list[tuple[str, str]]:
    """生成 (查询式, 领域标签) 列表：每个领域一个查询 + 通用捞取。

    为节省匿名 API 额度，每个领域只用第一个代表词，且放宽为 created/pushed 双通道，
    真正精细的领域判断交给本地打分逻辑完成。
    """
    s = cfg["search"]
    keywords = cfg["keywords"]
    since = _iso(s["lookback_days"])
    pushed = _iso(s.get("updated_lookback_days", 3))
    min_s = s["min_stars"]
    queries: list[tuple[str, str]] = []
    # 通道一：各领域近期新建项目（用代表词，不加引号，覆盖面更广）
    for category, words in keywords.items():
        if category.startswith("_") or not words:
            continue
        w = words[0]
        q = f'{w} created:>{since} stars:>={min_s}'
        queries.append((q, category))
    # 通道二：高星项目近期重要更新（捞取"值得关注的老项目新动作"）
    for category, words in list(keywords.items())[:2]:
        if category.startswith("_") or not words:
            continue
        w = words[0].split()[0]  # 取核心词
        q = f'{w} stars:>={max(min_s * 8, 500)} pushed:>{pushed}'
        queries.append((q, category))
    return queries[: s["max_queries_per_run"]]


def _contains_any(text: str, words) -> bool:
    low = text.lower()
    return any(w.lower() in low for w in words)


def filter_low_quality(repos: list[dict], cfg: dict) -> tuple[list[dict], dict]:
    """按配置过滤低质量项目，返回 (保留, 统计)。"""
    f = strip_notes(cfg["filters"])
    excl = strip_notes(cfg["exclude_words"])
    stats = {"total_raw": len(repos), "by_no_desc": 0, "by_short_desc": 0,
             "by_exclude_name": 0, "by_exclude_desc": 0, "by_fork_ratio": 0,
             "by_archived": 0, "by_stars": 0, "kept": 0}
    kept = []
    seen_name = set()
    for r in repos:
        name = r.get("full_name", "")
        if not name or name in seen_name:
            continue
        seen_name.add(name)
        desc = (r.get("description") or "").strip()
        if f.get("require_description", True) and not desc:
            stats["by_no_desc"] += 1
            continue
        if len(desc) < f.get("min_description_length", 25):
            stats["by_short_desc"] += 1
            continue
        if _contains_any(name, excl.get("name", [])):
            stats["by_exclude_name"] += 1
            continue
        if _contains_any(desc, excl.get("description", [])):
            stats["by_exclude_desc"] += 1
            continue
        if r.get("archived") and f.get("exclude_archived", True):
            stats["by_archived"] += 1
            continue
        if r.get("disabled") and f.get("exclude_disabled", True):
            stats["by_archived"] += 1
            continue
        stars = r.get("stargazers_count", 0)
        if stars < cfg["search"]["min_stars"] or stars > cfg["search"]["max_stars"]:
            stats["by_stars"] += 1
            continue
        forks = r.get("forks_count", 0)
        if stars > 0 and forks / stars > f.get("max_fork_ratio", 0.85):
            stats["by_fork_ratio"] += 1
            continue
        if r.get("size", 0) and r["size"] < f.get("min_size_kb", 20):
            stats["by_stars"] += 1
            continue
        kept.append(r)
    stats["kept"] = len(kept)
    return kept, stats


def score_repo(r: dict, category: str, cfg: dict) -> dict:
    """给单个仓库打"普通人实用价值"分，并给出难度、领域标签。"""
    sc = strip_notes(cfg["scoring"])
    name = r.get("full_name", "")
    desc = r.get("description") or ""
    topics = r.get("topics") or []
    text = f"{name} {desc} {' '.join(topics)}".lower()

    consumer_hits = sum(1 for w in CONSUMER_WORDS if w in text)
    dev_hits = sum(1 for w in DEVELOPER_WORDS if w in text)
    weight = sc.get("domain_weight", {}).get(category, 1.0)

    # 开发者基础设施检测（命中即视为对普通人无直接价值）
    infra_name_hit = _contains_any(name.lower(), DEV_INFRA_WORDS)
    infra_topic_hit = bool(set(t.lower() for t in topics) & DEV_INFRA_TOPICS)

    score = 40.0
    score += min(consumer_hits, 6) * 3.5          # 消费级信号，最多 +21
    score -= min(dev_hits, 5) * 3.0                # 开发者向，最多 -15
    score += min(len(topics), 6) * 1.2             # 有主题分类，信息更完整
    if infra_name_hit:
        score -= 30
    if infra_topic_hit:
        score -= 18
    stars = r.get("stargazers_count", 0)
    if stars >= 1000:
        score += 8
    elif stars >= 400:
        score += 5
    elif stars >= 150:
        score += 2
    if r.get("homepage"):
        score += 4
    # 新鲜度
    created = r.get("created_at", "")
    try:
        cd = datetime.fromisoformat(created.replace("Z", "+00:00"))
        age = (_now() - cd).days
        if age <= sc.get("fresh_bonus_days", 7):
            score += 10
        elif age <= 30:
            score += 5
    except Exception:
        pass
    score *= weight
    score = round(max(0, min(100, score)), 1)

    easy_hits = sum(1 for w in EASY_WORDS if w in text)
    hard_hits = sum(1 for w in HARD_WORDS if w in text)
    if easy_hits > hard_hits:
        difficulty = "低"
    elif hard_hits > easy_hits + 1:
        difficulty = "高"
    else:
        difficulty = "中"

    return {
        "full_name": name,
        "name": r.get("name", name.split("/")[-1]),
        "owner": r.get("owner", {}).get("login", name.split("/")[0]),
        "url": r.get("html_url", f"https://github.com/{name}"),
        "homepage": r.get("homepage") or "",
        "description": (r.get("description") or "").strip(),
        "stars": stars,
        "forks": r.get("forks_count", 0),
        "language": r.get("language") or "",
        "topics": topics[:8],
        "created_at": created,
        "pushed_at": r.get("pushed_at", ""),
        "category": category,
        "category_label": CATEGORY_LABEL.get(category, "🧰 综合"),
        "difficulty": difficulty,
        "score": score,
        "consumer_hits": consumer_hits,
        "dev_hits": dev_hits,
        "fresh": (created[:10] >= _iso(sc.get("fresh_bonus_days", 7))),
    }


def dedup_and_select(scored: list[dict], cfg: dict, history: dict
                     ) -> tuple[list[dict], dict]:
    """去重（历史 + 冷却期）并选出 Top N。"""
    d = strip_notes(cfg["dedup"])
    cooldown = d.get("cooldown_days", 30)
    records = history.get("records", {})
    now = _now()
    stats = {"by_history": 0, "in_cooldown": 0, "selected": 0}

    fresh_pool = []
    for item in scored:
        fn = item["full_name"]
        rec = records.get(fn)
        if rec:
            try:
                last = datetime.fromisoformat(rec["last_recommended"].replace("Z", "+00:00"))
                if (now - last).days < cooldown:
                    stats["in_cooldown"] += 1
                    continue
            except Exception:
                stats["by_history"] += 1
                continue
        fresh_pool.append(item)

    # 同名项目只保留得分最高的一条
    best: dict[str, dict] = {}
    for item in fresh_pool:
        fn = item["full_name"]
        if fn not in best or item["score"] > best[fn]["score"]:
            best[fn] = item

    ranked = sorted(best.values(), key=lambda x: (-x["score"], -x["stars"]))
    min_score = cfg["scoring"]["min_score"]
    ranked = [x for x in ranked if x["score"] >= min_score]
    top = ranked[: cfg["scoring"]["top_n"]]
    stats["selected"] = len(top)
    return top, stats


def update_history(history: dict, selected: list[dict], all_seen: list[str]) -> dict:
    """写回历史：推荐记录 + 所有已见过项目（防止每天重复出现在候选池）。"""
    now = _now().isoformat()
    for item in selected:
        fn = item["full_name"]
        rec = history["records"].get(fn, {"times_recommended": 0, "first_seen": now})
        rec["times_recommended"] += 1
        rec["last_recommended"] = now
        rec["last_title"] = item["name"]
        rec["last_score"] = item["score"]
        history["records"][fn] = rec
    for fn in all_seen:
        if fn not in history["records"]:
            history["records"][fn] = {
                "times_recommended": 0, "first_seen": now, "last_recommended": None,
            }
    history["updated_at"] = now
    history["total_tracked"] = len(history["records"])
    return history

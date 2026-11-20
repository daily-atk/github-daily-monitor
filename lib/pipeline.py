"""采集 → 过滤 → 去重 → 普通人价值打分 → 排序 的核心流水线。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .config import strip_notes

# 面向"普通人"的消费级信号词（命中即加分）
CONSUMER_WORDS = {
    "app", "application", "tool", "dashboard", "browser", "extension", "desktop",
    "mobile", "ios", "android", "web", "website", "self-hosted", "selfhosted", "no-code",
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
EASY_WORDS = {
    "browser extension", "web app", "online", "desktop app", "ios", "android",
    "chrome extension", "mobile app", "website", "no install", "一键", "网页", "插件",
}
HARD_WORDS = {
    "self-hosted", "docker", "server", "terminal", "cli", "command line",
    "kubernetes", "requirements.txt", "自建", "服务器", "命令行", "部署",
}
# 纯开发者基础设施信号：出现在项目名/topics 里即重罚
DEV_INFRA_WORDS = {
    "webkit", "browser engine", "rendering engine", "kernel", "database engine",
    "operating system", "linux distribution", "compiler", "runtime",
    "framework for", "sdk for", "api server", "orm", "query engine",
    "search engine library", "kubernetes", "container runtime", "package manager",
    "build system", "monorepo", "paradedb", "postgresql extension", "elasticsearch",
}
# 描述里的强开发者信号：只轻罚，避免把 Kodi 这类消费级项目误杀
DEV_INFRA_DESC_WORDS = {
    "sdk for", "api server", "framework for", "library for", "query engine",
    "container runtime", "build system", "monorepo", "postgresql extension",
    "elasticsearch", "orm", "database engine",
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

# 程序员版分类标签
DEV_CATEGORY_LABEL = {
    "AI/LLM": "🤖 AI/LLM", "开发工具": "🛠️ 开发工具", "框架/库": "🧩 框架/库",
    "数据库/存储": "🗄️ 数据库/存储", "DevOps/ infra": "⚙️ DevOps", "安全": "🔒 安全",
    "前端": "🎨 前端", "系统/语言": "💻 系统/语言", "综合": "🧰 综合",
    "Trending": "🔥 Trending",
}

# 程序员版：技术价值正向信号（命中加分，与普通人版相反）
DEV_POSITIVE_WORDS = {
    "framework", "library", "sdk", "engine", "database", "compiler", "runtime",
    "kubernetes", "cli", "api", "open source", "typescript", "rust", "go",
    "performance", "self-hosted", "developer", "tooling", "agent", "llm",
    "vector", "embedding", "inference", "observability", "orm", "bundler",
}
# 程序员版：成熟/可信信号
DEV_QUALITY_WORDS = {
    "production", "battle-tested", "used by", "framework", "documentation",
    "typescript", "tests", "benchmark", "actively maintained",
}

# 平台推断规则（用于报告里告诉普通人"手机/电脑能不能用"）
PLATFORM_RULES = [
    ("手机", ("android", "ios", "iphone", "ipad", "mobile", "手机")),
    ("网页", ("web app", "browser extension", "chrome extension", "website", "网页")),
    ("电脑", ("windows", "macos", "linux", "desktop", "桌面")),
    ("自托管", ("self-hosted", "selfhosted", "docker", "自建")),
]

# 查询短语里过于宽泛、不适合作为"必须命中"校验的词
QUERY_STOPWORDS = {"app", "application", "tool", "tools", "software", "platform"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(days_ago: int) -> str:
    return (_now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def _hits(text: str, words) -> int:
    """按单词边界统计命中，避免 api 命中 capital、app 命中 apple 这类误判。

    纯英文词用正则边界（允许简单复数 s）；中文词没有空格边界，仍按子串匹配。
    """
    low = (text or "").lower()
    n = 0
    for w in words:
        wl = str(w).lower().strip()
        if not wl:
            continue
        if re.search(r"[a-z]", wl):
            pat = r"(?<![a-z0-9])" + re.escape(wl) + r"(?:s)?(?![a-z0-9])"
            if re.search(pat, low):
                n += 1
        elif wl in low:
            n += 1
    return n


def _platforms(text: str) -> str:
    low = (text or "").lower()
    tags = [label for label, keys in PLATFORM_RULES if any(k in low for k in keys)]
    return " · ".join(tags) or "—"


def _terms_for(phrase: str) -> list[str]:
    """把配置里的短语拆成"必须命中"的词，去掉 app/tool 这类泛词。"""
    terms = [t for t in re.split(r"\s+", phrase.lower())
             if len(t) > 1 and t not in QUERY_STOPWORDS]
    return terms or [phrase.lower()]


def _matches_terms(repo: dict, terms: list[str]) -> bool:
    """本地校验：名称/描述/topics 必须包含短语里的所有实词。

    例如 "habit tracker" 会排除 habitat（缺少 tracker），但保留真正的习惯追踪器。
    """
    if not terms:
        return True
    text = " ".join([
        str(repo.get("name") or ""),
        str(repo.get("full_name") or ""),
        str(repo.get("description") or ""),
        " ".join(str(t) for t in (repo.get("topics") or [])),
    ]).lower()
    return all(term in text for term in terms)


def build_queries(cfg: dict) -> list[tuple[str, str, list[str]]]:
    """生成 (查询式, 领域标签, 必须命中词) 列表。

    查询用短语里的核心词保证召回，再用本地 _matches_terms 保证精度；
    代表词每天轮换，几天内覆盖配置里的全部关键词。
    """
    s = cfg["search"]
    keywords = cfg["keywords"]
    since = _iso(s["lookback_days"])
    pushed = _iso(s.get("updated_lookback_days", 3))
    min_s = s["min_stars"]
    rotation = datetime.now().toordinal()  # 每天 +1，逐日轮换代表词

    items = [(cat, words) for cat, words in keywords.items()
             if not cat.startswith("_") and words]
    queries: list[tuple[str, str, list[str]]] = []

    # 通道一：各领域近期新建项目（代表词轮换）
    for category, words in items:
        phrase = words[rotation % len(words)]
        terms = _terms_for(phrase)
        queries.append((f"{terms[0]} created:>{since} stars:>={min_s}", category, terms))

    # 通道二：全部领域的高星项目近期重要更新
    for category, words in items:
        phrase = words[(rotation + 1) % len(words)]
        terms = _terms_for(phrase)
        min_update = max(min_s * 4, 300)
        queries.append((f"{terms[0]} stars:>={min_update} pushed:>{pushed}", category, terms))

    return queries[: s["max_queries_per_run"]]


def _contains_any(text: str, words) -> bool:
    """排除词用子串匹配（支持 awesome- 这类前缀语义）。"""
    low = (text or "").lower()
    return any(str(w).lower() in low for w in words)


def filter_low_quality(repos: list[dict], cfg: dict) -> tuple[list[dict], dict]:
    """按配置过滤低质量项目，返回 (保留, 统计)。"""
    f = strip_notes(cfg["filters"])
    excl = strip_notes(cfg["exclude_words"])
    stats = {"total_raw": len(repos), "by_no_desc": 0, "by_short_desc": 0,
             "by_exclude_name": 0, "by_exclude_desc": 0, "by_fork_ratio": 0,
             "by_archived": 0, "by_stars": 0, "by_size": 0, "kept": 0}
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
            stats["by_size"] += 1
            continue
        kept.append(r)
    stats["kept"] = len(kept)
    return kept, stats


def score_repo(r: dict, category: str, cfg: dict) -> dict:
    """给单个仓库打"普通人实用价值"分，并给出难度、平台、许可证等字段。"""
    sc = strip_notes(cfg["scoring"])
    name = r.get("full_name", "")
    desc = r.get("description") or ""
    topics = [str(t) for t in (r.get("topics") or [])]
    text = f"{name} {desc} {' '.join(topics)}"

    consumer_hits = _hits(text, CONSUMER_WORDS)
    dev_hits = _hits(text, DEVELOPER_WORDS)
    weight = sc.get("domain_weight", {}).get(category, 1.0)

    # 开发者基础设施检测：项目名/topics 重罚，描述轻罚（防止误杀消费级项目）
    infra_name_hits = _hits(name, DEV_INFRA_WORDS)
    infra_desc_hits = _hits(desc, DEV_INFRA_DESC_WORDS)
    infra_topic_hit = bool({t.lower() for t in topics} & DEV_INFRA_TOPICS)

    lic = r.get("license") or {}
    spdx = (lic.get("spdx_id") or "") if isinstance(lic, dict) else ""
    if spdx.upper() in ("NOASSERTION", "NONE"):
        spdx = ""

    score = 40.0
    score += min(consumer_hits, 6) * 3.5          # 消费级信号，最多 +21
    score -= min(dev_hits, 5) * 3.0                # 开发者向，最多 -15
    score += min(len(topics), 6) * 1.2             # 有主题分类，信息更完整
    if infra_name_hits:
        score -= 30
    if infra_topic_hit:
        score -= 18
    if infra_desc_hits:
        score -= min(infra_desc_hits, 2) * 6

    stars = r.get("stargazers_count", 0)
    if stars >= 1000:
        score += 8
    elif stars >= 400:
        score += 5
    elif stars >= 150:
        score += 2
    if r.get("homepage"):
        score += 4
    if not spdx:
        # 没有开源许可证，普通人无法判断能否安全使用/商用，扣分
        score -= 6

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
    score = round(max(0.0, min(100.0, score)), 1)

    easy_hits = _hits(text, EASY_WORDS)
    hard_hits = _hits(text, HARD_WORDS)
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
        "license": spdx,
        "platforms": _platforms(f"{desc} {' '.join(topics)}"),
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


def dedup_and_select(scored: list[dict], cfg: dict, history: dict,
                     by_growth: bool = False) -> tuple[list[dict], dict]:
    """去重（推荐冷却 + 近期见过冷却）并按领域配额选出 Top N。

    by_growth=True 时按 stars_growth 排序（程序员热度榜），且 min_score 门槛放宽。
    """
    d = strip_notes(cfg["dedup"])
    sc = strip_notes(cfg["scoring"])
    cooldown = d.get("cooldown_days", 30)
    seen_cooldown = d.get("seen_cooldown_days", 7)
    records = history.get("records", {})
    now = _now()
    stats = {"in_cooldown": 0, "recent_seen": 0, "selected": 0}

    fresh_pool = []
    for item in scored:
        fn = item["full_name"]
        rec = records.get(fn)
        if isinstance(rec, dict):
            last_rec = rec.get("last_recommended")
            if last_rec:
                # 推荐过的项目：完整冷却期
                try:
                    last = datetime.fromisoformat(str(last_rec).replace("Z", "+00:00"))
                    if (now - last).days < cooldown:
                        stats["in_cooldown"] += 1
                        continue
                except Exception:
                    pass
            else:
                # 只是见过、从未推荐：短冷却。旧文件没有 last_seen 时退回 first_seen。
                last_seen = rec.get("last_seen") or rec.get("first_seen")
                if last_seen and seen_cooldown > 0:
                    try:
                        ls = datetime.fromisoformat(str(last_seen).replace("Z", "+00:00"))
                        # 同一天见过的不拦截：手动跑过之后，定时任务再跑不应把候选池耗尽
                        seen_days = (now.date() - ls.date()).days
                        if 1 <= seen_days < seen_cooldown:
                            stats["recent_seen"] += 1
                            continue
                    except Exception:
                        pass
        fresh_pool.append(item)

    # 同名项目只保留得分最高的一条
    best: dict[str, dict] = {}
    for item in fresh_pool:
        fn = item["full_name"]
        if fn not in best or item["score"] > best[fn]["score"]:
            best[fn] = item

    if by_growth:
        ranked = sorted(best.values(), key=lambda x: (-(x.get("stars_growth") or 0),
                                                      -x["score"], -x["stars"]))
    else:
        ranked = sorted(best.values(), key=lambda x: (-x["score"], -x["stars"]))
    min_score = sc.get("min_score", 45)
    ranked = [x for x in ranked if x["score"] >= min_score]

    # 领域配额：避免报告被单一领域刷屏
    max_per_domain = int(sc.get("max_per_domain", 0) or 0)
    top_n = sc.get("top_n", 10)
    top: list[dict] = []
    per_cat: dict[str, int] = {}
    for item in ranked:
        cat = item["category"]
        if max_per_domain and per_cat.get(cat, 0) >= max_per_domain:
            continue
        top.append(item)
        per_cat[cat] = per_cat.get(cat, 0) + 1
        if len(top) >= top_n:
            break

    stats["selected"] = len(top)
    return top, stats


def update_history(history: dict, selected: list[dict], all_seen: list[str]) -> dict:
    """写回历史：推荐记录 + 所有见过项目（只在首次见到时记录，7 天后自动解冻）。"""
    now = _now().isoformat()
    records = history.setdefault("records", {})
    for item in selected:
        fn = item["full_name"]
        rec = records.get(fn)
        if not isinstance(rec, dict):
            rec = {"times_recommended": 0, "first_seen": now}
        rec["times_recommended"] = int(rec.get("times_recommended", 0)) + 1
        rec["last_recommended"] = now
        rec["last_seen"] = now
        rec["last_title"] = item["name"]
        rec["last_score"] = item["score"]
        records[fn] = rec
    for fn in all_seen:
        if fn not in records:
            records[fn] = {
                "times_recommended": 0,
                "first_seen": now,
                "last_seen": now,
                "last_recommended": None,
            }
    history["updated_at"] = now
    history["total_tracked"] = len(records)
    return history


def normalize_history(history: dict) -> bool:
    """兼容旧版历史文件：给缺 last_seen 的记录补一个，避免被误判成永久冷却。

    返回是否发生了修改。
    """
    changed = False
    records = history.get("records")
    if not isinstance(records, dict):
        history["records"] = {}
        return True
    for rec in records.values():
        if not isinstance(rec, dict):
            continue
        if "last_seen" not in rec:
            rec["last_seen"] = rec.get("last_recommended") or rec.get("first_seen")
            changed = True
    return changed

# ============================================================
# 程序员排行榜版：反转打分逻辑（技术价值 + 近期热度为正）
# ============================================================

def score_repo_dev(r: dict, category: str, cfg: dict) -> dict:
    """程序员版打分：核心是近期 star 增长，辅以技术价值、活跃度、许可证。

    与普通人版相反：开发者 infrastructure 信号在这里是加分项。
    """
    sc = strip_notes(cfg["scoring"])
    name = r.get("full_name", "")
    desc = r.get("description") or ""
    topics = [str(t) for t in (r.get("topics") or [])]
    text = f"{name} {desc} {' '.join(topics)}"

    growth = int(r.get("stars_growth") or 0)          # 今日/本周新增 star
    stars = r.get("stargazers_count", 0)
    period = r.get("growth_period", "daily")

    # 增长分（对数压缩，避免头部项目一家独大）
    import math
    growth_score = math.log10(growth + 1) * 12 if growth else 0
    growth_score = min(growth_score, 30)

    positive_hits = _hits(text, DEV_POSITIVE_WORDS)
    quality_hits = _hits(text, DEV_QUALITY_WORDS)

    lic = r.get("license") or {}
    spdx = (lic.get("spdx_id") or "") if isinstance(lic, dict) else ""
    if not spdx and isinstance(r.get("license"), str):
        spdx = r["license"]
    if spdx.upper() in ("NOASSERTION", "NONE"):
        spdx = ""

    score = 30.0
    score += growth_score                              # 热度是主角
    score += min(positive_hits, 6) * 2.5               # 技术价值信号
    score += min(quality_hits, 4) * 2.0                # 成熟可信信号
    score += min(len(topics), 6) * 1.0
    if stars >= 10000:
        score += 8
    elif stars >= 1000:
        score += 5
    elif stars >= 300:
        score += 2
    if r.get("homepage"):
        score += 3
    if spdx:
        score += 4                                     # 有明确许可证加分（程序员关心商用/依赖合规）
    else:
        score -= 4

    # 活跃度：近期有推送
    pushed = r.get("pushed_at", "")
    if pushed:
        try:
            pd = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
            days = (_now() - pd).days
            if days <= 30:
                score += 6
            elif days <= 180:
                score += 3
            elif days > 365:
                score -= 8
        except Exception:
            pass

    # 新鲜度新建项目
    created = r.get("created_at", "")
    if created:
        try:
            cd = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if (_now() - cd).days <= sc.get("fresh_bonus_days", 7):
                score += 5
        except Exception:
            pass

    score = round(max(0.0, min(100.0, score)), 1)
    source = r.get("_source", "trending")
    return {
        "full_name": name,
        "name": r.get("name", name.split("/")[-1]),
        "owner": (r.get("owner") or {}).get("login", name.split("/")[0]),
        "url": r.get("html_url", f"https://github.com/{name}"),
        "homepage": r.get("homepage") or "",
        "description": desc.strip(),
        "stars": stars,
        "forks": r.get("forks_count", 0),
        "language": r.get("language") or "",
        "license": spdx,
        "platforms": "",  # 程序员版不展示"手机/网页"这种维度
        "topics": topics[:8],
        "created_at": created,
        "pushed_at": pushed,
        "category": category,
        "category_label": DEV_CATEGORY_LABEL.get(category, "🧰 综合"),
        "difficulty": "中",  # 程序员版不强调"上手难度"，报告里改展示别的
        "score": score,
        "stars_growth": growth,
        "growth_period": period,
        "source": source,
        "positive_hits": positive_hits,
        "fresh": bool(created and created[:10] >= _iso(sc.get("fresh_bonus_days", 7))),
    }


def build_queries_dev(cfg: dict) -> list[tuple[str, str, list[str]]]:
    """程序员版搜索通道的查询式（补充 Trending 之外的近期高星新项目）。"""
    s = cfg["search"]
    keywords = cfg["keywords"]
    since = _iso(s["lookback_days"])
    min_s = s["min_stars"]
    rotation = datetime.now().toordinal()
    items = [(cat, words) for cat, words in keywords.items()
             if not cat.startswith("_") and words]
    queries: list[tuple[str, str, list[str]]] = []
    for category, words in items:
        phrase = words[rotation % len(words)]
        terms = _terms_for(phrase)
        queries.append((f"{terms[0]} created:>{since} stars:>={min_s}", category, terms))
    return queries[: s["max_queries_per_run"]]

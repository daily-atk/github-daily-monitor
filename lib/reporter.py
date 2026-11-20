"""报告生成：Markdown 与单文件 HTML（浅色主题，无需外部依赖）。"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import strip_notes

DIFFICULTY_LABEL = {"低": "🟢 低（开箱即用）", "中": "🟡 中（需简单配置）", "高": "🔴 高（需技术背景）"}
DIFFICULTY_CLASS = {"低": "easy", "中": "medium", "高": "hard"}

# 这些仓库名太泛，单独显示会让普通人看不懂，改用 owner/name
GENERIC_REPO_NAMES = {
    "android", "ios", "app", "apps", "web", "core", "server", "client", "frontend",
    "backend", "desktop", "mobile", "cli", "main", "home", "docs", "website", "api",
    "tool", "tools", "platform", "dashboard", "extension",
}

REQUIRED_ENRICH_FIELDS = ("features", "audience", "value", "difficulty", "notes")


def render_analytics_snippet(cfg: dict) -> str:
    """生成可选访问统计的 <script> 片段；默认 off 时返回空串（零外部请求）。

    支持三种隐私友好方案：
      - plausible: 只统计页面浏览，不用 cookie
      - umami:     自托管/云端的无 cookie 统计
      - custom:    用户自填完整 <script> 标签（如 GoatCounter 等）
    所有外部 URL 必须是 https，防止混合内容与注入。
    """
    an = strip_notes(cfg.get("analytics") or {})
    if not isinstance(an, dict):
        return ""
    provider = str(an.get("provider") or "off").strip().lower()
    if provider == "off":
        return ""

    if provider == "plausible":
        domain = str(an.get("domain") or "").strip()
        if not domain or not re.fullmatch(r"[A-Za-z0-9.\-]+", domain):
            return ""
        return ('<script defer data-domain="%s" src="https://plausible.io/js/script.js"></script>'
                % html.escape(domain, quote=True))

    if provider == "umami":
        wid = str(an.get("website_id") or "").strip()
        script_url = str(an.get("script_url") or "https://cloud.umami.is/script.js").strip()
        if not wid or not script_url.lower().startswith("https://"):
            return ""
        return ('<script defer src="%s" data-website-id="%s"></script>'
                % (html.escape(script_url, quote=True), html.escape(wid, quote=True)))

    if provider == "custom":
        script = str(an.get("script") or "").strip()
        if not script or "<script" not in script.lower() or "</script>" not in script.lower():
            return ""
        # 拒绝明显的 javascript: 伪协议与非 https 外链，降低注入风险
        if "javascript:" in script.lower():
            return ""
        for m in re.finditer(r'src\s*=\s*["\']([^"\']+)["\']', script, re.I):
            if not m.group(1).lower().startswith("https://"):
                return ""
        return script

    return ""


def _first_sentence(text: str, limit: int = 140) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    parts = re.split(r"(?<=[。！？!?])|(?<=\.)\s+", t, maxsplit=1)
    s = parts[0].strip() if parts else t
    if len(s) <= limit:
        return s
    # 截断时尽量落在标点或空格处，避免出现 "designed f…" 这种半截单词
    cut = s[:limit]
    for sep in ("。", "！", "？", "；", "，", "、", ",", ";"):
        idx = cut.rfind(sep)
        if idx > limit * 0.6:
            return cut[:idx].rstrip() + "…"
    idx = cut.rfind(" ")
    if idx > limit * 0.6:
        cut = cut[:idx]
    return cut.rstrip() + "…"


def _product_from_description(desc: str) -> str:
    """从 "Super Productivity is an ..." / "Kodi is ..." 这类描述里提取产品名。"""
    m = re.match(
        r"^([A-Z][\w.+-]*(?:\s+[A-Z][\w.+-]*){0,2})\s+(?:is|—|-)\s",
        (desc or "").strip(),
    )
    return m.group(1) if m else ""


def display_name(item: dict) -> str:
    """给报告用的标题：优先产品名；仓库名太泛时用 owner/name。"""
    name = (item.get("name") or "").strip()
    full = item.get("full_name") or name
    desc = item.get("description") or ""
    if not name:
        return full
    owner = str(item.get("owner") or "").lower()
    if name.lower() in GENERIC_REPO_NAMES:
        return _product_from_description(desc) or full
    if owner and name.lower() == owner:
        return _product_from_description(desc) or name
    return name


def _safe_url(url: str) -> str:
    u = (url or "").strip()
    return u if u.lower().startswith(("http://", "https://")) else ""


def _date(iso: str) -> str:
    return (iso or "")[:10] or "—"


def _default_enrich(item: dict) -> dict:
    """AI 未增强时的规则版兜底文案：尽量按项目特征差异化，避免复读机。"""
    cat = item["category"]
    desc = (item.get("description") or "").strip()
    topics = [str(t) for t in (item.get("topics") or [])]
    low = f"{desc} {' '.join(topics)}".lower()

    base_audience = {
        "学习": "想提升学习效率、管理知识和笔记的普通人",
        "生活": "希望用工具打理日常事务、家居与个人生活的用户",
        "效率": "被任务、时间与注意力困扰，想要更自律的人",
        "健康": "关注健身、睡眠、饮食与生活习惯的用户",
        "财务": "想搞清收支、做预算与储蓄规划的普通人",
        "综合": "希望改善日常效率与生活品质的用户",
    }.get(cat, "普通用户")

    hints: list[str] = []
    if any(k in low for k in ("android", "ios", "iphone", "ipad", "mobile")):
        hints.append("想直接在手机上使用的人")
    if any(k in low for k in ("self-hosted", "selfhosted", "docker", "server")):
        hints.append("愿意自己搭服务的技术折腾者")
    if any(k in low for k in ("classroom", "education", "course", "student", "学习", "课程")):
        hints.append("学生、老师或培训组织者")
    if any(k in low for k in ("budget", "expense", "finance", "invoice", "记账", "预算")):
        hints.append("想管好收支和预算的人")
    if any(k in low for k in ("fitness", "workout", "sleep", "health", "meditation", "健康", "健身")):
        hints.append("关注健康习惯的人")
    audience = "；".join(hints[:2]) or base_audience

    topic_text = "、".join(topics[:2]) if topics else ""
    cat_value = {
        "财务": "把收支、预算和资产集中到一处查看，少维护几张表格。",
        "健康": "把运动、睡眠或习惯记录下来，看到趋势更容易坚持。",
        "效率": "把待办、专注计时和复盘放在一起，减少来回切换。",
        "生活": "把日常琐事集中管理，少装几个零散工具。",
        "学习": "把学习计划、笔记和复习串起来，减少临时抱佛脚。",
        "综合": "把原本零散、重复的操作收拢成一套现成流程，省时间也少踩坑。",
    }.get(cat, "围绕真实日常需求，用现成工具减少重复劳动。")
    value = cat_value + (f"主要围绕「{topic_text}」。" if topic_text else "")

    notes_parts: list[str] = []
    pushed = item.get("pushed_at") or ""
    if pushed:
        try:
            pd = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - pd).days
            if days <= 30:
                notes_parts.append("近期仍在活跃更新")
            else:
                notes_parts.append(f"最近一次更新在 {days} 天前，使用前先确认维护状态")
        except Exception:
            pass
    if not item.get("license"):
        notes_parts.append("未标注开源许可证，商用前请自行确认")
    notes_parts.append("建议先读 README 和最新 Issue")

    return {
        "full_name": item["full_name"],
        "features": _first_sentence(desc) or desc,
        "audience": audience,
        "value": value,
        "difficulty": item["difficulty"],
        "notes": "；".join(notes_parts),
    }


def _default_enrich_dev(item: dict) -> dict:
    """程序员版兜底文案：技术视角，不谈'适合普通人的价值'。"""
    desc = (item.get("description") or "").strip()
    topics = [str(t) for t in (item.get("topics") or [])]
    lang = item.get("language") or "未标注语言"
    lic = item.get("license") or "未标注许可证"
    growth = item.get("stars_growth", 0)
    period = "今日" if item.get("growth_period", "daily") == "daily" else "本周"

    notes_parts = []
    pushed = item.get("pushed_at") or ""
    if pushed:
        try:
            pd = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - pd).days
            if days <= 30:
                notes_parts.append("近 30 天有提交，维护活跃")
            elif days > 365:
                notes_parts.append(f"最近更新在 {days} 天前，接入前先确认维护状态")
        except Exception:
            pass
    if not item.get("license"):
        notes_parts.append("未标注开源许可证，商用/二次分发前请确认授权")
    notes_parts.append("热度来自 Trending，选型请结合文档与实际测试")
    topic_text = "、".join(topics[:3]) if topics else lang

    return {
        "full_name": item["full_name"],
        "features": _first_sentence(desc) or desc,
        "audience": "",  # 程序员版不用这个字段
        "value": "",
        "difficulty": "中",
        "notes": "；".join(notes_parts),
        # 程序员版专用展示字段
        "tech": f"{lang} · {lic}",
        "highlight": f"{period}新增 {growth:,} star，话题集中在 {topic_text}。",
    }


def load_enriched(path: Path, expect_date: str | None = None) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # 日期不匹配视为陈旧数据，忽略（防止隔天污染）
        if expect_date and data.get("date") != expect_date:
            return {}
        return {x["full_name"]: x for x in data.get("items", []) if x.get("full_name")}
    except Exception:
        return {}


def validate_enriched(path: Path, expect_date: str | None,
                      candidate_names: set[str]) -> list[str]:
    """校验 AI 增强结果；返回中文问题列表（空列表表示通过或文件不存在）。"""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"enriched 文件无法解析：{e}"]
    if not isinstance(data, dict):
        return ["enriched 文件最外层必须是 { ... }"]

    issues: list[str] = []
    if expect_date and data.get("date") != expect_date:
        issues.append(f"enriched 日期是 {data.get('date')}，与候选日期 {expect_date} 不一致（会被忽略）")

    items = data.get("items")
    if not isinstance(items, list) or not items:
        issues.append("enriched 里没有 items 列表或为空")
        return issues

    seen: set[str] = set()
    for idx, x in enumerate(items, 1):
        if not isinstance(x, dict):
            issues.append(f"第 {idx} 项不是对象")
            continue
        fn = x.get("full_name")
        if not fn:
            issues.append(f"第 {idx} 项缺少 full_name")
            continue
        if fn in seen:
            issues.append(f"{fn} 重复出现")
        seen.add(fn)
        if candidate_names and fn not in candidate_names:
            issues.append(f"{fn} 不在当日候选中")
        for k in REQUIRED_ENRICH_FIELDS:
            if not str(x.get(k) or "").strip():
                issues.append(f"{fn} 缺少字段 {k}")
        if x.get("difficulty") and x.get("difficulty") not in ("低", "中", "高"):
            issues.append(f"{fn} 的 difficulty 只能是 低/中/高")

    missing = candidate_names - seen
    if missing:
        issues.append(f"有 {len(missing)} 个候选未做 AI 增强，将使用脚本兜底文案"
                      f"（例如 {', '.join(sorted(missing)[:3])}）")
    return issues


def build_report_data(candidates: list[dict], cfg: dict, date_str: str,
                      enriched_path: Path | None = None) -> dict:
    enriched = load_enriched(enriched_path, expect_date=date_str) if enriched_path else {}
    by_name = {c["full_name"]: c for c in candidates}
    items = []
    is_dev = cfg.get("mode") == "developer"

    def make_item(item: dict, e: dict, rank: int) -> dict:
        fallback = _default_enrich_dev(item) if is_dev else _default_enrich(item)
        return {
            "rank": rank,
            **item,
            "display_name": display_name(item),
            "features": e.get("features") or fallback["features"],
            "audience": e.get("audience") or fallback["audience"],
            "value": e.get("value") or fallback["value"],
            "difficulty": e.get("difficulty") or item["difficulty"],
            "notes": e.get("notes") or fallback["notes"],
        }

    # 若存在 AI 增强数据：只保留增强里列出的项目，顺序即最终优先级（AI 语义终筛权威）
    if enriched:
        for fn in enriched:
            if fn in by_name:
                items.append(make_item(by_name[fn], enriched[fn], len(items) + 1))
    else:
        for c in candidates:
            items.append(make_item(c, {}, len(items) + 1))

    cooldown = strip_notes(cfg.get("dedup", {})).get("cooldown_days", 30)
    is_dev = cfg.get("mode") == "developer"
    trending = strip_notes(cfg.get("trending") or {})
    return {"date": date_str, "generated_at": datetime.now().isoformat(timespec="seconds"),
            "count": len(items), "cooldown_days": cooldown, "items": items,
            "mode": "developer" if is_dev else "consumer",
            "growth_period": trending.get("period", "daily")}


def _growth_label(data: dict) -> str:
    return "今日新增" if data.get("growth_period", "daily") == "daily" else "本周新增"


def _render_markdown_dev(data: dict) -> str:
    """程序员排行榜版 Markdown：按热度排，突出新增 star，去掉普通人维度。"""
    d = data["date"]
    cooldown = data.get("cooldown_days", 14)
    gl = _growth_label(data)
    lines = [
        f"# 🔥 GitHub 程序员热度榜 · {d}",
        "",
        f"> 按 GitHub Trending 真实 **{gl} star** 排序，收录今日最受开发者关注的项目。",
        "> 数据源：GitHub Trending + 近期新建高星项目，非人工精选，仅供参考。",
        "",
        f"| 排名 | 项目 | 方向 | {gl} star | 总 star | 热度分 |",
        "|:---:|---|:---:|---:|---:|---:|",
    ]
    for it in data["items"]:
        growth = it.get("stars_growth", 0)
        lines.append(
            f"| {it['rank']} | [{it['full_name']}]({it['url']}) | {it['category_label']} "
            f"| 🔥 +{growth:,} | ⭐ {it['stars']:,} | {it['score']} |"
        )
    lines += ["", "---", ""]
    for it in data["items"]:
        title = it.get("display_name") or it["name"]
        growth = it.get("stars_growth", 0)
        lic = it.get("license") or "未标注"
        topics = "、".join(it.get("topics", [])[:6]) or "—"
        lines += [
            f"## {it['rank']}. [{title}]({it['url']}) — {it['category_label']}",
            "",
            f"- 🔗 链接：{it['url']}" + (f" ｜ 官网：{it['homepage']}" if it.get("homepage") else ""),
            f"- 📝 项目：{it['features']}",
            f"- 🔥 热度：{gl} **+{growth:,}** star ｜ 累计 ⭐ {it['stars']:,} ｜ 🍴 {it['forks']:,}",
            f"- 🛠️ 技术栈：{it['language'] or '—'} ｜ 📄 许可证：{lic} ｜ 🕒 最近更新：{_date(it.get('pushed_at'))}",
            f"- 🏷️ 主题：{topics}",
            f"- ⚠️ 提示：{it['notes']}",
            "",
        ]
    lines += [
        "---",
        "",
        f"*本榜由「GitHub 监测助手·程序员版」自动生成，同一项目 {cooldown} 天内不重复上榜。*",
        "*热度数据来自 GitHub Trending，会实时变化；技术选型请自行调研，使用前以项目页面为准。*",
        "*Not affiliated with GitHub.*",
    ]
    return "\n".join(lines)


def render_markdown(data: dict) -> str:
    if data.get("mode") == "developer":
        return _render_markdown_dev(data)
    d = data["date"]
    cooldown = data.get("cooldown_days", 30)
    lines = [
        f"# 🛰️ 每日 GitHub 实用项目速递 · {d}",
        "",
        f"> 今日从 GitHub 筛选出 **{data['count']}** 个对普通人真正有用的项目，按推荐优先级排序。",
        "> 只看「能不能帮到学习 / 生活 / 效率 / 健康 / 财务」，不堆开发者玩具。",
        "",
        "| 排名 | 项目 | 领域 | 上手难度 | 星标 | 推荐分 |",
        "|:---:|---|:---:|:---:|---:|---:|",
    ]
    for it in data["items"]:
        lines.append(
            f"| {it['rank']} | [{it['full_name']}]({it['url']}) | {it['category_label']} "
            f"| {DIFFICULTY_LABEL.get(it['difficulty'], it['difficulty'])} "
            f"| ⭐ {it['stars']:,} | {it['score']} |"
        )
    lines += ["", "---", ""]
    for it in data["items"]:
        title = it.get("display_name") or it["name"]
        lines += [
            f"## {it['rank']}. [{title}]({it['url']}) — {it['category_label']}",
            "",
            f"- 🔗 链接：{it['url']}" + (f" ｜ 官网：{it['homepage']}" if it.get("homepage") else ""),
            f"- 🛠️ 主要功能：{it['features']}",
            f"- 👥 适合人群：{it['audience']}",
            f"- 💡 实用价值：{it['value']}",
            f"- 🎯 上手难度：{DIFFICULTY_LABEL.get(it['difficulty'], it['difficulty'])}",
            f"- 📦 平台：{it.get('platforms') or '—'} ｜ 🕒 最近更新：{_date(it.get('pushed_at'))} "
            f"｜ 📄 许可证：{it.get('license') or '未标注'}",
            f"- ⚠️ 注意事项：{it['notes']}",
            f"- 📊 数据：⭐ {it['stars']:,} ｜ 🍴 {it['forks']:,} ｜ 语言 {it['language'] or '—'} ｜ 推荐分 {it['score']}",
            "",
        ]
    lines += [
        "---",
        "",
        f"*本报告由「每日 GitHub 监测助手」自动生成并去重，同一项目 {cooldown} 天内不重复推荐。*",
        "*星标与维护状态会变化，使用前请以项目页面为准。*",
    ]
    return "\n".join(lines)


def _render_html_dev(data: dict, analytics_snippet: str = "") -> str:
    """程序员排行榜版 HTML：深色主题，突出热度增长数字。"""
    d = data["date"]
    cooldown = data.get("cooldown_days", 14)
    gl = _growth_label(data)
    cards = []
    for it in data["items"]:
        growth = it.get("stars_growth", 0)
        title = it.get("display_name") or it["name"]
        homepage_url = _safe_url(it.get("homepage") or "")
        homepage = (
            f'<a class="home" href="{html.escape(homepage_url)}" target="_blank" rel="noopener">官网 ↗</a>'
            if homepage_url else ""
        )
        topics = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in it.get("topics", [])[:6])
        cards.append(f"""
        <article class="card" id="{it['rank']}">
          <div class="card-top">
            <span class="rank">#{it['rank']}</span>
            <span class="cat">{html.escape(it['category_label'])}</span>
            <span class="growth">🔥 +{growth:,} {gl}</span>
          </div>
          <h2><a href="{html.escape(it['url'])}" target="_blank" rel="noopener">{html.escape(title)}</a></h2>
          <div class="repo">{html.escape(it['full_name'])}</div>
          <p class="features">{html.escape(it['features'])}</p>
          <div class="grid">
            <div class="cell"><span class="k">⭐ 累计星标</span><span class="v big">{it['stars']:,}</span></div>
            <div class="cell"><span class="k">🍴 Fork</span><span class="v big">{it['forks']:,}</span></div>
            <div class="cell"><span class="k">🛠️ 语言</span><span class="v">{html.escape(it['language'] or '—')}</span></div>
            <div class="cell"><span class="k">📄 许可证</span><span class="v">{html.escape(it.get('license') or '未标注')}</span></div>
            <div class="cell"><span class="k">🕒 最近更新</span><span class="v">{_date(it.get('pushed_at'))}</span></div>
            <div class="cell"><span class="k">📦 来源</span><span class="v">{'Trending 榜' if it.get('source')=='trending' else '搜索补充'}</span></div>
            <div class="cell full"><span class="k">🏷️ 主题</span><span class="v">{topics or '—'}</span></div>
            <div class="cell full"><span class="k">⚠️ 提示</span><span class="v">{html.escape(it['notes'])}</span></div>
          </div>
          <div class="foot">
            <div class="metrics"><span>热度分 {it['score']}</span><span>⭐ {it['stars']:,}</span></div>
            <div class="links"><a href="{html.escape(it['url'])}" target="_blank" rel="noopener">GitHub ↗</a>{homepage}</div>
          </div>
        </article>""")
    rows = "".join(
        f"<tr><td>{it['rank']}</td><td><a href='#{it['rank']}'>{html.escape(it.get('display_name') or it['name'])}</a></td>"
        f"<td>{html.escape(it['category_label'])}</td><td class='hot'>+{it.get('stars_growth',0):,}</td><td>{it['score']}</td></tr>"
        for it in data["items"]
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GitHub 程序员热度榜 · {d}</title>
<style>
:root{{--bg:#0d1117;--card:#161b22;--ink:#e6edf3;--mut:#8b949e;--line:#30363d;--brand:#58a6ff;--hot:#f85149}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:900px;margin:0 auto;padding:32px 18px 60px}}
header{{text-align:center;padding:18px 0 26px}}
h1{{font-size:27px;margin:0 0 8px}} .sub{{color:var(--mut);font-size:14px}}
.summary{{background:#161b22;border:1px solid var(--line);border-radius:14px;padding:14px 18px;margin:18px 0 26px;color:#c9d1d9;font-size:14px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border-radius:12px;overflow:hidden;font-size:13px}}
th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)}}
th{{background:#1c2128;color:var(--mut);font-weight:600}} td.hot{{color:var(--hot);font-weight:700}}
a{{color:var(--brand);text-decoration:none}} a:hover{{text-decoration:underline}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin:18px 0}}
.card-top{{display:flex;gap:10px;align-items:center;margin-bottom:10px}}
.rank{{background:#30363d;color:#fff;border-radius:8px;padding:2px 9px;font-weight:700;font-size:13px}}
.cat{{background:#1f2b3d;color:#79c0ff;border-radius:20px;padding:2px 11px;font-size:12px}}
.growth{{margin-left:auto;color:var(--hot);font-size:13px;font-weight:700}}
.card h2{{font-size:19px;margin:0 0 2px}} .repo{{color:var(--mut);font-size:12px;margin-bottom:12px}}
.features{{margin:0 0 14px;color:#c9d1d9}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:12px 0}}
.cell{{background:#0d1117;border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:13px}}
.cell.full{{grid-column:1/-1}} .k{{display:block;color:var(--mut);font-size:12px;margin-bottom:3px}} .v{{color:#e6edf3}} .v.big{{font-size:17px;font-weight:700}}
.tags{{margin:6px 0 12px}} .tag{{display:inline-block;background:#21262d;color:#8b949e;border-radius:6px;padding:1px 8px;font-size:11px;margin:0 5px 5px 0}}
.foot{{display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--line);padding-top:12px;font-size:13px}}
.metrics{{display:flex;gap:14px;color:var(--mut)}} .links{{display:flex;gap:14px}}
footer{{text-align:center;color:var(--mut);font-size:12px;margin-top:36px}}
@media(max-width:600px){{.grid{{grid-template-columns:1fr}}.foot{{flex-direction:column;gap:10px}}}}
</style>{analytics_snippet}</head><body><div class="wrap">
<header><h1>🔥 GitHub 程序员热度榜</h1><div class="sub">{d} · 按真实 {gl} star 增长排序</div></header>
<div class="summary">数据源 GitHub Trending + 近期新建高星项目，收录开发者社区今日真正关注的项目。<br>热度来自真实 star 增长，非人工精选；技术选型请以项目页面为准。</div>
<table><thead><tr><th>#</th><th>项目</th><th>方向</th><th>{gl} star</th><th>热度分</th></tr></thead><tbody>{rows}</tbody></table>
{''.join(cards)}
<footer>本榜由「GitHub 监测助手·程序员版」自动生成 · 同一项目 {cooldown} 天内不重复上榜<br>热度数据实时变化 · Not affiliated with GitHub</footer>
</div></body></html>"""


def render_html(data: dict, analytics_snippet: str = "") -> str:
    if data.get("mode") == "developer":
        return _render_html_dev(data, analytics_snippet)
    d = data["date"]
    cooldown = data.get("cooldown_days", 30)
    cards = []
    for it in data["items"]:
        diff = it["difficulty"]
        title = it.get("display_name") or it["name"]
        homepage_url = _safe_url(it.get("homepage") or "")
        homepage = (
            f'<a class="home" href="{html.escape(homepage_url)}" target="_blank" rel="noopener">官网 ↗</a>'
            if homepage_url else ""
        )
        topics = "".join(f'<span class="tag">#{html.escape(t)}</span>' for t in it.get("topics", [])[:5])
        update_license = f"{_date(it.get('pushed_at'))} · {html.escape(it.get('license') or '未标注')}"
        cards.append(f"""
        <article class="card" id="{it['rank']}">
          <div class="card-top">
            <span class="rank">#{it['rank']}</span>
            <span class="cat">{html.escape(it['category_label'])}</span>
            <span class="diff {DIFFICULTY_CLASS.get(diff,'medium')}">{DIFFICULTY_LABEL.get(diff,diff)}</span>
          </div>
          <h2><a href="{html.escape(it['url'])}" target="_blank" rel="noopener">{html.escape(title)}</a></h2>
          <div class="repo">{html.escape(it['full_name'])}</div>
          <p class="features">{html.escape(it['features'])}</p>
          <div class="grid">
            <div class="cell"><span class="k">👥 适合人群</span><span class="v">{html.escape(it['audience'])}</span></div>
            <div class="cell"><span class="k">💡 实用价值</span><span class="v">{html.escape(it['value'])}</span></div>
            <div class="cell"><span class="k">📦 平台</span><span class="v">{html.escape(it.get('platforms') or '—')}</span></div>
            <div class="cell"><span class="k">🕒 最近更新 · 📄 许可证</span><span class="v">{update_license}</span></div>
            <div class="cell full"><span class="k">⚠️ 注意事项</span><span class="v">{html.escape(it['notes'])}</span></div>
          </div>
          <div class="tags">{topics}</div>
          <div class="foot">
            <div class="metrics"><span>⭐ {it['stars']:,}</span><span>🍴 {it['forks']:,}</span><span>{html.escape(it['language'] or '—')}</span></div>
            <div class="links"><a href="{html.escape(it['url'])}" target="_blank" rel="noopener">GitHub ↗</a>{homepage}</div>
          </div>
        </article>""")

    rows = "".join(
        f"<tr><td>{it['rank']}</td><td><a href='#{it['rank']}'>{html.escape(it.get('display_name') or it['name'])}</a></td>"
        f"<td>{html.escape(it['category_label'])}</td><td>{it['score']}</td></tr>"
        for it in data["items"]
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>每日 GitHub 实用项目速递 · {d}</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--ink:#1f2328;--mut:#5b6572;--line:#e5e8ec;--brand:#2563eb;--accent:#f59e0b}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:900px;margin:0 auto;padding:32px 18px 60px}}
header{{text-align:center;padding:18px 0 26px}}
h1{{font-size:27px;margin:0 0 8px}}
.sub{{color:var(--mut);font-size:14px}}
.summary{{background:#eef2ff;border:1px solid #dbe3ff;border-radius:14px;padding:14px 18px;margin:18px 0 26px;color:#33417a;font-size:14px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border-radius:12px;overflow:hidden;font-size:13px}}
th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)}}
th{{background:#fafbfc;color:var(--mut);font-weight:600}}
a{{color:var(--brand);text-decoration:none}} a:hover{{text-decoration:underline}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin:18px 0;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.card-top{{display:flex;gap:10px;align-items:center;margin-bottom:10px}}
.rank{{background:var(--ink);color:#fff;border-radius:8px;padding:2px 9px;font-weight:700;font-size:13px}}
.cat{{background:#eef2ff;color:#4338ca;border-radius:20px;padding:2px 11px;font-size:12px}}
.diff{{margin-left:auto;font-size:12px;border-radius:20px;padding:2px 11px}}
.diff.easy{{background:#dcfce7;color:#166534}} .diff.medium{{background:#fef3c7;color:#92400e}} .diff.hard{{background:#fee2e2;color:#991b1b}}
.card h2{{font-size:19px;margin:0 0 2px}} .repo{{color:var(--mut);font-size:12px;margin-bottom:12px}}
.features{{margin:0 0 14px;color:#30363d}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:12px 0}}
.cell{{background:#f8fafc;border-radius:10px;padding:10px 12px;font-size:13px}}
.cell.full{{grid-column:1/-1}} .k{{display:block;color:var(--mut);font-size:12px;margin-bottom:3px}} .v{{color:#25292e}}
.tags{{margin:6px 0 12px}} .tag{{display:inline-block;background:#f1f5f9;color:#475569;border-radius:6px;padding:1px 8px;font-size:11px;margin:0 5px 5px 0}}
.foot{{display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--line);padding-top:12px;font-size:13px}}
.metrics{{display:flex;gap:14px;color:var(--mut)}} .links{{display:flex;gap:14px}}
footer{{text-align:center;color:var(--mut);font-size:12px;margin-top:36px}}
@media(max-width:600px){{.grid{{grid-template-columns:1fr}}.foot{{flex-direction:column;gap:10px}}}}
</style>{analytics_snippet}</head><body><div class="wrap">
<header><h1>🛰️ 每日 GitHub 实用项目速递</h1><div class="sub">{d} · 为普通人筛选的真有用项目</div></header>
<div class="summary">今日从 GitHub 筛选出 <b>{data['count']}</b> 个对普通人真正有用的项目，按推荐优先级排序。<br>只看「能不能帮到学习 / 生活 / 效率 / 健康 / 财务」，不堆开发者玩具。</div>
<table><thead><tr><th>#</th><th>项目</th><th>领域</th><th>推荐分</th></tr></thead><tbody>{rows}</tbody></table>
{''.join(cards)}
<footer>本报告由「每日 GitHub 监测助手」自动生成并去重 · 同一项目 {cooldown} 天内不重复推荐<br>星标与维护状态会变化，使用前请以项目页面为准</footer>
</div></body></html>"""


def save_reports(data: dict, cfg: dict) -> list[Path]:
    out = strip_notes(cfg["output"])
    reports_dir = out.get("reports_dir", "reports")
    from .config import root_path
    rd = root_path(reports_dir)
    rd.mkdir(parents=True, exist_ok=True)
    prefix = out.get("file_prefix") or "github-daily"
    written = []
    if "md" in out.get("formats", ["md", "html"]):
        p = rd / f"{prefix}-{data['date']}.md"
        p.write_text(render_markdown(data), encoding="utf-8")
        written.append(p)
    if "html" in out.get("formats", ["md", "html"]):
        p = rd / f"{prefix}-{data['date']}.html"
        p.write_text(render_html(data, render_analytics_snippet(cfg)), encoding="utf-8")
        written.append(p)
    return written
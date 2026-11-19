"""报告生成：Markdown 与单文件 HTML（浅色主题，无需外部依赖）。"""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from .config import strip_notes

DIFFICULTY_LABEL = {"低": "🟢 低（开箱即用）", "中": "🟡 中（需简单配置）", "高": "🔴 高（需技术背景）"}
DIFFICULTY_CLASS = {"低": "easy", "中": "medium", "高": "hard"}


def _default_enrich(item: dict) -> dict:
    """AI 未增强时的规则版兜底文案。"""
    cat = item["category"]
    return {
        "full_name": item["full_name"],
        "features": item["description"],
        "audience": {
            "学习": "想提升学习效率、管理知识和笔记的普通人",
            "生活": "希望用工具打理日常事务、家居与个人生活的用户",
            "效率": "被任务、时间与注意力困扰，想要更自律的人",
            "健康": "关注健身、睡眠、饮食与生活习惯的用户",
            "财务": "想搞清收支、做预算与储蓄规划的普通人",
            "综合": "希望改善日常效率与生活品质的用户",
        }.get(cat, "普通用户"),
        "value": "围绕真实日常需求，用现成工具减少重复劳动、节省时间或改善习惯。",
        "difficulty": item["difficulty"],
        "notes": "上手前先查看项目 README 与最新 Issue，确认维护状态；自托管类需准备相应环境。",
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


def build_report_data(candidates: list[dict], cfg: dict, date_str: str,
                      enriched_path: Path | None = None) -> dict:
    enriched = load_enriched(enriched_path, expect_date=date_str) if enriched_path else {}
    by_name = {c["full_name"]: c for c in candidates}
    items = []

    def make_item(item: dict, e: dict, rank: int) -> dict:
        return {
            "rank": rank,
            **item,
            "features": e.get("features") or item["description"],
            "audience": e.get("audience") or _default_enrich(item)["audience"],
            "value": e.get("value") or _default_enrich(item)["value"],
            "difficulty": e.get("difficulty") or item["difficulty"],
            "notes": e.get("notes") or _default_enrich(item)["notes"],
        }

    # 若存在 AI 增强数据：只保留增强里列出的项目，顺序即最终优先级（AI 语义终筛权威）
    if enriched:
        for fn in enriched:
            if fn in by_name:
                items.append(make_item(by_name[fn], enriched[fn], len(items) + 1))
    else:
        for c in candidates:
            items.append(make_item(c, {}, len(items) + 1))

    return {"date": date_str, "generated_at": datetime.now().isoformat(timespec="seconds"),
            "count": len(items), "items": items}


def render_markdown(data: dict) -> str:
    d = data["date"]
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
        lines += [
            f"## {it['rank']}. [{it['full_name']}]({it['url']}) — {it['category_label']}",
            "",
            f"- 🔗 链接：{it['url']}" + (f" ｜ 官网：{it['homepage']}" if it.get("homepage") else ""),
            f"- 🛠️ 主要功能：{it['features']}",
            f"- 👥 适合人群：{it['audience']}",
            f"- 💡 实用价值：{it['value']}",
            f"- 🎯 上手难度：{DIFFICULTY_LABEL.get(it['difficulty'], it['difficulty'])}",
            f"- ⚠️ 注意事项：{it['notes']}",
            f"- 📊 数据：⭐ {it['stars']:,} ｜ 🍴 {it['forks']:,} ｜ 语言 {it['language'] or '—'} ｜ 推荐分 {it['score']}",
            "",
        ]
    lines += [
        "---",
        "",
        "*本报告由「每日 GitHub 监测助手」自动生成并去重，同一项目 30 天内不重复推荐。*",
        "*星标与维护状态会变化，使用前请以项目页面为准。*",
    ]
    return "\n".join(lines)


def render_html(data: dict) -> str:
    d = data["date"]
    cards = []
    for it in data["items"]:
        diff = it["difficulty"]
        homepage = (
            f'<a class="home" href="{html.escape(it["homepage"])}" target="_blank" rel="noopener">官网 ↗</a>'
            if it.get("homepage") else ""
        )
        topics = "".join(f'<span class="tag">#{html.escape(t)}</span>' for t in it.get("topics", [])[:5])
        cards.append(f"""
        <article class="card">
          <div class="card-top">
            <span class="rank">#{it['rank']}</span>
            <span class="cat">{html.escape(it['category_label'])}</span>
            <span class="diff {DIFFICULTY_CLASS.get(diff,'medium')}">{DIFFICULTY_LABEL.get(diff,diff)}</span>
          </div>
          <h2><a href="{html.escape(it['url'])}" target="_blank" rel="noopener">{html.escape(it['name'])}</a></h2>
          <div class="repo">{html.escape(it['full_name'])}</div>
          <p class="features">{html.escape(it['features'])}</p>
          <div class="grid">
            <div class="cell"><span class="k">👥 适合人群</span><span class="v">{html.escape(it['audience'])}</span></div>
            <div class="cell"><span class="k">💡 实用价值</span><span class="v">{html.escape(it['value'])}</span></div>
            <div class="cell full"><span class="k">⚠️ 注意事项</span><span class="v">{html.escape(it['notes'])}</span></div>
          </div>
          <div class="tags">{topics}</div>
          <div class="foot">
            <div class="metrics"><span>⭐ {it['stars']:,}</span><span>🍴 {it['forks']:,}</span><span>{html.escape(it['language'] or '—')}</span></div>
            <div class="links"><a href="{html.escape(it['url'])}" target="_blank" rel="noopener">GitHub ↗</a>{homepage}</div>
          </div>
        </article>""")

    rows = "".join(
        f"<tr><td>{it['rank']}</td><td><a href='#{it['rank']}'>{html.escape(it['name'])}</a></td>"
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
</style></head><body><div class="wrap">
<header><h1>🛰️ 每日 GitHub 实用项目速递</h1><div class="sub">{d} · 为普通人筛选的真有用项目</div></header>
<div class="summary">今日从 GitHub 筛选出 <b>{data['count']}</b> 个对普通人真正有用的项目，按推荐优先级排序。<br>只看「能不能帮到学习 / 生活 / 效率 / 健康 / 财务」，不堆开发者玩具。</div>
<table><thead><tr><th>#</th><th>项目</th><th>领域</th><th>推荐分</th></tr></thead><tbody>{rows}</tbody></table>
{''.join(cards)}
<footer>本报告由「每日 GitHub 监测助手」自动生成并去重 · 同一项目 30 天内不重复推荐<br>星标与维护状态会变化，使用前请以项目页面为准</footer>
</div></body></html>"""


def save_reports(data: dict, cfg: dict) -> list[Path]:
    out = strip_notes(cfg["output"])
    reports_dir = out.get("reports_dir", "reports")
    from .config import root_path
    rd = root_path(reports_dir)
    rd.mkdir(parents=True, exist_ok=True)
    written = []
    if "md" in out.get("formats", ["md", "html"]):
        p = rd / f"github-daily-{data['date']}.md"
        p.write_text(render_markdown(data), encoding="utf-8")
        written.append(p)
    if "html" in out.get("formats", ["md", "html"]):
        p = rd / f"github-daily-{data['date']}.html"
        p.write_text(render_html(data), encoding="utf-8")
        written.append(p)
    return written

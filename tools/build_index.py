#!/usr/bin/env python3
"""扫描站点目录里的日报 HTML，生成历史归档索引页。

用法：
    python tools/build_index.py site
    REPO_URL=https://github.com/you/repo python tools/build_index.py site
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from lib.reporter import render_analytics_snippet
except ImportError:  # 作为独立脚本分发时 lib 可能不在路径里
    def render_analytics_snippet(cfg: dict) -> str:
        return ""

REPORT_RE = re.compile(r"^github-daily-(\d{4}-\d{2}-\d{2})\.html$")
DEV_REPORT_RE = re.compile(r"^dev-daily-(\d{4}-\d{2}-\d{2})\.html$")
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def find_reports(site_dir: Path, variant: str = "consumer") -> list[tuple[str, Path]]:
    """variant=consumer 找 github-daily-*.html；dev 找 dev-daily-*.html。"""
    reports: list[tuple[str, Path]] = []
    if not site_dir.exists():
        return reports
    pattern = "dev-daily-*.html" if variant == "dev" else "github-daily-*.html"
    rx = DEV_REPORT_RE if variant == "dev" else REPORT_RE
    for path in site_dir.glob(pattern):
        m = rx.match(path.name)
        if m:
            reports.append((m.group(1), path))
    return sorted(reports, key=lambda x: x[0], reverse=True)


def _safe_url(url: str) -> str:
    u = (url or "").strip()
    return u if u.lower().startswith(("http://", "https://")) else ""


def _weekday(date_str: str) -> str:
    try:
        return WEEKDAYS[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    except ValueError:
        return ""


def render_index(reports: list[tuple[str, Path]], repo_url: str = "",
                 analytics_snippet: str = "", variant: str = "consumer",
                 nav_html: str = "") -> str:
    is_dev = variant == "dev"
    count = len(reports)
    latest = reports[0][0] if reports else "—"

    if reports:
        items = []
        for date_str, path in reports:
            badge = '<span class="badge">最新</span>' if date_str == latest else ""
            items.append(
                f'<li><a href="{html.escape(path.name)}">'
                f'<span class="date">{html.escape(date_str)}</span>'
                f'<span class="week">{html.escape(_weekday(date_str))}</span>'
                f'{badge}<span class="arrow">查看 →</span></a></li>'
            )
        archive = '<ul class="archive">' + "".join(items) + "</ul>"
    else:
        cmd = ("python monitor.py --profile dev run" if is_dev
               else "python monitor.py run")
        label = "榜单" if is_dev else "日报"
        archive = (f'<div class="empty">还没有{label}。先运行 '
                   f'<code>{html.escape(cmd)}</code>，再重新生成索引。</div>')

    repo_link = ""
    safe_repo = _safe_url(repo_url)
    if safe_repo:
        repo_link = (f'<a href="{html.escape(safe_repo)}" target="_blank" '
                     f'rel="noopener">GitHub 仓库 ↗</a>')

    # 主题、标题、说明按版本切换
    if is_dev:
        title = "🔥 GitHub 程序员热度榜"
        h1 = "🔥 GitHub 程序员热度榜"
        sub = "按真实 star 增长排序 · 历史榜单"
        summary_text = (f"共收录 <b>{count}</b> 期榜单，最近一期：<b>{html.escape(latest)}</b>。")
        theme_vars = "--bg:#0d1117;--card:#161b22;--ink:#e6edf3;--mut:#8b949e;--line:#30363d;--brand:#58a6ff"
        summary_css = "background:#161b22;border:1px solid var(--line);color:#c9d1d9"
        hover_css = "border-color:#58a6ff;background:#161b22"
        code_css = "background:#21262d"
        badge_css = "background:#1f2b3d;color:#79c0ff"
        footer_note = "热度数据来自 GitHub Trending · 技术选型请自行调研"
    else:
        title = "GitHub 普通人日报 · 历史归档"
        h1 = "📚 GitHub 普通人日报"
        sub = "每天自动筛选 · 历史归档"
        summary_text = (f"共收录 <b>{count}</b> 期日报，最近一期：<b>{html.escape(latest)}</b>。")
        theme_vars = "--bg:#f6f7f9;--card:#fff;--ink:#1f2328;--mut:#5b6572;--line:#e5e8ec;--brand:#2563eb"
        summary_css = "background:#eef2ff;border:1px solid #dbe3ff;color:#33417a"
        hover_css = "border-color:#bfdbfe;background:#f8fbff"
        code_css = "background:#f1f5f9"
        badge_css = "background:#dcfce7;color:#166534"
        footer_note = "内容仅供参考，使用前请以项目页面为准"

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
{analytics_snippet}
<style>
:root{{{theme_vars}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:760px;margin:0 auto;padding:36px 18px 60px}}
.nav{{display:flex;gap:10px;justify-content:center;margin-bottom:8px;flex-wrap:wrap}}
.nav a{{padding:6px 16px;border-radius:20px;font-size:13px;text-decoration:none;border:1px solid var(--line)}}
.nav a.on{{background:var(--brand);color:#fff;border-color:var(--brand)}}
header{{text-align:center;padding:18px 0 22px}}
h1{{font-size:27px;margin:0 0 8px}}
.sub{{color:var(--mut);font-size:14px}}
.summary{{{summary_css};border-radius:14px;padding:14px 18px;margin:18px 0 26px;font-size:14px}}
.archive{{list-style:none;margin:0;padding:0}}
.archive li{{margin:10px 0}}
.archive a{{display:flex;align-items:center;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;text-decoration:none;color:var(--ink);box-shadow:0 1px 3px rgba(0,0,0,.03)}}
.archive a:hover{{{hover_css}}}
.date{{font-weight:700;font-variant-numeric:tabular-nums}}
.week{{color:var(--mut);font-size:13px}}
.badge{{{badge_css};border-radius:20px;padding:1px 9px;font-size:12px}}
.arrow{{margin-left:auto;color:var(--brand);font-size:13px}}
.empty{{background:var(--card);border:1px dashed var(--line);border-radius:12px;padding:24px;text-align:center;color:var(--mut)}}
code{{{code_css};border-radius:5px;padding:1px 6px;font-size:12px}}
footer{{text-align:center;color:var(--mut);font-size:12px;margin-top:36px;line-height:2}}
a{{color:var(--brand)}}
</style></head><body><div class="wrap">
{nav_html}
<header><h1>{h1}</h1><div class="sub">{sub}</div></header>
<div class="summary">{summary_text}</div>
{archive}
<footer>
{repo_link}{' ｜ ' if repo_link else ''}{footer_note}<br>
Not affiliated with GitHub
</footer>
</div></body></html>"""


def _load_analytics() -> str:
    """读取项目 config.json 里的可选统计配置（失败时静默关闭）。"""
    cfg_path = ROOT / "config.json"
    if not cfg_path.exists():
        return ""
    try:
        import json
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        return render_analytics_snippet(cfg)
    except Exception:
        return ""


def _nav(active: str) -> str:
    """两个榜单之间的切换导航。active=consumer/dev。

    普通人版归档页在站点根，程序员版在 dev/ 子目录，故链接相对路径不同。
    """
    consumer_cls = "on" if active == "consumer" else ""
    dev_cls = "on" if active == "dev" else ""
    # 从普通人版(index.html)看：普通人=./  程序员=dev/
    # 从程序员版(dev/index.html)看：普通人=../  程序员=./
    if active == "consumer":
        consumer_href, dev_href = "index.html", "dev/index.html"
    else:
        consumer_href, dev_href = "../index.html", "index.html"
    return (f'<nav class="nav">'
            f'<a class="{consumer_cls}" href="{consumer_href}">📚 普通人日报</a>'
            f'<a class="{dev_cls}" href="{dev_href}">🔥 程序员热度榜</a>'
            f'</nav>')


def build_index(site_dir: str | Path, repo_url: str = "",
                analytics_snippet: str | None = None,
                variant: str = "consumer", nav_html: str | None = None) -> Path:
    site = Path(site_dir)
    site.mkdir(parents=True, exist_ok=True)
    if analytics_snippet is None:
        analytics_snippet = _load_analytics()
    if variant == "dev":
        out = site / "dev" / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        reports = find_reports(out.parent, "dev")
    else:
        out = site / "index.html"
        reports = find_reports(site, "consumer")
    if nav_html is None:
        nav_html = ""
    out.write_text(
        render_index(reports, repo_url, analytics_snippet, variant=variant, nav_html=nav_html),
        encoding="utf-8",
    )
    return out


def build_all(site_dir: str | Path, repo_url: str = "") -> tuple[Path, Path]:
    """生成两版归档页，并互相加导航。普通人版在根，程序员版在 dev/。"""
    site = Path(site_dir)
    consumer = build_index(site, repo_url, variant="consumer",
                           nav_html=_nav("consumer"))
    dev = build_index(site, repo_url, variant="dev", nav_html=_nav("dev"))
    return consumer, dev


def main() -> None:
    ap = argparse.ArgumentParser(description="生成日报历史归档索引页")
    ap.add_argument("site_dir", nargs="?", default="site", help="站点目录（默认 site）")
    ap.add_argument("--repo-url", default=os.environ.get("REPO_URL", ""),
                    help="仓库地址，用于页脚链接")
    ap.add_argument("--all", action="store_true",
                    help="同时生成普通人版与程序员版的归档页并加切换导航")
    args = ap.parse_args()
    if args.all:
        consumer, dev = build_all(args.site_dir, args.repo_url)
        print(f"[索引] 已生成 {consumer} 和 {dev}")
    else:
        out = build_index(args.site_dir, args.repo_url)
        print(f"[索引] 已生成 {out}")


if __name__ == "__main__":
    main()
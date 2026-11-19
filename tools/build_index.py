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
from datetime import datetime
from pathlib import Path

REPORT_RE = re.compile(r"^github-daily-(\d{4}-\d{2}-\d{2})\.html$")
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def find_reports(site_dir: Path) -> list[tuple[str, Path]]:
    reports: list[tuple[str, Path]] = []
    if not site_dir.exists():
        return reports
    for path in site_dir.glob("github-daily-*.html"):
        m = REPORT_RE.match(path.name)
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


def render_index(reports: list[tuple[str, Path]], repo_url: str = "") -> str:
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
        archive = ('<div class="empty">还没有日报。先运行 '
                   '<code>python monitor.py run</code>，再重新生成索引。</div>')

    repo_link = ""
    safe_repo = _safe_url(repo_url)
    if safe_repo:
        repo_link = (f'<a href="{html.escape(safe_repo)}" target="_blank" '
                     f'rel="noopener">GitHub 仓库 ↗</a>')

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GitHub 普通人日报 · 历史归档</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--ink:#1f2328;--mut:#5b6572;--line:#e5e8ec;--brand:#2563eb}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:760px;margin:0 auto;padding:36px 18px 60px}}
header{{text-align:center;padding:18px 0 22px}}
h1{{font-size:27px;margin:0 0 8px}}
.sub{{color:var(--mut);font-size:14px}}
.summary{{background:#eef2ff;border:1px solid #dbe3ff;border-radius:14px;padding:14px 18px;margin:18px 0 26px;color:#33417a;font-size:14px}}
.archive{{list-style:none;margin:0;padding:0}}
.archive li{{margin:10px 0}}
.archive a{{display:flex;align-items:center;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;text-decoration:none;color:var(--ink);box-shadow:0 1px 3px rgba(0,0,0,.03)}}
.archive a:hover{{border-color:#bfdbfe;background:#f8fbff}}
.date{{font-weight:700;font-variant-numeric:tabular-nums}}
.week{{color:var(--mut);font-size:13px}}
.badge{{background:#dcfce7;color:#166534;border-radius:20px;padding:1px 9px;font-size:12px}}
.arrow{{margin-left:auto;color:var(--brand);font-size:13px}}
.empty{{background:var(--card);border:1px dashed var(--line);border-radius:12px;padding:24px;text-align:center;color:var(--mut)}}
code{{background:#f1f5f9;border-radius:5px;padding:1px 6px;font-size:12px}}
footer{{text-align:center;color:var(--mut);font-size:12px;margin-top:36px;line-height:2}}
a{{color:var(--brand)}}
</style></head><body><div class="wrap">
<header><h1>📚 GitHub 普通人日报</h1><div class="sub">每天自动筛选 · 历史归档</div></header>
<div class="summary">共收录 <b>{count}</b> 期日报，最近一期：<b>{html.escape(latest)}</b>。</div>
{archive}
<footer>
{repo_link}{' ｜ ' if repo_link else ''}内容仅供参考，使用前请以项目页面为准<br>
Not affiliated with GitHub
</footer>
</div></body></html>"""


def build_index(site_dir: str | Path, repo_url: str = "") -> Path:
    site = Path(site_dir)
    site.mkdir(parents=True, exist_ok=True)
    out = site / "index.html"
    out.write_text(render_index(find_reports(site), repo_url), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="生成日报历史归档索引页")
    ap.add_argument("site_dir", nargs="?", default="site", help="站点目录（默认 site）")
    ap.add_argument("--repo-url", default=os.environ.get("REPO_URL", ""),
                    help="仓库地址，用于页脚链接")
    args = ap.parse_args()
    out = build_index(args.site_dir, args.repo_url)
    print(f"[索引] 已生成 {out}")


if __name__ == "__main__":
    main()
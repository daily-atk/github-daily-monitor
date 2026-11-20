"""GitHub Trending 页面解析 —— 程序员排行榜版的数据源。

Trending 页面给出真实的"今日/本周新增 star"，这是普通搜索 API 拿不到的热度信号。
本模块只依赖标准库：抓页面 -> 解析 <article> -> 可选调用 GitHub API 补元数据。
"""
from __future__ import annotations

import html as _html
import re
import time
import urllib.request
from pathlib import Path

# Trending 页面里"stars today"的措辞随 period 变化
_PERIOD_LABEL = {
    "daily": ("stars today", "today"),
    "weekly": ("stars this week", "week"),
}

_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"


def _clean(fragment: str) -> str:
    """去掉 HTML 标签并反转义。"""
    if not fragment:
        return ""
    return _html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _to_int(text: str) -> int:
    m = re.search(r"([\d,]+)", text or "")
    return int(m.group(1).replace(",", "")) if m else 0


def parse_trending(html_text: str, period: str = "daily") -> list[dict]:
    """解析 Trending HTML，返回仓库 dict 列表（含 growth=今日/本周新增星标）。"""
    label, _ = _PERIOD_LABEL.get(period, _PERIOD_LABEL["daily"])
    articles = re.findall(r"<article[^>]*>(.*?)</article>", html_text, re.S)
    out: list[dict] = []
    for art in articles:
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"]+)"', art)
        if not m:
            continue
        full_name = m.group(1).strip("/")
        if "/" not in full_name:
            continue

        desc_m = re.search(
            r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', art, re.S)
        lang_m = re.search(
            r'itemprop="programmingLanguage"[^>]*>(.*?)</span>', art, re.S)
        growth_m = re.search(r"([\d,]+)\s+" + re.escape(label), art)
        stars_m = re.search(r'href="/[^"]+/stargazers"[^>]*>(.*?)</a>', art, re.S)
        forks_m = re.search(r'href="/[^"]+/forks"[^>]*>(.*?)</a>', art, re.S)

        owner, name = full_name.split("/", 1)
        out.append({
            "full_name": full_name,
            "name": name,
            "owner": {"login": owner},
            "html_url": f"https://github.com/{full_name}",
            "description": _clean(desc_m.group(1)) if desc_m else "",
            "language": _clean(lang_m.group(1)) if lang_m else "",
            "stargazers_count": _to_int(_clean(stars_m.group(1))) if stars_m else 0,
            "forks_count": _to_int(_clean(forks_m.group(1))) if forks_m else 0,
            # 排行榜核心信号：今日/本周新增星标
            "stars_growth": _to_int(growth_m.group(1)) if growth_m else 0,
            "growth_period": period,
            "_source": "trending",
        })
    return out


class TrendingClient:
    """抓取 Trending 页面 + 可选 API 补元数据，带磁盘缓存与限速。"""

    def __init__(self, period: str = "daily", delay: float = 2.0,
                 timeout: int = 25, use_cache: bool = True,
                 token: str = "", enrich_with_api: bool = True):
        self.period = period if period in _PERIOD_LABEL else "daily"
        self.delay = max(0.0, delay)
        self.timeout = timeout
        self.use_cache = use_cache
        self.token = token or ""
        self.enrich_with_api = enrich_with_api
        self.request_count = 0
        self.cache_hits = 0
        self._last_ts = 0.0
        if use_cache:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _throttle(self):
        if self.delay <= 0:
            return
        elapsed = time.time() - self._last_ts
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_ts = time.time()

    def _cache_get(self, key: str, ttl: int):
        if not self.use_cache:
            return None
        import hashlib
        p = _CACHE_DIR / (hashlib.md5(key.encode()).hexdigest() + ".json")
        if p.exists():
            try:
                import json
                payload = json.loads(p.read_text(encoding="utf-8"))
                if time.time() - payload.get("_ts", 0) < ttl:
                    self.cache_hits += 1
                    return payload["data"]
            except Exception:
                pass
        return None

    def _cache_set(self, key: str, data):
        if not self.use_cache:
            return
        import hashlib
        import json
        p = _CACHE_DIR / (hashlib.md5(key.encode()).hexdigest() + ".json")
        try:
            p.write_text(json.dumps({"_ts": time.time(), "data": data}, ensure_ascii=False),
                         encoding="utf-8")
        except Exception:
            pass

    def _get(self, url: str, headers: dict, ttl: int) -> str | None:
        cached = self._cache_get(url, ttl)
        if cached is not None:
            return cached
        for attempt in range(2):
            self._throttle()
            self.request_count += 1
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    text = resp.read().decode("utf-8", errors="ignore")
                self._cache_set(url, text)
                return text
            except Exception as e:
                if attempt == 0:
                    print(f"  [Trending 重试] {type(e).__name__}: {str(e)[:60]}")
        return None

    def fetch(self, count: int = 25) -> list[dict]:
        """抓 Trending 榜单；可选补全元数据。失败返回空列表（不抛异常）。"""
        url = f"https://github.com/trending?since={self.period}"
        html_text = self._get(url, {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/html,application/xhtml+xml",
        }, ttl=1800)
        if not html_text:
            return []
        repos = parse_trending(html_text, self.period)
        repos = [r for r in repos if r["stargazers_count"] > 0][:count]
        if self.enrich_with_api:
            repos = [self._enrich(r) for r in repos]
        return repos

    def _enrich(self, repo: dict) -> dict:
        """用 GitHub API 补 topics/license/pushed_at/created_at。失败保留原值。"""
        url = f"https://api.github.com/repos/{repo['full_name']}"
        headers = {
            "User-Agent": "github-daily-monitor/2.0",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        cached = self._cache_get("api:" + url, 86400)
        data = cached
        if data is None:
            self._throttle()
            self.request_count += 1
            try:
                import json
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                self._cache_set("api:" + url, data)
            except Exception:
                return repo
        if isinstance(data, dict):
            repo["topics"] = data.get("topics") or []
            lic = data.get("license") or {}
            spdx = (lic.get("spdx_id") or "") if isinstance(lic, dict) else ""
            repo["license"] = "" if spdx.upper() in ("NOASSERTION", "NONE") else spdx
            repo["pushed_at"] = data.get("pushed_at") or ""
            repo["created_at"] = data.get("created_at") or ""
            repo["homepage"] = data.get("homepage") or ""
            if data.get("stargazers_count"):
                repo["stargazers_count"] = data["stargazers_count"]
            if data.get("forks_count"):
                repo["forks_count"] = data["forks_count"]
        return repo

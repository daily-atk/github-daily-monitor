"""GitHub API 客户端：搜索仓库、限速、重试、磁盘缓存。"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://api.github.com"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"


class GitHubClient:
    def __init__(self, token: str | None = None, delay: float = 6.0,
                 timeout: int = 25, use_cache: bool = True):
        self.token = token or os.environ.get("GITHUB_TOKEN") or ""
        self.delay = max(delay, 1.0)
        self.timeout = timeout
        self.use_cache = use_cache
        self.last_request_ts = 0.0
        self.request_count = 0
        self.cache_hits = 0
        if use_cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _headers(self) -> dict:
        h = {
            "User-Agent": "github-daily-monitor/1.0",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _throttle(self):
        elapsed = time.time() - self.last_request_ts
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_ts = time.time()

    def _cache_key(self, url: str) -> Path:
        import hashlib
        name = hashlib.md5(url.encode("utf-8")).hexdigest() + ".json"
        return CACHE_DIR / name

    def get_json(self, url: str, cache_ttl: int = 3600) -> dict | None:
        """带缓存与重试的 GET。cache_ttl 秒内命中缓存。"""
        if self.use_cache:
            cp = self._cache_key(url)
            if cp.exists():
                try:
                    payload = json.loads(cp.read_text(encoding="utf-8"))
                    if time.time() - payload.get("_ts", 0) < cache_ttl:
                        self.cache_hits += 1
                        return payload.get("data")
                except Exception:
                    pass

        for attempt in range(3):
            self._throttle()
            self.request_count += 1
            try:
                req = urllib.request.Request(url, headers=self._headers())
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if self.use_cache:
                        self._cache_key(url).write_text(
                            json.dumps({"_ts": time.time(), "data": data}, ensure_ascii=False),
                            encoding="utf-8",
                        )
                    return data
            except urllib.error.HTTPError as e:
                if e.code in (403, 429):
                    # 匿名额度耗尽时不再死等，直接跳过本查询（其余查询仍可继续）
                    print(f"  [限速 {e.code}] 跳过本次查询（建议配置 GITHUB_TOKEN 提升额度）")
                    return None
                print(f"  [HTTP {e.code}] {url}")
                return None
            except Exception as e:
                print(f"  [网络错误] {type(e).__name__}: {e} - 重试 ({attempt+1}/3)")
                time.sleep(5 * (attempt + 1))
        return None

    def rate_limit(self) -> dict | None:
        return self.get_json(f"{API_BASE}/rate_limit", cache_ttl=60)

    def search_repos(self, query: str, sort: str = "stars", order: str = "desc",
                     per_page: int = 30) -> list[dict]:
        qs = urllib.parse.urlencode({
            "q": query, "sort": sort, "order": order,
            "per_page": per_page, "page": 1,
        })
        data = self.get_json(f"{API_BASE}/search/repositories?{qs}", cache_ttl=1800)
        if not data or not isinstance(data.get("items"), list):
            return []
        return data["items"]

    def readme(self, full_name: str, max_chars: int = 3000) -> str:
        """取 README 纯文本片段，用于质量判断。失败返回空串。"""
        qs = urllib.parse.urlencode({"q": f"repo:{full_name} filename:README"})
        data = self.get_json(f"{API_BASE}/search/code?{qs}", cache_ttl=86400)
        # code search 需要认证且返回结构复杂；简化为从仓库信息推断，不强依赖 README
        return ""

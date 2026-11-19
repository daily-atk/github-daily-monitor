"""测试用固定数据构造器。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

NOW = datetime.now(timezone.utc)


def make_repo(full_name: str = "example/app", **overrides):
    owner, _, name = full_name.partition("/")
    repo = {
        "full_name": full_name,
        "name": name or full_name,
        "owner": {"login": owner},
        "html_url": f"https://github.com/{full_name}",
        "homepage": "",
        "description": "A useful app for daily life.",
        "stargazers_count": 1000,
        "forks_count": 10,
        "language": "Python",
        "license": {"spdx_id": "MIT"},
        "topics": ["app"],
        "created_at": NOW.isoformat(),
        "pushed_at": NOW.isoformat(),
        "archived": False,
        "disabled": False,
        "size": 1000,
    }
    repo.update(overrides)
    return repo


def make_scored(full_name: str = "example/app", category: str = "生活",
                score: float = 80, **overrides):
    repo = make_repo(full_name)
    item = {
        "full_name": repo["full_name"],
        "name": repo["name"],
        "owner": repo["owner"]["login"],
        "url": repo["html_url"],
        "homepage": repo["homepage"],
        "description": repo["description"],
        "stars": repo["stargazers_count"],
        "forks": repo["forks_count"],
        "language": repo["language"],
        "license": "MIT",
        "platforms": "电脑",
        "topics": repo["topics"],
        "created_at": repo["created_at"],
        "pushed_at": repo["pushed_at"],
        "category": category,
        "category_label": category,
        "difficulty": "低",
        "score": score,
    }
    item.update(overrides)
    return item


def history_record(first_days: int = 3, seen_days: int | None = None,
                   recommended_days: int | None = None, times: int = 0) -> dict:
    now = datetime.now(timezone.utc)
    rec = {
        "times_recommended": times,
        "first_seen": (now - timedelta(days=first_days)).isoformat(),
        "last_recommended": ((now - timedelta(days=recommended_days)).isoformat()
                             if recommended_days is not None else None),
    }
    if seen_days is not None:
        rec["last_seen"] = (now - timedelta(days=seen_days)).isoformat()
    return rec
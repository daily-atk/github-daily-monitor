# Twitter / X Thread

> X 在国内通常不可直连；请在你能够正常访问 X 的网络环境下发布。  
> 发布时配 1–2 张截图（首推用 `docs/screenshot.png`），发布后置顶 thread。

## Tweet 1

```
GitHub Trending is built for developers.

I built a daily digest for everyone else — parents, students, friends who don't code.

It scans GitHub, keeps only projects ordinary people can use, and filters out SDKs/frameworks.

🧵
```

## Tweet 2

```
Every day it covers 5 domains: learning, life, productivity, health, personal finance.

Each report includes what it does, who it's for, platform, last update, license, and caveats — not just a repo name and a README slogan.
```

（配图：日报首屏截图）

## Tweet 3

```
To avoid recommending the same repos:
• 30-day cooldown after a recommendation
• 7-day cooldown for seen-but-not-selected
• max 3 items per domain

Boring engineering, but it makes the digest readable.
```

## Tweet 4

```
Search precision was the hardest part.

Query a core term for recall, then require the meaningful words locally.

"habit tracker" rejects "habitat". "investment tracker" rejects a .NET indicators library.
```

## Tweet 5

```
Zero dependencies: Python 3.10+ standard library only.
36 unit tests, no network calls.
Runs on Windows/macOS/Linux.
```

## Tweet 6

```
Optional AI enrichment is off by default. It supports any OpenAI-compatible endpoint, has --dry-run and a cost cap, and falls back to rule-based copy without a key.
```

## Tweet 7

```
It publishes a self-contained HTML report + archive via GitHub Actions + Pages.

Code (MIT): https://github.com/daily-atk/github-daily-monitor
Demo: https://daily-atk.github.io/github-daily-monitor/

Feedback welcome — especially which projects should be filtered out.
#opensource #python
```

## 发布备注

- 首推配图：`docs/screenshot.png`；第二推可配归档页截图。
- 发布后把 thread 置顶；前 2 小时尽量回复评论。
- 不写“please like/retweet”，不拉群点赞。
- 发布时间：美东上午 9–11 点，或北京时间晚上 9–11 点。
- X 的 URL 会按 23 字符计算，最后一条长度在限制内。
- 如果 Demo 打不开，正文里补一句“screenshot in the repo”，并附截图链接。
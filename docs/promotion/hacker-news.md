# Hacker News（Show HN）

## 标题（≤80 字符，必须 Show HN: 开头）

首选：

```
Show HN: Zero-dependency Python tool turns GitHub into a daily digest
```

备选：

```
Show HN: A GitHub daily digest for non-technical people
```

## 正文

```
Hi HN,

I built a small Python tool that generates a daily digest of GitHub projects for non-technical people.

GitHub Trending and most "awesome" lists are developer-oriented. This filters for things an ordinary person could use across learning, life, productivity, health, and personal finance, and removes developer infrastructure (SDKs, frameworks, CLI tools, self-hosted services).

How it works:
- GitHub Search API with keyword rotation and rate-limit handling
- Filters: missing description, excluded words, star/fork ratio, developer infrastructure
- 30-day recommendation cooldown + 7-day "seen but not selected" cooldown
- Max 3 items per domain
- Core-term search + local phrase validation ("habit tracker" rejects "habitat")
- Markdown + self-contained HTML report
- Optional OpenAI-compatible enrichment, off by default, with --dry-run and a cost cap
- GitHub Actions + Pages for daily publishing

Zero dependencies (Python stdlib), 36 tests, MIT.

Repo: https://github.com/daily-atk/github-daily-monitor
Demo: https://daily-atk.github.io/github-daily-monitor/

Limitations: the filtering is heuristic, the report is in Chinese (the target readers are Chinese non-technical users), and quality varies. I'd appreciate feedback on the dedup design and the filtering heuristics.
```

## 第一条评论（发布后自己补充技术细节）

```
A few implementation notes:

- The dedup cache originally had a bug: `last_recommended = None` raised inside a try/except, so projects seen but not selected were permanently skipped. Fixed with a separate `last_seen` field and a 7-day cooldown.
- Full-phrase GitHub queries had very low recall (10 queries → 9 results → 1 item). I switched to a core-term query plus a local phrase check, which restored recall without the false positives.
- The AI layer is optional and cost-capped; without a key the tool uses rule-based copy. I wanted the project to be useful without an API bill.
- The report is Chinese because the target audience is Chinese non-technical readers; the engine itself is language-agnostic.
```

## 发布注意事项

- HN 对营销非常敏感：不要写“please upvote”“please star”，不要拉朋友投票。
- 标题不要用感叹号、全大写、夸张形容词。
- 发布后至少留 2–3 小时回复评论；负面评论也要具体回应。
- 最好在**美国东部工作日上午**发布（北京时间晚上 9–11 点左右）。
- 如果被 flag，不要立刻重发；先检查是否违反了 Show HN 规则。
- Demo 打不开会影响转化；发布前确认 `https://daily-atk.github.io/github-daily-monitor/` 在你的网络和英文读者网络都可访问。
- 如果 Demo 在部分地区不可访问，正文里注明“repo includes a screenshot”，并附截图链接。
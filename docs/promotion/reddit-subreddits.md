# Reddit 分版文案

> Reddit 在国内通常不可直连；请在你能够正常访问 Reddit 的网络环境下发布。  
> 每个 subreddit 的规则不同，发之前先读置顶帖和 sidebar；**一次只发一个版，间隔 2–3 天**，不要同一天跨版复制同一段文字。

## 通用原则

- 明确写“I'm the author”，不要伪装成路人。
- 不要求 upvote / star；只请求具体反馈。
- 先参与社区（回复别人的帖子），再发自己的项目。
- 标题不要全大写、不要营销腔。
- 如果被 mod 删除，先问违反哪条规则，不要立刻重发。

---

## r/github

**Flair**：Show and Tell / Project（以版规为准）

**Title**

```
I built a zero-dependency Python tool that turns GitHub into a daily digest for non-technical people
```

**Body**

```
Hi r/github,

I kept running into the same problem: GitHub Trending and most "awesome" lists are written for developers. My family and friends don't care about SDKs or self-hosted infrastructure — they want to know what they could actually use today.

So I built GitHub Daily Monitor. It scans GitHub every day, keeps projects across learning, life, productivity, health, and personal finance, and filters out developer-only infrastructure.

A few details:
- 30-day recommendation cooldown + 7-day "seen but not selected" cooldown
- max 3 items per domain, so one category can't take over
- core-term search + local phrase validation ("habit tracker" rejects "habitat")
- Markdown + self-contained HTML report
- optional OpenAI-compatible enrichment, off by default
- GitHub Actions + Pages for daily publishing
- Python 3.10+ standard library only, 42 tests, MIT

Repo: https://github.com/daily-atk/github-daily-monitor
Demo: https://daily-atk.github.io/github-daily-monitor/

The filtering is heuristic, so quality varies. I'd especially appreciate feedback on which projects should be filtered out. I'm the author; not affiliated with GitHub.
```

---

## r/selfhosted

**Title**

```
A zero-dependency Python generator for a daily GitHub digest (self-hosted, no service)
```

**Body**

```
Hi r/selfhosted,

This is a small self-hosted tool, not a SaaS: a Python script that scans GitHub and generates a static Markdown + HTML digest for non-technical readers.

- Runs locally; no database, no Docker, no external services required
- Python 3.10+ standard library only
- Output is a self-contained HTML file you can host anywhere
- Optional GitHub Actions workflow publishes it to GitHub Pages daily
- 30-day dedup, 7-day seen cooldown, max 3 items per domain
- Optional OpenAI-compatible enrichment, off by default, with --dry-run and a cost cap

The goal is a "GitHub digest for ordinary people": learning, life, productivity, health, finance; no SDKs or frameworks.

Repo: https://github.com/daily-atk/github-daily-monitor
Demo: https://daily-atk.github.io/github-daily-monitor/

Feedback welcome, especially from anyone running it on a NAS or home server.
```

---

## r/Python

**Flair**：Showcase

**Title**

```
A stdlib-only Python tool that builds a daily GitHub digest (dedup, domain quotas, phrase validation)
```

**Body**

```
Hi r/Python,

I wrote a small tool that generates a daily GitHub digest for non-technical people. It is stdlib-only, so no requirements.txt.

The interesting parts:

1) Dedup: 30-day cooldown after a recommendation, 7-day cooldown for projects seen but not selected. The first version had a bug where `last_recommended = None` raised inside a try/except and permanently skipped the project; the fix was a separate `last_seen` field.

2) Search precision: query a core term for recall, then require the meaningful words locally:

```python
terms = [t for t in phrase.lower().split() if t not in {"app", "tool", "software"}]

def matches_terms(repo, terms):
    text = " ".join([repo["name"], repo["full_name"],
                     repo["description"], " ".join(repo["topics"])]).lower()
    return all(t in text for t in terms)
```

3) Domain quotas: max 3 items per domain, so the report is not all "life" projects.

4) Optional AI: any OpenAI-compatible endpoint, off by default, with --dry-run and a cost cap.

42 stdlib unit tests, GitHub Actions CI on Python 3.10 and 3.13.

Repo: https://github.com/daily-atk/github-daily-monitor

Happy to hear feedback on the heuristics or the code structure.
```

---

## r/opensource

**Title**

```
Open-sourced a zero-dependency GitHub daily digest generator (MIT)
```

**Body**

```
Hi all,

I open-sourced GitHub Daily Monitor, a small tool that turns GitHub into a daily digest for non-technical people. It filters for learning, life, productivity, health, and personal finance, and removes developer-only infrastructure.

- MIT licensed
- Python 3.10+, standard library only
- 42 unit tests + GitHub Actions CI
- Optional GitHub Actions workflow that publishes the report and an archive to Pages
- Optional AI enrichment, off by default

Repo: https://github.com/daily-atk/github-daily-monitor
Demo: https://daily-atk.github.io/github-daily-monitor/

Contribution areas I'd love help with:
- better filtering rules for "useful to ordinary people"
- more domain presets (health-only, finance-only, etc.)
- English copy for the report

If you maintain an awesome list and think it fits, I'd appreciate a pointer to the right contribution process.
```

---

## 首发（r/Python）操作清单

选 r/Python 首发：技术受众最能理解实现细节、反馈质量高、且对 Showcase 类内容相对友好。

**发布前**

- [ ] 确认能正常访问 Reddit（国内通常不可直连）
- [ ] 账号已注册并按社区规则养号（有真实发言记录，别用纯新号）
- [ ] 先花 10 分钟读 r/Python 的 sidebar 规则和置顶帖，确认 Showcase flair 可用
- [ ] 先回复 2–3 条别人的帖子，再发自己的
- [ ] 复制上面 r/Python 的 Title + Body 备用

**发布中 / 发布后**

1. 打开 https://www.reddit.com/r/Python/submit，选 **Text** 类型
2. 标题粘贴 Title，正文粘贴 Body，flair 选 **Showcase**
3. 发布后 48 小时内守评论，逐条认真答；明确自己就是作者
4. 有 bug 反馈就如实承认并说修复计划；不要删负评
5. 24h 后到 `FEEDBACK_LOG.md` 记 Star 增量和评论质量

## 发布节奏建议

| 顺序 | 版块 | 间隔 |
|---|---|---|
| 1 | r/Python | 第 1 天 |
| 2 | r/github | 第 3 天 |
| 3 | r/selfhosted | 第 5 天 |
| 4 | r/opensource | 第 7 天 |

每个版发完后至少留 48 小时回复评论，再考虑下一个版。**HN 和 Reddit 不要同一天发**——错开一周，先看 HN 反馈再调整 Reddit 文案。
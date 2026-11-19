# Product Hunt 发布文案

> Product Hunt 主要面向英文用户；本项目输出中文，发布时请明确说明目标读者是中文非技术用户。

## 基本信息

**Name**

```
GitHub Daily Monitor
```

**Tagline（≤60 字符）**

```
Turn GitHub into a daily digest for non-technical people
```

**Description（≤260 字符）**

```
GitHub Trending is built for developers. GitHub Daily Monitor filters GitHub daily for projects ordinary people can use — learning, life, productivity, health, finance — with 30-day dedup, domain quotas, and optional AI. Zero dependencies, MIT.
```

**Topics**

```
Developer Tools, Open Source, Productivity, GitHub, Python
```

**Links**

- Website: https://daily-atk.github.io/github-daily-monitor/
- GitHub: https://github.com/daily-atk/github-daily-monitor

## Gallery 文案

| # | 图片 | 文案 |
|---|---|---|
| 1 | 日报首屏截图 | A daily digest with platform, license, and last update |
| 2 | 归档页截图 | Every day is archived and browsable |
| 3 | 终端/bat 运行截图 | One-click run on Windows, macOS, and Linux |
| 4 | Actions 运行截图 | Optional daily publishing via GitHub Actions + Pages |

建议尺寸：1270×760（16:10），首图就是 `docs/screenshot.png`。

## 第一条评论（Maker Comment）

```
Hi Product Hunt!

I built GitHub Daily Monitor because my family kept asking for "useful GitHub projects" and every list I found was full of SDKs, frameworks, and self-hosted infrastructure. They don't care about any of that.

So I flipped the filter: only keep projects an ordinary person could actually use — learning, life, productivity, health, personal finance — and explicitly remove developer-only tools.

A few things I'm proud of:
- 30-day dedup + 7-day seen cooldown, so the digest doesn't repeat itself
- max 3 items per domain
- core-term search + local phrase validation (no more "habitat" when you search "habit tracker")
- zero dependencies: Python stdlib only
- optional AI enrichment, off by default, with a cost cap
- daily publishing to GitHub Pages via Actions

The report is in Chinese because the target readers are Chinese non-technical users; the engine is language-agnostic.

Would love feedback on the filtering heuristics — especially which kinds of projects should be excluded.
```

## 发布前检查

- [ ] 准备 240×240 logo（可用报告截图裁一个方形，或做一个简单的文字图标）
- [ ] Gallery 至少 3 张图（首图用日报截图）
- [ ] Demo 链接可访问（发布前用另一台设备/网络确认）
- [ ] Maker 个人资料完善
- [ ] 选好 launch 日期（避开周末；太平洋时间 00:01 上线）
- [ ] 发布后全天回复评论
- [ ] 不要求 upvote，不拉群投票

## 备注

- Product Hunt 的用户以英文为主，中文产品要有清楚的英文说明。
- 如果 Demo 在部分地区不可访问，在评论区补充截图和 repo 链接。
- Product Hunt 的转化更依赖首图和 tagline，截图质量比长文案重要。
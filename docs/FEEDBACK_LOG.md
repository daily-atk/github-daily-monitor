# 反馈与效果记录

> 配合 [`PROMOTION_PLAN.md`](PROMOTION_PLAN.md) 第 5、6 节使用。每周花 10 分钟更新，用来把流量变成产品力、把数据变成决策依据。

---

## 一、反馈归类

每收到一条 issue / discussion / 平台评论，按三类之一记一行。**质量误报优先处理**——推荐质量是这个项目的生命线。

| 日期 | 来源 | 类型 | 内容摘要 | 状态 | 处理结果 |
|---|---|---|---|---|---|
|  |  | 质量误报 / 功能请求 / 使用困难 |  | 待处理 / 处理中 / 已修复 |  |

**填写说明**

- **来源**：V2EX / 少数派 / GitHub Issue / Discussions / 小红书 / 知乎 / 即刻 / HN / Reddit / 其他
- **质量误报**：推荐了不合适的项目（开发者基础设施、与普通人无关等）→ 优先调 `exclude_words` 或关键词
- **功能请求**：想要新关键词源、导出格式、RSS 等 → 进 Roadmap
- **使用困难**：安装、配置、看不懂报告 → 补文档或简化入口
- **状态**：每条都要有闭环。修复后在原 issue/discussion 回复"已修复，感谢"，并公开致谢采纳的建议。

---

## 二、效果周记录

坚持 4 周就能看出哪个渠道值得长期投入。数字拿不到就留空，不要瞎填。

| 周次 | 日期区间 | Star | 新增 Star | Pages PV | 主要来源 | 本周发布渠道 | 备注 |
|---|---|---|---|---|---|---|---|
| W1 |  |  |  |  |  | V2EX |  |
| W2 |  |  |  |  |  | 少数派 + HelloGitHub |  |
| W3 |  |  |  |  |  | 掘金 + Show HN |  |
| W4 |  |  |  |  |  | Reddit + Twitter |  |

**怎么看数据**

- 看**新增 Star 的跃升点**对应哪次发布 → 那个渠道加倍投入。
- 看 **Pages PV 与来源** → 判断中文社媒是否真的把人带到了日报。
- 看 **Issue/Discussion 增长与质量** → 真实反馈比 star 更有价值。
- 某渠道发了两次都没水花 → 停掉，把时间给有效的那个。

**取数命令**（需要 gh CLI）

```bash
# 仓库当前 star / fork / issue 数
gh api repos/daily-atk/github-daily-monitor --jq '{stars:.stargazers_count,forks:.forks_count,issues:.open_issues_count}'

# 最近一周的 star 增长（按天）
gh api repos/daily-atk/github-daily-monitor/stargazers -H "Accept: application/vnd.github.star+json" \
  --jq '.[].starred_at' | tail -20
```

> Pages PV 需要单独接入隐私友好的统计（见方案 P1-5）后才能拿到；未接入前此列留空即可。

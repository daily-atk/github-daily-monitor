# 掘金 / OSChina / Gitee 技术文

## 标题（选一个）

1. 零依赖 Python 日报：我如何每天从 GitHub 筛出普通人能用的项目
2. 从 120 条候选到 8 个推荐：一个 GitHub 日报的去重与配额设计
3. 不用 AI 也能跑：一个零依赖 GitHub 日报的工程实践

## 摘要

一个面向普通人的 GitHub 日报生成器：纯 Python 标准库、零依赖，带 30 天去重、领域配额、关键词轮换和可选的 AI 文案增强。本文记录它的流水线设计、几个踩过的坑，以及如何用 GitHub Actions 每天自动发布。

---

## 一、为什么要做这个

GitHub Trending 和大多数“精选项目”列表默认读者是开发者：框架、SDK、命令行工具、自托管服务。对不写代码的人来说，这些内容很难转化成“今天我能用什么”。

我想做的不是又一个开发者日报，而是一份给普通人看的日报：只关心学习、生活、效率、健康、财务，明确把开发者基础设施排除在外。

约束也很明确：

- 纯 Python 标准库，零运行时依赖
- 输出中文 Markdown + 自包含 HTML
- 可以本地跑，也可以每天自动发布
- AI 只能是可选项，不能成为运行前提

## 二、整体流水线

```
采集候选 → 机械过滤 → 历史去重 → 普通人价值打分
→ 可选 AI 增强 → Markdown + HTML 报告 → GitHub Pages
```

对应到代码：

- `lib/github_client.py`：GitHub Search API、限流、缓存
- `lib/pipeline.py`：过滤、去重、打分、领域配额
- `lib/reporter.py`：报告渲染与增强数据校验
- `monitor.py`：collect / report / run / stats / validate
- `enrich.py`：可选的 OpenAI 兼容适配器
- `tools/build_index.py`：历史归档索引页

## 三、去重：两个冷却期

最早的实现只有一个 30 天推荐冷却，但很快遇到两个问题：

1. **见过的项目会反复出现在候选池**，每天占位置；
2. 如果简单地把“见过”也永久拉黑，候选池会逐日枯竭。

最后的规则是：

- **推荐过的项目**：30 天冷却（`dedup.cooldown_days`）
- **只是见过但没入选的项目**：7 天冷却（`dedup.seen_cooldown_days`，可设为 0 关闭）

```python
if last_recommended:
    if (now - last_recommended).days < cooldown:
        skip()
else:
    seen_days = (now.date() - last_seen.date()).days
    if 1 <= seen_days < seen_cooldown:
        skip()
```

注意 `1 <= seen_days`：**同一天见过的不拦截**。否则手动跑过一次之后，定时任务再跑就会把候选池全部判成冷却，生成一份 0 项的空日报。这个坑我在一天内踩了两次，最后还加了“当天已有非空候选就跳过采集”的幂等保护。

## 四、领域配额：避免整份日报都是“生活”

只按分数排序，结果很容易被某个领域刷屏。加一个简单的上限：

```python
for item in ranked:
    if max_per_domain and per_cat.get(item.category, 0) >= max_per_domain:
        continue
    top.append(item)
    per_cat[item.category] = per_cat.get(item.category, 0) + 1
```

默认每个领域最多 3 个。实际效果：某天 10 个项目里 8 个“生活”，调整后变成财务 3、效率 3、生活 3、学习 1。

## 五、搜索：召回与精度

关键词按领域分组，每天轮换代表词，避免只用到配置里的第一个词。

更大的问题是精度。比如配置里写 `habit tracker`：

- 只用 `habit` 搜，会搜到 `habitat`（一个开发者工具）；
- 只用完整短语搜，召回又太低。

最后的做法是 **核心词召回 + 本地短语校验**：

```python
terms = [t for t in phrase.lower().split() if t not in {"app", "tool", "software"}]

def matches_terms(repo, terms):
    text = " ".join([repo["name"], repo["full_name"],
                     repo["description"], " ".join(repo["topics"])]).lower()
    return all(t in text for t in terms)
```

搜索用核心词保证召回，结果再用 `matches_terms` 要求同时包含短语里的实词。`habit tracker` 会保留真正的习惯追踪器，排除 habitat；`investment tracker` 也不会混进 .NET 指标库。

## 六、普通人价值打分

打分不是“项目好不好”，而是“对普通人有没有用”：

- 消费级信号：app、tool、planner、tracker、reminder、一键、提醒等，加分
- 开发者信号：SDK、library、framework、CLI、API、Docker 等，扣分
- 开发者基础设施：项目名/topics 命中重罚，描述命中轻罚
- 无许可证：扣 6 分（普通人无法判断能否安全使用）
- 星标、官网、新鲜度：小幅加分

这里有一个细节：关键词匹配必须按单词边界，否则 `api` 会命中 `capital`，`app` 会命中 `apple`。

## 七、AI 是可选项

没有 AI，脚本仍然能生成完整报告，只是文案用规则兜底模板。想要更具体的描述时，可以接任意 OpenAI 兼容接口：

```bash
python enrich.py --dry-run
python enrich.py --enable --max-cost 0.05
```

设计上做了三件事：

- **默认关闭**：不加 `--enable` 不调用接口
- **费用上限**：`--max-cost` + 单价环境变量
- **格式校验**：写入前检查 `full_name`、字段、日期，缺项回退到兜底文案

## 八、报告与自动发布

报告是单文件 HTML，不依赖外部 CSS/JS，方便直接分享。每个项目包含：功能、适合人群、实用价值、平台、最近更新、许可证、注意事项。

GitHub Actions 每天 UTC 12:00（北京时间 20:00）运行：

1. 跑测试
2. 采集候选
3. 可选 AI 增强
4. 生成报告
5. 合并到 `gh-pages`
6. 生成历史归档索引
7. 发布到 GitHub Pages

这样仓库是引擎，Pages 是产品，普通人不需要 clone 也能看。

## 九、测试与踩坑

目前 36 个单元测试，不发真实 API 请求，覆盖配置、过滤、打分、去重、报告渲染和增强校验。

踩过的坑：

1. **去重黑洞**：旧逻辑对 `last_recommended = null` 调 `.replace()` 抛异常，异常被吞掉后项目被永久跳过；历史库 118 条里 108 条中招。
2. **同日空榜**：见上文的 `seen_days`。
3. **全短语低召回**：10 个查询只捞到 9 条，最终 1 项；改成核心词 + 本地校验后恢复。
4. **标题显示**：`xbmc/xbmc` 显示成 xbmc，`home-assistant/android` 显示成 android；后来加了 `display_name()`，从描述里提取产品名（xbmc → Kodi）。

## 十、结果与限制

- 零依赖、36 个测试、CI 通过
- 每天自动生成并发布，历史归档可追溯
- 筛选是启发式的，不是人工精选，质量会有波动
- 不保证每天都有 10 个，宁缺毋滥
- 不配置 AI 时文案偏模板化

## 链接

- 仓库：https://github.com/daily-atk/github-daily-monitor
- 在线 Demo：https://daily-atk.github.io/github-daily-monitor/
- 截图：`docs/screenshot.png`

---

## 发布备注

### 掘金

- 标签：Python、开源、GitHub、自动化
- 封面：`docs/screenshot.png`
- 文末加“欢迎提 Issue / 不喜勿喷”即可，不要求赞

### OSChina

- 标题可改为《一个零依赖的 GitHub 日报生成器：去重、领域配额与自动发布》
- 同步发布即可；OSChina 读者偏工程，保留“踩坑”部分

### Gitee

- Gitee 是代码托管，不是博客；技术文发 OSChina，代码做镜像：
  1. Gitee 新建仓库 → 「导入 GitHub 仓库」
  2. 填入 `https://github.com/daily-atk/github-daily-monitor`
  3. 开启 Gitee Pages（需实名；免费版可能有访问限制）
  4. README 顶部加一行「国内镜像：<Gitee 地址>」
- 注意：Gitee Pages 的政策和可用性会变化，开启前先确认当前规则。
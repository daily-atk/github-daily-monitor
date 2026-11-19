# 每日 GitHub 监测助手

每天自动从 GitHub 捞出「对普通人真正有用」的新项目 / 有重要更新的项目，筛选后生成一份简洁总结（Markdown + HTML），按推荐优先级排序。**同一项目 30 天内不重复推荐。**

## 它怎么工作

```
采集 GitHub 候选 → 机械过滤低质量 → 历史去重 → 普通人价值打分 → AI 语义终筛+文案润色 → 生成报告
```

- **机械层（Python 脚本）**：搜索、限流重试、过滤（无描述/排除词/星标/fork比/开发者基础设施）、30 天冷却期去重、打分排序。稳定可靠，无人值守也能跑。
- **语义层（AI，在每日自动化中执行）**：脚本初筛出的候选交给 AI，判断"是否真对普通人有用"，剔除凑数项目，用中文写清功能/适合人群/实用价值/上手难度/注意事项，并重新排序。

## 文件结构

| 文件 | 作用 |
|---|---|
| `config.json` | **用户配置**：关键词、排除词、时间、阈值、Top N、输出格式 |
| `monitor.py` | 主程序（collect / report / run / stats 四个命令） |
| `lib/` | 采集、过滤、打分、报告生成模块 |
| `AI_WORKFLOW.md` | 每日自动化 AI 的执行说明（作业指导书） |
| `data/history.json` | 历史去重记录（自动生成，勿手改） |
| `data/candidates_latest.json` | 最新候选数据 |
| `data/enriched_latest.json` | AI 增强数据（每日自动化生成） |
| `reports/` | 每日报告输出 |

## 常用命令

```bash
cd "D:/WorkBuddy产出/github-daily-monitor"

python monitor.py collect   # 只采集候选（写 candidates_latest.json）
python monitor.py report    # 只生成报告（读取候选+当日增强数据）
python monitor.py run       # 采集+报告一步到位
python monitor.py stats     # 查看历史去重库统计
```

## 如何配置

直接编辑 `config.json`（以 `_` 开头的键是说明，可忽略）：

- **监测关键词** `keywords`：按「学习/生活/效率/健康/财务」分组，每组用第一个词作为代表词发起搜索。想多覆盖就调整各组的第一个词，或增加领域。
- **排除词** `exclude_words.name` / `.description`：项目名或描述命中就过滤掉。
- **每日总结时间** `schedule.summary_time`：展示用；真正触发时间由定时自动化控制（当前设为每天 20:00），改时间需同步更新自动化任务。
- **每天推荐数量** `scoring.top_n`、最低分 `scoring.min_score`。
- **去重冷却期** `dedup.cooldown_days`（默认 30 天）。
- **输出格式** `output.formats`（md / html）。

## 提升采集额度（推荐）

匿名访问 GitHub Search API 限流很低（约 10 次/分钟，容易 403）。配置 Token 后可大幅提速：

1. 到 https://github.com/settings/tokens 生成一个 Public 仓库只读权限的 Token（classic 勾选 `public_repo` 即可，或 fine-grained 无需权限）。
2. 设置环境变量 `GITHUB_TOKEN`（脚本会自动读取 `config.json` 里 `github_token_env` 指定的变量名）。

Windows 临时设置：
```powershell
$env:GITHUB_TOKEN = "你的token"
```
永久设置可在「系统属性 → 环境变量」中添加。不配置也能用，只是采集时部分查询可能因限流被跳过。

## 自动化

已创建每天 20:00 的定时任务：自动运行采集 → AI 语义终筛与文案增强 → 生成并展示 Markdown + HTML 报告。执行细节见 `AI_WORKFLOW.md`。

## 说明与免责

- 星标数、维护状态会实时变化，报告内容仅供参考，使用前请以项目页面为准。
- 数据来自 GitHub 公开 API，遵守其服务条款；报告为本地生成，不涉及隐私数据上传。

## 许可证

MIT License — 详见 [LICENSE](LICENSE)。可自由使用、修改、商用，只需保留版权声明。

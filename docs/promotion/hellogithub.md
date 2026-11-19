# HelloGitHub 投稿

## 投稿入口

二选一：

1. 网站：https://hellogithub.com/periodical → 「推荐 / 自荐」
2. GitHub Issue：https://github.com/521xueweihan/HelloGitHub/issues/new/choose
   → 选择 **「提交项目」**（模板 `submit-cn.yaml`）

> 投稿前建议先在 https://hellogithub.com 搜索项目地址，确认没有被推荐过。当前仓库是新建的，未发现重复。

## 按模板填写

**项目地址**

```
https://github.com/daily-atk/github-daily-monitor
```

**类别**

```
Python
```

**项目标题**

```
每天筛选普通人能用的 GitHub 项目并生成中文日报
```

**项目描述（32–256 字符，不要复制 README）**

```
一个面向普通人的 GitHub 日报生成器：每天自动筛选学习、生活、效率、健康、财务类项目，过滤开发者基础设施，30 天内不重复推荐、每个领域最多 3 个，输出中文 HTML 和 Markdown。纯 Python 标准库、零依赖，可选 AI 润色，也能用 GitHub Actions 每天自动发布到 Pages。
```

**亮点**

```
- 普通人视角：明确排除 SDK、library、framework 等开发者基础设施，而不是又一个“开发者觉得酷”的榜单
- 去重与配额：推荐过的项目 30 天冷却，只是见过但没选中的 7 天冷却；每个领域最多 3 个，避免整份日报全是“生活”
- 搜索精度：核心词召回 + 本地短语校验，例如 “habit tracker” 会排除 habitat
- 零依赖：Python 3.10+ 标准库，不需要 pip install；Windows 双击 bat，macOS/Linux 跑 run.sh
- 可自部署：自带 GitHub Actions，每天定时生成并发布到 GitHub Pages，同时维护历史归档页
```

**示例代码（可选）**

```bash
git clone https://github.com/daily-atk/github-daily-monitor.git
cd github-daily-monitor
./run.sh          # macOS / Linux
# Windows：双击 运行日报.bat
```

**截图或演示**

- 在线 Demo：https://daily-atk.github.io/github-daily-monitor/
- 报告截图：https://github.com/daily-atk/github-daily-monitor/blob/main/docs/screenshot.png?raw=true

## 自荐说明（可附在正文）

```
你好，我是这个项目的作者。做它的起因是：GitHub Trending 和大多数精选列表都是写给开发者的，我家里人点进去第一步就劝退了。
所以我把筛选口径改成了“普通人能不能用”，并且把去重、领域配额、关键词轮换这些工程细节做完整。项目 MIT 开源、零依赖，欢迎试用和提建议。
```

## 投稿前检查

- [x] README 包含项目介绍、特性、快速开始、FAQ、贡献、协议
- [x] 有 CI（36 个单元测试）和持续提交
- [x] MIT 许可证、NOTICE、免责声明
- [x] 没有重复推荐记录
- [ ] 可选：先积累 3–7 天的日报和几个真实 issue，再投稿，通过率更高

## 备注

- HelloGitHub 对“自荐项目”不强制 star 数，但会看 Insights 活跃度和 Issues。
- 描述不要直接复制 README；上面这版是按模板重新写的。
- 如果被收录，记得在 issue 里回复致谢，并把贡献人链接加到 README（可选）。
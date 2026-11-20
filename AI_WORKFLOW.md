# 自动化任务的执行说明（供每日定时 AI 阅读）

每天 20:00 自动化触发时，请按以下流程执行。这份文件是给 AI 看的作业指导书，不是给用户看的报告。

## 目标

产出一份面向**普通人（非技术用户）**的 GitHub 实用项目速递，真正帮到学习/生活/效率/健康/财务。宁缺毋滥：只推荐确实有价值的，宁可少于 10 个，也不要凑数塞开发者玩具。

## 步骤

### 1. 采集
```bash
# 在项目根目录执行
python monitor.py collect
```
这会写 `data/candidates_latest.json`，里面是脚本机械初筛后的候选（已过滤低质量、已按 30 天冷却期去重）。

### 2. 语义终筛 + 文案增强（关键）
读取 `data/candidates_latest.json` 的 `candidates` 数组。对每一个候选：

1. **判断是否真的对普通人有价值**。以下情况直接剔除：
   - 纯开发者基础设施（浏览器引擎、数据库、SDK、框架、编译器、运维工具）——普通人用不上
   - 只是例行提交的老牌大项目，没有"值得关注的新动作"
   - 描述含糊、看不出具体用途
   - 需要很强技术背景才能用，且收益不明显
2. 对保留下来的项目，用你的理解填写下面字段（用中文，简洁具体，不写套话）：
   - `features`：主要功能——用 1-2 句话说清"这东西具体干什么"，而非复述 README 标语
   - `audience`：适合人群——具体到场景，如"经常忘记喝水、想要温和提醒的上班族"
   - `value`：实用价值——对普通人省了什么事、改善了什么，要具体
   - `difficulty`：上手难度（低/中/高），可覆盖脚本初判；低=网页/插件/App 开箱即用，中=需简单配置或自托管，高=需命令行/技术背景
   - `notes`：注意事项——许可证、维护状态、隐私/数据安全、是否需要付费或 API Key 等真实提醒
3. 按你的综合判断重新排序（推荐优先级：对普通人的实际帮助 > 新鲜度 > 热度）。

把结果写成 `data/enriched_latest.json`，格式：
```json
{
  "date": "YYYY-MM-DD",
  "items": [
    {
      "full_name": "owner/repo",
      "features": "……",
      "audience": "……",
      "value": "……",
      "difficulty": "低",
      "notes": "……"
    }
  ]
}
```
注意 `full_name` 必须与候选里的一致，用于对应。`items` 的顺序就是最终推荐顺序。

### 2.5 校验增强数据

```bash
python monitor.py validate
```

若提示字段缺失、项目不在候选内或日期不一致，请修正 `data/enriched_latest.json` 后重新校验。
缺少增强项不会阻断报告，但对应项目会使用脚本兜底文案。

### 3. 生成报告
```bash
python monitor.py report
```
脚本会把增强内容合并进 Markdown + HTML 报告，写到 `reports/` 目录。

### 4. 生成程序员热度榜
```bash
python monitor.py --profile dev collect
python monitor.py --profile dev report
```
它抓 GitHub Trending 真实新增 star，按热度排序，写到 `data-dev/candidates_latest.json` 和 `reports-dev/`。

想要程序员榜的 AI 文案（可选）：
```bash
python enrich.py --profile dev --enable --max-cost 0.05
python monitor.py --profile dev validate || true
python monitor.py --profile dev report
```
没有配置 `LLM_API_KEY` / `LLM_MODEL` 时跳过，报告使用技术视角兜底文案。

### 5. 同步两榜前三名到资料库
```bash
# 二选一：命令行参数或环境变量 WORKBUDDY_LIBRARY_DATABASE_ID
python tools/sync_library.py --database-id <你的资料库ID>
```
从两版最新数据各取前 3（共 6 条），写到 `data/top3_for_library.json`，并追加到资料库表格
「GitHub 每日榜单前三名」。资料库 ID 通过 `--database-id` 或环境变量 `WORKBUDDY_LIBRARY_DATABASE_ID` 提供；未配置时只导出 JSON，不写库。
表格 17 字段：日期 / 榜单 / 排名 / 项目 / 链接 / 一句话看点（中文，优先用第 2 步写的中文 features，否则按用途关键词生成）/ 语言 / 总Star / 今日新增Star / 适合人群 / 实用价值 / 上手难度 / 注意事项 / 方向分类 / 许可证 / 项目主页 / 技术亮点（程序员榜）。
按「日期 + 榜单 + 名次」幂等：项目相同则跳过，项目变了则更新，不会重复插入。
- stdout 是单行 JSON：`written` 新增数、`updated` 更新数、`skipped` 跳过数。
- 若 `mode=export-only`（自动化环境未找到资料库脚本），用资料库能力把 `data/top3_for_library.json` 的 records（已含全部 17 字段）写入该表，按「日期+榜单+排名」去重。
- `--force-update` 仅用于回填历史记录，日常自动化不要用。

### 6. 呈现
用文件展示工具把当天 4 份报告（普通人版 `.html`/`.md`、程序员版 `.html`/`.md`）呈现给用户：
普通人榜用 3-5 句话概括最值得看的 1-2 个项目，程序员榜用 1-2 句话概括热门项目；
并说明两榜前三名已同步到资料库表格，报一下新增/跳过条数。

## 去重说明
历史去重由脚本自动完成：同一项目 30 天内不会重复推荐，且所有见过的项目都会记入 `data/history.json`。不要手动修改历史文件。

## 配置修改
用户如要求调整监测关键词/排除词/时间，编辑 `config.json`。若用户要改推送时间，需同时用自动化工具更新定时任务的 rrule。

# 贡献指南

感谢参与！本项目是**纯 Python 标准库**项目，不需要安装任何第三方依赖。

## 环境要求

- Python 3.10+
- Windows / macOS / Linux

## 本地开发

1. Fork 并 clone 本仓库。
2. 新建分支：`git checkout -b feat/your-change`
3. 修改代码或文档。
4. 本地验证：

```bash
python -m py_compile monitor.py lib/*.py tests/*.py
python -m unittest discover -s tests -v
```

5. 提交 PR，说明动机、改动内容和验证结果。

## 代码约定

- **不引入第三方运行时依赖**，保持零安装。
- 新增配置项时，在 `config.json` 里用 `_` 开头的说明键补充注释。
- 面向普通人的文案避免技术术语；新增筛选项要说明对普通人的影响。
- 不提交 `data/`、`reports/`、`.workbuddy/`、`.env`、任何 token。
- 报告生成相关改动，请附上一份新生成的 HTML/MD 示例说明效果。

## 提交信息

中文或英文均可，建议使用 `feat:` / `fix:` / `docs:` / `test:` / `chore:` 前缀。
一个 PR 尽量只做一件事。

## 报告问题

- **Bug**：请提供系统、Python 版本、运行方式、复现步骤，以及 `data/run.log` 最后 20 行（先删除 token）。
- **内容误选**：附上项目链接，并说明为什么它不适合普通人。
- **安全问题**：请不要公开提交，按 [SECURITY.md](SECURITY.md) 私下报告。
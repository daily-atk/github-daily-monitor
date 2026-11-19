# 安全策略

## 支持版本

当前 `main` 分支。

## 报告安全问题

请不要在公开 Issue 中粘贴 token、`data/run.log` 中的敏感信息，或未修复的漏洞细节。

请通过 GitHub 仓库的 **Security → Report a vulnerability** 私下报告。我们会尽快回复，并在修复后致谢（如你愿意）。

## Token 处理

- 程序只从环境变量 `GITHUB_TOKEN` 读取 token，不写入代码或配置文件。
- 不要提交 `.env`、`*.token` 或任何包含凭证的文件。
- 怀疑 token 泄露时，立即到 GitHub **Settings → Developer settings → Tokens** 删除并重新生成。

## 内容安全

- 本项目只聚合 GitHub 公开信息，**不会自动安装或执行**任何被推荐的项目。
- 报告中的项目未经安全审计；使用前请自行查看项目主页、许可证与 Issue。
- 如发现报告推荐了恶意/垃圾项目，请附链接提交 Issue，我们会补充排除词。
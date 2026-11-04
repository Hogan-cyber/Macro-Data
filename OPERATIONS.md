# 独立运行与维护

本项目运行不依赖 AI、聊天记录、个人电脑、付费数据 key 或人工每周上传。GitHub 托管的 Ubuntu runner 按仓库中的 workflow 执行代码；GitHub 提供短期 `GITHUB_TOKEN` 用于提交数据与部署 Pages。读者及 Python SDK 不需要该 token。

## 每周的自动流程

1. 周一 00:00 UTC（香港 08:00）触发 `.github/workflows/weekly.yml`。
2. 安装 Python/R/Node.js 环境并运行程序测试。
3. Python 从 FRED 公开 CSV/元数据页面和 World Bank 官方 API 获取数据，核对序列身份、单位、频率、季调、日期、数值和历史完整性。
4. 保存原始响应、抓取时间及检测到的修订；每个指标保留原频率，缺失留空，真实零值保留。
5. 生成美国 Excel、全球 Excel/SQLite/SQL/CSV/Parquet/JSONL/ZIP，以及含 SHA-256 的 manifest。
6. 校验各格式、SQL 导入和 SDK 读取；运行美国 Python/R 训练前处理对照。
7. 构建静态 dashboard 与 Python wheel，提交数据，发布到同一个 GitHub Pages 地址。

全流程可在 [Actions](https://github.com/Hogan-cyber/Macro-Data/actions/workflows/weekly.yml) 查看每一步日志，也可点 **Run workflow** 手动运行。电脑关机不影响计划任务。触发可能排队，08:00 不是精确完成承诺。

## 来源故障与修复

- 某个来源超时、内容不合规、单位变化或已存日期丢失：采集器返回部分失败（退出码 2），该指标保留上次有效数据及原抓取时间；无旧数据时标记 `FAILED_EMPTY`。
- 部分失败仍生成带 `PARTIAL` 状态的 manifest 和可下载文件，dashboard 标记故障；部署后 Actions 明确报失败，避免把失败隐藏成一次完整成功。美国明细见 `data/refresh_status.json`，国际明细见 `data/international_snapshot.json`，合并结果见 `data/global/manifest.json`。
- 致命校验/构建/部署失败不会宣称已发布新版本；网站保留上次部署，检查页面更新时间及 Actions。修复代码或来源后重新运行 workflow。
- 免费公开网站可能变更接口、条款或停止发布；程序可以独立执行，但不能保证永远不需要维护。GitHub 的仓库、Actions 和 Pages 必须保持启用。

## 在其他机器复建

安装 Python 3.10+、Node.js 24 和 base R 后，克隆仓库并按 README 的本地运行命令操作。`python updater/bootstrap.py` 可恢复美国初始工作簿；后续从已保存数据继续比较修订。仓库包含采集/清洗/导出/测试/前端/包的全部源码，普通 CI、服务器或 cron 也可调用相同命令。

只使用数据时，无须运行采集器、R 或 Node.js：安装 Python wheel，或直接下载 Excel/SQLite/Parquet。离线使用解压后的完整 ZIP 并执行 `MacroData(data_dir="解压目录")`。

## 研究复现

记录数据版本、文件 SHA-256、Git 提交和处理代码。固定 SDK 的 Git `ref`，或使用已下载的离线副本。采集时间仅说明本系统何时取得该版本；未核实的历史发布日期保持 NULL，不把最新修订历史称为 point-in-time 数据。

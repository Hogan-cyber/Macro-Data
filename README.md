# 全球宏观与市场数据 · Global Macro Monitor

## [打开 Dashboard →](https://hogan-cyber.github.io/Macro-Data/)

[下载全球 Excel](https://hogan-cyber.github.io/Macro-Data/data/global/global_macro.xlsx) · [SQLite](https://hogan-cyber.github.io/Macro-Data/data/global/dataset.sqlite) · [完整 ZIP](https://hogan-cyber.github.io/Macro-Data/data/global/bundle.zip) · [Python package 指南](PACKAGE_GUIDE.md) · [查看自动更新](https://github.com/Hogan-cyber/Macro-Data/actions/workflows/weekly.yml)

88 项指标序列、11 个经济体：原有 49 项美国数据，加上 39 项国际数据。每项保留原始频率和单位。每周一香港时间 **08:00**（UTC 周一 00:00）由 GitHub Actions 抓取、校验、导出数据、保存修订历史并发布网站。

**运行完全独立于 AI、ChatGPT/Codex 和个人电脑。** 定时采集、清洗、校验、格式导出和 dashboard 发布均为确定性的 Python、R、Node.js 与 GitHub Actions 程序，不需要 LLM、AI key、聊天会话或手动上传。上游公开来源变化仍可能需要维护；实际故障会标记并保留已有有效数据，见 [独立运行说明](OPERATIONS.md)。

GitHub 定时任务可能排队延迟；08:00 是计划触发时间，不是完成时间承诺。失败状态见 Actions；部分来源失败时保留上一有效值，并在页面和日志标记。公开仓库长期没有活动时可能暂停计划任务，本流程正常刷新会提交更新记录。参见 [GitHub 官方 schedule 说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

## 全球数据下载与 Python package

| 格式 | 下载 | 用途 |
| --- | --- | --- |
| Excel | [global_macro.xlsx](https://hogan-cyber.github.io/Macro-Data/data/global/global_macro.xlsx) | 每个指标一页，附目录、字典和说明 |
| SQLite | [dataset.sqlite](https://hogan-cyber.github.io/Macro-Data/data/global/dataset.sqlite) | 无数据库服务器即可 SQL 查询 |
| SQL dump | [dataset.sql.gz](https://hogan-cyber.github.io/Macro-Data/data/global/dataset.sql.gz) | 解压后导入 SQLite；不是通用 PostgreSQL/MySQL 语法 |
| Parquet | [observations.parquet](https://hogan-cyber.github.io/Macro-Data/data/global/observations.parquet) | pandas / DuckDB 研究输入 |
| CSV | [observations.csv.gz](https://hogan-cyber.github.io/Macro-Data/data/global/observations.csv.gz) | Python、R、Excel 等通用长表 |
| JSON Lines | [observations.jsonl.gz](https://hogan-cyber.github.io/Macro-Data/data/global/observations.jsonl.gz) | 逐条读取 / 数据管道 |
| 完整文件包 | [bundle.zip](https://hogan-cyber.github.io/Macro-Data/data/global/bundle.zip) | 包含离线 manifest；解压即可使用 SDK 离线模式 |
| 字典与版本 | [dictionary.csv](https://hogan-cyber.github.io/Macro-Data/data/global/dictionary.csv) · [manifest.json](https://hogan-cyber.github.io/Macro-Data/data/global/manifest.json) | 单位、频率、来源、更新状态、版本与 SHA-256 |

```sh
python -m pip install "git+https://github.com/Hogan-cyber/Macro-Data.git"
# 也可直接安装网站提供的 wheel，无须 Git：
python -m pip install https://hogan-cyber.github.io/Macro-Data/packages/hogan_macro_data-0.1.0-py3-none-any.whl
```

```python
from hogan_macro import MacroData

data = MacroData()
print(data.catalog(country=["US", "CN", "JP", "GB"]))
us = data.load(series=["PAYEMS_CHANGE", "NASDAQSOX", "NASDAQCOM", "DGS10", "EMRATIO"], start="2020-01-01")
global_data = data.load(country=["CN", "JP", "GB"], start="2000-01-01")
counts = data.sql("SELECT country, COUNT(*) AS n FROM observations GROUP BY country")
data.download("excel", "downloads/global_macro.xlsx")
```

未发布到 PyPI。包名是 `hogan-macro-data`，导入名是 `hogan_macro`；[完整调用、离线与复现指南](PACKAGE_GUIDE.md)。用 `ref` 固定真实 Git 提交可冻结研究输入；各格式按 manifest 校验，不会把网络失败静默伪装成最新数据。

| 国际覆盖 | 股价指数 | GDP 增长、CPI 通胀、失业率 |
| --- | --- | --- |
| 日本、英国、德国、法国、加拿大、澳大利亚、韩国、印度、中国 | OECD 月度标准化股价指数 | World Bank 年度数据，各国 3 项 |
| 香港 | 暂未加入 | World Bank 年度数据，3 项 |

第一版国际历史从 2000 年开始，实际截止期见目录。月度股价指数不等于日频 FTSE/DAX/日经等具名基准收盘价；年度 CPI 通胀不是月度 CPI 指数，失业率为 ILO modeled estimate。日经 225 的来源要求再分发许可，未纳入公开文件。各国覆盖不完全相同。

R 读取全球长表（原有美国 R 训练前处理仍在下文）：

```r
url <- "https://hogan-cyber.github.io/Macro-Data/data/global/observations.csv.gz"
local_file <- tempfile(fileext = ".csv.gz")
download.file(url, local_file, mode = "wb", quiet = TRUE)
con <- gzfile(local_file, "rt")
global_data <- read.csv(con, na.strings = "", stringsAsFactors = FALSE)
close(con)
cn <- subset(global_data, country == "CN")
```

## 美国数据包含什么

- 通胀：CPI、核心 CPI、PCE、核心 PCE、PPI；同比率按相同日历月份计算。
- 就业：非农总人数、非农月度新增、失业率、就业人口比率、劳动参与率、初请/续请失业金、平均时薪、职位空缺。
- 市场：费城半导体 SOX、纳斯达克综合、纳斯达克 100、标普 500、VIX、美元、人民币汇率、原油。
- 利率与信用：3 月/2 年/5 年/10 年/30 年美债收益率、实际收益率、期限利差、联邦基金利率、投资级/高收益信用利差。
- 增长与房地产：实际/名义 GDP、实际 GDP 增速、工业生产、零售、新屋开工、建筑许可、M2、美联储资产。

默认起点 2000 年，各序列使用真实可得历史。SOX 自 2004 年起；SP500 和部分 ICE 指标有公开下载窗口限制，之后每次更新保留已采集历史。Excel 每页一种指标，数据区固定 A:C。缺失为空，真实零值保留，不插值、不删除真实极端值。

## 用 Python 调取并准备训练数据

Python 3.10+，在项目根目录执行：

```sh
python -m pip install -r ml/requirements.txt
python ml/prepare_python.py --base https://hogan-cyber.github.io/Macro-Data/data
```

读取任何一个变量，也可以从本地 `data/` 读取：

```python
from ml.prepare_python import load_native
observations, dictionary = load_native('https://hogan-cyber.github.io/Macro-Data/data')
nonfarm = observations.query("series_id == 'PAYEMS_CHANGE'")
cpi = observations.query("series_id == 'CPI_YOY'")
employment = observations.query("series_id == 'EMRATIO'")
sox = observations.query("series_id == 'NASDAQSOX'")
print(dictionary.loc['DGS10', ['unit', 'frequency', 'seasonal_adjustment']])
```

训练前处理默认用市场变量，目标只是可替换的例子：未来 4 周纳斯达克综合价格收益率（百分数）。选择其他指数或预测期限：

```sh
python ml/prepare_python.py --target NASDAQSOX --horizon 4
```

输出到 `ml/output/python/`：原始周频输入、处理前特征、`train.csv`、`validation.csv`、`test.csv` 和保存的预处理参数。时间顺序按约 70%/15%/15% 划分；删除跨越下一分区起点的标签；中位数填补和标准化仅在训练集拟合。保留缺失指示变量；周收益率不穿越缺失周；当前未结束的周不进入输入。默认包含 1/4/12 周滞后。目标、标签结束日期和日期索引不应作为 X 输入。

需要将宏观变量加入探索性研究时：

```sh
python ml/prepare_python.py --include-revised-macro
```

此模式假设月度数据在月末后 45 天、季度数据在季末后 100 天、周度数据在观察日后 7 天可用，并限制携带期限。这些仅是明确的研究假设，**不是经核实的历史发布日期，也不能消除修订偏差**。

## 用 R 调取并准备训练数据

只需 base R，无须安装额外包。在项目根目录执行：

```sh
Rscript ml/prepare_R.R https://hogan-cyber.github.io/Macro-Data/data
```

交互使用：

```r
source('ml/prepare_R.R')
dat <- load_macro('https://hogan-cyber.github.io/Macro-Data/data')
nonfarm <- subset(dat$observations, series_id == 'PAYEMS_CHANGE')
cpi <- subset(dat$observations, series_id == 'CPI_YOY')
employment <- subset(dat$observations, series_id == 'EMRATIO')
weekly <- make_weekly(dat$observations)
prepare_training(weekly, target='NASDAQSOX', horizon=4L)
```

输出到 `ml/output/R/`。默认市场输入、日期划分、缺失处理和标准化与 Python 相同，云端运行时自动核对两种语言的输出。两者都能读取全部 49 项原频数据。R 不默认混合月度宏观值；可先从原频数据研究，或读取 Python 显式宏观研究模式生成的 `weekly_inputs.csv` 后调用 `prepare_training()`。

## ML 数据使用边界

`date` / `observation_date` 是观察期间标签，不是发布日期。当前历史是 **latest revised**，不是完整的 point-in-time / vintage 数据；历史回测要另接 ALFRED 或官方逐期发布时间及版本。自项目开始采集后的原始响应、每次快照和修订保留在 Git 历史中，能追溯“本系统何时看到了变化”，不能反推采集前的首次发布值。市场价格示例同样不宣称免除数据修正、费用、交易时点等回测问题。

代码已经完成数据读取、特征、时序切分和训练参数准备，没有替你训练或挑选最优模型。

## 文件与本地运行

| 文件 | 用途 |
| --- | --- |
| `data/us_macro.xlsx` | 持续更新的 Excel；49 个指标页及目录、字典、更新与修订记录 |
| `data/observations.csv` | 长表：`series_id,date,value,is_missing` |
| `data/dictionary.csv` | 指标定义、单位、频率、季调、原始链接、成功抓取时间、状态 |
| `data/latest_snapshot.json` | 可复建 Excel 的完整快照 |
| `data/raw/` | 每次公开来源的原始 CSV 和校验元数据 |
| `updater/update_us_macro.py` | 抓取、清洗、全历史修订检查、失败回退、写 Excel |
| `updater/export_data.py` | 校验并导出 CSV 与 dashboard 数据 |
| `ml/prepare_python.py`, `ml/prepare_R.R` | 两种语言的读取和训练前处理 |
| `src/content/dashboard/` | Dashboard 页面和图表代码 |
| `.github/workflows/weekly.yml` | 每周更新、验证、发布任务 |

```sh
python -m pip install -r updater/requirements.txt -r ml/requirements.txt
python -m pip install . build
python updater/bootstrap.py
python updater/update_us_macro.py
python updater/international.py
python updater/export_data.py
python updater/export_global.py
python tests/verify_global_files.py
npm ci
npm run build
```

Node.js 24 用于构建。修改内容后推送 `main` 会运行工作流；也可以在 Actions → Weekly global macro dataset and dashboard → Run workflow 手动刷新。初次发布需 [Settings → Pages](https://github.com/Hogan-cyber/Macro-Data/settings/pages) 的 Source 设置为 GitHub Actions。无需把 API key 或个人 token 写入代码。

数据由 [FRED](https://fred.stlouisfed.org/) 官方公开 CSV 和元数据页面，以及 [World Bank API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation) 获取，原始提供者包括 BLS、BEA、Federal Reserve、Treasury、Nasdaq、S&P、ICE、OECD 等。部分市场数据受原始提供者使用条款限制，本仓库不授予这些数据的再许可。各指标的来源链接见数据字典。

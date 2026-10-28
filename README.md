# 美国宏观与市场数据 · US Macro Monitor

## [打开 Dashboard →](https://hogan-cyber.github.io/Macro-Data/)

[下载最新 Excel](https://hogan-cyber.github.io/Macro-Data/data/us_macro.xlsx) · [下载 CSV](https://hogan-cyber.github.io/Macro-Data/data/observations.csv) · [查看自动更新](https://github.com/Hogan-cyber/Macro-Data/actions/workflows/weekly.yml)

49 个美国宏观及市场指标，每项保留原始频率和单位。。每周一香港时间 **08:00**（UTC 周一 00:00）由 GitHub Actions 抓取、校验、更新 Excel/CSV、保存修订历史并发布网站。

GitHub 定时任务可能排队延迟；08:00 是计划触发时间，不是完成时间承诺。失败状态见 Actions；部分来源失败时保留上一有效值，并在页面和日志标记。公开仓库长期没有活动时可能暂停计划任务，本流程正常刷新会提交更新记录。参见 [GitHub 官方 schedule 说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

## 数据包含什么

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
python updater/update_us_macro.py
python updater/export_data.py
npm ci
npm run build
```

Node.js 24 用于构建。修改内容后推送 `main` 会运行工作流；也可以在 Actions → Weekly US macro refresh and dashboard → Run workflow 手动刷新。初次发布需 [Settings → Pages](https://github.com/Hogan-cyber/Macro-Data/settings/pages) 的 Source 设置为 GitHub Actions。无需把 API key 或个人 token 写入代码。

数据由 [FRED](https://fred.stlouisfed.org/) 官方公开 CSV 和元数据页面获取，原始提供者包括 BLS、BEA、Federal Reserve、Treasury、Nasdaq、S&P、ICE 等。部分市场数据受原始提供者使用条款限制，本仓库不授予这些数据的再许可。各指标的来源链接见数据字典。

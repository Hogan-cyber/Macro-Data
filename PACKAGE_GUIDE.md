# Hogan Macro Data · Python 数据包

`hogan-macro-data` 是全球宏观及市场数据的 Python 调用包，导入名为 `hogan_macro`。支持按国家和变量读取、只读 SQL 查询，以及下载 Excel、SQLite、Parquet、压缩 CSV/JSONL/SQL 和 ZIP 数据包。数据保留原始观察频率、单位、缺失值与来源元数据。

## 安装

Python 3.10 或以上。此包通过 GitHub 源码或构建出的 wheel 分发，**未发布到 PyPI**。

```sh
python -m pip install "git+https://github.com/Hogan-cyber/Macro-Data.git"
```

在仓库目录中安装或构建 wheel：

```sh
python -m pip install .
python -m pip wheel --no-deps . --wheel-dir wheels
python -m pip install wheels/hogan_macro_data-0.1.0-py3-none-any.whl
```

基础依赖为 pandas 和 certifi；SQLite 使用 Python 标准库。下载 Parquet 不需要额外依赖；使用 pandas 读取 Parquet 时可安装可选依赖：

```sh
python -m pip install ".[parquet]"
```

## 三步读取

```python
from hogan_macro import MacroData

data = MacroData()
catalog = data.catalog(country=["CN", "JP", "US"])
print(catalog[["series_id", "country", "indicator_zh", "frequency", "unit"]])

# 用目录中真实存在的 ID 选变量；长表可以保留不同频率。
ids = catalog.groupby("country").head(1).series_id.tolist()
observations = data.load(series=ids, start="2000-01-01")
print(observations.tail())
```

默认从公共仓库 `Hogan-cyber/Macro-Data` 的 `main` 分支读取 `data/global/manifest.json`，然后下载经过 SHA-256 和字节数校验的 SQLite 数据库。无需 API key。每个实例固定使用建立时或最近一次成功 `refresh()` 时的 manifest；读取每个变量不会重新抓取上游经济数据。

国家采用两位代码，例如中国 `CN`、日本 `JP`、美国 `US`、英国 `GB`、德国 `DE`、法国 `FR`、加拿大 `CA`、澳大利亚 `AU`、韩国 `KR`、印度 `IN`、香港 `HK`。**以当前 `catalog()` 的实际覆盖为准**；不同国家不保证拥有相同变量或历史长度。

## 目录、筛选与宽表

```python
print(data.catalog(country="JP"))
print(data.catalog(search="GDP"))  # 字面子串匹配，不解释为正则表达式
print(data.catalog().asset_class.unique())

# 若已知所需美国 ID，可直接读取。
us = data.load(series=["NASDAQCOM", "DGS10"], start="2020-01-01", end="2025-12-31")

# 宽表以 date 为索引、series_id 为列；先选同一频率。
monthly = data.catalog().query("frequency == 'Monthly'")
if not monthly.empty:
    wide = data.load(series=monthly.series_id.tolist(), wide=True)
```

`catalog(country=None, asset_class=None, search=None)` 返回元数据 DataFrame；国家代码与资产类别筛选不区分大小写。资产类别应从目录中发现，未知类别或搜索词会得到空表。`load(series=None, country=None, start=None, end=None, wide=False)` 返回原频率观察值；日期边界包含首尾，使用 `YYYY-MM-DD` 或 Python 日期对象。变量 ID 区分大小写。未知国家、未知变量、空的国家/变量选择列表会报错，避免拼写错误扩大或隐藏读取范围。

长表字段为：`series_id, country, date, value, is_missing, frequency, unit, seasonal_adjustment, retrieved_at_utc, release_date, update_status`。`date` 与 `release_date` 为 pandas 日期类型，抓取时间为 UTC 时间类型，`value` 为可缺失的 `Float64`，`is_missing` 为可缺失的 `Int64`。真实零值保留；无法取得的值保持缺失。没有逐次真实发布日期时，`release_date` 为空。

`wide=True` 默认拒绝混合频率。如果确实需要按观察日期外连接不同频率，可明确使用 `allow_mixed_frequencies=True`。它只改变排列方式，不重采样、不插值、不向前填充，也不假定数据在观察日期已经发布。同频率也不代表相同单位、同一季调口径或可以直接比较。

## SQL 查询与文件下载

```python
result = data.sql("""
    SELECT s.country, s.series_id, s.indicator_zh, s.frequency, s.unit,
           o.date, o.value, o.release_date
    FROM observations o JOIN series s USING (series_id)
    WHERE s.country = ? AND o.date >= ?
    ORDER BY o.date, s.series_id
""", ("JP", "2020-01-01"))

data.download("excel", destination="downloads/global_macro.xlsx")
data.download("sqlite", destination="downloads/dataset.sqlite")
data.download("parquet", destination="downloads/observations.parquet")
data.download("csv", destination="downloads/observations.csv.gz")
data.download("jsonl", destination="downloads/observations.jsonl.gz")
data.download("sql", destination="downloads/dataset.sql.gz")
data.download("bundle", destination="downloads/bundle.zip")
```

SQLite 包含 `series` 元数据表和 `observations` 观察值表；观察值主键为 `(series_id, date)`。通过 SQL 可以连接两表并执行聚合。SDK 仅接受单条只读 `SELECT` / `WITH` 查询，支持参数绑定；`PRAGMA`、建表、写入、附件数据库和加载扩展均被禁止。SQL 返回 SQLite 原始类型，日期为字符串；需要统一 pandas 类型时使用 `load()`。下载的独立 SQLite 文件可由其他软件自行查询或复制后加工。

`download()` 的 `destination` 是目标**文件**路径；返回绝对路径。完整下载通过字节数及 SHA-256 校验后，才会原子替换已有目标文件。CSV、JSONL、SQL 保持 gzip 压缩，不因目标文件名而自动解压。SQL 导出采用 SQLite 方言，迁移到其他数据库前需检查类型与语法。

```python
import pandas as pd
csv_data = pd.read_csv("downloads/observations.csv.gz")
parquet_data = pd.read_parquet("downloads/observations.parquet")  # 安装 pyarrow
```

## 离线、缓存与可复现研究

下载完整 `bundle.zip` 并解压到一个目录后，可直接把该目录传给 `data_dir`；压缩包内包含与内容匹配的 manifest。运行包不调用 AI，也不需要 API key。数据采集本身由仓库 GitHub Actions 独立执行。

```python
# 离线目录应有 manifest.json 和 dataset.sqlite；下载其他格式时还需要对应文件。
offline = MacroData(data_dir="data/global")
print(offline.load(country="CN").tail())

# 自定义缓存，不改变源数据。
data = MacroData(cache_dir=".macro-cache")
print(data.manifest["dataset_version"])
data.refresh()  # 显式更新 manifest，下一次读取使用新版本对应的数据库
```

默认缓存目录为 `~/.cache/hogan_macro`。远程数据库按 SHA-256 内容哈希存储，每次查询前验证文件；刷新后的数据库哈希相同时可复用已验证文件。缓存损坏会抛出 `IntegrityError`；删除报错的缓存文件或改用新的 `cache_dir` 后重新读取。旧哈希文件不会自动删除，便于由使用者管理缓存。

网络连接最多尝试三次，每次连接设置 30 秒超时，证书通过 certifi 验证。网络失败、校验失败或无效 manifest 会报错，**不会默默切换到旧版本**。失败的 `refresh()` 会清空活动快照；成功刷新前不能继续读取。主动离线运行需显式提供 `data_dir`。

需要冻结研究输入时，应同时记录：SDK 版本、数据 manifest、数据库 SHA-256、完整 Git commit SHA 和处理代码。`ref="main"` 会随仓库更新；可将 `ref` 改为实际的完整 commit SHA，从该提交获取数据。`ref` 支持不含斜杠的简单分支、标签或 commit SHA。SDK 版本与数据版本是两回事：安装旧 SDK 并不会自动冻结默认 `main` 数据。

```python
import json
from pathlib import Path
from hogan_macro import __version__

print("SDK:", __version__)
Path("research_manifest.json").write_text(
    json.dumps(data.manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
# 把下面变量设为仓库中已经存在、含 data/global 数据的完整提交 SHA。
# frozen = MacroData(ref=YOUR_VERIFIED_COMMIT_SHA)
```

## 用于量化训练前必须明确的口径

这是一套 **latest revised（最新修订）历史数据**，不是完整的 point-in-time / vintage 数据库。观察日期通常是所属月份、季度或年份的标签，不能替代真实公布时间；抓取时间也不等于首次公布时间。固定 Git 提交可以复现该次抓取结果，但不能还原该次抓取之前每个历史时点可见的初值。

训练和回测前应完成以下步骤：

1. 先用目录确认来源、单位、频率、季调、覆盖范围和 `update_status`；识别失效来源或保留上次有效值的序列。
2. 为严格历史回测接入真实发布日及历史版本，按信息可获得时间连接。任意固定滞后只是一种研究假设，不能消除修订偏差。
3. 显式决定频率与时间窗口。World Bank 年度增长、通胀或失业率不是月度宏观数据；OECD 月度股价指数也不是日度交易基准。指数点位通常不含分红再投资，也不代表可交易、已复权的总收益序列，须核对定义。
4. 先按时间划分训练、验证、测试集，再仅在训练集拟合填补、标准化等参数。跨越下一分区的未来收益标签应剔除；保留缺失标记，收益率不能跨未观测期间伪装成单期收益。
5. 保存输入 manifest、筛选与转换代码。按同一频率拼成宽表只完成排列，不会自动解决前视偏差、修订偏差或单位差异。

SDK 不训练模型、选择最优策略或自动加入宏观滞后。完整调用例子在 `examples/use_package.py`：

```sh
python examples/use_package.py --data-dir data/global --output macro_downloads
# 使用远程当前版本：
python examples/use_package.py --output macro_downloads
```

数据许可沿用各原始提供者的条款；安装此 SDK 不授予底层市场数据的额外再分发权。

## 开发验证

```sh
python -m unittest discover -s tests -p test_package.py -v
```

测试使用独立合成 SQLite 与 manifest，覆盖缺失和零值、筛选、混合频率、只读 SQL、路径校验、刷新、校验和损坏及下载原子性。远程路径使用模拟传输，不依赖线上数据。

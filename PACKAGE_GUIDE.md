# Hogan Macro Data Python Package

`hogan-macro-data` provides global macroeconomic and market data through the `hogan_macro` import. It supports country and series selection, read-only SQL and downloads of Excel, SQLite, Parquet, gzip-compressed CSV/JSONL/SQL and ZIP bundles. Native frequencies, units, missing values and provenance are retained.

## Installation

Requires Python 3.10+. Version 0.2.0 is distributed through GitHub source and built wheels; it is **not published on PyPI**.

```sh
python -m pip install "git+https://github.com/Hogan-cyber/Macro-Data.git"
python -m pip install https://hogan-cyber.github.io/Macro-Data/packages/hogan_macro_data-0.2.0-py3-none-any.whl
```

Alternatively, install or build from the repository:

```sh
python -m pip install .
python -m pip wheel --no-deps . --wheel-dir wheels
python -m pip install wheels/hogan_macro_data-0.2.0-py3-none-any.whl
```

Base dependencies are pandas and certifi; SQLite uses Python's standard library. Downloading Parquet needs no extra dependency. To read it with pandas, install the optional Parquet dependencies from the repository:

```sh
python -m pip install ".[parquet]"
```

## First query

```python
from hogan_macro import MacroData

data = MacroData()
catalog = data.catalog(country=["CN", "JP", "US"])
print(catalog[["series_id", "country", "indicator_zh", "frequency", "unit"]])
ids = catalog.groupby("country").head(1).series_id.tolist()
observations = data.load(series=ids, start="2000-01-01")
print(observations.tail())
```

The default source is `data/global/manifest.json` on the public `Hogan-cyber/Macro-Data` repository's `main` branch. The SDK downloads SQLite and checks its byte count and SHA-256. No API key is required. Each instance uses its initial manifest or the most recent successful `refresh()` snapshot; querying a series does not recollect upstream data.

Country codes include `CN`, `JP`, `US`, `GB`, `DE`, `FR`, `CA`, `AU`, `KR`, `IN`, `HK`, `SG` and `TW`. **The actual catalog controls coverage**; variables and history lengths differ between economies. The expanded dataset targets 105 series across 13 economies; inspect the published manifest to confirm availability.

## Catalog, selection and wide tables

```python
print(data.catalog(country="JP"))
print(data.catalog(search="GDP"))  # Literal substring, not a regular expression
print(data.catalog().asset_class.unique())
print(data.catalog(frequency="daily"))
us = data.load(series=["NASDAQCOM", "DGS10"], start="2020-01-01", end="2025-12-31")
daily = data.load(series=["HSI", "NIKKEI225", "DAX", "DJIA"], frequency="daily", wide=True)
monthly = data.catalog().query("frequency == 'Monthly'")
if not monthly.empty:
    wide = data.load(series=monthly.series_id.tolist(), wide=True)
```

`catalog()` returns metadata and accepts `country`, `asset_class`, `search` and `frequency` filters. Country and asset-class matching is case-insensitive. Discover asset classes in the catalog; unknown classes or search text return an empty table. `load()` accepts `series`, `country`, `start`, `end`, `wide`, `frequency` and `allow_mixed_frequencies`. Date bounds are inclusive, using `YYYY-MM-DD` or Python date objects. Series IDs are case-sensitive. Unknown countries or series and empty country/series selection lists raise errors to prevent accidental changes in scope.

The `frequency="daily"` group includes native `Daily` and `Daily, Close`, but excludes `Daily, 7-Day` macro observations. The original frequency labels remain in the data. Daily index `value` is the closing level, with the date expressed in the market's local calendar. The collector excludes the current local date; missing sessions are not filled. This API provides close series, not OHLC bars. `DAX` is a gross total return index, whereas the other added named daily indices are price indices. Existing `SP500`, `NASDAQCOM`, `NASDAQ100` and `NASDAQSOX` are retained.

Long-table fields are `series_id, country, date, value, is_missing, frequency, unit, seasonal_adjustment, retrieved_at_utc, release_date, update_status`. `date` and `release_date` use pandas date types; retrieval timestamps use UTC; `value` is nullable `Float64`; `is_missing` is nullable `Int64`. Real zeros remain zero and unavailable values remain missing. Unverified release dates remain empty.

`wide=True` uses dates as the index and series IDs as columns. Mixed frequencies are rejected by default, with the daily group treated together. Use `allow_mixed_frequencies=True` only when intentionally aligning different frequencies by observation date. Wide output does not resample, interpolate, forward-fill or establish historical availability. Equal frequencies do not imply equal units or definitions; markets also have different holidays.

## SQL and downloads

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

SQLite has `series` metadata and `observations`, keyed by `(series_id, date)`. The SDK accepts one read-only `SELECT` / `WITH` statement and parameter binding. PRAGMA, writes, table creation, attached databases and extension loading are prohibited. SQL returns SQLite types, including dates as strings; use `load()` for standardized pandas types. Other software can query a downloaded database or process a copy.

`download()` requires the keyword-only `destination` argument: a target **file** path. It returns an absolute path and replaces an existing file atomically only after complete size/hash verification. CSV, JSONL and SQL remain gzip-compressed regardless of destination filename. SQL uses SQLite syntax; check types and syntax before migrating to another database.

```python
import pandas as pd
csv_data = pd.read_csv("downloads/observations.csv.gz")
parquet_data = pd.read_parquet("downloads/observations.parquet")  # Requires pyarrow
```

## Offline access, caching and reproducibility

Extract the complete ZIP and pass its directory as `data_dir`. The bundle includes a matching manifest. Neither SDK use nor scheduled collection needs AI or an AI key; GitHub Actions runs collection independently.

```python
# Needs manifest.json and dataset.sqlite; other downloads need their corresponding files.
offline = MacroData(data_dir="data/global")
print(offline.load(country="CN").tail())
data = MacroData(cache_dir=".macro-cache")
print(data.manifest["dataset_version"])
data.refresh()  # Refresh manifest; the next read uses the corresponding database
```

The default cache is `~/.cache/hogan_macro`. Remote databases are stored by SHA-256 and checked before queries. An unchanged verified hash can be reused after refresh. Corruption raises `IntegrityError`; remove the affected cache file or use a new cache directory to download again. Old hash files are not automatically deleted.

Network requests retry up to three times with a 30-second timeout per connection and certifi certificate verification. Network, integrity and manifest errors are surfaced: **there is no silent fallback to an older SDK snapshot**. A failed `refresh()` clears the active snapshot until a successful refresh. To use an offline copy, explicitly supply `data_dir`. This differs from the collectors' documented retention of last valid source data.

For reproducibility, record the SDK version, manifest, database SHA-256, full Git commit SHA and processing code. `ref="main"` changes over time. Set `ref` to a verified full commit SHA containing the global data to freeze that input. Simple branch/tag/commit references without slashes are supported. SDK version and dataset version are distinct: installing an old SDK does not freeze default `main` data.

```python
import json
from pathlib import Path
from hogan_macro import __version__
print("SDK:", __version__)
Path("research_manifest.json").write_text(
    json.dumps(data.manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
# Set this to a verified existing full commit SHA containing data/global:
# frozen = MacroData(ref=YOUR_VERIFIED_COMMIT_SHA)
```

## Research assumptions

History is **latest revised**, not a complete point-in-time/vintage database. Observation dates label periods and are not verified release timestamps. Retrieval time is not first publication time. Pinning a commit reproduces that collected snapshot, not every historical initial release.

1. Check sources, units, frequencies, seasonal adjustment, coverage and `update_status`, including retained data from failed sources.
2. For strict historical backtests, join real release dates and vintages by availability time. Fixed assumed lags do not remove revision bias.
3. Choose frequency and windows explicitly. World Bank annual indicators differ from monthly macro data; OECD monthly share-price indices differ from daily trading benchmarks. Check price versus total-return definitions and do not assume tradability or dividend reinvestment.
4. Split chronologically before fitting imputation/scaling. Purge future-return labels crossing partition boundaries. Preserve missing indicators and avoid treating returns across unobserved periods as single-period returns.
5. Save manifests and transformation code. A wide table alone does not resolve look-ahead bias, revisions or incompatible units.

The SDK does not train models, choose strategies or add macro release lags. Examples:

```sh
python examples/use_package.py --data-dir data/global --output macro_downloads
# Current remote dataset:
python examples/use_package.py --output macro_downloads
```

Original provider and index-owner terms apply to all data. Public endpoints and SDK installation do not grant additional redistribution rights; the repository does not sublicense underlying data.

## Development validation

```sh
python -m unittest discover -s tests -p test_package.py -v
```

Package tests use synthetic SQLite and manifests to exercise missing/zero values, selection, frequency handling, read-only SQL, paths, refresh, integrity failures and atomic downloads. Remote transport is mocked; these tests do not prove current upstream availability or publication.

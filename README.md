# Global Macro Monitor

## [Open the dashboard](https://hogan-cyber.github.io/Macro-Data/)

[Global Excel](https://hogan-cyber.github.io/Macro-Data/data/global/global_macro.xlsx) · [SQLite](https://hogan-cyber.github.io/Macro-Data/data/global/dataset.sqlite) · [Complete ZIP](https://hogan-cyber.github.io/Macro-Data/data/global/bundle.zip) · [Python package guide](PACKAGE_GUIDE.md) · [Scheduled updates](https://github.com/Hogan-cyber/Macro-Data/actions/workflows/weekly.yml)

The expanded dataset covers **105 series across 13 economies**: the existing 49 US series and 39 OECD/World Bank series, plus 17 named daily equity indices in the same dataset. Check the published catalog and manifest for actual available coverage and source status. Native frequencies and units are retained. GitHub Actions is scheduled to collect, validate, export, record revisions and publish every Monday at **00:00 UTC / 08:00 Hong Kong time**.

**Operation is independent of AI, ChatGPT/Codex and personal computers.** Collection, cleaning, validation, exports and publication use deterministic Python, R, Node.js and GitHub Actions programs. No AI key, chat session or manual weekly upload is required. Public sources can change and require maintenance. Failed sources retain their last valid data with visible status; see [Operations](OPERATIONS.md).

GitHub may delay scheduled jobs: 08:00 is a trigger time, not a completion guarantee. See Actions for failures and publication status. Schedules in inactive public repositories can be disabled; normal refreshes commit update records. See [GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Downloads and Python access

### Market pages

The dashboard has dedicated **United States**, **Mainland China**, **Europe** and **Hong Kong** pages, plus the **Global Dataset** explorer for all 13 economies.

| Page | Equity coverage | Macro coverage |
| --- | --- | --- |
| United States | S&P 500, Nasdaq Composite, Nasdaq 100 and Philadelphia Semiconductor | Overview and existing US inflation/jobs, rates/markets, growth/housing and data/update detail pages |
| Mainland China | CSI 300, CSI 500, CSI 1000, Shanghai Composite and Shenzhen Component daily closes | World Bank annual GDP growth, CPI inflation and ILO modeled unemployment; separate OECD monthly share-price history |
| Europe | Germany's DAX, France's CAC 40 and the UK's FTSE 100 daily closes | Select Germany, France or the UK for annual national macro indicators; separate OECD monthly share-price histories |
| Hong Kong | Hang Seng Index daily closes | World Bank annual GDP growth, CPI inflation and ILO modeled unemployment |

Europe is a view of three national markets, **not a euro-area aggregate**. DAX is gross total return; CAC 40 and FTSE 100 are price indices. International annual macro indicators are not equivalent to monthly national releases. Headline cards identify the observation period and native frequency; source coverage separately shows provider update and retrieval timestamps. An updated source check does not imply that a new reference month or year has been released.

The reference-period filter applies to cards, charts and selected CSV downloads on every market page. Regional CSV downloads include all series in that region within the selected period; Excel and SQLite links contain the complete global dataset. Full-history source-coverage tables remain independent of the reference-period filter. Dataset IDs, Python API and the weekly cloud schedule are unchanged.

| Format | Download | Use |
| --- | --- | --- |
| Excel | [global_macro.xlsx](https://hogan-cyber.github.io/Macro-Data/data/global/global_macro.xlsx) | One sheet per series, catalog, dictionary and notes |
| SQLite | [dataset.sqlite](https://hogan-cyber.github.io/Macro-Data/data/global/dataset.sqlite) | Local SQL without a database server |
| SQL dump | [dataset.sql.gz](https://hogan-cyber.github.io/Macro-Data/data/global/dataset.sql.gz) | Gzip-compressed SQLite SQL, not generic PostgreSQL/MySQL syntax |
| Parquet | [observations.parquet](https://hogan-cyber.github.io/Macro-Data/data/global/observations.parquet) | pandas or DuckDB research |
| CSV | [observations.csv.gz](https://hogan-cyber.github.io/Macro-Data/data/global/observations.csv.gz) | Compressed long table for Python, R or Excel |
| JSON Lines | [observations.jsonl.gz](https://hogan-cyber.github.io/Macro-Data/data/global/observations.jsonl.gz) | Record-oriented pipelines |
| Complete bundle | [bundle.zip](https://hogan-cyber.github.io/Macro-Data/data/global/bundle.zip) | Includes an offline manifest; extract for SDK offline access |
| Metadata | [dictionary.csv](https://hogan-cyber.github.io/Macro-Data/data/global/dictionary.csv) · [manifest.json](https://hogan-cyber.github.io/Macro-Data/data/global/manifest.json) | Definitions, sources, status, versions and SHA-256 hashes |

```sh
python -m pip install "git+https://github.com/Hogan-cyber/Macro-Data.git"
# Install the published wheel without Git:
python -m pip install https://hogan-cyber.github.io/Macro-Data/packages/hogan_macro_data-0.2.0-py3-none-any.whl
```

```python
from hogan_macro import MacroData

data = MacroData()
print(data.catalog(country=["US", "CN", "JP", "GB"]))
print(data.catalog(frequency="daily"))
us = data.load(series=["PAYEMS_CHANGE", "NASDAQSOX", "NASDAQCOM", "DGS10", "EMRATIO"], start="2020-01-01")
daily = data.load(series=["HSI", "NIKKEI225", "DAX", "DJIA"], frequency="daily", wide=True)
global_data = data.load(country=["CN", "JP", "GB"], start="2000-01-01")
counts = data.sql("SELECT country, COUNT(*) AS n FROM observations GROUP BY country")
data.download("excel", destination="downloads/global_macro.xlsx")
```

The package is not published on PyPI. Install name: `hogan-macro-data`; import name: `hogan_macro`. See the [full API, offline and reproducibility guide](PACKAGE_GUIDE.md). Pin a verified Git commit with `ref` to freeze research inputs. Downloads are checked against the manifest; network failures are not silently presented as fresh data.

## International and daily market coverage

The existing international layer remains unchanged: OECD monthly standardized share-price indices for Japan, UK, Germany, France, Canada, Australia, Korea, India and China; World Bank annual GDP growth, CPI inflation and unemployment for those economies plus Hong Kong. Its requested history starts in 2000; actual availability varies by series. Annual CPI inflation is not a monthly CPI index, and unemployment uses the ILO modeled estimate.

| Economy | Added daily index IDs |
| --- | --- |
| Hong Kong | `HSI` |
| Japan | `NIKKEI225` |
| Germany | `DAX` |
| UK | `FTSE100` |
| France | `CAC40` |
| Canada | `TSX` |
| Australia | `ASX200` |
| Korea | `KOSPI` |
| India | `NIFTY50` |
| Singapore | `STI` |
| Taiwan | `TAIEX` |
| China | `CSI300`, `CSI500`, `CSI1000`, `SSE_COMPOSITE`, `SZSE_COMPONENT` |
| US | `DJIA` |

These are daily **close values**, not OHLC bars. Non-China indices use Yahoo's public chart JSON; mainland China indices use Eastmoney's public kline interface. Dates are market-local session dates. The current market-local date is excluded to avoid incomplete sessions. There is no calendar filling or interpolation, and different markets have different holidays. The DAX series is a **gross total return index**; the other added series are price indices. Check definitions before comparing returns. Existing `SP500`, `NASDAQCOM`, `NASDAQ100` and `NASDAQSOX` series remain unchanged. The SDK's `frequency="daily"` groups `Daily` and `Daily, Close` while excluding `Daily, 7-Day` macro series.

Public access does not grant redistribution rights. Provider and index-owner terms continue to apply, including to Nikkei and other branded indices; this repository grants no sublicense. Source availability and historical coverage are not guaranteed.

R can read the global long table directly:

```r
url <- "https://hogan-cyber.github.io/Macro-Data/data/global/observations.csv.gz"
local_file <- tempfile(fileext = ".csv.gz")
download.file(url, local_file, mode = "wb", quiet = TRUE)
con <- gzfile(local_file, "rt")
global_data <- read.csv(con, na.strings = "", stringsAsFactors = FALSE)
close(con)
cn <- subset(global_data, country == "CN")
```

## Existing US coverage

- Inflation: CPI, core CPI, PCE, core PCE and PPI; year-over-year rates use matching calendar months.
- Employment: payroll levels and monthly changes, unemployment, employment/population ratio, participation, initial/continuing claims, hourly earnings and job openings.
- Markets: SOX, Nasdaq Composite, Nasdaq 100, S&P 500, VIX, US dollar, renminbi exchange rate and crude oil.
- Rates and credit: 3-month/2/5/10/30-year Treasury yields, real yields, term spreads, federal funds rate and investment-grade/high-yield spreads.
- Growth and housing: real/nominal GDP, real GDP growth, industrial production, retail sales, housing starts, permits, M2 and Federal Reserve assets.

The default requested start is 2000; actual available history is retained. SOX starts in 2004. SP500 and some ICE series have public download windows; subsequent updates retain collected history. US Excel sheets use columns A:C for each series. Missing values remain blank and real zeros are preserved. No interpolation or removal of genuine extremes is applied.

## Python and R training preparation

Python 3.10+, from the repository root:

```sh
python -m pip install -r ml/requirements.txt
python ml/prepare_python.py --base https://hogan-cyber.github.io/Macro-Data/data
python ml/prepare_python.py --target NASDAQSOX --horizon 4
```

```python
from ml.prepare_python import load_native
observations, dictionary = load_native("https://hogan-cyber.github.io/Macro-Data/data")
nonfarm = observations.query("series_id == 'PAYEMS_CHANGE'")
cpi = observations.query("series_id == 'CPI_YOY'")
employment = observations.query("series_id == 'EMRATIO'")
sox = observations.query("series_id == 'NASDAQSOX'")
print(dictionary.loc["DGS10", ["unit", "frequency", "seasonal_adjustment"]])
```

The loaders also accept local `data/`. Training preparation uses the existing US dataset. The default illustrative target is the next four weeks' Nasdaq Composite price return in percent. Outputs in `ml/output/python/` include weekly inputs, features before processing, train/validation/test CSVs and fitted preprocessing parameters. Chronological splits are approximately 70%/15%/15%. Labels crossing the next partition boundary are purged. Imputation and scaling fit only on training data. Missing indicators are preserved; returns do not bridge missing weeks; unfinished weeks are excluded. Default lags are 1/4/12 weeks. Do not include targets, label-end dates or date indices as X features.

```sh
python ml/prepare_python.py --include-revised-macro
```

This optional exploratory mode assumes monthly data become available 45 days after month-end, quarterly data 100 days after quarter-end and weekly data 7 days after observation, with limited carry-forward windows. These are research assumptions, **not verified historical release dates**, and do not remove revision bias.

Base R requires no additional packages:

```sh
Rscript ml/prepare_R.R https://hogan-cyber.github.io/Macro-Data/data
```

```r
source('ml/prepare_R.R')
dat <- load_macro('https://hogan-cyber.github.io/Macro-Data/data')
nonfarm <- subset(dat$observations, series_id == 'PAYEMS_CHANGE')
cpi <- subset(dat$observations, series_id == 'CPI_YOY')
employment <- subset(dat$observations, series_id == 'EMRATIO')
weekly <- make_weekly(dat$observations)
prepare_training(weekly, target='NASDAQSOX', horizon=4L)
```

R writes to `ml/output/R/` with the same default market inputs, chronological splits and preprocessing as Python. Cloud runs compare both implementations. Both native loaders can read the existing 49 US series. R does not mix monthly macro data by default; research the native data or pass Python's explicit macro-mode `weekly_inputs.csv` to `prepare_training()`.

## Research limitations

`date` / `observation_date` labels the observation period, not the release date. History is **latest revised**, not a complete point-in-time/vintage database. Rigorous historical backtests require ALFRED or verified release schedules and vintages. Raw responses, snapshots and revisions collected since this project began are retained in Git history: they show when this system saw a change, not original releases before collection began. Market examples do not eliminate corrections, transaction costs or execution-timing issues. The preparation code does not train models or select an optimal strategy.

## Files and local execution

| Path | Purpose |
| --- | --- |
| `data/us_macro.xlsx` | Existing 49-series US workbook with catalog, dictionary and refresh/revision records |
| `data/observations.csv` | US long table: `series_id,date,value,is_missing` |
| `data/dictionary.csv` | US definitions, units, frequency, adjustment, sources and retrieval status |
| `data/latest_snapshot.json` | Snapshot sufficient to rebuild the US workbook |
| `data/raw/` | Source responses and validation metadata |
| `updater/update_us_macro.py` | US collection, cleaning, revision checks, fallback and Excel output |
| `updater/international.py` | Existing OECD/World Bank layer |
| `updater/daily_indices.py` | Named daily closing-index collection |
| `updater/export_data.py` | US validation and CSV/dashboard exports |
| `updater/export_global.py` | Combined global exports |
| `ml/prepare_python.py`, `ml/prepare_R.R` | US loaders and training preparation |
| `src/content/dashboard/` | Dashboard code |
| `.github/workflows/weekly.yml` | Scheduled refresh, validation and publication |

```sh
python -m pip install -r updater/requirements.txt -r ml/requirements.txt
python -m pip install . build
python updater/bootstrap.py
python updater/update_us_macro.py
python updater/international.py
python updater/daily_indices.py
python updater/export_data.py
python updater/export_global.py
python tests/verify_global_files.py
npm ci
npm run build
```

Node.js 24 builds the site. Pushing to `main` triggers the workflow; manual refresh is available in Actions → Weekly global macro dataset and dashboard → Run workflow. Initial publication requires [Settings → Pages](https://github.com/Hogan-cyber/Macro-Data/settings/pages) Source to be GitHub Actions. Do not put personal tokens in code.

Sources include [FRED](https://fred.stlouisfed.org/) public CSV and metadata, the [World Bank API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation), Yahoo Finance and Eastmoney. Original providers include BLS, BEA, Federal Reserve, Treasury, Nasdaq, S&P, ICE and OECD. Consult the series dictionary for specific source links and applicable terms.

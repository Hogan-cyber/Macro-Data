# Independent Operation and Maintenance

This project runs without AI, chat history, a personal computer, paid data keys or manual weekly uploads. A GitHub-hosted Ubuntu runner executes the repository workflow. GitHub supplies a short-lived `GITHUB_TOKEN` to commit data and deploy Pages; readers and SDK users do not need it.

## Weekly workflow

1. `.github/workflows/weekly.yml` is scheduled for Monday 00:00 UTC / 08:00 Hong Kong time.
2. Install Python, R and Node.js and run program tests.
3. Collect the existing US and international layers from FRED public CSV/metadata and the World Bank API. Collect added daily index closes from Yahoo public chart JSON and Eastmoney public kline. Validate identity, definitions, dates, values and history.
4. Preserve source responses, retrieval timestamps and detected revisions. Keep native frequencies, missing values and real zeros. Daily index dates use market-local calendars; exclude the current local date and do not fill missing sessions.
5. Run `python updater/daily_indices.py` before `python updater/export_global.py`, combining daily indices with the existing 49 US and 39 OECD/World Bank series. Generate US Excel and global Excel/SQLite/SQL/CSV/Parquet/JSONL/ZIP plus a SHA-256 manifest.
6. Validate formats, SQL import and SDK access; compare US Python and R training-preparation outputs.
7. Build the static dashboard and Python wheel, commit generated data and publish at the existing GitHub Pages address.

Inspect step logs in [Actions](https://github.com/Hogan-cyber/Macro-Data/actions/workflows/weekly.yml), or use **Run workflow** for a manual refresh. Turning off a personal computer does not interrupt the schedule. Jobs may queue: 08:00 is not a guaranteed completion time. Daily observation frequency does not mean daily collection; this workflow refreshes weekly.

The expanded coverage is 105 series across 13 economies, including Singapore and Taiwan. The actual published catalog and manifest determine available coverage. Existing US and OECD/World Bank series are retained. Added indices provide close levels only; DAX is gross total return and the other additions are price indices.

## Source failures and recovery

- On a timeout, invalid response, changed definition or missing stored history, collectors retain the affected series' last valid data and original retrieval timestamp. With no previous valid data, the series is marked `FAILED_EMPTY`. Partial collection failures use exit code 2.
- Partial refreshes still export data with `PARTIAL` status and visible source-failure information. The workflow reports failure after publication so partial source failures are not represented as full success. US details are in `data/refresh_status.json`, existing international details in `data/international_snapshot.json`, and combined status in `data/global/manifest.json`; consult collection logs for daily-source details.
- Fatal validation, build or deployment failures do not prove that a new version was published. Check Actions and the live page's update timestamp; the last successful deployment remains the reference. Fix the source/code and rerun the workflow.
- Public services may change interfaces, terms or availability. Independent execution does not guarantee maintenance-free operation. The repository, Actions and Pages must remain enabled.

The collectors' explicit retention of last valid observations differs from SDK network behavior: the SDK surfaces network/integrity failures and requires explicit offline configuration to use a local snapshot. Always distinguish successful data retrieval, successful file generation and successful deployment.

## Rebuild on another machine

Install Python 3.10+, Node.js 24 and base R, clone the repository and follow the README's local commands. `python updater/bootstrap.py` can restore the initial US workbook; later runs compare against saved observations for revisions. The repository contains collection, cleaning, export, tests, frontend and package source. Other CI services, servers or cron can run the same commands.

Data consumers do not need collectors, R or Node.js: install the Python wheel or download Excel/SQLite/Parquet. For offline SDK use, extract the full ZIP and run `MacroData(data_dir="extracted_directory")`.

## Reproducibility and terms

Record dataset version, file hashes, Git commit and processing code. Pin the SDK data `ref` to a verified commit or retain a downloaded offline bundle. Retrieval time records when this system obtained a version; unknown historical release dates remain NULL. Latest-revised history is not a point-in-time database.

Source and index-owner copyright and usage terms remain applicable. Yahoo/Eastmoney public access is not a grant of redistribution rights. The repository does not sublicense data or promise unrestricted use, perpetual source access or complete historical coverage.

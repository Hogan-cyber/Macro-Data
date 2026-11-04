Global macro and equity research dataset
Version: cf6af61b855b2aea5867
Generated: 2026-11-04T06:12:51Z
Latest-revised observations, not complete historical point-in-time data.
date identifies the observation period, NOT the publication date. release_date is NULL when unverified.
Raw frequencies and units are retained. No interpolation, winsorization, forward-fill or automatic frequency conversion.
OECD monthly share-price indices are normalized broad-market series, not daily FTSE/DAX/etc. index closes.
Source retrieval time records this system acquisition, not the historical first public release.
Daily index closes use market-local dates; current local sessions are excluded. No exchange-calendar forward-fill. DAX is gross total return; see return_type before comparing.
Country coverage and history differ. See dictionary and coverage.csv before joining features.
SQLite tables: observations, series, revisions, dataset_info.
SQL dump uses SQLite SQL syntax; gunzip before import.

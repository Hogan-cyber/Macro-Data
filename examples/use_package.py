"""Run after installing hogan-macro-data; use --data-dir data/global offline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hogan_macro import MacroData


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, help="Directory containing manifest.json and dataset.sqlite")
    parser.add_argument("--ref", default="main", help="GitHub branch/tag or pinned commit SHA")
    parser.add_argument("--output", type=Path, default=Path("macro_downloads"))
    args = parser.parse_args()
    data = MacroData(data_dir=args.data_dir, ref=args.ref)
    args.output.mkdir(parents=True, exist_ok=True)

    print("Dataset version:", data.manifest["dataset_version"])
    # Discover IDs first: indicator coverage, units and native frequency differ by country.
    catalog = data.catalog(country=["CN", "JP", "US"])
    print(catalog[["series_id", "country", "indicator_zh", "frequency", "unit"]].to_string(index=False))
    catalog.to_csv(args.output / "selected_catalog.csv", index=False)

    # One available variable per country; long format preserves different frequencies.
    ids = catalog.sort_values("series_id").groupby("country").head(1).series_id.tolist()
    observations = data.load(series=ids, start="2000-01-01")
    print(observations.tail())
    observations.to_csv(args.output / "selected_observations.csv", index=False)

    print(data.sql("""
        SELECT s.country, s.series_id, s.indicator_zh, s.frequency, s.unit,
               COUNT(o.value) AS valid_observations, MAX(o.date) AS last_period
        FROM series s LEFT JOIN observations o USING (series_id)
        WHERE s.country IN (?, ?, ?)
        GROUP BY s.series_id ORDER BY s.country, s.series_id
    """, ("CN", "JP", "US")).to_string(index=False))

    excel = data.download("excel", destination=args.output / "global_macro.xlsx")
    print("Verified Excel:", excel)
    # Keep the manifest with research outputs so the exact snapshot remains identifiable.
    (args.output / "manifest.json").write_text(
        json.dumps(data.manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("For training: establish real availability/vintages first, split chronologically,")
    print("purge overlapping target horizons, and fit preprocessing only on the training set.")
    print("These latest-revised observations and their period labels are not point-in-time data.")


if __name__ == "__main__":
    main()

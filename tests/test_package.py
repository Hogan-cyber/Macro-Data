"""Offline contract tests; neither public endpoints nor real data are required."""
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from hogan_macro import IntegrityError, MacroData, MacroDataError, ReadOnlyQueryError


def make_dataset(directory):
    """A real SQLite fixture, with a zero and explicit missing observation."""
    db = directory / "dataset.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE series (
                series_id TEXT PRIMARY KEY, country TEXT, country_name TEXT,
                indicator_zh TEXT, asset_class TEXT, category TEXT, frequency TEXT,
                unit TEXT, seasonal_adjustment TEXT, source_title TEXT, source_url TEXT,
                download_url TEXT, first_observation TEXT, last_observation TEXT,
                valid_rows INTEGER, missing_rows INTEGER, retrieved_at_utc TEXT,
                source_last_updated TEXT, update_status TEXT, definition TEXT, usage_note TEXT
            );
            CREATE TABLE observations (
                series_id TEXT, country TEXT, date TEXT, value REAL,
                is_missing INTEGER, frequency TEXT, unit TEXT, seasonal_adjustment TEXT,
                retrieved_at_utc TEXT, release_date TEXT, update_status TEXT,
                PRIMARY KEY (series_id, date)
            );
        """)
        for sid, country, freq in [("CN_CPI", "CN", "Monthly"), ("JP_CPI", "JP", "Monthly"), ("US_EQ", "US", "Daily")]:
            conn.execute("INSERT INTO series VALUES (" + ",".join(["?"] * 21) + ")", (
                sid, country, {"CN": "China", "JP": "Japan", "US": "United States"}[country],
                "Consumer prices" if "CPI" in sid else "Equity index", "Macro" if "CPI" in sid else "Equity",
                "Test", freq, "Index", "NSA", "Synthetic", "https://example.com", "https://example.com",
                "2024-01-01", "2024-02-01", 2, 1, "2024-03-01T00:00:00Z", None, "ok", "Synthetic", "Test only",
            ))
            for date, value in [("2024-01-01", 0.0), ("2024-02-01", None)]:
                conn.execute("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                    sid, country, date, value, int(value is None), freq, "Index", "NSA",
                    "2024-03-01T00:00:00Z", None, "ok",
                ))
    (directory / "observations.csv.gz").write_bytes(b"synthetic compressed export")
    (directory / "global_macro.xlsx").write_bytes(b"synthetic excel export")
    write_manifest(directory)


def write_manifest(directory, version="test-1"):
    files = {}
    for path in directory.iterdir():
        if path.name != "manifest.json" and path.is_file():
            content = path.read_bytes()
            files[path.name] = {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    (directory / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "dataset_version": version, "generated_at_utc": "2024-03-01T00:00:00Z",
        "countries": ["CN", "JP", "US"], "series_count": 3, "observation_count": 6,
        "valid_observation_count": 3, "files": files, "limitations": ["Synthetic data"],
    }), encoding="utf-8")


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name) / "data"
        self.directory.mkdir()
        make_dataset(self.directory)
        self.client = MacroData(data_dir=self.directory, cache_dir=Path(self.tmp.name) / "cache")

    def tearDown(self):
        self.tmp.cleanup()

    def test_catalog_filter_and_literal_search(self):
        self.assertEqual(self.client.catalog(country="cn").series_id.tolist(), ["CN_CPI"])
        self.assertEqual(len(self.client.catalog(asset_class="macro")), 2)
        self.assertEqual(len(self.client.catalog(search="consumer")), 2)
        self.assertEqual(len(self.client.catalog(search=".*")), 0)

    def test_frequency_filter_applies_to_sql_rows(self):
        self.assertEqual(self.client.catalog(frequency='daily').series_id.tolist(),['US_EQ'])
        self.assertEqual(set(self.client.load(frequency='daily').series_id),{'US_EQ'})
        self.assertEqual(self.client.load(frequency='daily',wide=True).columns.tolist(),['US_EQ'])
        self.assertTrue(self.client.load(country='CN',frequency='daily').empty)
        with self.assertRaises(ValueError):self.client.catalog(frequency='typo')

    def test_unknown_or_empty_selection_raises(self):
        for method, kwargs in [("catalog", {"country": "ZZ"}), ("load", {"country": ["CN", "ZZ"]}),
                               ("load", {"series": "TYPO"}), ("load", {"series": []}),
                               ("load", {"country": []})]:
            with self.subTest(method=method, kwargs=kwargs), self.assertRaises(ValueError):
                getattr(self.client, method)(**kwargs)

    def test_long_preserves_missing_zero_and_dates(self):
        rows = self.client.load(series="CN_CPI")
        self.assertEqual(rows.value.iloc[0], 0)
        self.assertTrue(pd.isna(rows.value.iloc[1]))
        self.assertEqual(rows.is_missing.tolist(), [0, 1])
        self.assertEqual(str(rows.value.dtype), "Float64")
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(rows.date))
        self.assertTrue(rows.release_date.isna().all())
        self.assertEqual(rows.update_status.tolist(), ["ok", "ok"])

    def test_dates_filter_inclusive_and_validate_order(self):
        rows = self.client.load(country="CN", start="2024-02-01", end="2024-02-01")
        self.assertEqual(len(rows), 1)
        with self.assertRaises(ValueError):
            self.client.load(start="2024-03-01", end="2024-01-01")
        with self.assertRaises(ValueError):
            self.client.load(start="not a date")

    def test_wide_preserves_missing_rows_without_resampling(self):
        wide = self.client.load(series=["CN_CPI", "JP_CPI"], wide=True)
        self.assertEqual(wide.shape, (2, 2))
        self.assertTrue(wide.loc["2024-02-01"].isna().all())
        self.assertEqual(wide.index.name, "date")

    def test_wide_mixed_frequency_requires_acknowledgement(self):
        with self.assertRaisesRegex(ValueError, "frequenc"):
            self.client.load(wide=True)
        wide = self.client.load(wide=True, allow_mixed_frequencies=True)
        self.assertEqual(set(wide.columns), {"CN_CPI", "JP_CPI", "US_EQ"})

    def test_empty_result_retains_schema(self):
        rows = self.client.load(series="CN_CPI", start="2030-01-01")
        self.assertEqual(len(rows), 0)
        self.assertIn("release_date", rows.columns)
        self.assertTrue(self.client.load(series="CN_CPI", start="2030-01-01", wide=True).empty)

    def test_sql_with_join_and_parameters(self):
        rows = self.client.sql("""-- safe query
            WITH chosen AS (SELECT * FROM observations WHERE country = ?)
            SELECT c.series_id, s.country_name, c.value FROM chosen c
            JOIN series s USING (series_id) ORDER BY c.date
        """, ("CN",))
        self.assertEqual(rows.country_name.tolist(), ["China", "China"])
        self.assertTrue(pd.isna(rows.value.iloc[1]))

    def test_sql_denies_all_writes_and_unsafe_operations(self):
        queries = ["DELETE FROM observations", "DROP TABLE series", "PRAGMA user_version=5",
                   "ATTACH DATABASE ':memory:' AS other", "SELECT load_extension('bad')",
                   "WITH chosen AS (SELECT 1) DELETE FROM observations",
                   "SELECT * FROM observations; DELETE FROM observations"]
        for query in queries:
            with self.subTest(query=query), self.assertRaises((ReadOnlyQueryError, sqlite3.Error)):
                self.client.sql(query)
        self.assertEqual(len(self.client.load()), 6)

    def test_sql_injection_is_only_a_parameter(self):
        with self.assertRaises(ValueError):
            self.client.load(series="CN_CPI'); DROP TABLE series; --")
        self.assertEqual(len(self.client.catalog()), 3)

    def test_local_operation_never_uses_network(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            self.client.refresh()
            self.assertEqual(len(self.client.load()), 6)
            self.client.download("excel", destination=Path(self.tmp.name) / "copy.xlsx")

    def test_local_checksum_corruption_rejected(self):
        self.client.load()
        with (self.directory / "dataset.sqlite").open("ab") as handle:
            handle.write(b"corrupt")
        with self.assertRaises(IntegrityError):
            self.client.load()

    def test_download_atomic_and_verified(self):
        target = Path(self.tmp.name) / "nested" / "data.csv.gz"
        self.assertEqual(self.client.download("csv", destination=target), target.resolve())
        self.assertEqual(target.read_bytes(), (self.directory / "observations.csv.gz").read_bytes())
        target.write_bytes(b"existing valid user file")
        (self.directory / "observations.csv.gz").write_bytes(b"bad")
        with self.assertRaises(IntegrityError):
            self.client.download("csv", destination=target)
        self.assertEqual(target.read_bytes(), b"existing valid user file")
        self.assertEqual(list(target.parent.glob("*.tmp")), [])

    def test_refresh_loads_new_version_and_manifest_is_defensive_copy(self):
        manifest = self.client.manifest
        manifest["files"]["dataset.sqlite"]["sha256"] = "f" * 64
        self.assertNotEqual(manifest, self.client.manifest)
        write_manifest(self.directory, "test-2")
        self.client.refresh()
        self.assertEqual(self.client.manifest["dataset_version"], "test-2")

    def test_failed_refresh_does_not_silently_serve_previous_data(self):
        (self.directory / "manifest.json").write_text("broken", encoding="utf-8")
        with self.assertRaises(MacroDataError):
            self.client.refresh()
        with self.assertRaises(MacroDataError):
            self.client.load()

    def test_manifest_path_traversal_and_bad_digest_rejected(self):
        for name, digest in [("../dataset.sqlite", "a" * 64), ("dataset.sqlite", "wrong")]:
            manifest = self.client.manifest
            manifest["files"][name] = {"bytes": 1, "sha256": digest}
            (self.directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.subTest(name=name), self.assertRaises(MacroDataError):
                MacroData(data_dir=self.directory)

    def test_unsafe_ref_rejected_before_network(self):
        for ref in ["../main", "main/../../secret", "main?token=foo", "", "https://bad"]:
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                MacroData(ref=ref)

    def test_remote_uses_verified_cache_and_no_stale_manifest_fallback(self):
        def respond(request, **kwargs):
            return io.BytesIO((self.directory / request.full_url.rsplit("/", 1)[1]).read_bytes())
        with patch("urllib.request.urlopen", side_effect=respond) as network:
            client = MacroData(cache_dir=Path(self.tmp.name) / "remote-cache")
            self.assertEqual(len(client.load()), 6)
            self.assertEqual(len(client.load()), 6)
            self.assertEqual(network.call_count, 2)  # manifest once, database once
        with patch("urllib.request.urlopen", side_effect=OSError("offline")), patch("time.sleep"):
            with self.assertRaises(MacroDataError):
                client.refresh()
            with self.assertRaises(MacroDataError):
                client.load()

    def test_remote_download_hash_mismatch_leaves_no_database(self):
        def respond(request, **kwargs):
            if request.full_url.endswith("manifest.json"):
                return io.BytesIO((self.directory / "manifest.json").read_bytes())
            return io.BytesIO(b"bad database")
        cache = Path(self.tmp.name) / "corrupt-cache"
        with patch("urllib.request.urlopen", side_effect=respond):
            client = MacroData(cache_dir=cache)
            with self.assertRaises(IntegrityError):
                client.load()
        self.assertEqual(list(cache.rglob("*.sqlite")), [])
        self.assertEqual(list(cache.rglob("*.tmp")), [])

    def test_same_length_corrupt_content_is_rejected(self):
        export = self.directory / "global_macro.xlsx"
        export.write_bytes(b"x" * export.stat().st_size)
        with self.assertRaises(IntegrityError):
            self.client.download("excel", destination=Path(self.tmp.name) / "copy.xlsx")

    def test_corrupted_remote_cache_is_not_served(self):
        def respond(request, **kwargs):
            return io.BytesIO((self.directory / request.full_url.rsplit("/", 1)[1]).read_bytes())
        cache = Path(self.tmp.name) / "remote-cache"
        with patch("urllib.request.urlopen", side_effect=respond):
            client = MacroData(cache_dir=cache)
            client.load()
        cached = next(cache.rglob("*.sqlite"))
        with cached.open("r+b") as handle:
            handle.write(b"x" * 16)
        with self.assertRaises(IntegrityError):
            client.load()

    def test_refresh_switches_to_changed_database(self):
        self.client.load()
        with sqlite3.connect(self.directory / "dataset.sqlite") as conn:
            conn.execute("UPDATE observations SET value=7 WHERE series_id='CN_CPI' AND is_missing=0")
        write_manifest(self.directory, "test-2")
        with self.assertRaises(IntegrityError):
            self.client.load()
        self.client.refresh()
        self.assertEqual(self.client.load(series="CN_CPI").value.iloc[0], 7)


if __name__ == "__main__":
    unittest.main()

"""Small synchronous SDK. No credentials, implicit stale fallback, or data imputation."""
from __future__ import annotations

from contextlib import closing, contextmanager
from copy import deepcopy
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import ssl
import tempfile
import time
from typing import Iterable
import urllib.error
import urllib.request

import certifi
import pandas as pd


class MacroDataError(RuntimeError):
    """Dataset manifest, transport, or schema is unavailable or invalid."""


class IntegrityError(MacroDataError):
    """Downloaded/local bytes do not match the manifest size and SHA-256."""


class ReadOnlyQueryError(MacroDataError):
    """Only read-only SELECT/WITH statements are permitted."""


_OBS_COLUMNS = (
    "series_id", "country", "date", "value", "is_missing", "frequency", "unit",
    "seasonal_adjustment", "retrieved_at_utc", "release_date", "update_status",
)
_FORMATS = {
    "excel": "global_macro.xlsx", "sqlite": "dataset.sqlite", "parquet": "observations.parquet",
    "csv": "observations.csv.gz", "jsonl": "observations.jsonl.gz", "sql": "dataset.sql.gz",
    "bundle": "bundle.zip",
}
_SAFE_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_SAFE_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_READ_START = re.compile(r"\A(?:\s|--[^\n]*(?:\n|$)|/\*.*?\*/)*(SELECT|WITH)\b", re.I | re.S)
_MAX_MANIFEST = 2 * 1024 * 1024
_CHUNK_SIZE = 1024 * 1024


def _selection(value: str | Iterable[str] | None, label: str) -> list[str] | None:
    if value is None:
        return None
    values = [value] if isinstance(value, str) else list(value)
    if not values or any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError(f"{label} must be a non-empty string or non-empty collection of strings")
    return list(dict.fromkeys(item.strip() for item in values))


def _date_bound(value: str | date | None, label: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date (YYYY-MM-DD) or date object") from exc


def _readonly_authorizer(action, arg1, arg2, database, trigger):
    if action == sqlite3.SQLITE_FUNCTION:
        # Extensions and filesystem helpers are never part of this data API.
        return sqlite3.SQLITE_DENY if str(arg2).lower() in {"load_extension", "writefile", "readfile"} else sqlite3.SQLITE_OK
    if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_RECURSIVE}:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


class MacroData:
    """A verified dataset snapshot, refreshed explicitly with :meth:`refresh`.

    ``ref`` is a simple GitHub branch/tag or commit SHA, with no slashes. Pin a
    commit SHA for reproducibility. ``data_dir`` selects explicit offline mode
    and must contain manifest.json and the files used by the requested methods.
    The default remote URL is the public Hogan-cyber/Macro-Data repository.
    """

    def __init__(self, cache_dir: str | Path | None = None, ref: str = "main", data_dir: str | Path | None = None):
        if not isinstance(ref, str) or not _SAFE_REF.fullmatch(ref) or ".." in ref:
            raise ValueError("ref must be a simple branch/tag or commit SHA, without slashes, '..', or URL parameters")
        self.ref = ref
        self.data_dir = Path(data_dir).expanduser().resolve() if data_dir is not None else None
        self.cache_dir = Path(cache_dir).expanduser().resolve() if cache_dir is not None else Path.home() / ".cache" / "hogan_macro"
        self._base_url = f"https://raw.githubusercontent.com/Hogan-cyber/Macro-Data/{ref}/data/global/"
        self._manifest: dict | None = None
        self._db_path: Path | None = None
        self.refresh()

    @property
    def manifest(self) -> dict:
        """A defensive copy of the active manifest (including version and hashes)."""
        return deepcopy(self._require_manifest())

    def _require_manifest(self) -> dict:
        if self._manifest is None:
            raise MacroDataError("No valid manifest is active; call refresh() successfully before reading data")
        return self._manifest

    @contextmanager
    def _remote_stream(self, filename: str):
        request = urllib.request.Request(
            self._base_url + filename,
            headers={"User-Agent": "hogan-macro-data/0.2.0", "Accept-Encoding": "identity"},
        )
        response = None
        for attempt in range(3):
            try:
                response = urllib.request.urlopen(request, timeout=30, context=ssl.create_default_context(cafile=certifi.where()))
                break
            except (urllib.error.URLError, OSError) as exc:
                if isinstance(exc, urllib.error.HTTPError) and exc.code not in {408, 429, 500, 502, 503, 504}:
                    raise MacroDataError(f"Cannot fetch {filename}: HTTP {exc.code}; no stale fallback") from exc
                if attempt == 2:
                    raise MacroDataError(f"Cannot fetch {filename} after 3 attempts; no stale fallback: {exc}") from exc
                time.sleep(0.25 * (2 ** attempt))
        try:
            with closing(response):
                yield response
        except OSError as exc:
            raise MacroDataError(f"Interrupted download of {filename}; no stale fallback: {exc}") from exc

    def refresh(self) -> "MacroData":
        """Fetch the current manifest and invalidate active database state.

        A failed refresh leaves no active snapshot. Offline use must be selected
        explicitly with data_dir; cached remote bytes are never a stale fallback.
        """
        self._manifest = None
        self._db_path = None
        try:
            if self.data_dir is not None:
                with (self.data_dir / "manifest.json").open("rb") as source:
                    payload = source.read(_MAX_MANIFEST + 1)
            else:
                with self._remote_stream("manifest.json") as source:
                    payload = source.read(_MAX_MANIFEST + 1)
            if len(payload) > _MAX_MANIFEST:
                raise MacroDataError("manifest.json exceeds the supported 2 MiB size")
            manifest = json.loads(payload)
            self._validate_manifest(manifest)
        except (OSError, ValueError, TypeError) as exc:
            raise MacroDataError(f"Invalid or unavailable manifest.json: {exc}") from exc
        self._manifest = manifest
        return self

    @staticmethod
    def _validate_manifest(manifest):
        if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
            raise MacroDataError("Only manifest schema_version=1 is supported")
        if not isinstance(manifest.get("dataset_version"), str) or not manifest["dataset_version"]:
            raise MacroDataError("Manifest is missing dataset_version")
        files = manifest.get("files")
        if not isinstance(files, dict) or "dataset.sqlite" not in files:
            raise MacroDataError("Manifest must describe dataset.sqlite")
        for name, spec in files.items():
            if not isinstance(name, str) or not _SAFE_FILENAME.fullmatch(name) or ".." in name:
                raise MacroDataError(f"Unsafe manifest filename: {name!r}")
            if not isinstance(spec, dict) or not isinstance(spec.get("sha256"), str) or not re.fullmatch(r"[a-fA-F0-9]{64}", spec["sha256"]):
                raise MacroDataError(f"Missing or invalid SHA-256 for {name}")
            if type(spec.get("bytes")) is not int or spec["bytes"] < 0:
                raise MacroDataError(f"Missing or invalid byte size for {name}")

    def _file_spec(self, filename: str) -> dict:
        files = self._require_manifest()["files"]
        if filename not in files:
            raise MacroDataError(f"{filename} is not included in this dataset version")
        return files[filename]

    @staticmethod
    def _verify(path: Path, spec: dict):
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(_CHUNK_SIZE), b""):
                    size += len(block)
                    if size > spec["bytes"]:
                        raise IntegrityError(f"Size mismatch for {path.name}: exceeds {spec['bytes']} bytes")
                    digest.update(block)
        except OSError as exc:
            raise MacroDataError(f"Cannot read {path}: {exc}") from exc
        if size != spec["bytes"] or digest.hexdigest() != spec["sha256"].lower():
            raise IntegrityError(f"Size or SHA-256 mismatch for {path.name}; refusing unverified data")

    def _copy_verified(self, filename: str, destination: Path) -> Path:
        spec = self._file_spec(filename)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp", delete=False) as target:
                temp_path = Path(target.name)
                source_context = (self.data_dir / filename).open("rb") if self.data_dir is not None else self._remote_stream(filename)
                with source_context as source:
                    digest = hashlib.sha256()
                    size = 0
                    for block in iter(lambda: source.read(_CHUNK_SIZE), b""):
                        size += len(block)
                        if size > spec["bytes"]:
                            raise IntegrityError(f"Size mismatch for {filename}: exceeds {spec['bytes']} bytes")
                        digest.update(block)
                        target.write(block)
                if size != spec["bytes"] or digest.hexdigest() != spec["sha256"].lower():
                    raise IntegrityError(f"Size or SHA-256 mismatch for {filename}; existing destination preserved")
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp_path, destination)
        except OSError as exc:
            raise MacroDataError(f"Cannot download {filename}: {exc}") from exc
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        return destination

    def _database_path(self) -> Path:
        spec = self._file_spec("dataset.sqlite")
        if self.data_dir is not None:
            path = self.data_dir / "dataset.sqlite"
            self._verify(path, spec)
        else:
            path = self.cache_dir / "datasets" / f"{spec['sha256'].lower()}.sqlite"
            if path.exists():
                self._verify(path, spec)
            else:
                self._copy_verified("dataset.sqlite", path)
        self._db_path = path
        return path

    def sql(self, query: str, params=()) -> pd.DataFrame:
        """Run one read-only SELECT/WITH statement; binds params using SQLite.

        SQL results retain SQLite types. Use load() for standardized datetime and
        nullable numeric columns. Writes, PRAGMA, ATTACH and extensions fail.
        """
        if not isinstance(query, str) or not _READ_START.match(query):
            raise ReadOnlyQueryError("Only a single read-only SELECT or WITH query is accepted")
        path = self._database_path()
        try:
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
                conn.execute("PRAGMA query_only = ON")
                conn.execute("PRAGMA trusted_schema = OFF")
                conn.set_authorizer(_readonly_authorizer)
                cursor = conn.execute(query, params)
                if cursor.description is None:
                    raise ReadOnlyQueryError("The query must return rows")
                return pd.DataFrame.from_records(cursor.fetchall(), columns=[col[0] for col in cursor.description])
        except sqlite3.DatabaseError as exc:
            if "authorized" in str(exc).lower() or "readonly" in str(exc).lower():
                raise ReadOnlyQueryError(f"Read-only query rejected: {exc}") from exc
            raise

    @staticmethod
    def _country_filter(catalog: pd.DataFrame, country) -> list[str] | None:
        values = _selection(country, "country")
        if values is None:
            return None
        countries = {str(item).upper(): item for item in catalog["country"].unique()}
        unknown = [item for item in values if item.upper() not in countries]
        if unknown:
            raise ValueError(f"Unknown country code(s): {', '.join(unknown)}. Available: {', '.join(sorted(countries))}")
        return [countries[item.upper()] for item in values]

    @staticmethod
    def _frequency_mask(catalog, frequency):
        if not isinstance(frequency, str) or not frequency.strip():
            raise ValueError('frequency must be a non-empty string')
        key=frequency.strip().casefold()
        aliases={'daily':['Daily','Daily, Close'],'monthly':['Monthly'],'quarterly':['Quarterly'],'annual':['Annual']}
        if key=='weekly':return catalog.frequency.str.startswith('Weekly',na=False)
        accepted=aliases.get(key,[frequency])
        if key not in aliases and not catalog.frequency.str.casefold().eq(key).any():
            raise ValueError('Unknown frequency; inspect catalog().frequency')
        return catalog.frequency.str.casefold().isin([x.casefold() for x in accepted])

    def catalog(self, country=None, asset_class=None, search: str | None = None, frequency: str | None = None) -> pd.DataFrame:
        """Inspect series metadata; country codes and asset classes are case-insensitive.

        search is a literal, case-insensitive substring across text metadata.
        Unknown country codes raise ValueError rather than returning empty data.
        """
        catalog = self.sql("SELECT * FROM series ORDER BY country, series_id")
        frequency_mask=self._frequency_mask(catalog,frequency) if frequency is not None else None
        countries = self._country_filter(catalog, country)
        if frequency_mask is not None:catalog=catalog.loc[frequency_mask]
        if countries is not None:
            catalog = catalog.loc[catalog.country.isin(countries)]
        assets = _selection(asset_class, "asset_class")
        if assets is not None:
            catalog = catalog.loc[catalog.asset_class.str.casefold().isin([item.casefold() for item in assets])]
        if search is not None:
            if not isinstance(search, str):
                raise ValueError("search must be a string")
            matched = catalog.astype("string").apply(lambda col: col.str.contains(search, case=False, regex=False, na=False)).any(axis=1)
            catalog = catalog.loc[matched]
        return catalog.reset_index(drop=True)

    def load(self, series=None, country=None, start=None, end=None, wide: bool = False, *, allow_mixed_frequencies: bool = False, frequency: str | None = None) -> pd.DataFrame:
        """Load native observations with inclusive observation-date bounds.

        No filling, aggregation, resampling, lagging, or release-date inference.
        wide=True requires one frequency unless allow_mixed_frequencies=True
        explicitly acknowledges the sparse mixed-frequency outer alignment.
        Matching frequencies alone do not make units or definitions comparable.
        """
        catalog = self.catalog()
        countries = self._country_filter(catalog, country)
        selected = _selection(series, "series")
        if selected is not None:
            unknown = sorted(set(selected) - set(catalog.series_id))
            if unknown:
                raise ValueError(f"Unknown series ID(s): {', '.join(unknown)}. Inspect catalog() for valid IDs")
            catalog = catalog.loc[catalog.series_id.isin(selected)]
        if countries is not None:
            catalog = catalog.loc[catalog.country.isin(countries)]
        if frequency is not None:
            catalog=catalog.loc[self._frequency_mask(catalog,frequency)]
            selected=catalog.series_id.tolist()
        frequencies = catalog.frequency.replace({'Daily, Close':'Daily'}).dropna().unique()
        if wide and len(frequencies) > 1 and not allow_mixed_frequencies:
            raise ValueError(f"Mixed frequencies: {', '.join(map(str, frequencies))}. Select one frequency, or explicitly set allow_mixed_frequencies=True; no resampling is performed")
        lower, upper = _date_bound(start, "start"), _date_bound(end, "end")
        if lower is not None and upper is not None and lower > upper:
            raise ValueError("start must be on or before end")
        clauses, params = [], []
        if selected==[]:clauses.append('1=0')
        for field, values in [("series_id", selected), ("country", countries)]:
            if values is not None:
                clauses.append(f"{field} IN ({','.join('?' for _ in values)})")
                params.extend(values)
        if lower is not None:
            clauses.append("date >= ?")
            params.append(lower)
        if upper is not None:
            clauses.append("date <= ?")
            params.append(upper)
        query = "SELECT " + ", ".join(_OBS_COLUMNS) + " FROM observations"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        rows = self.sql(query + " ORDER BY date, series_id", params)
        rows["date"] = pd.to_datetime(rows["date"], errors="raise")
        rows["release_date"] = pd.to_datetime(rows["release_date"], errors="raise")
        rows["retrieved_at_utc"] = pd.to_datetime(rows["retrieved_at_utc"], utc=True, errors="raise")
        rows["value"] = pd.array(rows["value"], dtype="Float64")
        rows["is_missing"] = pd.array(rows["is_missing"], dtype="Int64")
        if wide:
            result = rows.pivot(index="date", columns="series_id", values="value").sort_index()
            # Keep requested, valid series even if their selected date range is empty.
            return result.reindex(columns=sorted(catalog.series_id))
        return rows

    def download(self, format: str = "excel", *, destination: str | Path) -> Path:
        """Atomically save a manifest-verified export; return its absolute path.

        destination must be a file path. An existing file is replaced only after
        the full size and SHA-256 check passes. CSV, JSONL and SQL are gzip files;
        the SDK preserves their bytes and does not decompress based on the name.
        """
        if format not in _FORMATS:
            raise ValueError(f"Unknown format {format!r}; choose one of {', '.join(_FORMATS)}")
        return self._copy_verified(_FORMATS[format], Path(destination).expanduser().resolve())

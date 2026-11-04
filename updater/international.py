#!/usr/bin/env python3
"""Public international series; native frequencies, latest revisions, no filling.

Run from any directory. Exit 0 = complete retrieval, 2 = one or more sources
failed (last valid data retained), 1 = fatal configuration/output failure.
"""
from __future__ import annotations

import argparse
import concurrent.futures
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import ssl
import sys
import time
import urllib.parse
import urllib.request

try:
    from .update_us_macro import compare_rows, metadata_from_html, now_iso, parse_csv
except ImportError:
    from update_us_macro import compare_rows, metadata_from_html, now_iso, parse_csv

ROOT = Path(__file__).resolve().parents[1]
AVAILABILITY_NOTE = ('Dates are observation-period labels, not release dates. Historical first-release '
                     'timestamps and vintages are unavailable. Latest-revised data are unsuitable for '
                     'claims of point-in-time backtesting; retrieval time records when this copy was acquired.')


def download(url):
    """Bounded public HTTP requests; no credential or browser dependency."""
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    for attempt in range(2):
        try:
            with urllib.request.urlopen(url, timeout=25, context=context) as response:
                return response.read().decode('utf-8-sig')
        except (OSError, TimeoutError):
            if attempt == 1:
                raise
            time.sleep(1)


def archive(raw_dir, filename, text):
    (raw_dir / filename).write_text(text, encoding='utf-8')
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def parse_world_bank(payload, spec):
    if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[0], dict):
        raise ValueError('Invalid World Bank response envelope')
    header, records = payload
    if header.get('pages') != 1 or header.get('page') != 1 or not isinstance(records, list):
        raise ValueError('Incomplete or paginated World Bank response')
    if header.get('total') != len(records):
        raise ValueError('World Bank response count mismatch')
    if str(header.get('sourceid')) != '2':
        raise ValueError('Unexpected World Bank source; expected World Development Indicators')
    values = {}
    for record in records:
        if record.get('indicator', {}).get('id') != spec['indicator']:
            raise ValueError('World Bank indicator identity mismatch')
        if record.get('indicator', {}).get('value') != spec['source_name']:
            raise ValueError('World Bank indicator definition/unit name changed')
        if record.get('country', {}).get('id') != spec['country']:
            continue
        year = record.get('date', '')
        if not isinstance(year, str) or len(year) != 4 or not year.isdigit():
            raise ValueError('Expected annual World Bank year label')
        day = date(int(year), 1, 1).isoformat()
        value = record.get('value')
        if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value)):
            raise ValueError('Invalid World Bank numeric value')
        if record.get('unit', '') not in ('', spec['unit']):
            raise ValueError('Unexpected World Bank unit')
        if day in values and values[day] != value:
            raise ValueError('Conflicting duplicate World Bank year')
        values[day] = value
    if not values or not any(value is not None for value in values.values()):
        raise ValueError('No numeric World Bank observations for requested economy')
    return [[day, value, int(value is None)] for day, value in sorted(values.items())], header.get('lastupdated', '')


def fetch_fred(spec, start, end, raw_dir):
    sid = spec['id']
    url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?' + urllib.parse.urlencode({'id': sid, 'cosd': start, 'coed': end})
    text = download(url)
    digest = archive(raw_dir, sid + '.csv', text)
    rows = parse_csv(text, sid)
    source_url = 'https://fred.stlouisfed.org/series/' + sid
    page = download(source_url)
    archive(raw_dir, sid + '.html', page)
    meta = metadata_from_html(page)
    for field in ('unit', 'frequency', 'seasonal_adjustment'):
        if meta[field] != spec[field]:
            raise ValueError(f'Unverified FRED {field} change: {meta[field]!r}')
    if spec['source_name'] not in meta['source_title']:
        raise ValueError('FRED source title/identity mismatch')
    meta.update({'source_url': source_url, 'download_url': url,
                 'retrieved_at_utc': now_iso(), 'sha256': digest,
                 'provider': 'FRED', 'original_provider': spec['original_provider'],
                 'usage_note': spec['usage_note'], 'definition': spec['definition']})
    archive(raw_dir, sid + '.metadata.json', json.dumps(meta, ensure_ascii=False, indent=2))
    return {sid: (rows, meta)}


def fetch_world_bank(specs, raw_dir):
    indicator = specs[0]['indicator']
    countries = ';'.join(spec['country'] for spec in specs)
    # Full history avoids source pagination and unsupported date-filter variants.
    url = f'https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}?format=json&per_page=20000'
    text = download(url)
    digest = archive(raw_dir, indicator + '.json', text)
    metadata_url = f'https://api.worldbank.org/v2/indicator/{indicator}?format=json'
    metadata_text = download(metadata_url)
    archive(raw_dir, indicator + '.metadata.json', metadata_text)
    metadata_payload = json.loads(metadata_text)
    if not isinstance(metadata_payload, list) or len(metadata_payload) != 2 or len(metadata_payload[1]) != 1:
        raise ValueError('World Bank indicator metadata unavailable')
    source = metadata_payload[1][0]
    if source.get('id') != indicator or source.get('name') != specs[0]['source_name'] or source.get('source', {}).get('id') != '2':
        raise ValueError('Unverified World Bank indicator definition change')
    if not source.get('sourceNote') or source.get('unit', '') not in ('', specs[0]['unit']):
        raise ValueError('Unverified World Bank units/definition')
    payload = json.loads(text)
    result = {}
    for spec in specs:
        try:
            rows, updated = parse_world_bank(payload, spec)
            meta = {key: spec[key] for key in ('unit', 'frequency', 'seasonal_adjustment')}
            meta.update({'source_title': source['name'], 'source_url': f'https://data.worldbank.org/indicator/{indicator}?locations={spec["country"]}',
                         'download_url': url, 'metadata_url': metadata_url, 'source_last_updated': updated,
                         'retrieved_at_utc': now_iso(), 'provider': 'World Bank WDI', 'original_provider': source.get('sourceOrganization', ''),
                         'sha256': digest, 'definition': source['sourceNote'], 'usage_note': spec['usage_note'],
                         'source_indicator_id': indicator, 'source_period_label': 'year'})
            result[spec['id']] = (rows, meta)
        except Exception as exc:
            result[spec['id']] = exc
    return result


def fetch_all(specs, start, end, raw_dir):
    jobs = []
    groups = {}
    for spec in specs:
        if spec['provider'] == 'fred':
            jobs.append(([spec], fetch_fred, (spec, start, end, raw_dir)))
        elif spec['provider'] == 'world_bank':
            groups.setdefault(spec['indicator'], []).append(spec)
        else:
            raise ValueError('Unknown provider')
    jobs.extend((group, fetch_world_bank, (group, raw_dir)) for group in groups.values())
    result = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fn, *args): group for group, fn, args in jobs}
        for future in concurrent.futures.as_completed(futures):
            try:
                result.update(future.result())
            except Exception as exc:
                result.update({spec['id']: exc for spec in futures[future]})
    return result


def dataset_entry(spec, rows, meta, status, today, error=''):
    valid = [row for row in rows if row[1] is not None]
    threshold = {'Daily': 10, 'Daily, Close': 10, 'Monthly': 120, 'Annual': 1100}.get(meta.get('frequency', spec.get('frequency')), 400)
    age = (date.fromisoformat(today) - date.fromisoformat(valid[-1][0])).days if valid else None
    meta = {**meta, 'series_id': spec['id'], 'indicator_zh': spec['label'], 'category': spec['group'],
            'country': spec['country'], 'country_name': spec['country_name'], 'asset_class': spec['asset_class'],
            'first_observation': valid[0][0] if valid else '', 'last_observation': valid[-1][0] if valid else '',
            'valid_rows': len(valid), 'missing_rows': len(rows) - len(valid), 'update_status': status, 'error': error,
            'definition': meta.get('definition', spec['definition']), 'availability_note': AVAILABILITY_NOTE,
            'availability_basis': 'observation_period_only', 'vintage_basis': 'latest_revised',
            'observation_lag_days': age, 'freshness_threshold_days': threshold,
            'freshness_status': 'NO_DATA' if age is None else 'LAGGING' if age > threshold else 'WITHIN_THRESHOLD',
            'freshness_note': 'Heuristic observation-age threshold; not a verified release-calendar deadline.',
            'last_checked_at_utc': now_iso()}
    return {'spec': spec, 'meta': meta, 'rows': rows}


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')
        os.replace(temporary, path)
    finally:
        if temporary.exists(): temporary.unlink()


def collect(catalog, output, start, raw_root):
    date.fromisoformat(start)
    specs = catalog['series']
    if not specs or len({spec['id'] for spec in specs}) != len(specs):
        raise ValueError('Empty catalog or duplicate series identifiers')
    previous = json.loads(output.read_text(encoding='utf-8')) if output.exists() else {'schema_version': 1, 'entries': [], 'revisions': []}
    if previous.get('schema_version') != 1:
        raise ValueError('Unsupported prior snapshot schema')
    prior = {entry['spec']['id']: entry for entry in previous['entries']}
    if len(prior) != len(previous['entries']) or prior.keys() - {spec['id'] for spec in specs}:
        raise ValueError('Prior duplicate identifiers or catalog removal would lose saved series')
    for old in prior.values():
        if old['rows'] and old['rows'][0][0] < start:
            raise ValueError('Start date would truncate saved history')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    started = now_iso()
    end = date.today().isoformat()
    raw_dir = raw_root / run_id
    raw_dir.mkdir(parents=True, exist_ok=False)
    downloaded = fetch_all(specs, start, end, raw_dir)
    entries, failures = [], []
    revisions = list(previous.get('revisions', []))
    for spec in specs:
        sid = spec['id']
        old = prior.get(sid, {'rows': [], 'meta': {}})
        try:
            fetched = downloaded[sid]
            if isinstance(fetched, Exception): raise fetched
            received, meta = fetched
            if any(row[0] > end for row in received):
                raise ValueError('Source contains observation labels after current cutoff')
            rows = [row for row in received if row[0] >= start]
            if not any(row[1] is not None for row in rows):
                raise ValueError('No numeric history inside requested date range')
            for field in ('unit', 'frequency', 'seasonal_adjustment'):
                if old['rows'] and old['meta'].get(field) and old['meta'][field] != meta[field]:
                    raise ValueError(f'Source {field} changed; retained previous series')
            _, changes = compare_rows(old['rows'], rows)
            revisions.extend({'run_id': run_id, 'detected_at_utc': started, 'series_id': sid,
                              'observation_date': change[0], 'old_value': change[1], 'new_value': change[2],
                              'change_type': change[3]} for change in changes)
            entry = dataset_entry(spec, rows, meta, 'UPDATED', end)
        except Exception as exc:
            failures.append({'series_id': sid, 'error': str(exc)})
            defaults = {key: spec.get(key, '') for key in ('unit', 'frequency', 'seasonal_adjustment', 'usage_note')}
            entry = dataset_entry(spec, old['rows'], {**defaults, **old['meta']}, 'FAILED_RETAINED' if old['rows'] else 'FAILED_EMPTY', end, str(exc))
        entries.append(entry)
        print(f'{sid}: {entry["meta"]["update_status"]}, {entry["meta"]["valid_rows"]} valid rows', flush=True)
    payload = {'schema_version': 1, 'run_id': run_id, 'completed_at_utc': now_iso(),
               'status': 'partial_failure' if failures else 'success', 'failures': failures,
               'entries': entries, 'revisions': revisions}
    atomic_json(output, payload)
    atomic_json(output.with_name('international_revisions.json'), revisions)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=ROOT/'updater/international_catalog.json')
    parser.add_argument('--output', type=Path, default=ROOT/'data/international_snapshot.json')
    parser.add_argument('--raw-dir', type=Path, default=ROOT/'data/international_raw')
    parser.add_argument('--start', default='2000-01-01')
    args = parser.parse_args()
    try:
        result = collect(json.loads(args.catalog.read_text(encoding='utf-8')), args.output, args.start, args.raw_dir)
        print(json.dumps({'status': result['status'], 'series': len(result['entries']), 'failures': result['failures']}, ensure_ascii=False))
        return 2 if result['failures'] else 0
    except Exception as exc:
        print(f'International refresh fatal: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

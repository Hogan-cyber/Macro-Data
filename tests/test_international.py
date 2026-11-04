"""Behavioral checks for international ingestion and last-valid preservation."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'updater'))
try:
    import international as module
except ImportError:
    module = None


SPEC = {'id': 'WB_JP_GDP_GROWTH', 'label': '日本实际 GDP 增长', 'group': '国际经济',
        'country': 'JP', 'country_name': 'Japan', 'asset_class': 'macro',
        'provider': 'world_bank', 'indicator': 'NY.GDP.MKTP.KD.ZG',
        'source_name': 'GDP growth (annual %)', 'unit': 'Percent', 'frequency': 'Annual',
        'seasonal_adjustment': 'Not Seasonally Adjusted', 'definition': 'Annual real GDP growth.'}
META = {'unit': 'Percent', 'frequency': 'Annual', 'seasonal_adjustment': 'Not Seasonally Adjusted',
        'source_title': 'GDP growth (annual %)', 'retrieved_at_utc': '2026-11-01T00:00:00Z',
        'source_last_updated': '2026-10-08'}


def wb_payload(values):
    rows = [{'indicator': {'id': 'NY.GDP.MKTP.KD.ZG', 'value': 'GDP growth (annual %)'},
             'country': {'id': 'JP', 'value': 'Japan'}, 'countryiso3code': 'JPN',
             'date': year, 'value': value, 'unit': '', 'obs_status': '', 'decimal': 1}
            for year, value in values]
    return [{'page': 1, 'pages': 1, 'per_page': 2000, 'total': len(rows),
             'sourceid': '2', 'lastupdated': '2026-10-08'}, rows]


class InternationalTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module, 'international ingestion module must exist')

    def test_annual_period_is_label_zero_and_missing_remain_distinct(self):
        rows, updated = module.parse_world_bank(wb_payload([('2024', 0), ('2023', None), ('2022', -1.25)]), SPEC)
        self.assertEqual(rows, [['2022-01-01', -1.25, 0], ['2023-01-01', None, 1], ['2024-01-01', 0, 0]])
        self.assertEqual(updated, '2026-10-08')

    def test_rejects_partial_page_and_wrong_indicator_and_conflicting_duplicate(self):
        payload = wb_payload([('2024', 1)])
        payload[0]['pages'] = 2
        with self.assertRaises(ValueError): module.parse_world_bank(payload, SPEC)
        payload = wb_payload([('2024', 1)])
        payload[1][0]['indicator']['id'] = 'WRONG'
        with self.assertRaises(ValueError): module.parse_world_bank(payload, SPEC)
        with self.assertRaises(ValueError):
            module.parse_world_bank(wb_payload([('2024', 1), ('2024', 2)]), SPEC)

    def test_rejects_boolean_nonfinite_and_all_missing_values(self):
        for value in [True, float('inf'), None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.parse_world_bank(wb_payload([('2024', value)]), SPEC)

    def test_failed_refresh_preserves_prior_rows_and_retrieval_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'snapshot.json'
            rows = [['2023-01-01', 0, 0], ['2024-01-01', 1, 0]]
            old = module.dataset_entry(SPEC, rows, META, 'UPDATED', '2026-11-01')
            target.write_text(json.dumps({'schema_version': 1, 'entries': [old], 'revisions': []}))
            with patch.object(module, 'fetch_all', return_value={SPEC['id']: RuntimeError('offline')}):
                result = module.collect({'series': [SPEC]}, target, '2000-01-01', Path(directory)/'raw')
            self.assertEqual(result['status'], 'partial_failure')
            self.assertEqual(result['entries'][0]['rows'], rows)
            self.assertEqual(result['entries'][0]['meta']['retrieved_at_utc'], '2026-11-01T00:00:00Z')
            self.assertEqual(result['entries'][0]['meta']['update_status'], 'FAILED_RETAINED')
            self.assertEqual(len(result['failures']), 1)

    def test_truncation_and_unit_drift_retain_prior_data(self):
        for received, meta in [([['2024-01-01', 2, 0]], META),
                               ([['2023-01-01', 1, 0], ['2024-01-01', 2, 0]], {**META, 'unit': 'Index'})]:
            with self.subTest(meta=meta, received=received), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / 'snapshot.json'
                rows = [['2023-01-01', 0, 0], ['2024-01-01', 1, 0]]
                old = module.dataset_entry(SPEC, rows, META, 'UPDATED', '2026-11-01')
                target.write_text(json.dumps({'schema_version': 1, 'entries': [old], 'revisions': []}))
                with patch.object(module, 'fetch_all', return_value={SPEC['id']: (received, meta)}):
                    result = module.collect({'series': [SPEC]}, target, '2000-01-01', Path(directory)/'raw')
                self.assertEqual(result['entries'][0]['rows'], rows)
                self.assertEqual(result['status'], 'partial_failure')

    def test_revision_record_and_atomic_saved_result(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'snapshot.json'
            old = module.dataset_entry(SPEC, [['2023-01-01', 0, 0]], META, 'UPDATED', '2026-11-01')
            target.write_text(json.dumps({'schema_version': 1, 'entries': [old], 'revisions': []}))
            new = [['2023-01-01', 1, 0], ['2024-01-01', None, 1]]
            with patch.object(module, 'fetch_all', return_value={SPEC['id']: (new, META)}):
                result = module.collect({'series': [SPEC]}, target, '2000-01-01', Path(directory)/'raw')
            self.assertEqual(result['status'], 'success')
            revision = result['revisions'][0]
            self.assertEqual((revision['old_value'], revision['new_value'], revision['change_type']), (0, 1, 'revised'))
            self.assertEqual(json.loads(target.read_text()), result)
            self.assertEqual(result['entries'][0]['meta']['missing_rows'], 1)

    def test_observation_age_has_explicit_threshold_warning(self):
        old = module.dataset_entry(SPEC, [['2020-01-01', 1, 0]], META, 'UPDATED', '2026-11-04')
        self.assertEqual(old['meta']['freshness_status'], 'LAGGING')
        self.assertIn('release', old['meta']['availability_note'])

    def test_failed_empty_placeholder_does_not_block_verified_metadata_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'snapshot.json'
            old = module.dataset_entry(SPEC, [], {**META, 'unit': 'unverified'}, 'FAILED_EMPTY', '2026-11-01')
            target.write_text(json.dumps({'schema_version': 1, 'entries': [old], 'revisions': []}))
            with patch.object(module, 'fetch_all', return_value={SPEC['id']: ([['2024-01-01', 1, 0]], META)}):
                result = module.collect({'series': [SPEC]}, target, '2000-01-01', Path(directory)/'raw')
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['entries'][0]['meta']['unit'], 'Percent')


if __name__ == '__main__': unittest.main()

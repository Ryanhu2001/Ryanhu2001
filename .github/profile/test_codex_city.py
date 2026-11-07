import copy
import datetime as dt
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import update_codex_city as city


NOW = dt.datetime(2026, 11, 7, 16, 30, tzinfo=dt.timezone.utc)  # Nov 8 in Shanghai


def export():
    return {
        'app': {'name': 'token-monitor', 'version': '0.82.0'},
        'generatedAt': '2026-11-07T16:20:00Z',
        'daily': [
            {'date': '2026-11-04', 'tokens': 1100, 'perClient': {
                'codex': {'tokens': 100, 'cacheReadTokens': 60, 'outputTokens': 30, 'reasoningTokens': 20},
                'claude': {'tokens': 1000}}},
            {'date': '2026-11-05', 'perClient': {'claude': {'tokens': 99999}}},
            {'date': '2026-11-06', 'perClient': {'codex': {'tokens': 0}}},
            {'date': '2026-11-07', 'perClient': {'codex': {'tokens': 800}}},
            {'date': '2026-11-08', 'perClient': {'codex': {'tokens': 999999}}},
        ],
        'snapshot': {'allTime': {'totalTokens': 999999999, 'sessions': {'PRIVATE_ID': 'PRIVATE_TEXT'}}},
        'credentials': 'SECRET_CANARY',
        'projects': ['/PRIVATE_PATH'],
    }


class TokenMonitorContractTests(unittest.TestCase):
    def test_codex_only_completed_dates_and_no_double_counting(self):
        data = city.sanitize(export(), NOW)
        self.assertEqual(data['recordedTokens'], 900)
        self.assertEqual(data['coverage']['through'], '2026-11-07')
        self.assertEqual(data['coverage']['missingDates'], ['2026-11-05'])
        self.assertEqual(data['dailyUsageBuckets'][1], {'startDate': '2026-11-06', 'tokens': 0})
        self.assertEqual(data['schemaVersion'], 2)
        self.assertNotIn('PRIVATE_', json.dumps(data))
        self.assertNotIn('SECRET_CANARY', json.dumps(data))
        for mobile in (False, True):
            svg = city.render(data, mobile)
            ET.fromstring(svg)
            self.assertIn('Token Monitor', svg)
            self.assertIn('data-date="2026-11-05" data-state="missing"', svg)
            self.assertIn('data-date="2026-11-06" data-state="zero"', svg)
            self.assertNotIn('PRIVATE_', svg)
            self.assertNotIn('999,999 recorded tokens', svg)

    def test_invalid_counts_components_and_duplicate_dates_stop(self):
        for value in (True, -1, 1.5, None, 10**16):
            with self.subTest(value=value):
                data = export()
                data['daily'][0]['perClient']['codex']['tokens'] = value
                with self.assertRaises(ValueError):
                    city.sanitize(data, NOW)
        data = export()
        data['daily'][0]['perClient']['codex']['cacheReadTokens'] = 101
        with self.assertRaises(ValueError):
            city.sanitize(data, NOW)
        data = export()
        data['daily'].append(copy.deepcopy(data['daily'][0]))
        with self.assertRaises(ValueError):
            city.sanitize(data, NOW)

    def test_unavailable_stale_future_and_old_api_data_stop(self):
        cases = [
            {'dailyUsageBuckets': [{'startDate': '2026-11-07', 'tokens': 100}]},
            {**export(), 'daily': []},
            {**export(), 'generatedAt': '2026-11-01T00:00:00Z'},
            {**export(), 'generatedAt': '2026-11-09T00:00:00Z'},
            {**export(), 'generatedAt': '2026-11-07T16:20:00'},
            {**export(), 'daily': [{'date': '2026-11-09', 'perClient': {'codex': {'tokens': 1}}}]},
            {**export(), 'daily': [{'date': '2026-11-01', 'perClient': {'codex': {'tokens': 1}}}]},
            {**export(), 'daily': [{'date': '2026-11-07', 'tokens': 100}]},
            {**export(), 'daily': [{'date': '2026-11-08', 'perClient': {'codex': {'tokens': 1}}}]},
        ]
        for data in cases:
            with self.subTest(data_keys=list(data)):
                with self.assertRaises(ValueError):
                    city.sanitize(data, NOW)

    def test_zero_history_renders(self):
        data = export()
        for day in data['daily']:
            day['perClient'] = {'codex': {'tokens': 0}}
        clean = city.sanitize(data, NOW)
        self.assertEqual(clean['recordedTokens'], 0)
        for mobile in (False, True):
            ET.fromstring(city.render(clean, mobile))

    def test_configured_export_read_and_disabled_autoexport(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = root / 'token-monitor-export.json'
            path.write_text(json.dumps(export()))
            settings = root / 'settings.json'
            settings.write_text(json.dumps({'exportAutoEnabled': True, 'exportDir': tmp}))
            with patch.object(city, 'SETTINGS', settings):
                self.assertEqual(city.read_usage(), export())
                settings.write_text(json.dumps({'exportAutoEnabled': False, 'exportDir': tmp}))
                with self.assertRaises(ValueError):
                    city.read_usage()


if __name__ == '__main__':
    unittest.main()

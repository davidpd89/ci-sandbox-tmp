"""Regresión PR38: no red, móvil, perfiles ni registros reales."""
import contextlib
import datetime as dt
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import tiktok_source_evidence as se

TODAY = dt.date(2026, 10, 9)


def snapshot(n=150, back=40, **changes):
    item = dict(eligible=n, converted=back, not_converted=n-back,
                unknown=0, censored=0, pending=0, legacy_unverified=0,
                weak_identity=0, coverage='complete')
    item.update(changes)
    return {'date': TODAY.isoformat(), 'coverage_complete': True,
            'complete_dates': [TODAY.isoformat()],
            'cohorts_v2': {'schema_version': 2, 'timezone': 'Europe/Madrid',
                           'definition': 'first_observed_positive_by_local_D+N',
                           'windows': {'D+7': {'followers:@private.seed': item}}}}


class SourceEvidenceTests(unittest.TestCase):
    def test_valid_observational_interval_never_recommends_actions(self):
        res = se.report(snapshot(), today=TODAY)
        row = res['sources'][0]
        self.assertEqual(row['status'], 'observational_only')
        self.assertLess(row['wilson95'][0], row['rate'])
        self.assertGreater(row['wilson95'][1], row['rate'])
        self.assertFalse(res['recommendations_enabled'])
        self.assertNotIn('private.seed', str(res))

    def test_single_success_is_not_enough(self):
        row = se.report(snapshot(n=1, back=1), today=TODAY)['sources'][0]
        self.assertEqual(row['status'], 'blocked')
        self.assertIsNone(row['rate'])
        self.assertIn('insufficient_sample', row['reasons'])

    def test_actual_weak_tiktok_handle_blocks_even_with_large_n(self):
        row = se.report(snapshot(weak_identity=150), today=TODAY)['sources'][0]
        self.assertIn('weak_identity', row['reasons'])
        self.assertIsNone(row['wilson95'])

    def test_legacy_baseline_blocks(self):
        row = se.report(snapshot(legacy_unverified=1), today=TODAY)['sources'][0]
        self.assertIn('unverified_baseline', row['reasons'])

    def test_missing_negative_checkpoints_blocks(self):
        row = se.report(snapshot(not_converted=0, unknown=110), today=TODAY)['sources'][0]
        self.assertIn('incomplete_outcomes', row['reasons'])

    def test_partial_and_stale_snapshot_block(self):
        s = snapshot()
        s['coverage_complete'] = False
        self.assertIn('snapshot_incomplete', se.report(s, today=TODAY)['global_blockers'])
        s = snapshot()
        self.assertIn('snapshot_stale_or_future', se.report(s, today=TODAY + dt.timedelta(days=4))['global_blockers'])

    def test_rejects_bad_counts(self):
        for changes in ({'eligible': -1}, {'converted': 999}, {'unknown': '4'},
                        {'legacy_unverified': 999}, {'coverage': None}):
            s = snapshot(**changes)
            if changes == {'coverage': None}:
                self.assertEqual(se.report(s, today=TODAY)['sources'][0]['status'], 'blocked')
            else:
                with self.assertRaises(ValueError):
                    se.report(s, today=TODAY)

    def test_rejects_noncertified_study_definition(self):
        s = snapshot()
        s['cohorts_v2']['definition'] = 'legacy'
        with self.assertRaises(ValueError):
            se.report(s, today=TODAY)

    def test_no_lowering_sample_floor(self):
        with self.assertRaises(ValueError):
            se.report(snapshot(), today=TODAY, min_sample=1)

    def test_cli_read_only_and_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'reciprocity_audit.json'
            path.write_text(json.dumps(snapshot()), encoding='utf-8')
            before = path.read_bytes()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = se.main([str(path)])
            # Si el reloj real está lejos de la fecha del fixture: salida válida pero bloqueada.
            self.assertIn(rc, (0, 3))
            self.assertEqual(path.read_bytes(), before)
            self.assertNotIn('private.seed', out.getvalue())

    def test_malformed_complete_dates_never_certifies(self):
        s = snapshot()
        s['complete_dates'] = TODAY.isoformat()  # texto, no lista de checkpoints
        self.assertIn('snapshot_incomplete', se.report(s, today=TODAY)['global_blockers'])

    def test_cli_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ambiguous.json'
            path.write_text('{"date": "2026-10-09", "date": "2026-10-10"}', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(se.main([str(path)]), 2)

    def test_no_files_or_api_access_on_invalid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'missing.json'
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = se.main([str(path)])
            self.assertEqual(rc, 2)
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()

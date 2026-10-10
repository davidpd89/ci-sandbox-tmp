"""Regresiones sintéticas: sin cuentas, red, perfiles, tokens ni datos reales."""
import unittest
import sys
import datetime
import json
import io
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from experiment_uplift import analyze_experiment
import growth_attribution as ga
import daily_review as dr
import volume_shape as vs
import random

FLAGS = dict(window_days=14, randomized_pre_exposure=True,
             complete_assignment_log=True, fixed_outcome_window=True,
             no_interference=True, study_finished=True)


def rows(a=200, b=200, ya=40, yb=20):
    return [dict(unit_id=f'{arm}-{i}', network='bluesky', cohort='2026-10',
                 arm=arm, converted=i < (ya if arm == 'treatment' else yb),
                 contaminated=False, followup_days=14)
            for arm, num in (('treatment', a), ('control', b)) for i in range(num)]


class UpliftTest(unittest.TestCase):
    def test_valid_difference_and_newcombe(self):
        r = analyze_experiment(rows(), design=FLAGS)
        self.assertEqual(r['status'], 'review_only')
        self.assertAlmostEqual(r['difference_pp'], 10)
        self.assertAlmostEqual(r['ci_pp'][0], 3.0029022527831253)
        self.assertAlmostEqual(r['ci_pp'][1], 16.98703930609256)
        self.assertFalse(r['causal_claim_approved'])
        self.assertAlmostEqual(r['srm_p'], 1)

    def test_missing_proof_is_blocked_without_publishing_uplift(self):
        design = {**FLAGS, 'randomized_pre_exposure': False}
        r = analyze_experiment(rows(), design=design)
        self.assertEqual(r['status'], 'blocked')
        self.assertIn('randomized_pre_exposure', r['reasons'])
        self.assertIsNone(r['difference_pp'])
        self.assertIsNone(r['ci_pp'])

    def test_contaminated_control_blocks_instead_of_dropping_it(self):
        data = rows()
        data[-1]['contaminated'] = True
        r = analyze_experiment(data, design=FLAGS)
        self.assertIn('contamination_detected', r['reasons'])
        self.assertEqual(r['control']['n'], 200)
        self.assertIsNone(r['difference_pp'])
        self.assertIsNone(r['ci_pp'])

    def test_mismatch_blocks(self):
        r = analyze_experiment(rows(700, 100, 140, 10), design=FLAGS)
        self.assertIn('sample_ratio_mismatch', r['reasons'])
        self.assertIsNone(r['difference_pp'])

    def test_preregistered_asymmetric_allocation_has_no_false_srm(self):
        data = rows(700, 300, 140, 30)
        d = {**FLAGS, 'expected_treatment_fraction': 0.7}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'fixed.json'
            path.write_text(json.dumps({'design': d, 'records': data}), encoding='utf-8')
            output = io.StringIO()
            with redirect_stdout(output):
                rc = ga.main(['--experiment-report', str(path)])
        self.assertEqual(rc, 0)
        report = json.loads(output.getvalue())
        self.assertAlmostEqual(report['srm_p'], 1)
        self.assertEqual(report['status'], 'review_only')

    def test_small_sample_blocks(self):
        r = analyze_experiment(rows(2, 2, 1, 0), design=FLAGS)
        self.assertIn('insufficient_n', r['reasons'])
        self.assertIsNone(r['ci_pp'])

    def test_legacy_holdout_is_selected_only_from_non_elite(self):
        plan = [{'kind': 'follow', 'handle': f'user{i}'} for i in range(100)]
        treated, control = vs.split_holdout(
            plan, rng=random.Random(1), share=0.20, elite_share=0.25)
        held_handles = {row['handle'] for row in control}
        self.assertEqual(len(control), 20)
        self.assertTrue({f'user{i}' for i in range(25)}.isdisjoint(held_handles))
        self.assertEqual(len(treated), 80)
        # Todo usuario elite termina solo en tratamiento: comparación global sesgada.
        self.assertTrue({f'user{i}' for i in range(25)}.issubset(
            {row['handle'] for row in treated}))

    def test_small_groups_do_not_expose_person_level_outcomes(self):
        result = analyze_experiment(rows(2, 2, 1, 0), design=FLAGS)
        self.assertEqual(result['status'], 'blocked')
        for arm in ('treatment', 'control'):
            self.assertIsNone(result[arm]['conversions'])
            self.assertIsNone(result[arm]['rate'])

    def test_same_pure_contract_for_all_known_social_surfaces(self):
        networks = ('bluesky', 'mastodon', 'threads', 'x', 'facebook',
                    'pinterest', 'reddit', 'tiktok', 'instagram')
        for network in networks:
            data = rows()
            for item in data:
                item['network'] = network
            with self.subTest(network=network):
                result = analyze_experiment(data, design=FLAGS)
                self.assertEqual(result['status'], 'review_only')
                self.assertEqual(result['network'], network)
                self.assertFalse(result['causal_claim_approved'])

    def test_zero_and_full_bounds(self):
        a = analyze_experiment(rows(100, 100, 0, 100), design=FLAGS)
        self.assertTrue(-100 <= a['ci_pp'][0] <= a['ci_pp'][1] <= 100)

    def test_strict_validation(self):
        for changed in [lambda x: x.append(dict(x[0])),
                        lambda x: x[0].update(network='mastodon'),
                        lambda x: x[0].update(cohort='other-batch'),
                        lambda x: x[0].update(followup_days=10),
                        lambda x: x[0].update(converted=1),
                        lambda x: x[0].update(unit_id=''),
                        lambda x: x[0].update(arm=[]),
                        lambda x: x[0].update(unit_id='@handle'),
                        lambda x: x[0].update(network='unverified_social'),
                        lambda x: x[0].update(cohort='abc\\nsecond')]:
            data = rows()
            changed(data)
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                analyze_experiment(data, design=FLAGS)

    def test_legacy_holdout_duplicates_do_not_inflate_denominator(self):
        today = datetime.date(2026, 10, 9)
        past = {'fecha': '2026-09-20', 'cuenta': '@ana'}
        rows_old = [past, dict(past), {'fecha': '2026-10-08', 'cuenta': '@ana'},
                    {'fecha': '2026-09-21', 'cuenta': ''},
                    {'fecha': '2026-09-22', 'cuenta': '@bea'}]
        self.assertEqual(ga.holdout_view(rows_old, ['ana'], today, 14), (2, 1))

    def test_daily_notice_is_readonly_and_never_claims_causality(self):
        lines = dr.experiment_notice()
        self.assertIn('asociaciones', ' '.join(lines))
        self.assertIn('--experiment-report', ' '.join(lines))
        self.assertIn('revisión humana', ' '.join(lines))

    def test_invalid_design(self):
        with self.assertRaises(ValueError):
            analyze_experiment(rows(), design={**FLAGS, 'study_finished': 'yes'})
        with self.assertRaises(ValueError):
            analyze_experiment(rows(), design=FLAGS, min_per_arm=True)
        with self.assertRaises(ValueError):
            analyze_experiment(rows(), design=FLAGS, min_per_arm=1)
        with self.assertRaises(ValueError):
            analyze_experiment(rows(), design=FLAGS,
                               expected_treatment_fraction=10 ** 500)


    def test_cli_offline_never_calls_social_apis(self):
        data = {'design': FLAGS, 'records': rows()}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'anonymous.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            output = io.StringIO()
            with (redirect_stdout(output),
                  mock.patch.object(ga, 'bluesky_followers',
                                    side_effect=AssertionError('API accessed')),
                  mock.patch.object(ga, 'mastodon_followers',
                                    side_effect=AssertionError('API accessed'))):
                rc = ga.main(['--experiment-report', str(path)])
        self.assertEqual(rc, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['status'], 'review_only')
        self.assertNotIn('treatment-0', output.getvalue())

    def test_cli_rejects_oversize_manifest_without_any_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'too_big.json'
            path.write_text('x' * 2_000_001, encoding='utf-8')
            output = io.StringIO()
            with (redirect_stdout(output),
                  mock.patch.object(ga, 'bluesky_followers',
                                    side_effect=AssertionError('API accessed'))):
                code = ga.main(['--experiment-report', str(path)])
        self.assertEqual(code, 2)
        self.assertIn('inválido/inaccesible', output.getvalue())
        self.assertNotIn('xxxxx', output.getvalue())

    def test_cli_rejects_duplicate_json_and_nonstandard_numbers(self):
        valid = json.dumps({'design': FLAGS, 'records': rows()})
        duplicate = valid.replace('"design":', '"design": {}, "design":', 1)
        nan = valid.replace('"window_days": 14', '"window_days": NaN', 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'
            for raw in (duplicate, nan, '[' * 1100):
                with self.subTest(raw=raw[:20]):
                    path.write_text(raw, encoding='utf-8')
                    output = io.StringIO()
                    with redirect_stdout(output):
                        code = ga.main(['--experiment-report', str(path)])
                    self.assertEqual(code, 2)
                    self.assertIn('inválido/inaccesible', output.getvalue())
                    self.assertNotIn('unit_id', output.getvalue())

    def test_cli_blocked_design_returns_three(self):
        data = {'design': {**FLAGS, 'randomized_pre_exposure': False},
                'records': rows()}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'data.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            with redirect_stdout(io.StringIO()):
                rc = ga.main(['--experiment-report', str(path)])
        self.assertEqual(rc, 3)


if __name__ == '__main__':
    unittest.main()

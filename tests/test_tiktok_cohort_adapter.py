"""Regresión de la proyección #33, sin importar Android ni el auditor vivo."""
import datetime
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from tiktok_cohort_adapter import project


class TikTokAdapterTests(unittest.TestCase):
    def test_preserves_historical_projection_without_inventing_negative(self):
        follows = [('old', '2026-10-01', 'mutual:old'),
                   ('fast', '2026-10-08', 'mutual:q'),
                   ('slow', '2026-10-08', 'followers:@seed'),
                   ('never', '2026-10-08', 'followers:@seed'),
                   ('young', '2026-10-14', 'mutual:q')]
        v2, old = project(follows, {'old': '2026-10-08', 'fast': '2026-10-09',
                                   'slow': '2026-10-12'},
                          '2026-10-08', datetime.date(2026, 10, 16))
        self.assertEqual(old['D+1']['mutual:q'], {'followed': 2, 'back': 1, 'rate': 0.5})
        self.assertEqual(old['D+7']['followers:@seed'], {'followed': 2, 'back': 1, 'rate': 0.5})
        self.assertNotIn('mutual:old', old['D+1'])
        self.assertEqual(v2['D+1']['followers:@seed']['unknown'], 2)
        self.assertIsNone(v2['D+1']['followers:@seed']['rate'])

    def test_complete_checkpoint_only_valid_on_matching_day(self):
        follows = [('ana', '2026-10-08', 'q')]
        v2, old = project(follows, {}, '2026-10-08',
                          datetime.date(2026, 10, 16), complete_dates=['2026-10-12'])
        self.assertEqual(v2['D+1']['q']['unknown'], 1)
        self.assertEqual(v2['D+3']['q']['unknown'], 1)
        self.assertEqual(old['D+1']['q']['rate'], 0.0)
        v2, _ = project(follows, {}, '2026-10-08', datetime.date(2026, 10, 16),
                         complete_dates=['2026-10-09'])
        self.assertEqual(v2['D+1']['q']['not_converted'], 1)

    def test_legacy_preexisting_is_excluded(self):
        v2, old = project([('ana', '2026-10-08', 'followback')], {}, '2026-10-08',
                          datetime.date(2026, 10, 16))
        self.assertEqual(old['D+1'], {})
        self.assertEqual(v2['D+1'], {})


if __name__ == '__main__':
    unittest.main()

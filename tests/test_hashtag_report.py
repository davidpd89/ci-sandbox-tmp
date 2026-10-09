import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import hashtag_report as hr


class RankTests(unittest.TestCase):
    def test_weekly_sums_string_counts(self):
        history = [{'uses': '10', 'accounts': '4'}, {'uses': '5', 'accounts': '3'}]
        self.assertEqual(hr.weekly(history), (15, 7, 2))
        self.assertEqual(hr.weekly([]), (0, 0, 0))

    def test_rank_orders_by_distinct_accounts_and_handles_dead_tags(self):
        infos = {'Muerta': {'history': [{'uses': '0', 'accounts': '0'}]},
                 'Viva': {'history': [{'uses': '20', 'accounts': '10'}]},
                 'Media': {'history': [{'uses': '9', 'accounts': '3'}]}}
        rows = hr.rank(infos)
        self.assertEqual([r['tag'] for r in rows], ['Viva', 'Media', 'Muerta'])
        self.assertEqual(rows[0]['uses_per_account'], 2.0)
        self.assertIsNone(rows[2]['uses_per_account'])


if __name__ == '__main__':
    unittest.main()

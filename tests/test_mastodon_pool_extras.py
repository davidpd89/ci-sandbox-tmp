import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import mastodon_pool as mp
from test_mastodon_pool import FakeApi, account, TODAY


class Api(FakeApi):
    def __init__(self):
        super().__init__()
        self.directory_offsets, self.endorse_calls = [], []

    def suggestions(self):
        return [{"source": "past_interactions", "account": account("sug@masto.es", "Lectora de fantasía y novela juvenil")}]

    def directory(self, offset):
        self.directory_offsets.append(offset)
        return [account(f"dir{offset + i}@masto.es", "Escribo novela y poesía en español") for i in range(3)] if offset < 160 else []

    def endorsements(self, account_id):
        self.endorse_calls.append(account_id)
        return [account("destacada@masto.es", "Reseñas de libros de fantasía")]


class ExtraSurfacesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = mp.connect(os.path.join(self.tmp.name, "pool.sqlite3"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_suggestions_directory_and_endorsements_feed_the_pool(self):
        api = Api()
        seeds = {"ed": {"account_id": "1"}}
        result = mp.mine_extras(self.db, api, seeds, today=TODAY, pause=0)
        self.assertGreaterEqual(result["new"], 8)
        rows = {r[0]: r[1:] for r in self.db.execute("SELECT acct, seeds_count, first_source FROM accounts")}
        self.assertEqual(rows["sug@masto.es"], (0, "suggestions"))             # no cuenta como semilla del nicho
        self.assertEqual(rows["dir0@masto.es"], (0, "directory"))
        self.assertEqual(rows["destacada@masto.es"], (1, "seed_endorsement"))  # una semilla la destaca: si cuenta
        self.assertEqual(api.directory_offsets, [0, 80, 160])                  # cursor por offset
        mp.mine_extras(self.db, api, seeds, today=TODAY, pause=0)
        self.assertEqual(api.endorse_calls, ["1"])                             # las destacadas se refrescan cada semana, no cada ejecucion
        self.assertEqual(api.directory_offsets[3:], [0, 80, 160])               # directorio agotado: vuelve a empezar (el orden `active` cambia)


if __name__ == "__main__":
    unittest.main()

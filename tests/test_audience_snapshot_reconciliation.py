"""Tests sintéticos para la reconciliación de snapshots completos de audiencias."""
import pathlib
import tempfile
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import audience_discovery as ad

NOW = "2026-10-10T12:00:00+00:00"
POST = "2026-10-09T12:00:00+00:00"


def actor(network, uid="7", handle="lectora"):
    if network == "bluesky":
        return {"did": "did:plc:" + uid, "handle": handle, "bio": "Leo fantasía"}
    if network == "mastodon":
        return {"id": uid, "acct": handle + "@example.org", "bio": "Leo fantasía"}
    return {"id": uid, "username": handle, "bio": "Leo fantasía"}


class SnapshotReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.store = ad.AudienceStore()

    def tearDown(self):
        self.store.close()

    def test_reconciliation_deactivates_missing_users_on_complete_snapshot(self):
        # Snapshot 1: Usuarios 1, 2 y 3 le dan a like
        def fetch_snap1(cur):
            return {
                "items": [
                    {"actor": actor("bluesky", "1", "user1"), "event_id": "1"},
                    {"actor": actor("bluesky", "2", "user2"), "event_id": "2"},
                    {"actor": actor("bluesky", "3", "user3"), "event_id": "3"},
                ],
                "kind": "like",
                "post_key": "post_1",
                "post_created_at": POST,
                "next_cursor": None,
                "coverage_complete": True,
            }

        res1 = ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                                fetch_page=fetch_snap1, observed_at=NOW, use_snapshot_reconciliation=True)
        self.assertTrue(res1["complete"])
        self.assertEqual(len(self.store.ranked("bluesky")), 3)

        # Snapshot 2: El usuario 2 quitó su like. Solo devueltos usuarios 1 y 3.
        def fetch_snap2(cur):
            return {
                "items": [
                    {"actor": actor("bluesky", "1", "user1"), "event_id": "1"},
                    {"actor": actor("bluesky", "3", "user3"), "event_id": "3"},
                ],
                "kind": "like",
                "post_key": "post_1",
                "post_created_at": POST,
                "next_cursor": None,
                "coverage_complete": True,
            }

        res2 = ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                                fetch_page=fetch_snap2, observed_at="2026-10-10T12:05:00+00:00",
                                use_snapshot_reconciliation=True)
        self.assertTrue(res2["complete"])
        self.assertEqual(res2["deactivated_events"], 1)

        ranked = self.store.ranked("bluesky")
        self.assertEqual(len(ranked), 2)
        handles = {r["handle"] for r in ranked}
        self.assertIn("user1", handles)
        self.assertIn("user3", handles)
        self.assertNotIn("user2", handles)

    def test_interrupted_snapshot_preserves_previous_active_events(self):
        # Snapshot 1 completo con 3 usuarios
        def fetch_snap1(cur):
            return {
                "items": [
                    {"actor": actor("bluesky", "1", "u1"), "event_id": "1"},
                    {"actor": actor("bluesky", "2", "u2"), "event_id": "2"},
                    {"actor": actor("bluesky", "3", "u3"), "event_id": "3"},
                ],
                "kind": "like",
                "post_key": "post_1",
                "post_created_at": POST,
                "next_cursor": None,
                "coverage_complete": True,
            }

        ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                         fetch_page=fetch_snap1, observed_at=NOW, use_snapshot_reconciliation=True)
        self.assertEqual(len(self.store.ranked("bluesky")), 3)

        # Snapshot 2: falla en la página 2
        def fetch_snap2_failing(cur):
            if cur is None:
                return {
                    "items": [{"actor": actor("bluesky", "1", "u1"), "event_id": "1"}],
                    "kind": "like",
                    "post_key": "post_1",
                    "post_created_at": POST,
                    "next_cursor": "page2",
                }
            raise RuntimeError("Error de red/Timeout")

        with self.assertRaisesRegex(RuntimeError, "Error de red/Timeout"):
            ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                             fetch_page=fetch_snap2_failing, observed_at="2026-10-10T12:10:00+00:00",
                             use_snapshot_reconciliation=True)

        # Confirmar que los 3 usuarios siguen activos
        self.assertEqual(len(self.store.ranked("bluesky")), 3)
        # Verificar que el staging no dejó registros huérfanos
        staging_count = self.store.db.execute("SELECT COUNT(*) FROM audience_snapshot_staging").fetchone()[0]
        self.assertEqual(staging_count, 0)

    def test_empty_page_with_complete_coverage_clears_all_active_events(self):
        def fetch_initial(cur):
            return {
                "items": [{"actor": actor("bluesky", "1", "u1"), "event_id": "1"}],
                "kind": "like",
                "post_key": "post_1",
                "post_created_at": POST,
                "next_cursor": None,
                "coverage_complete": True,
            }

        ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                         fetch_page=fetch_initial, observed_at=NOW, use_snapshot_reconciliation=True)
        self.assertEqual(len(self.store.ranked("bluesky")), 1)

        def fetch_empty(cur):
            return {
                "items": [],
                "kind": "like",
                "post_key": "post_1",
                "post_created_at": POST,
                "next_cursor": None,
                "coverage_complete": True,
            }

        res = ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                               fetch_page=fetch_empty, observed_at="2026-10-10T12:15:00+00:00",
                               use_snapshot_reconciliation=True)
        self.assertTrue(res["complete"])
        self.assertEqual(res["deactivated_events"], 1)
        self.assertEqual(len(self.store.ranked("bluesky")), 0)

    def test_incomplete_coverage_flag_aborts_reconciliation(self):
        def fetch_initial(cur):
            return {
                "items": [{"actor": actor("bluesky", "1", "u1"), "event_id": "1"}],
                "kind": "like",
                "post_key": "post_1",
                "post_created_at": POST,
                "next_cursor": None,
                "coverage_complete": True,
            }

        ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                         fetch_page=fetch_initial, observed_at=NOW, use_snapshot_reconciliation=True)

        # Snapshot con actores omitidos por rate limit/cuarentena
        def fetch_incomplete(cur):
            return {
                "items": [],
                "kind": "like",
                "post_key": "post_1",
                "post_created_at": POST,
                "next_cursor": None,
                "coverage_complete": False,  # No se garantiza completitud
            }

        res = ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                               fetch_page=fetch_incomplete, observed_at="2026-10-10T12:20:00+00:00",
                               use_snapshot_reconciliation=True)
        self.assertFalse(res["complete"])
        self.assertEqual(res["deactivated_events"], 0)
        self.assertEqual(len(self.store.ranked("bluesky")), 1)

    def test_multi_network_isolation_during_snapshot_reconciliation(self):
        def fetch_bsky(cur):
            return {
                "items": [{"actor": actor("bluesky", "b1", "bsky_user"), "event_id": "b1"}],
                "kind": "like",
                "post_key": "post_common",
                "post_created_at": POST,
                "next_cursor": None,
                "coverage_complete": True,
            }

        def fetch_masto(cur):
            return {
                "items": [{"actor": actor("mastodon", "m1", "masto_user"), "event_id": "m1"}],
                "kind": "like",
                "post_key": "post_common",
                "post_created_at": POST,
                "next_cursor": None,
                "coverage_complete": True,
            }

        ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="sb",
                         fetch_page=fetch_bsky, observed_at=NOW, use_snapshot_reconciliation=True)
        ad.collect_pages(self.store, network="mastodon", surface="liked_by", seed="sm",
                         fetch_page=fetch_masto, observed_at=NOW, use_snapshot_reconciliation=True)

        self.assertEqual(len(self.store.ranked("bluesky")), 1)
        self.assertEqual(len(self.store.ranked("mastodon")), 1)

        # Reconciliación en Bluesky para post_common no desactiva Mastodon para post_common
        def fetch_bsky_empty(cur):
            return {
                "items": [],
                "kind": "like",
                "post_key": "post_common",
                "post_created_at": POST,
                "next_cursor": None,
                "coverage_complete": True,
            }

        ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="sb",
                         fetch_page=fetch_bsky_empty, observed_at="2026-10-10T12:25:00+00:00",
                         use_snapshot_reconciliation=True)

        self.assertEqual(len(self.store.ranked("bluesky")), 0)
        self.assertEqual(len(self.store.ranked("mastodon")), 1)

    def test_sqlite_file_persistence_and_abort(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(pathlib.Path(tmpdir) / "snapshot_test.db")
            store = ad.AudienceStore(db_path)

            sid = store.start_snapshot("bluesky", "liked_by", "s1", "post_p", "like", NOW)
            obs = [ad.normalize("bluesky", "like", {"actor": actor("bluesky", "101")},
                                surface="liked_by", post_key="post_p", observed_at=NOW, post_created_at=POST)]
            store.stage_snapshot_observations(sid, obs)

            staging_before = store.db.execute("SELECT COUNT(*) FROM audience_snapshot_staging WHERE snapshot_id=?", (sid,)).fetchone()[0]
            self.assertEqual(staging_before, 1)

            store.abort_snapshot(sid)
            staging_after = store.db.execute("SELECT COUNT(*) FROM audience_snapshot_staging WHERE snapshot_id=?", (sid,)).fetchone()[0]
            self.assertEqual(staging_after, 0)
            store.close()


if __name__ == "__main__":
    unittest.main()

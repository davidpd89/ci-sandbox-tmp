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

    def test_missing_coverage_complete_field_aborts_reconciliation(self):
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

        # Snapshot que omite el campo coverage_complete
        def fetch_missing_flag(cur):
            return {
                "items": [],
                "kind": "like",
                "post_key": "post_1",
                "post_created_at": POST,
                "next_cursor": None,
                # Sin campo coverage_complete
            }

        res = ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                               fetch_page=fetch_missing_flag, observed_at="2026-10-10T12:21:00+00:00",
                               use_snapshot_reconciliation=True)
        self.assertFalse(res["complete"])
        self.assertEqual(res["deactivated_events"], 0)
        self.assertEqual(len(self.store.ranked("bluesky")), 1)

    def test_inconsistent_post_key_across_pages_aborts_snapshot(self):
        def fetch_mismatched(cur):
            if cur is None:
                return {
                    "items": [{"actor": actor("bluesky", "1", "u1"), "event_id": "1"}],
                    "kind": "like",
                    "post_key": "post_A",
                    "post_created_at": POST,
                    "next_cursor": "p2",
                }
            return {
                "items": [{"actor": actor("bluesky", "2", "u2"), "event_id": "2"}],
                "kind": "like",
                "post_key": "post_B",  # Incoherente con post_A
                "post_created_at": POST,
                "next_cursor": None,
                "coverage_complete": True,
            }

        with self.assertRaisesRegex(ad.ObservationError, "incoherente"):
            ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                             fetch_page=fetch_mismatched, observed_at=NOW, use_snapshot_reconciliation=True)

    def test_active_snapshot_collision_and_recovery(self):
        # Iniciar snapshot sin recuperar abandonados para forzar error
        sid1 = self.store.start_snapshot("bluesky", "liked_by", "s1", "post_1", "like", NOW)
        self.assertTrue(sid1)

        with self.assertRaisesRegex(ad.ObservationError, "snapshot_activo_existente"):
            self.store.start_snapshot("bluesky", "liked_by", "s1", "post_1", "like", NOW, recover_abandoned=False)

        # Con recover_abandoned=True (defecto), se aborta automáticamente el anterior y se crea el nuevo
        sid2 = self.store.start_snapshot("bluesky", "liked_by", "s1", "post_1", "like", NOW, recover_abandoned=True)
        self.assertTrue(sid2)
        status_old = self.store.db.execute("SELECT status FROM audience_snapshots WHERE snapshot_id=?", (sid1,)).fetchone()[0]
        self.assertEqual(status_old, "aborted")

    def test_concurrent_ingestion_after_snapshot_started_is_preserved(self):
        # Initial active: u1
        def snap1(cur):
            return {
                "items": [{"actor": actor("bluesky", "1", "u1"), "event_id": "1"}],
                "kind": "like", "post_key": "p1", "post_created_at": POST,
                "next_cursor": None, "coverage_complete": True,
            }
        ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                         fetch_page=snap1, observed_at="2026-10-10T10:00:00+00:00", use_snapshot_reconciliation=True)

        # Iniciar snapshot 2 a las 11:00 (llegará staging sin u1)
        sid = self.store.start_snapshot("bluesky", "liked_by", "s1", "p1", "like", "2026-10-10T11:00:00+00:00")

        # Ingesta normal paralela de un nuevo like u2 a las 11:30 (posterior a started_at del snapshot)
        new_obs = ad.normalize("bluesky", "like", {"actor": actor("bluesky", "2", "u2"), "event_id": "2"},
                               surface="liked_by", post_key="p1", observed_at="2026-10-10T11:30:00+00:00", post_created_at=POST)
        self.store.ingest([new_obs], network="bluesky", surface="liked_by", seed="s1", next_cursor=None, now="2026-10-10T11:30:00+00:00")

        # Confirmar snapshot 2 (que se inició a las 11:00 y no traía ni u1 ni u2)
        # u1 estaba antes de 11:00 -> se desactiva. u2 ocurrió después de 11:00 -> BARRERA DE CONSISTENCIA lo preserva activo.
        self.store.commit_snapshot_reconciliation(sid, now="2026-10-10T12:00:00+00:00")

        ranked = self.store.ranked("bluesky")
        handles = {r["handle"] for r in ranked}
        self.assertNotIn("u1", handles)
        self.assertIn("u2", handles)

    def test_reactivation_after_deactivation(self):
        # Snapshot 1: u1 activo
        def snap1(cur):
            return {
                "items": [{"actor": actor("bluesky", "1", "u1"), "event_id": "1"}],
                "kind": "like", "post_key": "p1", "post_created_at": POST,
                "next_cursor": None, "coverage_complete": True,
            }
        ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                         fetch_page=snap1, observed_at=NOW, use_snapshot_reconciliation=True)
        self.assertEqual(len(self.store.ranked("bluesky")), 1)

        # Snapshot 2: u1 ausente (desactivado)
        def snap2(cur):
            return {
                "items": [],
                "kind": "like", "post_key": "p1", "post_created_at": POST,
                "next_cursor": None, "coverage_complete": True,
            }
        ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                         fetch_page=snap2, observed_at="2026-10-10T12:05:00+00:00", use_snapshot_reconciliation=True)
        self.assertEqual(len(self.store.ranked("bluesky")), 0)

        # Snapshot 3: u1 vuelve a dar like (reactivación)
        def snap3(cur):
            return {
                "items": [{"actor": actor("bluesky", "1", "u1"), "event_id": "1"}],
                "kind": "like", "post_key": "p1", "post_created_at": POST,
                "next_cursor": None, "coverage_complete": True,
            }
        ad.collect_pages(self.store, network="bluesky", surface="liked_by", seed="s1",
                         fetch_page=snap3, observed_at="2026-10-10T12:10:00+00:00", use_snapshot_reconciliation=True)
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

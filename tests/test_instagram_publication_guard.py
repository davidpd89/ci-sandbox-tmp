"""Regresión offline: la publicación propia de Instagram no se duplica."""
import datetime
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import content_publisher as cp
import instagram_publish_guard as guard
import meta_common as mc
import meta_publish as mp


class DurableIntentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "guard.sqlite3")
        self.item = os.path.join(self.tmp.name, "ficha_sintetica.md")

    def tearDown(self):
        self.tmp.cleanup()

    def test_lost_final_response_does_not_retry(self):
        sent = []
        def uncertain(checkpoint):
            checkpoint("C-SYNTHETIC")
            sent.append("POST /media_publish")
            raise TimeoutError("respuesta perdida")
        with self.assertRaises(TimeoutError):
            guard.publish_guarded(self.item, "IG-SYNTH", uncertain, db_path=self.db)
        with self.assertRaises(guard.InstagramPublicationHeld):
            guard.publish_guarded(self.item, "IG-SYNTH", uncertain, db_path=self.db)
        self.assertEqual(sent, ["POST /media_publish"])

    def test_permission_error_before_final_publish_can_retry(self):
        with self.assertRaises(PermissionError):
            guard.publish_guarded(
                self.item, "IG-SYNTH",
                lambda callback: (_ for _ in ()).throw(PermissionError("falta scope")),
                db_path=self.db,
            )
        self.assertEqual(
            guard.publish_guarded(
                self.item, "IG-SYNTH",
                lambda callback: callback("C-OK") or "MEDIA-OK",
                db_path=self.db,
            ), "MEDIA-OK",
        )

    def test_success_followed_by_local_crash_is_still_held(self):
        self.assertEqual(
            guard.publish_guarded(
                self.item, "IG-SYNTH",
                lambda callback: callback("C-OK") or "MEDIA-OK",
                db_path=self.db,
            ), "MEDIA-OK",
        )
        with self.assertRaises(guard.InstagramPublicationHeld):
            guard.publish_guarded(self.item, "IG-SYNTH", lambda cb: "DUPLICATE", db_path=self.db)

    def test_missing_checkpoint_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "omitio"):
            guard.publish_guarded(self.item, "IG-SYNTH", lambda cb: "MEDIA", db_path=self.db)
        with self.assertRaises(guard.InstagramPublicationHeld):
            guard.publish_guarded(self.item, "IG-SYNTH", lambda cb: "MEDIA", db_path=self.db)

    def test_two_processes_only_one_enters_publish(self):
        script = (
            "import sys,time\n"
            "from instagram_publish_guard import publish_guarded,InstagramPublicationHeld\n"
            "def submit(cb):\n"
            " cb('C-SYNTH');time.sleep(.15);return 'MEDIA-OK'\n"
            "try:\n"
            " publish_guarded(sys.argv[1],'IG-SYNTH',submit,db_path=sys.argv[2]);print('SENT')\n"
            "except InstagramPublicationHeld:\n"
            " print('HELD')\n"
        )
        env = dict(os.environ, PYTHONPATH=str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
        args = [sys.executable, "-c", script, self.item, self.db]
        p1 = subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p2 = subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out1, err1 = p1.communicate(timeout=20)
        out2, err2 = p2.communicate(timeout=20)
        self.assertEqual((p1.returncode, p2.returncode), (0, 0), err1 + err2)
        self.assertEqual(sorted([out1.strip(), out2.strip()]), ["HELD", "SENT"])


    def test_checkpoint_update_affecting_zero_rows_never_posts(self):
        # ActionLedger.settle hace UPDATE ... WHERE status=RESERVED sin
        # comprobar rowcount. Simular actualizacion silenciosa de 0 filas.
        sent = []
        original = guard.ActionLedger.settle

        def no_checkpoint(ledger, kind, target, status, detail=""):
            if status == guard.UNCERTAIN:
                return None
            return original(ledger, kind, target, status, detail)

        def submit(checkpoint):
            checkpoint("C-SYNTH")
            sent.append("POST /media_publish")
            return "MEDIA"

        with patch.object(guard.ActionLedger, "settle", no_checkpoint):
            with self.assertRaisesRegex(guard.InstagramPublicationHeld, "checkpoint"):
                guard.publish_guarded(self.item, "IG-SYNTH", submit, db_path=self.db)
        self.assertEqual(sent, [])

    def test_checkpoint_row_deleted_before_post_never_posts(self):
        # Una herramienta administrativa externa puede borrar una reserva
        # sin respetar el candado de publicacion. El callback debe verificar
        # que la fila sigue existiendo antes de permitir el POST.
        sent = []
        original = guard.ActionLedger.settle

        def deleted(ledger, kind, target, status, detail=""):
            if status == guard.UNCERTAIN:
                return ledger.release(kind, target)
            return original(ledger, kind, target, status, detail)

        def submit(checkpoint):
            checkpoint("C-SYNTH")
            sent.append("POST /media_publish")
            return "MEDIA"

        with patch.object(guard.ActionLedger, "settle", deleted):
            with self.assertRaisesRegex(guard.InstagramPublicationHeld, "checkpoint"):
                guard.publish_guarded(self.item, "IG-SYNTH", submit, db_path=self.db)
        self.assertEqual(sent, [])

    def test_same_fixture_baseline_two_posts_guard_one(self):
        # Reproduce el protocolo: status FINISHED y timeout DESPUÉS del POST.
        # Baseline (dos ejecuciones sin journal) = 2 envíos; guard = 1.
        sent = []
        def fake_post(base, path, token, **params):
            if path.endswith("/media_publish"):
                sent.append(path)
                raise TimeoutError("Meta procesó el POST pero se perdió la respuesta")
            return {"id": "CONTAINER-1"}
        def fake_get(base, path, token, **params):
            return {"status_code": "FINISHED"}
        def submit(callback=None):
            return mp.publish_instagram(
                "synthetic", "IG-SYNTH", "Texto", ["https://example.invalid/a.jpg"],
                before_publish=callback,
            )
        with patch.object(mp.mc, "graph_post", side_effect=fake_post), \
             patch.object(mp.mc, "graph_get", side_effect=fake_get):
            for _ in range(2):
                with self.assertRaises(TimeoutError):
                    submit()
            baseline_count = len(sent)
            sent.clear()
            with self.assertRaises(TimeoutError):
                guard.publish_guarded(
                    self.item, "IG-SYNTH", submit, db_path=self.db,
                )
            with self.assertRaises(guard.InstagramPublicationHeld):
                guard.publish_guarded(
                    self.item, "IG-SYNTH", submit, db_path=self.db,
                )
            guarded_count = len(sent)
        self.assertEqual((baseline_count, guarded_count), (2, 1))

    def test_corrupt_journal_fails_closed_without_sending(self):
        import sqlite3
        with open(self.db, "wb") as stream:
            stream.write(b"esto no es SQLite")
        calls = []
        with self.assertRaises(sqlite3.DatabaseError):
            guard.publish_guarded(
                self.item, "IG-SYNTH",
                lambda cb: calls.append("POST"),
                db_path=self.db,
            )
        self.assertEqual(calls, [])


class MetaContractTests(unittest.TestCase):
    def test_final_post_only_after_finished_and_checkpoint(self):
        calls = []
        def post(base, path, token, **params):
            calls.append(("POST", path))
            return {"id": "C1" if path.endswith("/media") else "MEDIA1"}
        def get(base, path, token, **params):
            calls.append(("GET", path))
            return {"status_code": "FINISHED"}
        with patch.object(mp.mc, "graph_post", side_effect=post), patch.object(mp.mc, "graph_get", side_effect=get):
            media_id = mp.publish_instagram(
                "synthetic-token", "IG", "Pie de prueba", ["https://example.invalid/imagen.jpg"],
                before_publish=lambda cid: calls.append(("CHECKPOINT", cid)),
            )
        self.assertEqual(media_id, "MEDIA1")
        self.assertEqual([x[0] for x in calls], ["POST", "GET", "CHECKPOINT", "POST"])
        self.assertEqual(calls[-1][1], "IG/media_publish")

    def test_carousel_child_error_never_reaches_publish(self):
        paths = []
        def post(base, path, token, **params):
            paths.append(path)
            return {"id": "C1"}
        with patch.object(mp.mc, "graph_post", side_effect=post), \
             patch.object(mp.mc, "graph_get", return_value={"status_code": "ERROR"}):
            with self.assertRaisesRegex(RuntimeError, "ERROR"):
                mp.publish_instagram(
                    "fake", "IG", "Pie", ["https://example.invalid/a.jpg", "https://example.invalid/b.jpg"],
                )
        self.assertEqual(paths, ["IG/media"])

    def test_expired_and_timeout_do_not_invoke_publish(self):
        for status in ("EXPIRED", "IN_PROGRESS"):
            with self.subTest(status=status), \
                 patch.object(mp.mc, "graph_get", return_value={"status_code": status}):
                with self.assertRaises(RuntimeError):
                    mp._wait_container("fake", "C", tries=2, sleep=lambda seconds: None)


class IntegrationTests(unittest.TestCase):
    def test_caller_does_not_repeat_ambiguous_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            sent = []
            env = {
                "FB_PAGE_TOKEN": "fake", "FB_PAGE_ID": "FB",
                "IG_ACCESS_TOKEN": "fake", "IG_USER_ID": "IG",
            }
            item = {"md_path": os.path.join(tmp, "test.md"), "texto": "Pie de prueba"}
            def remote(token, uid, caption, urls, alts, *, before_publish):
                before_publish("C-SYNTH")
                sent.append("POST")
                raise TimeoutError("respuesta ambigua")
            with patch.object(guard, "GUARD_DB", os.path.join(tmp, "guard.db")), \
                 patch.object(mc, "read_env", return_value=env), \
                 patch.object(cp, "_media", return_value=(["fake.png"], ["Texto ALT"])), \
                 patch.object(mp, "public_image_url", return_value="https://example.invalid/a.jpg"), \
                 patch.object(mp, "publish_instagram", side_effect=remote):
                with self.assertRaises(TimeoutError):
                    cp.publish_instagram(item)
                with self.assertRaises(guard.InstagramPublicationHeld):
                    cp.publish_instagram(item)
            self.assertEqual(sent, ["POST"])

    def test_unreadable_remote_fails_before_any_send(self):
        sent = []
        with patch.object(cp, "load_config", return_value={
            "enabled": {"instagram": True}, "max_overdue_days": 3,
        }), patch.object(cp.cq, "pending_parse_issues", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "no se puede verificar"):
                cp.run("instagram", apply=True, now=datetime.datetime(2026, 10, 9, 12),
                       verify=lambda red, now: {"unverifiable": True},
                       publishers={"instagram": lambda item: sent.append(item)},
                       out=lambda line: None)
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()

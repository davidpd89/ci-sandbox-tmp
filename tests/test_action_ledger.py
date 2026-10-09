"""action_ledger.py (03/10): reserva atomica entre procesos y bloqueo por fichero."""
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import action_ledger as al


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.ledger = al.ActionLedger(os.path.join(self.tmp.name, "l.sqlite"), stale_after=100, clock=self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_the_first_reservation_wins_and_confirmed_blocks_forever(self):
        self.assertEqual(self.ledger.reserve("reply", "at://x/1"), "ok")
        self.assertEqual(self.ledger.reserve("reply", "at://x/1"), "reserved")
        self.ledger.settle("reply", "at://x/1", al.CONFIRMED)
        self.clock.now += 10_000
        self.assertEqual(self.ledger.reserve("reply", "at://x/1"), "confirmed")
        self.assertEqual(self.ledger.reserve("like", "at://x/1"), "ok")  # otro kind, otro objetivo logico

    def test_count_since_counts_only_confirmed_actions_of_the_period(self):
        for target in ('a', 'b'):
            self.ledger.reserve('like', target)
            self.ledger.settle('like', target, al.CONFIRMED)
        self.ledger.reserve('like', 'c')
        self.ledger.reserve('follow', 'd')
        self.ledger.settle('follow', 'd', al.FAILED)
        self.clock.now += 5000
        self.ledger.reserve('like', 'e')
        self.ledger.settle('like', 'e', al.CONFIRMED)
        self.assertEqual(self.ledger.count_since(0), 3)
        self.assertEqual(self.ledger.count_since(3000), 1)


    def test_failed_and_abandoned_reservations_can_be_retried_uncertain_cannot(self):
        self.ledger.reserve("follow", "ana")
        self.ledger.settle("follow", "ana", al.FAILED)
        self.assertEqual(self.ledger.reserve("follow", "ana"), "ok")
        self.clock.now += 101  # proceso caido: la reserva caduca
        self.assertEqual(self.ledger.reserve("follow", "ana"), "ok")
        self.ledger.settle("follow", "ana", al.UNCERTAIN)
        self.assertEqual(self.ledger.reserve("follow", "ana"), "uncertain")

    def test_concurrent_reservations_have_exactly_one_winner(self):
        winners = []

        def worker():
            winners.append(al.ActionLedger(self.ledger.path).reserve("reply", "at://x/race"))
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(winners.count("ok"), 1)

    def test_target_for_and_settle_results(self):
        self.assertEqual(al.ActionLedger.target_for("follow", {"handle": "@Ana"}), "ana")
        self.assertEqual(al.ActionLedger.target_for("reply", {"_target_uri": "at://a/1", "url": "u"}), "at://a/1")
        self.assertEqual(al.ActionLedger.target_for("favourite", {"status_id": 7, "url": "u"}), "7")
        reserved = {("reply", "at://a/1"), ("like", "at://a/2"), ("follow", "luis")}
        for kind, target in reserved:
            self.ledger.reserve(kind, target)
        results = [{"kind": "reply", "_target_uri": "at://a/1", "resultado": "confirmado"},
                   {"kind": "like", "url": "at://a/2", "resultado": "saltado_ya_reaccionado"}]
        al.settle_results(self.ledger, reserved, results)
        self.assertEqual(self.ledger.status("reply", "at://a/1"), al.CONFIRMED)
        self.assertEqual(self.ledger.status("like", "at://a/2"), al.CONFIRMED)
        self.assertEqual(self.ledger.status("follow", "luis"), al.FAILED)  # sin resultado: reintentable

    def test_outcome_mapping(self):
        self.assertEqual(al.outcome_to_status("confirmado"), al.CONFIRMED)
        self.assertEqual(al.outcome_to_status("saltado_ya_seguido"), al.CONFIRMED)
        self.assertEqual(al.outcome_to_status("parada_rate_limit:429"), al.FAILED)
        self.assertEqual(al.outcome_to_status("fallo:boom"), al.FAILED)
        self.assertEqual(al.outcome_to_status("pendiente_verificacion"), al.UNCERTAIN)


class HoldoutLedgerTests(unittest.TestCase):
    def test_held_targets_are_never_actioned_even_after_the_stale_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = Clock()
            ledger = al.ActionLedger(os.path.join(tmp, "l.sqlite"), stale_after=10, clock=clock)
            ledger.hold("follow", "control")
            clock.now += 100_000
            self.assertEqual(ledger.reserve("follow", "control"), "holdout")
            ledger.release("follow", "control")
            self.assertEqual(ledger.reserve("follow", "control"), "ok")


class ExclusiveTests(unittest.TestCase):
    def test_second_holder_is_refused_and_released_afterwards(self):
        with tempfile.TemporaryDirectory() as tmp:
            with al.exclusive("x", directory=tmp):
                with self.assertRaises(al.RoundBusy):
                    with al.exclusive("x", directory=tmp):
                        pass
            with al.exclusive("x", directory=tmp):
                pass  # liberado al salir

    def test_stale_lock_is_taken_over(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rrss_lock_y.lock")
            pathlib.Path(path).write_text("999 1", encoding="utf-8")
            os.utime(path, (1, 1))
            # PID 999 puede existir en CI: el fixture no debe presuponer
            # que un número arbitrario representa un proceso ya muerto.
            with mock.patch.object(al, "_pid_alive", return_value=False):
                with al.exclusive("y", stale_after=60, directory=tmp):
                    pass

    def test_lock_left_by_a_dead_process_is_taken_over_immediately(self):
        import subprocess
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()   # PID ya inexistente
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rrss_lock_z.lock")
            pathlib.Path(path).write_text(f"{proc.pid} 1", encoding="utf-8")
            with al.exclusive("z", directory=tmp):    # fresco (no caducado) pero su dueño murio: se toma
                pass

    def test_lock_of_a_live_process_is_still_respected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rrss_lock_w.lock")
            pathlib.Path(path).write_text(f"{os.getpid()} 1", encoding="utf-8")
            with self.assertRaises(al.RoundBusy):
                with al.exclusive("w", directory=tmp):
                    pass


if __name__ == "__main__":
    unittest.main()


class BrowserSessionTests(unittest.TestCase):
    def test_waits_for_the_holder_then_runs_and_releases(self):
        import tempfile
        import threading
        import time as _t
        with tempfile.TemporaryDirectory() as d:
            order = []

            def holder():
                with al.exclusive("edge_browser", directory=d):
                    order.append("holder_in")
                    _t.sleep(1)
                order.append("holder_out")

            thread = threading.Thread(target=holder)
            thread.start()
            _t.sleep(0.3)
            real_sleep = _t.sleep
            with mock.patch.object(al.time, "sleep", lambda s: real_sleep(0.2)):
                with al.browser_session(wait_minutes=1, directory=d):
                    order.append("mine")
            thread.join()
            self.assertEqual(order, ["holder_in", "holder_out", "mine"])
            with al.exclusive("edge_browser", directory=d):   # liberado
                pass

    def test_child_of_a_round_that_holds_the_turn_does_not_ask_again(self):
        with tempfile.TemporaryDirectory() as d:
            with al.browser_session(wait_minutes=0, directory=d):
                inherited = {
                    "RRSS_BROWSER_LOCK_HELD": "edge_browser",
                    "RRSS_BROWSER_LOCK_OWNER_PID": str(os.getpid()),
                }
                from process_identity import creation_token
                birth = creation_token(os.getpid())
                if birth:
                    inherited["RRSS_BROWSER_LOCK_OWNER_BIRTH"] = birth
                with mock.patch.dict(os.environ, inherited):
                    # La reentrada del MISMO hilo mantiene compatibilidad.
                    with al.browser_session(wait_minutes=0, directory=d) as nested:
                        self.assertIsNone(nested)
                    # El hijo real hereda el marcador y no se bloquea a sí mismo.
                    code = (
                        "import sys; sys.path.insert(0, sys.argv[1]); "
                        "from action_ledger import browser_session; "
                        "c = browser_session(wait_minutes=0, directory=sys.argv[2]); "
                        "v = c.__enter__(); print('delegated' if v is None else 'unexpected'); "
                        "c.__exit__(None, None, None)"
                    )
                    proc = subprocess.run(
                        [sys.executable, "-c", code, str(pathlib.Path(al.__file__).parent), d],
                        capture_output=True, text=True, timeout=15,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(proc.stdout.strip(), "delegated")

    def test_process_environment_flag_cannot_bypass_turn_in_another_thread(self):
        with tempfile.TemporaryDirectory() as d:
            with al.browser_session(wait_minutes=0, directory=d):
                marker = {
                    "RRSS_BROWSER_LOCK_HELD": "edge_browser",
                    "RRSS_BROWSER_LOCK_OWNER_PID": str(os.getpid()),
                }
                with mock.patch.dict(os.environ, marker):
                    results = []

                    def other_thread():
                        try:
                            with al.browser_session(wait_minutes=0, directory=d):
                                results.append("incorrectly_entered")
                        except al.RoundBusy:
                            results.append("busy")

                    thread = threading.Thread(target=other_thread)
                    thread.start()
                    thread.join(timeout=10)
                    self.assertFalse(thread.is_alive())
                    self.assertEqual(results, ["busy"])

    def test_legacy_marker_without_owner_is_not_proof_of_holding_the_lock(self):
        with tempfile.TemporaryDirectory() as d:
            with al.exclusive("edge_browser", directory=d):
                with mock.patch.dict(os.environ, {
                    "RRSS_BROWSER_LOCK_HELD": "edge_browser",
                }, clear=True):
                    with self.assertRaises(al.RoundBusy):
                        with al.browser_session(wait_minutes=0, directory=d):
                            self.fail("marcador heredado sin prueba de propietario")

    def test_parent_marker_after_release_does_not_bypass_new_acquisition(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {
                "RRSS_BROWSER_LOCK_HELD": "edge_browser",
                "RRSS_BROWSER_LOCK_OWNER_PID": str(os.getpid()),
            }):
                with al.browser_session(wait_minutes=0, directory=d) as path:
                    self.assertIsNotNone(path)

    def test_child_does_not_trust_live_pid_when_os_guard_is_free(self):
        with tempfile.TemporaryDirectory() as d:
            lock = pathlib.Path(d) / "rrss_lock_edge_browser.lock"
            lock.write_text(f"{os.getpid()} 1", encoding="utf-8")
            env = {**os.environ,
                   "RRSS_BROWSER_LOCK_HELD": "edge_browser",
                   "RRSS_BROWSER_LOCK_OWNER_PID": str(os.getpid())}
            script = (
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "from action_ledger import _delegated_browser_owner; "
                "print(_delegated_browser_owner('edge_browser', sys.argv[2]))"
            )
            result = subprocess.run(
                [sys.executable, "-c", script, str(pathlib.Path(al.__file__).parent), d],
                env=env, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "False")

    def test_zero_wait_never_sleeps_even_if_wall_clock_does_not_advance(self):
        with tempfile.TemporaryDirectory() as d:
            with al.exclusive("edge_browser", directory=d):
                with mock.patch.object(al.time, "time", return_value=1000):
                    with mock.patch.object(al.time, "sleep",
                                           side_effect=AssertionError("espera indebida")):
                        with self.assertRaises(al.RoundBusy):
                            with al.browser_session(wait_minutes=0, directory=d):
                                self.fail("adquirió Edge con guard ocupado")

    def test_gives_up_after_the_deadline(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with al.exclusive("edge_browser", directory=d):
                with self.assertRaises(al.RoundBusy):
                    with al.browser_session(wait_minutes=0, directory=d):
                        pass

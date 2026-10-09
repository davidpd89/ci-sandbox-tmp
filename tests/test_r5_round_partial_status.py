"""R5/F16: una ronda con acciones confirmadas y error parcial no es 'ok'.

Casos derivados del comportamiento observado el 08/10/2026. Sin acceso a cuentas:
se simula subprocess.run y se escribe el CSV en un directorio temporal.
La prueba debe FALLAR contra el clasificador anterior.
"""
import csv
import datetime
import os
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import round_queue as q


class RoundPartialStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_log = q.LOG
        q.LOG = os.path.join(self.temp.name, "tiempos.csv")

    def tearDown(self):
        q.LOG = self.old_log
        self.temp.cleanup()

    def simulate(self, *, returncode, confirmed, skipped=0, failed=0, message=""):
        summary = (f"[mastodon] {confirmed} confirmadas {{'like': {confirmed}}}, "
                   f"{skipped} saltadas, {failed} fallos")
        process = SimpleNamespace(
            returncode=returncode, stdout=summary + "\n" + message, stderr=""
        )
        with mock.patch.object(q.subprocess, "run", return_value=process):
            state = q.run_round("mastodon")
        with open(q.LOG, encoding="utf-8", newline="") as stream:
            row = list(csv.DictReader(stream))[-1]
        return state, row

    def test_nonzero_exit_with_confirmations_is_partial_not_ok(self):
        state, row = self.simulate(returncode=2, confirmed=39, skipped=5)
        self.assertEqual(state, "parcial")
        self.assertEqual(row["estado"], "parcial")
        # Contrato CSV legado: desglose por clase de acción, NO total plano.
        self.assertEqual(row["confirmadas"], "{'like': 39}")
        self.assertEqual(row["codigo"], "2")

    def test_success_exit_with_confirmations_and_failures_is_partial(self):
        state, row = self.simulate(returncode=0, confirmed=8, failed=2)
        self.assertEqual(state, "parcial")
        self.assertEqual(row["fallos"], "2")

    def test_zero_confirmed_and_failures_is_error_even_if_process_says_zero(self):
        state, _ = self.simulate(returncode=0, confirmed=0, failed=3)
        self.assertEqual(state, "error")

    def test_all_skipped_is_not_recorded_as_success(self):
        state, _ = self.simulate(returncode=0, confirmed=0, skipped=12)
        self.assertEqual(state, "saltada")

    def test_clean_execution_with_confirmations_is_ok(self):
        state, _ = self.simulate(returncode=0, confirmed=12, skipped=3, failed=0)
        self.assertEqual(state, "ok")

    def test_partial_is_counted_as_work_done_on_resume_not_repeated(self):
        self.simulate(returncode=2, confirmed=39)
        done = q.done_today(datetime.date.today())
        self.assertEqual(done.get("mastodon"), 1)

    def test_spaced_chain_does_not_repeat_partially_completed_round(self):
        until = datetime.datetime.now() + datetime.timedelta(minutes=1)
        with mock.patch.object(q, "run_round", return_value="parcial") as run:
            with mock.patch.object(q, "control_signal", return_value=None):
                with mock.patch.object(q, "budget_left", return_value=0):
                    with mock.patch.object(q, "nap", return_value=None):
                        q.spaced_chain("mastodon", until, target=1, done_count=0,
                                       label="mastodon")
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()

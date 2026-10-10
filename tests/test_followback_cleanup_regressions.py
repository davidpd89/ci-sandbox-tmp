"""Regresiones de la propuesta de unfollow; todas las entradas son ficticias."""
import datetime as dt
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import unfollow_cleanup as uc
import follow_review as fr

NOW = dt.date(2026, 10, 10)


def event(account, on="2026-09-01", kind="follow"):
    return {"fecha": on, "cuenta": account, "tipo": kind, "resultado": "confirmado"}


class CleanupCandidateRegressionTests(unittest.TestCase):
    def test_old_ledger_follow_not_in_current_following_is_not_offered(self):
        with mock.patch.object(uc, "protected_accounts", return_value=set()):
            picked = uc.candidates([event("@ana")], [], NOW, following={},
                                   network="bluesky")
        self.assertEqual(picked, [])

    def test_protected_accounts_are_excluded_from_both_candidate_routes(self):
        bio = "Schreibt Fantasy und Science Fiction. Hat Ahnung von Büchern."
        with mock.patch.object(uc, "protected_accounts", return_value={"ana"}):
            result = uc.candidates([event("@ana")], [], NOW,
                                   following={"ana": bio}, network="bluesky")
        self.assertEqual(result, [])

    def test_federated_names_not_confused_between_servers(self):
        one, two = "ana@example.com", "ana@example.org"
        with mock.patch.object(uc, "protected_accounts", return_value=set()):
            picked = uc.candidates([event("@" + one)], [two], NOW,
                                   following={one: ""}, network="mastodon")
        self.assertEqual([c["account"] for c in picked], [one])
        # Un registro de ana@uno no hace unfollow a ana@dos.
        with mock.patch.object(uc, "protected_accounts", return_value=set()):
            missing = uc.candidates([event("@" + one)], [], NOW,
                                    following={two: ""}, network="mastodon")
        self.assertEqual(missing, [])

    def test_mastodon_exact_positive_prevents_cleanup(self):
        with mock.patch.object(uc, "protected_accounts", return_value=set()):
            out = uc.candidates([event("@ana@example.com")], ["ana@example.com"],
                                NOW, following={"ana@example.com": ""},
                                network="mastodon")
        self.assertEqual(out, [])

    def test_engaged_account_stays_out_after_seven_days(self):
        rows = [event("@ana"), event("@ana", "2026-09-03", "reply")]
        with mock.patch.object(uc, "protected_accounts", return_value=set()):
            out = uc.candidates(rows, [], NOW, following={"ana": ""},
                                network="bluesky")
        self.assertEqual(out, [])

    def test_first_follow_after_unfollow_resets_elapsed_days(self):
        rows = [event("ana", "2026-09-01"),
                event("ana", "2026-09-04", "unfollow"),
                event("ana", "2026-10-08", "follow")]
        out = fr.review(rows, [], NOW, days=7, network="mastodon")
        self.assertEqual(out, [])

    def test_already_unfollowed_marker_closes_the_old_cycle(self):
        rows = [event("ana", "2026-09-01"),
                {**event("ana", "2026-09-02", "unfollow"),
                 "resultado": "saltado_ya_no_seguido"}]
        self.assertEqual(fr.review(rows, [], NOW, days=7, network="mastodon"), [])
        with mock.patch.object(uc, "protected_accounts", return_value=set()):
            self.assertEqual(uc.candidates(rows, [], NOW,
                                           following={"ana": ""}, network="mastodon"), [])

    def test_mastodon_ids_do_not_fallback_to_other_servers(self):
        adapter = uc.Mastodon()
        adapter.ids = {"ana@example.com": "remote-one", "ana": "local"}
        self.assertEqual(adapter._id("ana@example.com"), "remote-one")
        self.assertEqual(adapter._id("ana"), "local")
        self.assertIsNone(adapter._id("ana@example.org"))


if __name__ == "__main__":
    unittest.main()

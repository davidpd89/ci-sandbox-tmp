"""Only synthetic adapters; source assertions are not live verification."""
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from native_alias_observations import NATIVE_RULES, ingest_observations
from stable_account_aliases import AliasError, AliasTimeline, NETWORKS


class NativeAliasAdapters(unittest.TestCase):
    def fixture(self, net, queue):
        handle, remote_id, flag, _ = NATIVE_RULES[net]
        row = {"network": net, "evidence_id": "obs-"+net+"-"+queue,
               "observed_at": "2026-10-10T04:00:00Z", "queue": queue,
               "source": "synthetic-"+net, "proof": "native-profile-id"}
        row[handle] = "writer@example.org" if net == "mastodon" else "writer"
        row[remote_id] = ("did:plc:abcdefghijklmnopqrstuvwx" if net == "bluesky"
                          else "https://example.org/users/writer" if net == "mastodon" else "123456")
        row[flag] = True
        return row

    def test_nine_networks_three_queues(self):
        self.assertEqual(set(NATIVE_RULES), NETWORKS)
        for net in NETWORKS:
            timeline = AliasTimeline()
            for queue in ("WEB", "API", "MOBILE"):
                with self.subTest(net=net, queue=queue):
                    r = ingest_observations(net, [self.fixture(net, queue)], timeline=timeline)
                    self.assertEqual(r["diagnostics"], [])
                    self.assertEqual(len(r["accepted"]), 1)
            self.assertEqual(len(timeline.evidence), 3)

    def test_unverified_and_unsupported_never_assumed(self):
        for net in NETWORKS:
            row = self.fixture(net, "API")
            row[NATIVE_RULES[net][2]] = "true"
            r = ingest_observations(net, [row])
            self.assertFalse(r["accepted"])
            self.assertEqual(r["diagnostics"][0]["reason"], "native_identity_not_verified")
        with self.assertRaises(AliasError):
            ingest_observations("unknown", [])

    def test_required_fields_wrong_network_and_nonmapping(self):
        a = self.fixture("bluesky", "API")
        b = dict(a, network="x", evidence_id="other")
        del a["proof"]
        r = ingest_observations("bluesky", [a, b, None])
        self.assertEqual([x["reason"] for x in r["diagnostics"]],
                         ["missing_required_field", "network_mismatch", "row_invalid"])

    def test_replay_and_collision(self):
        a = self.fixture("bluesky", "WEB")
        r = ingest_observations("bluesky", [a, a])
        self.assertEqual(len(r["timeline"].evidence), 1)
        self.assertEqual(len(r["accepted"]), 2)
        b = dict(a, handle="impostor")
        after = ingest_observations("bluesky", [b], timeline=r["timeline"])
        self.assertEqual(after["diagnostics"][0]["reason"], "evidence_id_collision")

    def test_failure_does_not_echo_proof_or_mutate(self):
        a = self.fixture("threads", "MOBILE")
        a["proof"] = "opaque-sensitive-synthetic-string"
        a["remote_account_id"] = "broken value"
        old = dict(a)
        r = ingest_observations("threads", [a])
        self.assertEqual(a, old)
        self.assertNotIn("opaque-sensitive", str(r["diagnostics"]))


if __name__ == "__main__":
    unittest.main()

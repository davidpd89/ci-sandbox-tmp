"""Pruebas sintéticas y sin conectividad: puentes #108."""
import json
import unittest
from tools.native_relationship_evidence_bridge import Batch, NETWORK_QUEUES, availability, bridge_results, bridge_snapshot

class Sink:
    def __init__(self):
        self.items = {}
        self.snapshots = []
    def append_many(self, events):
        incoming = {}
        for event in events:
            key = (event["network"], event["source"], event["source_id"])
            if key in self.items and self.items[key] != event:
                raise ValueError("conflict")
            incoming[key] = event
        count = sum(k in self.items for k in incoming)
        self.items.update(incoming)
        return {"inserted": len(incoming) - count, "replayed": count}
    def reconcile_followers(self, **kwargs):
        self.snapshots.append(kwargs)
        subjects = set(kwargs["tracked"])
        present = set(kwargs["followers"])
        events = [dict(network=kwargs["network"], source=kwargs["source"],
                       source_id=kwargs["snapshot_id"] + ":" + s,
                       outcome="present" if s in present else "absent")
                  for s in subjects if s in present or kwargs["complete"]]
        return {**self.append_many(events),
                "unknown": len(subjects - present) if not kwargs["complete"] else 0}

def row(**updates):
    x = dict(record_id="1", kind="follow", handle="@autora", resultado="confirmado",
             occurred_at="2026-10-10T09:00:00Z")
    x.update(updates)
    return x

def ack(queue, **updates):
    x = dict(id="ack1", kind="follow", target="@autora",
             basis={"WEB": "ui_state", "API": "api_response",
                    "MOBILE": "mobile_observed"}[queue])
    x.update(updates)
    return x

class EvidenceTest(unittest.TestCase):
    def test_all_nine_producers_and_queues(self):
        self.assertEqual(len(NETWORK_QUEUES), 9)
        self.assertEqual({a["queue"] for a in availability()}, {"WEB", "API", "MOBILE"})
        for spec in availability():
            b = Batch(spec["network"], spec["queue"], spec["producer"], "exp")
            s = Sink()
            result = bridge_results(s, b, [row(ack=ack(b.queue), reservation_id="res1")])
            self.assertEqual(result["inserted"], 1, spec)
            event = next(iter(s.items.values()))
            self.assertEqual(event["outcome"], "confirmed")
            self.assertEqual(event["correlation_id"], "reserve:res1|ack:ack1")

    def test_wrong_queue(self):
        with self.assertRaises(ValueError):
            bridge_results(Sink(), Batch("x", "MOBILE", "x_execute.run_plan", "exp"), [])

    def test_success_without_ack_is_not_success(self):
        s = Sink()
        b = Batch("x", "WEB", "x_execute.run_plan", "exp")
        self.assertEqual(bridge_results(s, b, [row()])["downgraded_no_ack"], 1)
        self.assertEqual(next(iter(s.items.values()))["outcome"], "unverified")
        self.assertEqual(bridge_results(s, b, [row(ack=ack("WEB"))])["inserted"], 1)
        self.assertEqual(bridge_results(s, b, [row(ack=ack("WEB"))])["replayed"], 1)
        self.assertEqual({v["outcome"] for v in s.items.values()},
                         {"unverified", "confirmed"})

    def test_bad_ack(self):
        b = Batch("x", "WEB", "x_execute.run_plan", "exp")
        for bad in [ack("API"), ack("WEB", target="@otra"),
                    ack("WEB", kind="reply")]:
            s = Sink()
            bridge_results(s, b, [row(ack=bad)])
            self.assertEqual(next(iter(s.items.values()))["outcome"], "unverified")

    def test_no_false_outcomes(self):
        s = Sink()
        b = Batch("x", "WEB", "x_execute.run_plan", "exp")
        labels = ["saltado_ya_seguido", "saltado_otra",
                  "pendiente_verificacion", "incierto:sin_ack",
                  "no_intentado", "fallo:401", "pendiente_aprobacion"]
        expected = ["observed", "skipped", "uncertain", "uncertain",
                    "skipped", "failed", "uncertain"]
        bridge_results(s, b, [row(record_id=str(i), resultado=v)
                              for i, v in enumerate(labels)])
        self.assertEqual([next(v["outcome"] for v in s.items.values()
                         if json.loads(v["source_id"]) == ["exp", str(i), "result", None])
                         for i in range(len(labels))], expected)

    def test_missing_source_unknown(self):
        s = Sink()
        b = Batch("reddit", "WEB", "reddit_execute.run_plan", "exp")
        r = bridge_results(s, b, [row(record_id=None), row(handle=None),
                                  row(kind="plan"), row(resultado="???")])
        self.assertEqual(r["unknown"], 4)
        self.assertFalse(s.items)

    def test_partial_complete_and_aggregate(self):
        b = Batch("tiktok", "MOBILE", "tiktok_mobile_execute.run_plan", "exp")
        s = Sink()
        snap = dict(snapshot_id="s1", observed_at="2026-10-10T09:00:00Z",
                    tracked=["one", "two"], followers=["one"],
                    coverage=dict(identity_stable=True, complete=True,
                                  all_pages=False, account_scope="self"))
        self.assertEqual(bridge_snapshot(s, b, snap)["unknown"], 1)
        self.assertEqual({x["outcome"] for x in s.items.values()}, {"present"})
        snap["snapshot_id"] = "s2"
        snap["coverage"]["all_pages"] = True
        self.assertEqual(bridge_snapshot(s, b, snap)["unknown"], 0)
        self.assertEqual({x["outcome"] for x in s.items.values()}, {"present", "absent"})
        p = Batch("pinterest", "API", "pinterest_loyalty_observations", "exp")
        self.assertEqual(bridge_snapshot(Sink(), p,
                         dict(tracked=["one"], followers_count=20))["unknown"], 1)

if __name__ == "__main__":
    unittest.main()

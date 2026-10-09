import pathlib
import random
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import tiktok_behavior as tb
import tiktok_human as th


class FakeClient:
    def __init__(self):
        self.calls = []

    def tap(self, x, y, device_id=None):
        self.calls.append(("tap", x, y))

    def swipe(self, x1, y1, x2, y2, *, duration_ms=None, device_id=None):
        self.calls.append(("swipe", x1, y1, x2, y2, duration_ms))

    def type_text(self, text, device_id=None):
        self.calls.append(("text", text))

    def _device(self, device_id):
        return "dev"

    def _rpc(self, method, params):
        self.calls.append((method, params))


def apply_plan(plan):
    buffer = ""
    for kind, value in plan:
        if kind == "text":
            buffer += value
        elif kind == "backspace":
            buffer = buffer[: len(buffer) - value]
    return buffer


class TypingTests(unittest.TestCase):
    TEXT = "Un libro en un mes me parece una locura preciosa. ¿Cuántas palabras escribías al día? 😅"

    def test_typing_plan_always_reproduces_the_exact_text(self):
        for seed in range(60):
            client = th.HumanClient(FakeClient(), th.HumanProfile(typo_rate=0.5),
                                    random.Random(seed), sleep=lambda s: None)
            self.assertEqual(apply_plan(client._typing_plan(self.TEXT)), self.TEXT, seed)

    def test_typing_is_chunked_not_all_at_once_and_has_pauses(self):
        client = th.HumanClient(FakeClient(), th.HumanProfile(), random.Random(1), sleep=lambda s: None)
        plan = client._typing_plan(self.TEXT)
        chunks = [v for k, v in plan if k == "text"]
        self.assertGreater(len(chunks), 15)
        self.assertTrue(all(len(c) <= 6 for c in chunks))
        self.assertTrue(any(k == "pause" for k, _ in plan))

    def test_typos_use_backspace(self):
        client = th.HumanClient(FakeClient(), th.HumanProfile(typo_rate=1.0), random.Random(3),
                                sleep=lambda s: None)
        plan = client._typing_plan("palabras largas siempre")
        self.assertTrue(any(k == "backspace" for k, _ in plan))

    def test_off_profile_types_in_one_call(self):
        raw = FakeClient()
        client = th.HumanClient(raw, th.HumanProfile.off(), random.Random(1), sleep=lambda s: None)
        client.type_text("hola mundo")
        self.assertEqual(raw.calls, [("text", "hola mundo")])


class GestureTests(unittest.TestCase):
    def test_taps_are_jittered_but_bounded(self):
        raw = FakeClient()
        client = th.HumanClient(raw, th.HumanProfile(), random.Random(7), sleep=lambda s: None)
        for _ in range(200):
            client.tap(500, 1000)
        xs = {c[1] for c in raw.calls}
        self.assertGreater(len(xs), 5)
        self.assertTrue(all(abs(c[1] - 500) <= 16 and abs(c[2] - 1000) <= 16 for c in raw.calls))

    def test_swipes_vary_duration_and_drift(self):
        raw = FakeClient()
        client = th.HumanClient(raw, th.HumanProfile(), random.Random(9), sleep=lambda s: None)
        for _ in range(30):
            client.swipe(540, 1800, 540, 700)
        self.assertGreater(len({c[5] for c in raw.calls}), 10)
        self.assertGreater(len({c[3] for c in raw.calls}), 10)

    def test_unknown_attributes_delegate_to_client(self):
        raw = FakeClient()
        raw.extra = lambda: "ok"
        self.assertEqual(th.HumanClient(raw).extra(), "ok")


class PaceTests(unittest.TestCase):
    def test_gaps_are_variable_and_loosen_with_fatigue(self):
        pace = th.Pace(rng=random.Random(2))
        early = [pace.action_gap() for _ in range(200)]
        pace.actions = 150
        late = [pace.action_gap() for _ in range(200)]
        self.assertGreater(len(set(round(g) for g in early)), 20)
        self.assertGreater(sum(late) / 200, sum(early) / 200)

    def test_micro_breaks_happen(self):
        pace = th.Pace(rng=random.Random(4))
        breaks = [pace.register_action() for _ in range(60)]
        self.assertGreaterEqual(len([b for b in breaks if b]), 3)

    def test_dwell_mixes_skips_and_long_watches(self):
        pace = th.Pace(rng=random.Random(5))
        kinds = {pace.video_dwell()[0] for _ in range(300)}
        self.assertEqual(kinds, {"skip", "short", "watch", "long"})


class BehaviorTests(unittest.TestCase):
    def test_before_like_always_watches_a_few_seconds(self):
        slept = []

        class A:
            client = FakeClient()
            device = type("D", (), {"id": "x"})()

        beh = tb.Behavior(A(), th.Pace(rng=random.Random(1)), random.Random(1), sleep=slept.append)
        for _ in range(50):
            beh.before_like()
        self.assertTrue(all(s >= 3.0 for s in slept))


if __name__ == "__main__":
    unittest.main()

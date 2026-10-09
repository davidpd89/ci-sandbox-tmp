"""R1 / F11: regresiones del autor None que anuló el filtro de Mastodon.

Los ejemplos reproducen *estructuras de salida* de bluesky_growth_scan y
mastodon_growth_scan; NO contienen cuentas ni datos reales.
"""
import pathlib
import io
import json
import tempfile
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import api_comment_writer as acw


TEXT = "Leyendo fantasía juvenil y comparando sagas diferentes con los amigos de toda la vida."


def _post(post_id):
    status_id = str(100000 + sum((n + 1) * ord(ch) for n, ch in enumerate(post_id)))
    return {"id": post_id, "status_id": status_id,
            "uri": f"at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/{post_id}",
            "url": f"https://bsky.app/profile/lectora.bsky.social/post/{post_id}",
            "text": TEXT, "es": True, "actions": ["reply"]}


class CandidateIdentityContractTests(unittest.TestCase):
    def test_mastodon_must_use_acct_not_handle_when_both_exist(self):
        state = {"shortlist": [{"acct": "lector@otra-instancia.social",
                               "handle": "cuenta_equivocada", "score": 1,
                               "posts": [_post("post-1")]}]}
        items = acw.pick_posts(state, 10, network="mastodon")
        self.assertEqual(items[0]["author"], "lector@otra-instancia.social")

    def test_bluesky_requires_handle_and_does_not_fall_back_to_mastodon_acct(self):
        events = []
        state = {"shortlist": [
            {"acct": "no-es-un-handle", "posts": [_post("p1")], "score": 10},
            {"handle": "lectora.bsky.social", "posts": [_post("p2")], "score": 5},
        ]}
        items = acw.pick_posts(state, 10, network="bluesky", log=events.append)
        self.assertEqual([item["id"] for item in items], ["p2"])
        self.assertEqual(items[0]["author"], "lectora.bsky.social")
        self.assertTrue(any("IDENTIDAD_INVALIDA" in line for line in events))

    def test_mastodon_author_none_must_warn_but_not_kill_healthy_items(self):
        warnings = []
        state = {"shortlist": [
            {"posts": [_post("bad")], "score": 10},
            {"acct": "otra@ejemplo.social", "posts": [_post("ok")], "score": 5},
        ]}
        items = acw.pick_posts(state, 10, network="mastodon", log=warnings.append)
        self.assertEqual([r["id"] for r in items], ["ok"])
        self.assertEqual(sum("IDENTIDAD_INVALIDA" in warning for warning in warnings), 1)
        self.assertIn("IDENTIDAD_INVALIDA", warnings[0])

    def test_missing_network_warns_that_inference_is_legacy_only(self):
        notices = []
        acw.pick_posts({"shortlist": [{"acct": "ana@ejemplo.social", "score": 1,
                                       "posts": [_post("p1")]}]}, 3, log=notices.append)
        self.assertTrue(any("RED_INFERIDA_COMPATIBILIDAD" in note for note in notices))

    def test_invalid_candidates_emit_aggregate_count_and_allow_valid(self):
        notices = []
        state = {"shortlist": [
            {"score": 2, "posts": [_post("p1")]},
            {"acct": "ana@ejemplo.social", "score": 1, "posts": [_post("p2")]}
        ]}
        kept = acw.pick_posts(state, 3, network="mastodon", log=notices.append)
        self.assertEqual(len(kept), 1)
        self.assertTrue(any("candidatos_o_posts_invalidos=1" in x for x in notices))

    def test_non_string_id_cannot_escape_contract(self):
        warnings = []
        state = {"shortlist": [
            {"acct": ["incorrecto"], "posts": [_post("bad")], "score": 2},
            {"acct": "lectora@ejemplo.social", "posts": [_post("ok")], "score": 1},
        ]}
        items = acw.pick_posts(state, 10, network="mastodon", log=warnings.append)
        self.assertEqual([r["id"] for r in items], ["ok"])
        self.assertEqual(sum("IDENTIDAD_INVALIDA" in warning for warning in warnings), 1)

    def test_invalid_post_id_skipped_without_stopping_valid_candidate(self):
        warnings = []
        state = {"shortlist": [
            {"acct": "primera@ejemplo.social", "posts": [{"text": TEXT, "actions": ["reply"], "es": True}], "score": 2},
            {"acct": "segunda@ejemplo.social", "posts": [_post("ok")], "score": 1},
        ]}
        items = acw.pick_posts(state, 10, network="mastodon", log=warnings.append)
        self.assertEqual([r["id"] for r in items], ["ok"])
        self.assertTrue(any("POST_INVALIDO" in line for line in warnings))

    def test_contract_only_for_wired_api_scanners(self):
        from candidate_identity import resolve_author
        samples = {
            "bluesky": {"handle": "lectora.bsky.social"},
            "mastodon": {"acct": "lectora@ejemplo.social"},
        }
        for network, row in samples.items():
            with self.subTest(network=network):
                self.assertEqual(resolve_author(network, row), next(iter(row.values())))
                with self.assertRaises(ValueError):
                    resolve_author(network, {})
        for network in ("x", "threads", "facebook", "pinterest", "reddit", "tiktok"):
            with self.subTest(network=network):
                with self.assertRaisesRegex(ValueError, "red_no_admitida"):
                    resolve_author(network, {"handle": "ficticia"})

    def test_scanner_output_shapes_anonymised_from_source_code(self):
        # Esquemas extraídos de _build_output en los scanners API: el
        # repositorio NO contiene una snapshot real que permita afirmar
        # que este fixture proceda de un candidato real.
        fixtures = {
            "mastodon": {"id": "M001", "acct": "lectora@instancia.ejemplo",
                         "account_id": "123", "score": 9, "bio": "fantasía",
                         "posts": [_post("M001-P1")]},
            "bluesky": {"id": "B001", "handle": "lectora.bsky.social",
                        "score": 9, "profile": {"bio": "fantasía"},
                        "posts": [_post("B001-P1")]},
        }
        for network, candidate in fixtures.items():
            with self.subTest(network=network):
                items = acw.pick_posts({"shortlist": [candidate]}, 3, network=network)
                self.assertEqual(items[0]["author"], candidate["acct" if network == "mastodon" else "handle"])


    def test_real_main_wires_network_and_uses_remote_post_reference(self):
        # Simula el formato real del scan sin contactar redes ni encolar.
        for network, field in (("bluesky", "handle"), ("mastodon", "acct")):
            with self.subTest(network=network), tempfile.TemporaryDirectory() as folder:
                row = {"id": "G001" if network == "bluesky" else "M001",
                       field: "lectora.bsky.social" if network == "bluesky" else "lectora@instancia.social",
                       "score": 3, "posts": [_post("P1")]}
                cfg = acw.NETWORKS[network]
                with open(pathlib.Path(folder) / cfg["state"], "w", encoding="utf-8") as stream:
                    json.dump({"shortlist": [row]}, stream)
                stdout = io.StringIO()
                with mock.patch.object(acw, "ROOT", folder), mock.patch.object(
                    acw.rq, "get_or_enqueue", return_value={}
                ) as queue, mock.patch.dict(sys.modules, {"reply_hold": SimpleNamespace(held=lambda: False)}):
                    with redirect_stdout(stdout):
                        self.assertEqual(acw.main([network, "--reset"]), 0)
                self.assertNotIn("RED_INFERIDA_COMPATIBILIDAD", stdout.getvalue())
                self.assertEqual(queue.call_args.args[0][0]["post_uri"],
                                 _post("P1")["uri" if network == "bluesky" else "status_id"])


    def test_malformed_score_and_posts_do_not_kill_healthy_candidates(self):
        notes = []
        state = {"shortlist": [
            None, {"acct": "rota@ejemplo.social", "score": "no-numero", "posts": "basura"},
            {"acct": "bien@ejemplo.social", "score": float("nan"), "posts": [_post("sano")]},
        ]}
        items = acw.pick_posts(state, 4, network="mastodon", log=notes.append)
        self.assertEqual([i["id"] for i in items], ["sano"])
        self.assertTrue(any("POST_INVALIDO" in n for n in notes))
        self.assertTrue(any("IDENTIDAD_INVALIDA" in n for n in notes))

    def test_post_requires_stable_remote_reference(self):
        for network, field in (("bluesky", "handle"), ("mastodon", "acct")):
            notes = []
            state = {"shortlist": [{field: "lectora.bsky.social" if network == "bluesky" else "ana@ejemplo.social",
                                    "score": 1, "posts": [{"id": "P1", "text": TEXT, "actions": ["reply"]}]}]}
            self.assertEqual(acw.pick_posts(state, 2, network=network, log=notes.append), [])
            self.assertTrue(any("POST_INVALIDO" in n for n in notes))

    def test_stable_account_keys_differ_from_visible_handles(self):
        from candidate_identity import resolve_stable_account
        self.assertEqual(resolve_stable_account("bluesky",
                          {"handle": "antes.bsky.social", "did": "did:plc:abcdefgh"}),
                         resolve_stable_account("bluesky",
                          {"handle": "ahora.bsky.social", "did": "did:plc:abcdefgh"}))
        self.assertNotEqual(resolve_stable_account("mastodon", {"instance": "mastodon.social", "account_id": "12"}),
                            resolve_stable_account("mastodon", {"instance": "otra.social", "account_id": "12"}))


    def test_plan_rejects_id_reused_for_different_post(self):
        import bluesky_build_plan as blue
        import mastodon_build_plan as mast
        for net, builder, kind, cid in (
            ("bluesky", blue.build, "like", "G001"),
            ("mastodon", mast.build, "favourite", "M001"),
        ):
            with self.subTest(network=net):
                post = _post(f"{cid}-P1")
                post["actions"] = [kind]
                post["sources"] = []
                scan = {"shortlist": [{"id": cid, "handle": "lectora.bsky.social",
                                       "acct": "lectora@ejemplo.social",
                                       "posts": [post]}]}
                ref = post["uri" if net == "bluesky" else "status_id"]
                decision = {"actions": [{"kind": kind, "post": post["id"], "post_uri": ref}]}
                self.assertEqual(len(builder(scan, decision)), 1)
                decision["actions"][0]["post_uri"] = "otro-destino"
                with self.assertRaisesRegex(ValueError, "referencia remota distinta"):
                    builder(scan, decision)

    def test_legacy_without_network_preserves_old_readers_not_production(self):
        for field, value in (("handle", "a"), ("acct", "ana@masto.es")):
            with self.subTest(field=field):
                notices = []
                state = {"shortlist": [{field: value, "score": 2,
                                       "posts": [{"id": "legado-P1", "text": TEXT, "actions": ["reply"]}]}]}
                items = acw.pick_posts(state, 3, log=notices.append)
                self.assertEqual(items[0]["author"], value)
                self.assertIsNone(items[0]["post_uri"])
                self.assertTrue(any("RED_INFERIDA_COMPATIBILIDAD" in note for note in notices))
                notes = []
                explicit = "bluesky" if field == "handle" else "mastodon"
                self.assertEqual(acw.pick_posts(state, 3, network=explicit, log=notes.append), [])
                self.assertTrue(any("POST_INVALIDO" in n or "IDENTIDAD_INVALIDA" in n for n in notes))


if __name__ == "__main__":
    unittest.main()

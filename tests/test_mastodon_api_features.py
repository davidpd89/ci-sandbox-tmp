"""Mastodon API: discovery e interacción segura; sin red real."""
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

# Usar el paquete HTTP real; los tests mockean sus puntos de entrada.
# Inyectar x_interact solo durante la importación, sin contaminar otras suites.
import requests  # noqa: F401

x_stub = types.ModuleType("x_interact")
x_stub._check_spanish_orthography = lambda text: None
with patch.dict(sys.modules, {"x_interact": x_stub}):
    import mastodon_interact as m
    import mastodon_execute as execute


class MastodonSearchTests(unittest.TestCase):
    def test_search_v2_params_and_limit(self):
        captured = {}
        with patch.object(
            m,
            "_get_v2",
            side_effect=lambda path, params: captured.update(
                {"path": path, "params": params}
            ) or {"accounts": [], "hashtags": [], "statuses": []},
        ):
            m.search(
                "fantasía",
                "statuses",
                999,
                resolve=True,
                account_id="42",
            )
        self.assertEqual(captured["path"], "search")
        self.assertEqual(captured["params"]["type"], "statuses")
        self.assertEqual(captured["params"]["limit"], 40)
        self.assertEqual(captured["params"]["resolve"], "true")
        self.assertEqual(captured["params"]["account_id"], "42")

    def test_remote_status_url_is_resolved_not_numeric_tail_reused(self):
        remote = "https://example.social/@lectora/999999"
        with patch.object(
            m,
            "search",
            return_value={
                "statuses": [{"id": "12345", "url": remote, "uri": remote}]
            },
        ):
            self.assertEqual(m._status_id(remote), "12345")

        self.assertEqual(
            m._status_id("https://mastodon.social/@lectora/777"),
            "777",
        )

        with patch.object(m, "search", return_value={"statuses": []}), \
             self.assertRaisesRegex(RuntimeError, "univoca"):
            m._status_id("https://mastodon.social.evil.example/@x/777")

    def test_hashtag_combination_is_forwarded_and_path_is_encoded(self):
        captured = {}
        class Response:
            status_code = 200
            headers = {}
            text = ""
            def json(self):
                return []
        with patch.object(
            m,
            "_get_response",
            side_effect=lambda url, params: captured.update(
                {"path": url.split("/api/v1/", 1)[1], "params": params}
            ) or Response(),
        ):
            m.get_hashtag_statuses(
                "#Bookstodon/../otro",
                any_tags=["Fantasy", "#Reading"],
                all_tags=["Books"],
                none_tags=["politics"],
                local=True,
                only_media=True,
            )
        self.assertEqual(
            captured["path"],
            "timelines/tag/Bookstodon%2F..%2Fotro",
        )
        self.assertEqual(
            captured["params"]["any[]"],
            ["Fantasy", "Reading"],
        )
        self.assertEqual(captured["params"]["all[]"], ["Books"])
        self.assertEqual(captured["params"]["none[]"], ["politics"])
        self.assertEqual(captured["params"]["local"], "true")
        self.assertEqual(captured["params"]["only_media"], "true")

    def test_list_id_is_encoded_as_one_path_segment(self):
        with patch.object(m, "_get", return_value=[]) as get:
            m.list_timeline("../accounts/1")
        get.assert_called_once_with(
            "timelines/list/..%2Faccounts%2F1",
            {"limit": 20},
        )


class MastodonIdentityTests(unittest.TestCase):
    def setUp(self):
        m._IDENTITY_VERIFIED = False

    def test_every_post_write_requires_expected_account_first(self):
        class Response:
            status_code = 200
            text = ""
            def json(self):
                return {"following": True}

        calls = []
        with patch.object(
            m,
            "_assert_expected_account",
            side_effect=lambda: calls.append("identity"),
        ), patch.object(
            m,
            "_headers",
            return_value={"Authorization": "Bearer SECRET"},
        ), patch.object(
            m.requests,
            "post",
            side_effect=lambda *a, **k: calls.append("post") or Response(),
        ):
            m._post("accounts/1/follow")
        self.assertEqual(calls, ["identity", "post"])

    def test_delete_requires_expected_account_first(self):
        class Response:
            status_code = 200
            text = ""
            def json(self):
                return {}

        calls = []
        with patch.object(
            m,
            "_assert_expected_account",
            side_effect=lambda: calls.append("identity"),
        ), patch.object(
            m,
            "_headers",
            return_value={"Authorization": "Bearer SECRET"},
        ), patch.object(
            m.requests,
            "delete",
            side_effect=lambda *a, **k: calls.append("delete") or Response(),
        ):
            m._delete("statuses/1")
        self.assertEqual(calls, ["identity", "delete"])

    def test_wrong_account_never_becomes_verified(self):
        wrong = {
            "username": "otra",
            "acct": "otra",
            "url": "https://mastodon.social/@otra",
        }
        with patch.object(m, "_get", return_value=wrong):
            with self.assertRaises(m.WrongAccountActive):
                m._assert_expected_account()
        self.assertFalse(m._IDENTITY_VERIFIED)

    def test_unverifiable_token_identity_is_terminal(self):
        with patch.object(
            m,
            "_get",
            side_effect=RuntimeError("401 unauthorized"),
        ):
            with self.assertRaises(m.WrongAccountActive):
                m._assert_expected_account()
        self.assertFalse(m._IDENTITY_VERIFIED)

    def test_malformed_identity_is_terminal(self):
        with patch.object(m, "_get", return_value=[]):
            with self.assertRaises(m.WrongAccountActive):
                m._assert_expected_account()
        self.assertFalse(m._IDENTITY_VERIFIED)

    def test_expected_account_sets_cache(self):
        expected = {
            "username": "autorademodiaz",
            "acct": "autorademodiaz",
            "url": "https://mastodon.social/@autorademodiaz",
        }
        with patch.object(m, "_get", return_value=expected):
            m._assert_expected_account()
        self.assertTrue(m._IDENTITY_VERIFIED)


class MastodonInteractionTests(unittest.TestCase):
    def test_reply_dedupe_only_counts_direct_own_reply(self):
        context = {
            "descendants": [
                {
                    "id": "child",
                    "in_reply_to_id": "target",
                    "account": {"username": "otra"},
                },
                {
                    "id": "grandchild",
                    "in_reply_to_id": "child",
                    "account": {"username": "autorademodiaz"},
                },
            ]
        }
        with patch.object(m, "_get", return_value=context):
            self.assertFalse(m._already_commented("target"))

        context["descendants"].append(
            {
                "id": "mine",
                "in_reply_to_id": "target",
                "account": {"username": "AUTORADEMODIAZ"},
            }
        )
        with patch.object(m, "_get", return_value=context):
            self.assertTrue(m._already_commented("target"))

    def test_reply_preserves_unlisted_visibility(self):
        def fake_get(path, params=None):
            if path.endswith("/context"):
                return {"descendants": []}
            return {
                "visibility": "unlisted",
                "account": {"acct": "lectora@example.com"},
            }

        with patch.object(m, "_status_id", return_value="7"), \
             patch.object(m, "_get", side_effect=fake_get), \
             patch.object(
                 m,
                 "_create_status",
                 return_value={"id": "9"},
             ) as create, \
             patch.object(m, "_check_spanish_orthography"), \
             patch.object(m, "_check_length"):
            m.reply_to("7", "Gracias")

        body = create.call_args.args[0]
        self.assertEqual(body["visibility"], "unlisted")

    def test_private_and_direct_replies_are_never_automated(self):
        for visibility in ("private", "direct", None):
            with self.subTest(visibility=visibility), \
                 patch.object(m, "_status_id", return_value="7"), \
                 patch.object(m, "_already_commented", return_value=False), \
                 patch.object(
                     m,
                     "_get",
                     return_value={
                         "visibility": visibility,
                         "account": {"acct": "lectora"},
                     },
                 ), \
                 patch.object(m, "_create_status") as create:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "public/unlisted",
                ):
                    m.reply_to("7", "Respuesta")
                create.assert_not_called()

    def test_existing_actions_are_not_counted_as_new(self):
        with patch.object(m, "_resolve_account_id", return_value="42"), \
             patch.object(
                 m,
                 "_get",
                 return_value=[{"following": True}],
             ):
            self.assertEqual(m.follow("lectora"), "already")

        with patch.object(m, "_status_id", return_value="7"), \
             patch.object(m, "_get", return_value={"favourited": True}):
            self.assertEqual(m.favourite("7"), "already")

        with patch.object(m, "_status_id", return_value="7"), \
             patch.object(m, "_get", return_value={"reblogged": True}):
            self.assertEqual(m.boost("7"), "already")

    def test_follow_tag_is_idempotent(self):
        with patch.object(
            m,
            "tag_info",
            return_value={"following": True},
        ), patch.object(m, "_post") as post:
            self.assertEqual(m.follow_tag("Bookstodon"), "already")
            post.assert_not_called()


class MastodonPublicationPolicyTests(unittest.TestCase):
    def test_direct_publication_helpers_are_disabled(self):
        for func, args in (
            (m.post, ("Texto",)),
            (m.quote, ("7", "Texto")),
            (m.poll, ("Pregunta", ["A", "B"])),
        ):
            with self.subTest(func=func.__name__), \
                 patch.object(m, "_post") as post_call:
                with self.assertRaises(m.OwnPublicationDisabled):
                    func(*args)
                post_call.assert_not_called()

    def test_executor_rejects_own_publication_kinds(self):
        for kind in ("post", "quote", "poll"):
            item = {"kind": kind, "curated": True, "text": "Texto", "url": "7"}
            with self.subTest(kind=kind), \
                 patch("repost_policy.done_today", return_value=0), \
                 patch.object(execute.dup, "check", return_value=[]):
                result = execute.run_plan([item])
            self.assertEqual(
                result[0]["resultado"],
                f"rechazado_publicacion_manual:{kind}",
            )

    def test_executor_still_supports_interactions(self):
        with patch.object(
            execute.m,
            "follow",
            return_value="already",
        ), patch.object(execute.dup, "check", return_value=[]):
            result = execute.run_plan(
                [{"kind": "follow", "handle": "lectora"}]
            )
        self.assertEqual(
            result[0]["resultado"],
            "saltado_ya_follow",
        )

    def test_invalid_later_reply_blocks_earlier_follow(self):
        plan = [
            {"kind": "follow", "handle": "lectora"},
            {"kind": "reply", "url": "7", "text": "  "},
        ]
        with patch.object(execute.m, "follow") as follow, \
             patch.object(execute.dup, "check", return_value=[]):
            result = execute.run_plan(plan)

        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))
        follow.assert_not_called()


if __name__ == "__main__":
    unittest.main()

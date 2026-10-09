"""Pruebas aisladas de la auditoría Pinterest API: sin token ni red real."""
import io
import json
import pathlib
import sys
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import pinterest_api_audit as audit


def response(payload):
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


class PinterestAPIAuditTests(unittest.TestCase):
    def test_audit_flags_internal_id_home_and_requires_https(self):
        self.assertEqual(
            audit.audit_pin(
                {
                    "id": "1",
                    "title": "IG-02-08: lectura",
                    "link": "https://autorademodiaz.com/?utm_source=pin",
                    "board_id": "4",
                    "alt_text": "Lectura accesible",
                }
            ),
            ["ID interno visible en título", "destino genérico a la home"],
        )

        problems = audit.audit_pin(
            {
                "id": "2",
                "title": "Una novela",
                "link": "http://autorademodiaz.com/cuaderno/",
                "board_id": "4",
                "alt_text": "Escena de lectura",
            }
        )
        self.assertTrue(any("HTTPS" in problem for problem in problems))

        self.assertEqual(
            audit.audit_pin(
                {
                    "id": "3",
                    "title": "Una novela de fantasía",
                    "link": "https://autorademodiaz.com/cuaderno/",
                    "board_id": "4",
                    "alt_text": "Escena de una novela de fantasía",
                }
            ),
            [],
        )

    def test_invalid_fields_are_reported_without_aborting_pin_audit(self):
        problems = audit.audit_pin(
            {
                "id": "123",
                "title": None,
                "link": None,
                "board_id": "",
                "alt_text": "",
            }
        )
        self.assertTrue(any("título" in p for p in problems))
        self.assertTrue(any("sin enlace" in p for p in problems))
        self.assertTrue(any("board_id" in p for p in problems))
        self.assertTrue(any("ALT ausente" in p for p in problems))

        invalid_board = audit.audit_pin(
            {
                "id": "125",
                "title": "Lectura",
                "link": "https://autorademodiaz.com/cuaderno/",
                "board_id": "abc",
                "alt_text": "Texto alternativo",
            }
        )
        self.assertTrue(any("board_id" in p for p in invalid_board))

        for link in (
            "javascript:alert(1)",
            "https://[bad/route",
            "https://example.org:port/route",
            "https://user:pass@example.org/route",
            "https://example.org:444/route",
        ):
            with self.subTest(link=link):
                problems = audit.audit_pin(
                    {
                        "id": "124",
                        "title": "Lectura",
                        "link": link,
                        "board_id": 9,
                        "alt_text": "Texto alternativo",
                    }
                )
                self.assertTrue(any("HTTPS" in p for p in problems))

    def test_request_json_only_allows_exact_official_api_host(self):
        with patch.object(audit, "_open_request") as get:
            with self.assertRaisesRegex(RuntimeError, "solo puede llamar"):
                audit._request_json(
                    "https://api.pinterest.com.evil.example/v5/pins",
                    "secreto",
                )
            get.assert_not_called()

    def test_verify_account_accepts_exact_username(self):
        with patch.object(
            audit,
            "_open_request",
            return_value=response({"username": "AutoraDemoDiaz"}),
        ) as get:
            profile = audit.verify_account("token")
        self.assertEqual(profile["username"], "AutoraDemoDiaz")
        request = get.call_args.args[0]
        self.assertEqual(request.full_url, audit.USER_ACCOUNT_URL)
        self.assertEqual(request.get_header("Authorization"), "Bearer token")

    def test_verify_account_rejects_valid_token_for_wrong_account(self):
        with patch.object(
            audit,
            "_open_request",
            return_value=response({"username": "otra_cuenta"}),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "se esperaba @autorademodiaz",
            ):
                audit.verify_account("token")

    def test_verify_account_requires_username(self):
        with patch.object(
            audit,
            "_open_request",
            return_value=response({"account_type": "BUSINESS"}),
        ):
            with self.assertRaisesRegex(RuntimeError, "confirmar identidad"):
                audit.verify_account("token")

    def test_reads_two_pages_only_after_identity_check_and_deduplicates(self):
        identity = {"username": "autorademodiaz"}
        one = {
            "items": [{"id": "1"}, {"id": "1"}],
            "bookmark": "page2",
        }
        two = {"items": [{"id": "2"}], "bookmark": None}
        replies = [response(v) for v in (identity, one, two)]

        with patch.object(
            audit,
            "_open_request",
            side_effect=replies,
        ) as get:
            ids = [x["id"] for x in audit.list_pins("token", max_pages=3)]

        self.assertEqual(ids, ["1", "2"])
        self.assertEqual(get.call_count, 3)
        self.assertEqual(
            get.call_args_list[0].args[0].full_url,
            audit.USER_ACCOUNT_URL,
        )
        self.assertIn(
            "bookmark=page2",
            get.call_args_list[2].args[0].full_url,
        )
        self.assertIn(
            "include_protected_pins=false",
            get.call_args_list[1].args[0].full_url,
        )

    def test_wrong_account_stops_before_list_pins_request(self):
        with patch.object(
            audit,
            "_open_request",
            return_value=response({"username": "otra"}),
        ) as get:
            with self.assertRaisesRegex(RuntimeError, "Auditoría cancelada"):
                list(audit.list_pins("token"))
        self.assertEqual(get.call_count, 1)
        self.assertEqual(
            get.call_args.args[0].full_url,
            audit.USER_ACCOUNT_URL,
        )

    def test_metrics_are_explicit_opt_in(self):
        replies = [
            response({"username": "autorademodiaz"}),
            response(
                {
                    "items": [
                        {
                            "id": "1",
                            "pin_metrics": {"impressions": 12},
                        }
                    ],
                    "bookmark": None,
                }
            ),
        ]
        with patch.object(
            audit,
            "_open_request",
            side_effect=replies,
        ) as get:
            list(audit.list_pins("token", include_metrics=True))
        self.assertIn(
            "pin_metrics=true",
            get.call_args_list[1].args[0].full_url,
        )

    def test_pin_missing_id_is_explicit_audit_error(self):
        replies = [
            response({"username": "autorademodiaz"}),
            response(
                {
                    "items": [{"title": "Sin identificador"}],
                    "bookmark": None,
                }
            ),
        ]
        with patch.object(
            audit,
            "_open_request",
            side_effect=replies,
        ):
            with self.assertRaisesRegex(RuntimeError, "sin identificador"):
                list(audit.list_pins("token"))

    def test_bool_id_is_rejected(self):
        replies = [
            response({"username": "autorademodiaz"}),
            response({"items": [{"id": True}], "bookmark": None}),
        ]
        with patch.object(
            audit,
            "_open_request",
            side_effect=replies,
        ):
            with self.assertRaisesRegex(RuntimeError, "sin identificador"):
                list(audit.list_pins("token"))

    def test_repeated_bookmark_is_error(self):
        repeated = {"items": [], "bookmark": "duplicate"}
        replies = [
            response({"username": "autorademodiaz"}),
            response(repeated),
            response(repeated),
        ]
        with patch.object(
            audit,
            "_open_request",
            side_effect=replies,
        ):
            with self.assertRaisesRegex(RuntimeError, "repetido"):
                list(audit.list_pins("token", max_pages=3))

    def test_page_limit_reports_incomplete_audit(self):
        replies = [
            response({"username": "autorademodiaz"}),
            response({"items": [{"id": "1"}], "bookmark": "next"}),
        ]
        with patch.object(
            audit,
            "_open_request",
            side_effect=replies,
        ):
            with self.assertRaisesRegex(RuntimeError, "INCOMPLETA"):
                list(audit.list_pins("token", max_pages=1))

    def test_page_size_documented_limit(self):
        replies = [
            response({"username": "autorademodiaz"}),
            response({"items": [], "bookmark": None}),
        ]
        with patch.object(
            audit,
            "_open_request",
            side_effect=replies,
        ) as get:
            list(audit.list_pins("token", page_size=250))
        self.assertIn(
            "page_size=250",
            get.call_args_list[1].args[0].full_url,
        )

        with self.assertRaisesRegex(ValueError, "page_size"):
            list(audit.list_pins("token", page_size=251))

    def test_redirect_handler_refuses_redirect(self):
        handler = audit._NoRedirectHandler()
        request = audit.urllib.request.Request(
            audit.PINS_URL,
            headers={"Authorization": "Bearer secreto"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://evil.example/steal",
            )
        self.assertEqual(ctx.exception.code, 302)
        self.assertNotIn("secreto", str(ctx.exception))

    def test_http_error_does_not_expose_token(self):
        error = urllib.error.HTTPError(
            audit.USER_ACCOUNT_URL,
            401,
            "Unauthorized",
            hdrs=None,
            fp=None,
        )
        with patch.object(
            audit,
            "_open_request",
            side_effect=error,
        ):
            with self.assertRaises(RuntimeError) as ctx:
                audit.verify_account("SUPER_SECRET_TOKEN")
        self.assertNotIn("SUPER_SECRET_TOKEN", str(ctx.exception))
        self.assertIn("HTTP 401", str(ctx.exception))

    def test_invalid_json_fails_closed(self):
        with patch.object(
            audit,
            "_open_request",
            return_value=io.BytesIO(b"not-json"),
        ):
            with self.assertRaisesRegex(RuntimeError, "JSON inválido"):
                audit.verify_account("token")

    def test_never_uses_network_in_demo(self):
        with patch.object(audit, "_open_request") as get, \
             patch.object(
                 sys,
                 "argv",
                 ["pinterest_api_audit.py", "--demo"],
             ), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            audit.main()
        get.assert_not_called()
        self.assertIn(
            "Auditados 2 pines publicados; 1 con incidencias.",
            output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()

"""PR #12: contratos sintéticos de búsqueda federada, sin HTTP ni escrituras.

Los perfiles de tests/fixtures/mastodon_search_capabilities.json reproducen la
estructura JSON y la cuota de página publicada para GET /api/v2/search.
NO son capturas de servidores reales ni certifican compatibilidad universal.
"""
import json
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

requests_stub = types.ModuleType("requests")
requests_stub.get = lambda *a, **k: (_ for _ in ()).throw(AssertionError("HTTP prohibido"))
requests_stub.post = lambda *a, **k: (_ for _ in ()).throw(AssertionError("escritura prohibida"))
requests_stub.delete = lambda *a, **k: (_ for _ in ()).throw(AssertionError("escritura prohibida"))
x_stub = types.ModuleType("x_interact")
x_stub._check_spanish_orthography = lambda _text: None
sys.modules.setdefault("requests", requests_stub)
sys.modules.setdefault("x_interact", x_stub)

import mastodon_interact as m
import mastodon_execute as execute

FIXTURES = json.loads(
    (ROOT / "tests/fixtures/mastodon_search_capabilities.json").read_text(encoding="utf-8")
)


class MastodonAccountSearchContractTests(unittest.TestCase):
    def test_two_instances_keep_exact_offsets_and_never_duplicate_local_accounts(self):
        for instance in FIXTURES["instances"]:
            with self.subTest(instance=instance["name"]):
                offsets = []

                def server_search(path, params):
                    self.assertEqual(path, "search")
                    self.assertEqual(params["type"], "accounts")
                    # Contrato real de Mastodon API v2, no se debe enviar 80.
                    self.assertEqual(params["limit"], 40)
                    offset = params["offset"]
                    offsets.append(offset)
                    matching = next(
                        (p for p in instance["pages"] if p["offset"] == offset), None
                    )
                    if not matching:
                        return {"accounts": [], "statuses": [], "hashtags": []}
                    accounts = [
                        {
                            "id": str(matching["first_id"] + n),
                            "acct": f"lectora{matching['first_id'] + n}@{instance['hostname']}",
                        }
                        for n in range(matching["count"])
                    ]
                    return {"accounts": accounts, "statuses": [], "hashtags": []}

                with patch.object(m, "_get_v2", side_effect=server_search):
                    rows = m.search_accounts_pages("fantasía", limit=80, max_pages=8)

                self.assertEqual(offsets, instance["expected_offsets"])
                self.assertEqual(len(rows), instance["expected_unique"])
                self.assertEqual(len({str(row["id"]) for row in rows}), len(rows))
                self.assertTrue(all("@" + instance["hostname"] in row["acct"] for row in rows))

    def test_before_after_on_identical_indexed_fixture(self):
        """Control negativo: el algoritmo anterior se detenía al recibir 40 < 80."""
        fixture = FIXTURES["instances"][0]
        offsets = []

        def search_v2(_path, params):
            offsets.append(params["offset"])
            page = next(
                (p for p in fixture["pages"] if p["offset"] == params["offset"]), None
            )
            accounts = ([] if page is None else [
                {"id": str(page["first_id"] + j),
                 "acct": f"lectora{page['first_id'] + j}@{fixture['hostname']}"}
                for j in range(page["count"])
            ])
            return {"accounts": accounts, "statuses": [], "hashtags": []}

        def baseline_as_found_in_mirror():
            rows = []
            page_size = max(1, min(int(80), 80))
            for page in range(8):
                data = m.search("fantasía", "accounts", page_size,
                                offset=page * page_size)
                accounts = data.get("accounts") or []
                rows.extend(accounts)
                if len(accounts) < page_size:
                    break
            return rows

        with patch.object(m, "_get_v2", side_effect=search_v2):
            before = baseline_as_found_in_mirror()
            offsets_before = offsets[:]
            offsets.clear()
            after = m.search_accounts_pages("fantasía", limit=80, max_pages=8)
        self.assertEqual((len(before), offsets_before), (40, [0]))
        self.assertEqual((len(after), offsets), (82, [0, 40, 80]))

    def test_without_fulltext_index_search_for_accounts_still_works(self):
        server = FIXTURES["instances"][1]
        self.assertFalse(server["statuses_search"])

        def server_search(_path, params):
            if params["type"] == "statuses":
                return {"accounts": [], "hashtags": [], "statuses": []}
            return {"accounts": [{"id": "42", "acct": "lectora@" + server["hostname"]}],
                    "hashtags": [], "statuses": []}

        with patch.object(m, "_get_v2", side_effect=server_search):
            self.assertEqual(m.search("libros", "statuses")["statuses"], [])
            accounts = m.search_accounts_pages("libros", limit=2, max_pages=2)
        self.assertEqual([row["id"] for row in accounts], ["42"])

    def test_malformed_accounts_response_fails_closed(self):
        for payload in ({"hashtags": [], "statuses": []}, {"accounts": None}, {"accounts": "oops"},
                        {"accounts": [{"acct": "sinid@example.test"}]}):
            with self.subTest(payload=payload), patch.object(m, "_get_v2", return_value=payload):
                with self.assertRaisesRegex(RuntimeError, "accounts\\[\\]|sin ID local"):
                    m.search_accounts_pages("libros", limit=40, max_pages=2)

    def test_second_page_error_propagates_instead_of_silent_partial_success(self):
        observed = []

        def server_search(_path, params):
            observed.append(params["offset"])
            if len(observed) == 2:
                raise TimeoutError("segundo lote sin respuesta")
            return {"accounts": [{"id": str(i), "acct": f"u{i}@example.test"}
                                  for i in range(40)]}

        with patch.object(m, "_get_v2", side_effect=server_search):
            with self.assertRaisesRegex(TimeoutError, "segundo lote"):
                m.search_accounts_pages("libros", limit=80, max_pages=4)
        self.assertEqual(observed, [0, 40])

    def test_remote_urls_with_identical_numeric_tail_resolve_to_local_ids(self):
        urls = ["https://libros.example/@ana/77", "https://historias.example/@ana/77"]
        local_ids = {"https://libros.example/@ana/77": "9001",
                     "https://historias.example/@ana/77": "9002"}

        def resolve(q, kind, limit, *, resolve=False, **_kwargs):
            self.assertEqual(kind, "statuses")
            self.assertTrue(resolve)
            return {"statuses": [{"url": q, "id": local_ids[q]}]}

        with patch.object(m, "search", side_effect=resolve), patch.object(m, "_post") as write:
            self.assertEqual([m._status_id(u) for u in urls], ["9001", "9002"])
            write.assert_not_called()

    def test_two_remote_aliases_same_local_status_are_rejected_before_any_action(self):
        urls = ["https://libros.example/@ana/77", "https://historias.example/@ana/77"]

        def resolve(q, *_args, **_kwargs):
            return {"statuses": [{"url": q, "id": "9001"}]}

        with patch.object(m, "search", side_effect=resolve), patch.object(m, "_post") as write:
            with self.assertRaisesRegex(ValueError, "varias acciones"):
                execute._preflight_plan([
                    {"kind": "favourite", "url": urls[0]},
                    {"kind": "boost", "url": urls[1]},
                ])
            write.assert_not_called()


if __name__ == "__main__":
    unittest.main()

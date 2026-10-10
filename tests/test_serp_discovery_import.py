"""Solo fixtures sintéticos. No conexiones, cuentas, secretos ni writes a redes."""
import importlib.util
import json
import pathlib
import tempfile
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "serp_discovery_import.py"
spec = importlib.util.spec_from_file_location("serp_discovery_import", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TestSerpImport(unittest.TestCase):
    def row(self, link, **kwargs):
        return {"link": link, "title": "¿Qué libro de fantasía recomendáis?", "snippet": "Romantasy", **kwargs}

    def test_all_nine_networks(self):
        urls = [
            "https://www.facebook.com/club/posts/123",
            "https://www.instagram.com/p/abc1",
            "https://www.threads.net/@lectora/post/abcd",
            "https://x.com/lectora/status/123",
            "https://bsky.app/profile/lectora.bsky.social/post/xxx",
            "https://mastodon.social/@lectora/123",
            "https://www.pinterest.com/pin/123",
            "https://www.reddit.com/r/libros/comments/123/abc",
            "https://www.tiktok.com/@lectora/video/123",
        ]
        rows = [self.row(u, **({"network": "mastodon"} if "mastodon.social" in u else {})) for u in urls]
        result = mod.import_results(rows)
        self.assertEqual(result["review_count"], 9)
        self.assertEqual({c["network"] for c in result["candidates"]}, mod.NETWORKS)
        self.assertTrue(all(c["action_allowed"] is False and c["published_at"] is None and c["review_required"] for c in result["candidates"]))

    def test_mastodon_requires_declaration_and_shape(self):
        self.assertEqual(mod.import_results([self.row("https://mastodon.social/@lectora/123")])["review_count"], 0)
        self.assertEqual(mod.import_results([self.row("https://evil.example/@lectora/123", network="mastodon")])["review_count"], 1)
        self.assertEqual(mod.import_results([self.row("https://evil.example/admin", network="mastodon")])["review_count"], 0)

    def test_fb_group_never_authorized(self):
        result = mod.import_results([self.row("https://www.facebook.com/groups/123/permalink/456")])
        self.assertEqual(result["candidates"][0]["surface"], "group_manual")
        self.assertFalse(result["candidates"][0]["permission_verified"])

    def test_ambiguous_facebook_url(self):
        result = mod.import_results([self.row("https://www.facebook.com/story.php?story_fbid=12&id=3")])
        self.assertEqual(result["candidates"][0]["surface"], "ambiguous_manual")

    def test_query_cannot_authorize_page_post(self):
        result = mod.import_results([self.row("https://www.facebook.com/name/posts/42?source=group")])
        self.assertEqual(result["candidates"][0]["surface"], "ambiguous_manual")

    def test_dedup_utm_and_fragment_without_mixing_domains(self):
        link = "https://www.facebook.com/name/posts/42"
        rows = [self.row(link + "?utm_source=test#abc"), self.row(link), self.row("https://www.instagram.com/name/posts/42")]
        result = mod.import_results(rows)
        self.assertEqual(result["review_count"], 2)
        self.assertEqual(result["counts"]["duplicate"], 1)

    def test_duplicate_prefers_evidence_not_first_serp_position(self):
        url = "https://www.facebook.com/club/posts/123"
        rows = [{"link": url, "title": "Agenda", "snippet": "Próximo evento"},
                self.row("https://facebook.com/club/posts/123?utm_campaign=abc")]
        r = mod.import_results(rows)
        self.assertEqual(r["review_count"], 1)
        self.assertEqual(r["counts"]["duplicate"], 1)
        self.assertEqual(r["candidates"][0]["intent"], "pide_recomendacion")

    def test_encoded_host_path_collision_not_accepted(self):
        rows = [self.row("https://facebook.com.evil.example/name/posts/42"),
                self.row("https://facebook.com@evil.example/name/posts/42"),
                self.row("http://www.facebook.com/name/posts/42"),
                self.row("https://www.facebook.com:8443/name/posts/42")]
        result = mod.import_results(rows)
        self.assertEqual(result["review_count"], 0)

    def test_wrong_declared_network_is_rejected(self):
        self.assertEqual(mod.import_results([self.row("https://www.facebook.com/name/posts/42", network="instagram")])["review_count"], 0)

    def test_non_literary_discard(self):
        result = mod.import_results([{"link": "https://www.facebook.com/news/posts/42", "title": "Coche", "snippet": "Oferta de coches"}])
        self.assertEqual(result["counts"]["without_literary_evidence"], 1)

    def test_spanish_question_intent(self):
        c = mod.import_results([self.row("https://www.facebook.com/book/posts/42")])["candidates"][0]
        self.assertEqual(c["intent"], "pide_recomendacion")

    def test_none_and_broken_entries(self):
        r = mod.import_results([None, {}, self.row("https://www.facebook.com/book/posts/42"), self.row("https://www.facebook.com/book/posts/42")])
        self.assertEqual(r["input_count"], 4)
        self.assertEqual(r["review_count"], 1)
        self.assertEqual(r["counts"]["invalid_row"], 1)
        self.assertEqual(r["counts"]["invalid_url"], 1)

    def test_batch_limits(self):
        for invalid in (None, {}, "x", [None] * 5001):
            with self.subTest(value=type(invalid).__name__):
                with self.assertRaises(ValueError):
                    mod.import_results(invalid)

    def test_cli_local_only_and_unicode(self):
        with tempfile.TemporaryDirectory() as d:
            inp, out = pathlib.Path(d) / "in.json", pathlib.Path(d) / "out.json"
            inp.write_text(json.dumps({"organicResults": [self.row("https://www.facebook.com/club/posts/11")]}, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(mod.main([str(inp), "--output", str(out)]), 0)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["review_count"], 1)

    def test_does_not_infer_published_at_from_serp_rank(self):
        c = mod.import_results([self.row("https://www.facebook.com/club/posts/11", rank=1, date_time="2026-10-10")])["candidates"][0]
        self.assertIsNone(c["published_at"])
        self.assertFalse(c["author_id_verified"])


if __name__ == "__main__":
    unittest.main()

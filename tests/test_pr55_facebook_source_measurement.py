"""PR55: pruebas sin red, sin credenciales y sin rutas productivas."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import facebook_source_quality as sq

NOW = dt.datetime(2026, 10, 9, 12, tzinfo=dt.timezone.utc)


def row(url="https://www.facebook.com/libreria/posts/123", text="Reseña de una novela de fantasía", source="search:libros", created_at="2026-10-08T10:00:00Z"):
    return {"permalink": url, "text": text, "source": source, "created_at": created_at}


class FacebookSourceQuality(unittest.TestCase):
    def test_no_url_authorizes_writing(self):
        cases = [row(), row("https://www.facebook.com/groups/12/posts/4"), row(created_at=None)]
        self.assertTrue(all(sq.assess(item, now=NOW)["action_allowed"] is False for item in cases))

    def test_group_links_rejected_including_percent_encoded_paths(self):
        for url in ("https://facebook.com/groups/123/posts/456",
                    "https://facebook.com/%67roups/123/posts/456",
                    "https://facebook.com/literatura/posts/456?group_id=123"):
            self.assertEqual(sq.assess(row(url), now=NOW)["reason"], "group_not_authorized")
        self.assertEqual(sq.assess(row(source="group:literatura"), now=NOW)["reason"], "group_not_authorized")
        self.assertEqual(sq.assess(row(source="GROUP:literatura"), now=NOW)["reason"], "group_not_authorized")

    def test_rejects_host_confusion_and_unsafe_url(self):
        for url in ("https://facebook.com.evil.invalid/user/posts/123", "http://facebook.com/user/posts/123",
                    "https://example.com/user/posts/123", "https://facebook.com:8443/user/posts/123"):
            self.assertEqual(sq.assess(row(url), now=NOW)["reason"], "invalid_url")

    def test_spam_employment_discarded_even_if_literary(self):
        self.assertEqual(sq.assess(row(text="Empleo para escritor: vacantes, enviar CV"), now=NOW)["reason"], "spam_or_job")

    def test_explicit_ai_label_requires_review_and_not_auto_plan(self):
        post = row(text="Esta reseña de novela fue generada con IA")
        verdict = sq.assess(post, now=NOW)
        self.assertEqual(verdict["reason"], "ai_generated_label")
        self.assertEqual(verdict["decision"], "review")
        self.assertFalse(verdict["action_allowed"])
        self.assertEqual(sq.hard_exclusion_reason(post["text"]), "ai_generated_label")

    def test_topic_unknown_date_and_age(self):
        self.assertEqual(sq.assess(row(), now=NOW)["decision"], "candidate")
        self.assertEqual(sq.assess(row(text="Buenos días"), now=NOW)["reason"], "non_literary")
        self.assertEqual(sq.assess(row(created_at=None), now=NOW)["reason"], "age_unknown")
        self.assertEqual(sq.assess(row(created_at="2026-09-29T00:00:00Z"), now=NOW)["reason"], "not_recent_for_comment")
        self.assertEqual(sq.assess(row(created_at="2026-10-11T00:00:00Z"), now=NOW)["reason"], "age_unknown")

    def test_ambiguous_photo_remains_review_only(self):
        self.assertEqual(sq.assess(row("https://www.facebook.com/photo/?fbid=123"), now=NOW)["reason"], "surface_unverified")

    def test_summary_unique_by_url_and_privacy(self):
        rows = [row(), row(), row("https://facebook.com/groups/123/posts/123"), row(text="Empleo en librería, buscamos CV")]
        report = sq.summary(rows, now=NOW, hmac_key=b"synthetic-key-16-chars")
        self.assertTrue(report["measurement_only"])
        self.assertEqual(len(report["sources"]), 1)
        stats = report["sources"][0]
        self.assertEqual(stats["observed"], 4)
        self.assertEqual(stats["unique_post_urls"], 2)
        self.assertEqual(stats["group_blocked"], 1)
        self.assertEqual(stats["spam_blocked"], 1)
        self.assertEqual(stats["candidate"], 2)
        self.assertEqual(stats["unique_candidate_urls_in_batch"], 1)
        self.assertEqual(stats["duplicate_observations_in_batch"], 2)
        for private in ("libreria", "123/posts", "Empleo", "libros"):
            self.assertNotIn(private, repr(report))
        anonymous = sq.summary(rows, now=NOW)
        self.assertIsNone(anonymous["sources"][0]["source_key"])

    def test_source_keys_are_stable_and_separated(self):
        a = sq.summary([row(source="search:fantasía")], now=NOW,
                       hmac_key=b"synthetic-key-16-chars")
        b = sq.summary([row(source="search:fantasía")], now=NOW,
                       hmac_key=b"synthetic-key-16-chars")
        c = sq.summary([row(source="search:otros")], now=NOW,
                       hmac_key=b"synthetic-key-16-chars")
        self.assertEqual(a["sources"][0]["source_key"], b["sources"][0]["source_key"])
        self.assertNotEqual(a["sources"][0]["source_key"], c["sources"][0]["source_key"])
        self.assertNotIn("fantasía", repr(a))

    def test_hmac_matches_shared_discovery_attribution_normalization(self):
        import discovery_attribution as attribution
        key = b"synthetic-key-for-pr55-32bytes"
        original = sq.summary([row(source="search:FANTASÍA")], now=NOW,
                              hmac_key=key)["sources"][0]["source_key"]
        equivalent = sq.summary([row(source=" search:fantasi" + chr(0x0301) + "a ")], now=NOW,
                                hmac_key=key)["sources"][0]["source_key"]
        expected = attribution._token("search:fantasía", key, "facebook/source")
        self.assertEqual(original, equivalent)
        self.assertEqual(original, expected)

    def test_extreme_timestamp_falls_back_to_review(self):
        event = row(created_at="0001-01-01T00:00:00+14:00")
        self.assertEqual(sq.assess(event, now=NOW)["decision"], "review")
        self.assertEqual(sq.assess(row(source="SEARCH:fantasía"), now=NOW)["decision"], "candidate")

    def test_direct_post_url_shape_blocks_group_and_ambiguous_photo(self):
        self.assertTrue(sq.page_post_url_shape("https://facebook.com/libreria/posts/99"))
        for url in ("https://facebook.com/groups/12/posts/3",
                    "https://facebook.com/photo/?fbid=2",
                    "https://facebook.com/story.php?story_fbid=4",
                    "https://facebook.com/page/posts/9?group_id=10"):
            self.assertFalse(sq.page_post_url_shape(url))
            with self.assertRaises(ValueError):
                sq.require_page_post_url_shape(url)


    def test_scan_metrics_are_aggregated_without_content(self):
        import facebook_scan as scan
        rows = [
            ("Autor privado", "https://facebook.com/pagina/posts/1", "Novela"),
            ("Grupo secreto", "https://facebook.com/groups/5/posts/8", "Lectura"),
            ("Tienda", "https://facebook.com/pagina/posts/2", "Empleo para escritores"),
        ]
        report = scan._source_quality_metrics(rows, "search", 1.75)
        self.assertEqual(report["observados"], 3)
        self.assertEqual(report["post_shape"], 2)
        self.assertEqual(report["grupos"], 1)
        self.assertEqual(report["spam"], 1)
        self.assertEqual(report["segundos_escaneo"], 1.75)
        self.assertFalse(report["permiso_acreditado"])
        for private in ("Autor privado", "Grupo secreto", "facebook.com", "Lectura"):
            self.assertNotIn(private, repr(report))


    def test_metrics_error_does_not_stop_regular_discovery(self):
        from unittest import mock
        import facebook_scan as scan
        rows = [("Autora", "https://facebook.com/pagina/posts/12",
                 "Lectura fantástica")]
        with mock.patch.object(scan, "_source_quality_metrics",
                               side_effect=ValueError("simulado")), \
             mock.patch("builtins.print") as printer:
            self.assertIsNone(scan._print_source_quality(rows, "search", 1.0))
        self.assertEqual(len(rows), 1)
        output = " ".join(str(arg) for call in printer.call_args_list for arg in call.args)
        self.assertIn("estado=no_disponible", output)
        self.assertNotIn("Autora", output)


if __name__ == "__main__":
    unittest.main()

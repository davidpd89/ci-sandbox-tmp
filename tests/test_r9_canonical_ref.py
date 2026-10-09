"""R9: la cola API comparte identidad remota con #121; sin acciones de red."""
import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import reply_queue as rq
import reply_cache_audit as audit
from candidate_identity import CandidateIdentityError, resolve_post_ref


URI = "at://did:plc:abc/app.bsky.feed.post/xyz"


class CanonicalRemoteTargetTests(unittest.TestCase):
    def test_bluesky_raw_uri_same_identity_as_resolved_post_uri(self):
        raw = {"author": "autora.example", "text": "Mi novela de fantasía",
               "uri": URI, "status_id": "123"}
        resolved = {"author": "autora.example", "text": "Mi novela de fantasía",
                    "post_uri": URI}
        self.assertEqual(rq._remote_target(raw, "bluesky"), URI)
        self.assertEqual(rq.key_for("bluesky", raw),
                         rq.key_for("bluesky", resolved))

    def test_mastodon_raw_status_id_matches_writer_post_uri(self):
        raw = {"author": "escritora@social.example", "text": "Hoy leo más",
               "status_id": 12345, "uri": URI}
        resolved = {"author": raw["author"], "text": raw["text"],
                    "post_uri": "12345"}
        self.assertEqual(rq._remote_target(raw, "mastodon"), "12345")
        self.assertEqual(rq.key_for("mastodon", raw),
                         rq.key_for("mastodon", resolved))

    def test_invalid_native_ref_cannot_fallback_to_ordinal_id(self):
        item = {"author": "autora.example", "text": "Leo fantasía",
                "uri": "no-es-una-uri", "post_id": "G001-P1"}
        self.assertEqual(rq._remote_target(item, "bluesky"), "")
        self.assertNotEqual(
            rq.key_for("bluesky", dict(item, context="primer hilo")),
            rq.key_for("bluesky", dict(item, context="segundo hilo")),
        )
        item.pop("uri")
        self.assertEqual(rq._remote_target(item, "bluesky"), "")

    def test_mastodon_local_scan_ordinal_is_not_a_status(self):
        row = {"author": "autora@social.example", "text": "Libros y lecturas",
               "status_id": "M001-P1", "id": "M001-P1"}
        self.assertEqual(rq._remote_target(row, "mastodon"), "")
        with self.assertRaises(CandidateIdentityError):
            resolve_post_ref("mastodon", row)  # el escritor tampoco recibe un ID ordinal
        self.assertEqual(rq._remote_target({**row, "post_uri": "M001-P1"}, "mastodon"), "")
        self.assertNotEqual(
            rq.key_for("mastodon", {**row, "context": "primera conversación"}),
            rq.key_for("mastodon", {**row, "context": "otra conversación"}),
        )

    def test_mastodon_alphanumeric_remote_id_remains_accepted(self):
        # La documentación oficial no garantiza que todos los ID sean numéricos.
        row = {"status_id": "external-snowflake.1", "text": "Un libro"}
        self.assertEqual(rq._remote_target(row, "MaStOdOn"), "external-snowflake.1")

    def test_legacy_explicit_post_uri_is_preserved(self):
        old = {"post_uri": "at://did:plc:abc/post/uno",
               "author": "autora.example", "text": "Lectura"}
        self.assertEqual(rq._remote_target(old, "bluesky"), old["post_uri"])

    def test_cache_audit_recognizes_raw_mastodon_status_id(self):
        now = datetime.datetime(2026, 10, 8, 15, 0)
        entry = {"network": "mastodon", "author": "autora@social.example",
                 "text": "He terminado un libro", "status_id": "12345",
                 "ts": now.isoformat()}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pending.json").write_text(
                json.dumps({"legacy": entry}), encoding="utf-8",
            )
            result = audit.audit(tmp, now=now)
        self.assertEqual(result["pending_fresh"], 1)
        self.assertEqual(result["pending_without_remote_target"], 0)

    def test_web_networks_keep_their_own_target_conventions(self):
        item = {"post_id": "web-event-7", "permalink": "https://example.org/p/7"}
        self.assertEqual(rq._remote_target(item, "x"), "web-event-7")
        self.assertEqual(rq._remote_target(item, "mastodon"),
                         "https://example.org/p/7")


if __name__ == "__main__":
    unittest.main()

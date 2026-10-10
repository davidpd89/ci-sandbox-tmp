"""Regresiones offline de detección de intención y fuentes multired.

Ejecutar: python -m pytest tests/test_reciprocity_signals.py -q
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import discovery_terms
import reciprocity
import reciprocity_signals as rs


TODAY = dt.date(2026, 10, 10)
FIXTURE = Path(__file__).parent / "fixtures" / "reciprocity_signals_synthetic.json"


class SignalTests(unittest.TestCase):
    def test_all_nine_networks_get_searches_and_tags(self):
        self.assertEqual(len(rs.NETWORKS), 9)
        for net in rs.NETWORKS:
            self.assertTrue(rs.search_terms(net))
            self.assertTrue(rs.search_terms(net, "hashtags"))
        self.assertEqual(rs.search_terms("untrusted"), ())
        self.assertEqual(rs.search_terms("x", "unknown"), ())

    def test_dataset_is_only_synthetic_and_complete(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertTrue(data["synthetic"])
        self.assertEqual(data["schema"], 1)
        self.assertEqual(len(data["rows"]), 108)
        self.assertEqual({r["network"] for r in data["rows"]}, rs.NETWORKS)
        result = rs.evaluate(data["rows"], as_of=TODAY)
        for network, counters in result.items():
            with self.subTest(network=network):
                self.assertEqual(counters["tp"], 5)
                self.assertEqual(counters["tn"], 7)
                self.assertEqual(counters["fp"], 0)
                self.assertEqual(counters["fn"], 0)
                self.assertEqual(counters["precision"], 1.0)
                self.assertEqual(counters["recall"], 1.0)

    def test_signal_families_explained_not_merged(self):
        rows = rs.classify_text("Romantasy. Sígueme y te sigo; comenta y te comento; cadena de lectura.")
        self.assertEqual([x["kind"] for x in rows],
                         ["follow_exchange", "comment_exchange", "reading_chain"])
        self.assertTrue(all(x["intent"] == "explicit" for x in rows))
        self.assertTrue(all(x["matched"] for x in rows))

    def test_support_group_is_not_generic_support(self):
        self.assertEqual(rs.classify_text("Me gusta el apoyo mutuo"), [])
        self.assertEqual(rs.classify_text("Grupo de apoyo mutuo de escritores")[0]["kind"],
                         "support_group")

    def test_accents_punctuation_and_unicode_nfkc(self):
        self.assertEqual(rs.classify_text("Ｓígueme   y TE sigo")[0]["kind"], "follow_exchange")
        self.assertEqual(rs.classify_text("C4C lectoras")[0]["kind"], "comment_exchange")
        self.assertEqual(rs.classify_text("intercambio de reseñas")[0]["kind"], "reading_chain")

    def test_boundaries_and_casual_mentions(self):
        self.assertEqual(rs.classify_text("pref4foo sdvv ff4f"), [])
        self.assertEqual(rs.classify_text("texto cualquiera"), [])
        self.assertEqual(rs.classify_text(None), [])
        self.assertEqual(rs.classify_text("x" * 20001), [])
        cases = (
            "¿Qué significa f4f para escritores?",
            "No hago followback, soy lectora",
            "Prefiero no recomendar c4c a los autores",
            "El personaje dice sígueme y te sigo en mi novela",
        )
        for value in cases:
            with self.subTest(value=value):
                self.assertTrue(rs.classify_text(value))
                self.assertTrue(all(x["intent"] == "mention" for x in rs.classify_text(value)))

    def test_adversarial_negation_does_not_suppress_different_clause(self):
        mixed = rs.classify_text(
            "No hago f4f entre escritores; pero sí hago intercambio de reseñas.")
        self.assertEqual([(x["kind"], x["intent"]) for x in mixed],
                         [("follow_exchange", "mention"), ("reading_chain", "explicit")])
        positive = rs.assess_candidate(
            {"network": "threads", "surface": "bio",
             "text": "No hago f4f; pero sí hago intercambio de reseñas de fantasía"},
            as_of=TODAY)
        self.assertEqual(positive["status"], "eligible")

    def test_legacy_followback_and_opposed_intentions_in_one_sentence(self):
        # El contrato heredado reconocía «sigo a mis seguidores».
        self.assertEqual(reciprocity.declared_bonus("Sigo a mis seguidores; leo libros"), 2.5)
        # La negación de una intención no debe borrar una oferta distinta.
        signals = rs.classify_text(
            "No hago f4f, sí hago intercambio de reseñas de fantasía"
        )
        self.assertEqual(
            [(s["kind"], s["intent"]) for s in signals],
            [("follow_exchange", "mention"), ("reading_chain", "explicit")],
        )
        self.assertEqual(
            reciprocity.declared_bonus("No hago f4f, sí hago followback; libros"),
            2.5,
        )
        # El metacomentario sin oferta sigue sin recibir puntos.
        self.assertEqual(
            reciprocity.declared_bonus("No hago f4f, sí hablo de followback"), 0.0
        )

    def test_declared_followback_refusal_is_never_a_positive_bonus(self):
        for bio in (
            "No sigo de vuelta, libros",
            "Nunca devuelvo el follow. Leo fantasía",
            "No quiero f4f, escribo novelas",
            "No me gusta el followback entre escritores",
        ):
            with self.subTest(bio=bio):
                self.assertEqual(reciprocity.declared_bonus(bio), 0.0)
                self.assertTrue(all(s["intent"] == "mention"
                                    for s in rs.classify_text(bio)))

    def test_missing_niche_is_review_not_promotion(self):
        value = rs.assess_candidate({"network": "x", "surface": "bio",
                                     "text": "f4f fotografía"}, as_of=TODAY)
        self.assertEqual(value["status"], "review")
        self.assertEqual(value["reason"], "niche_unverified")
        verified = rs.assess_candidate({"network": "x", "surface": "bio",
                                         "text": "f4f", "niche_verified": True}, as_of=TODAY)
        self.assertEqual(verified["status"], "eligible")

    def test_post_freshness_enforced_even_when_declared(self):
        candidate = {"network": "tiktok", "surface": "post",
                     "text": "Comenta y te comento, libros"}
        self.assertEqual(rs.assess_candidate(candidate, as_of=TODAY)["reason"], "post_age_unknown")
        candidate["created_on"] = "2026-10-02"
        self.assertEqual(rs.assess_candidate(candidate, as_of=TODAY)["reason"], "stale_post")
        candidate["created_on"] = "2026-10-03"
        self.assertEqual(rs.assess_candidate(candidate, as_of=TODAY)["status"], "eligible")
        candidate["created_on"] = "2026-10-12"
        self.assertEqual(rs.assess_candidate(candidate, as_of=TODAY)["reason"], "post_age_unknown")

    def test_legacy_phrases_are_not_lost_when_integrating(self):
        for bio in ("Sigo de regreso, lectores", "Síguenos y te seguimos, libros",
                    "Sigo a quienes me siguen, autoras"):
            with self.subTest(bio=bio):
                self.assertEqual(reciprocity.declared_bonus(bio), 2.5)

    def test_existing_reciprocity_bonus_uses_real_intent(self):
        self.assertEqual(reciprocity.declared_bonus("Leo libros. Sigo de vuelta"), 2.5)
        self.assertEqual(reciprocity.declared_bonus("No hago followback. Leo libros"), 0.0)
        self.assertEqual(reciprocity.declared_bonus("Qué significa f4f"), 0.0)

    def test_existing_query_pipeline_adds_without_duplicates(self):
        original_path = discovery_terms.PATH
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as path:
                discovery_terms.PATH = os.path.join(path, "terms.json")
                Path(discovery_terms.PATH).write_text(json.dumps({
                    "x": {"busquedas": ["sigo de vuelta libros", "fantasía juvenil"],
                          "hashtags": ["#FollowBack", "booktok"]}}), encoding="utf-8")
                values = discovery_terms.terms("x")
                self.assertEqual(values.count("sigo de vuelta libros"), 1)
                self.assertIn("fantasía juvenil", values)
                self.assertIn("comentario por comentario escritores", values)
                self.assertEqual(discovery_terms.terms("x", skip=("sigo de vuelta libros",)),
                                 ["fantasía juvenil", "comentario por comentario escritores"])
                self.assertEqual(discovery_terms.terms("x", "hashtags"),
                                 ["FollowBack", "booktok", "SiguemeYTeSigo"])
                self.assertIn(" lang:es", discovery_terms.terms("x", suffix=" lang:es")[0])
        finally:
            discovery_terms.PATH = original_path

    def test_discovery_terms_work_if_local_json_absent(self):
        initial = discovery_terms.PATH
        try:
            discovery_terms.PATH = os.path.join("/nonexistent", "never_found.json")
            self.assertEqual(discovery_terms.terms("reddit"),
                             list(rs.search_terms("reddit")))
        finally:
            discovery_terms.PATH = initial

    def test_outcomes_only_verified_mature_and_distinct(self):
        def row(actor, kind="follow_exchange", **extra):
            return {"network": "x", "kind": kind, "actor_id": actor,
                    "source_id": "synthetic-search-1", "observed_on": "2026-10-01",
                    "verified": True, "relation_active": True,
                    "comments": False, "visits": None, **extra}
        records = [row("a"), row("a"), row("b", kind="reading_chain"),
                   row("c", verified=False), row("d", observed_on="2026-10-09"),
                   row("e", relation_active=None, comments=True),
                   row("f", source_id="synthetic-search-2", visits=True)]
        report = rs.outcome_report(records, as_of=TODAY)
        f = report["x/follow_exchange"]
        self.assertEqual(f["relation_active"], {"confirmed": 2, "observed": 2, "rate": 1.0})
        self.assertEqual(f["comments"], {"confirmed": 1, "observed": 3, "rate": 0.333})
        self.assertEqual(f["visits"], {"confirmed": 1, "observed": 1, "rate": 1.0})
        self.assertEqual(report["x/reading_chain"]["relation_active"]["observed"], 1)

    def test_outcome_report_preserves_two_signal_kinds_from_same_source(self):
        shared = {"network": "x", "actor_id": "synthetic-a", "source_id": "search-1",
                  "observed_on": "2026-10-01", "verified": True}
        records = [
            {**shared, "kind": "follow_exchange", "relation_active": True},
            {**shared, "kind": "reading_chain", "comments": True},
        ]
        report = rs.outcome_report(records, as_of=TODAY)
        self.assertEqual(
            report["x/follow_exchange"]["relation_active"]["observed"], 1
        )
        self.assertEqual(report["x/reading_chain"]["comments"]["confirmed"], 1)

    def test_outcomes_do_not_confuse_platform_identity(self):
        records = [
            {"network": net, "kind": "follow_exchange", "actor_id": "shared",
             "source_id": "search-1", "observed_on": "2026-10-01", "verified": True,
             "relation_active": net == "x"} for net in ("x", "mastodon")
        ]
        report = rs.outcome_report(records, as_of=TODAY)
        self.assertEqual(report["x/follow_exchange"]["relation_active"]["confirmed"], 1)
        self.assertEqual(report["mastodon/follow_exchange"]["relation_active"]["confirmed"], 0)

    def test_invalid_input_is_not_silently_actionable(self):
        self.assertEqual(rs.assess_candidate({"network": "other", "surface": "post",
                                              "text": "f4f libros"}, as_of=TODAY)["status"], "rejected")
        with self.assertRaises(ValueError):
            rs.assess_candidate(None, as_of=TODAY)
        with self.assertRaises(ValueError):
            rs.evaluate([{"network": "x"}], as_of=TODAY)
        with self.assertRaises(ValueError):
            rs.outcome_report([], as_of=TODAY, min_age_days=-1)


if __name__ == "__main__":
    unittest.main()

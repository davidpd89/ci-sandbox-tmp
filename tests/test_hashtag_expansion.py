"""Contrato sintético sin credenciales, red ni estado vivo."""
import json
import pathlib
import subprocess
import unicodedata
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import hashtag_expansion as h
import discovery_terms

NOW = "2026-10-10T12:00:00+00:00"
RECENT = "2026-10-09T12:00:00+00:00"


def posts(network="bluesky", tag="FantasiaÉpica", n=3, seed="fantasía",
          source="api", date=RECENT):
    return [{"network": network, "source": source,
             "post_id": f"{network}-{tag}-{i}", "author_id": f"a{i}",
             "created_at": date, "text": f"Leo {seed} y #{tag}"}
            for i in range(n)]


class HashtagExpansionTest(unittest.TestCase):
    def build(self, rows, **kwargs):
        return h.build_snapshot(rows, now=NOW, seeds={"fantasia": ["fantasía"]}, **kwargs)

    def test_two_networks_not_leaking_and_provenance(self):
        result = self.build(posts() + posts("mastodon", source="stream"))
        self.assertEqual(result["networks"]["bluesky"]["hashtags"], ["fantasiaépica"])
        self.assertEqual(result["networks"]["mastodon"]["hashtags"], ["fantasiaépica"])
        self.assertEqual(result["networks"]["reddit"]["hashtags"], [])
        self.assertEqual(result["networks"]["mastodon"]["candidates"][0]["sources"], ["stream"])
        self.assertEqual(result["diagnostics"]["selected"], 2)

    def test_unique_post_distinct_authors_and_sources(self):
        rows = posts(n=2)
        rows.append({**rows[0], "source": "jetstream"})
        result = self.build(rows)
        candidate = result["networks"]["bluesky"]["candidates"][0]
        self.assertEqual(candidate["sources"], ["api", "jetstream"])
        self.assertEqual(candidate["posts"], 2)
        self.assertEqual(candidate["authors"], 2)
        self.assertEqual(result["diagnostics"]["duplicates"], 1)
        self.assertFalse(self.build(posts(n=1) * 5)["networks"]["bluesky"]["hashtags"])

    def test_old_future_and_naive_dates_skipped(self):
        rows = (posts(tag="Antiguo", date="2026-09-01T12:00:00Z") +
                posts(tag="Futuro", date="2026-10-11T12:00:00Z") +
                posts(tag="SinZona", date="2026-10-09T12:00:00"))
        result = self.build(rows)
        self.assertEqual(result["networks"]["bluesky"]["hashtags"], [])
        self.assertEqual(result["diagnostics"]["stale"], 6)
        self.assertEqual(result["diagnostics"]["invalid"], 3)

    def test_noise_unrelated_and_weak_association(self):
        rows = posts(tag="SorteoGratis") + posts(tag="Fantasía")
        rows += posts(tag="Tendencia", n=2)
        noise = posts(tag="Tendencia", seed="fútbol", n=5)
        for i, row in enumerate(noise):
            row["post_id"] = f"elsewhere-{i}"
        rows += noise
        rows += posts(tag="Futbol", seed="fútbol")
        self.assertEqual(self.build(rows)["networks"]["bluesky"]["hashtags"], [])

    def test_unicode_casefold_and_multiple_tags(self):
        rows = posts(tag="NiñezLectóra", n=2)
        rows += posts(tag="NIÑEZLECTÓRA", n=2)
        rows += posts(tag=unicodedata.normalize("NFD", "NiñezLectóra"), n=2)
        result = self.build(rows)
        self.assertEqual(result["networks"]["bluesky"]["hashtags"], ["niñezlectóra"])
        self.assertEqual(h.extract("Prueba #" + unicodedata.normalize("NFD", "NiñezLectóra")),
                         {"niñezlectóra"})

    def test_distinct_spanish_hashtags_do_not_collide(self):
        rows = posts(tag="Año") + posts(tag="Ano")
        rows += posts(tag="Niño") + posts(tag="Nino")
        actual = self.build(rows)["networks"]["bluesky"]["hashtags"]
        self.assertEqual(set(actual), {"año", "ano", "niño", "nino"})

    def test_accented_noise_stays_excluded(self):
        self.assertEqual(h.extract("Libro #Sórteo #Crýpto"), set())
        self.assertEqual(h.extract("Libro #Año"), {"año"})

    def test_feedback_changes_score(self):
        rows = posts(tag="Aventura", n=4) + posts(tag="Biblioteca", n=4)
        feedback = [
            {"network": "bluesky", "tag": "Aventura", "eligible": 20,
             "engaged": 18, "replies": 5, "followers": 2},
            {"network": "bluesky", "tag": "Biblioteca", "eligible": 20, "engaged": 0},
        ]
        result = self.build(rows, feedback=feedback)
        scores = {x["tag"]: x["score"]
                  for x in result["networks"]["bluesky"]["candidates"]}
        self.assertGreater(scores["aventura"], scores["biblioteca"])

    def test_topic_diversity_not_only_highest_frequency(self):
        rows = posts(tag="Magia", n=3) + posts(tag="Dragones", n=3)
        rows += posts(tag="Lectores", seed="lectura", n=3)
        result = h.build_snapshot(rows, now=NOW,
                                  seeds={"fantasia": ["fantasía"], "lectura": ["lectura"]},
                                  max_per_network=2)
        topics = {x["topic"] for x in result["networks"]["bluesky"]["candidates"]}
        self.assertEqual(topics, {"fantasia", "lectura"})

    def test_cache_expired_or_malformed_is_noop(self):
        result = self.build(posts())
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "out.json"
            h.save_snapshot(path, result)
            self.assertEqual(h.snapshot_terms("bluesky", path=path, now=NOW),
                             ["fantasiaépica"])
            self.assertEqual(h.snapshot_terms("bluesky", path=path,
                                              now="2026-10-13T12:00:00Z"), [])
            path.write_text('{"wrong": true}', encoding="utf-8")
            self.assertEqual(h.snapshot_terms("bluesky", path=path, now=NOW), [])

    def test_all_networks_have_explicit_search_and_tag_policy(self):
        rows = sum((posts(network=network) for network in h.NETWORKS), [])
        result = self.build(rows)
        self.assertEqual(set(result["networks"]), h.NETWORKS)
        for network in h.NETWORKS:
            self.assertEqual(result["networks"][network]["busquedas"], ["fantasiaépica"])
            self.assertEqual(bool(result["networks"][network]["hashtags"]),
                             network in h.TAG_NETWORKS)

    def test_terms_integration_and_static_fallback(self):
        result = self.build(posts())
        with tempfile.TemporaryDirectory() as folder:
            static, overlay = (pathlib.Path(folder) / name for name in ("static.json", "overlay.json"))
            static.write_text('{"bluesky":{"hashtags":["#FantasiaÉpica","BookSky"]}}',
                              encoding="utf-8")
            h.save_snapshot(overlay, result)
            original = h.snapshot_terms
            with patch.object(discovery_terms, "PATH", str(static)), \
                 patch.object(h, "DEFAULT_CACHE", overlay), \
                 patch.object(h, "snapshot_terms", side_effect=lambda network, kind: original(network, kind, now=NOW)):
                self.assertEqual(discovery_terms.terms("bluesky", "hashtags",
                                                      skip=["BookSky"]), ["FantasiaÉpica"])
                static.unlink()
                self.assertEqual(discovery_terms.terms("bluesky", "hashtags"),
                                 ["fantasiaépica"])

    def test_package_style_import_from_repo_root(self):
        # Un proceso nuevo evita que el sys.path modificado por este test oculte
        # el fallo de imports que aparece en los consumidores externos.
        root = pathlib.Path(__file__).resolve().parents[1]
        script = ("from tools import discovery_terms; "
                  "print(discovery_terms.terms('bluesky', 'hashtags'))")
        run = subprocess.run([sys.executable, "-c", script], cwd=root,
                             capture_output=True, text=True, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_malformed_static_network_entry_falls_back_without_crashing(self):
        with tempfile.TemporaryDirectory() as folder:
            static = pathlib.Path(folder) / "catalog.json"
            with patch.object(discovery_terms, "PATH", str(static)), \
                 patch.object(h, "snapshot_terms", return_value=[]):
                for document in ('{"bluesky": "not-a-dict"}',
                                 '{"bluesky": ["no"]}',
                                 '{"bluesky": {"hashtags": "wrong-type"}}',
                                 '["invalid-root"]'):
                    with self.subTest(document=document):
                        static.write_text(document, encoding="utf-8")
                        self.assertEqual(discovery_terms.terms("bluesky", "hashtags"), [])

    def test_cli_synthetic_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            source, out = (pathlib.Path(folder) / n for n in ("fixture.json", "overlay.json"))
            source.write_text(json.dumps(posts(), ensure_ascii=False), encoding="utf-8")
            self.assertEqual(h.main(["--observations", str(source), "--output", str(out),
                                     "--now", NOW]), 0)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["schema"], 1)

    def test_synthetic_quality_precision_recall_improvement(self):
        rows = posts(tag="FantasiaEpica") + posts(tag="LecturaMagica")
        rows += posts(tag="SorteoGratis") + posts(tag="Futbol", seed="fútbol")
        result = self.build(rows)
        predicted = set(result["networks"]["bluesky"]["hashtags"])
        gold = {"fantasiaepica", "lecturamagica"}
        precision = len(predicted & gold) / max(1, len(predicted))
        recall = len(predicted & gold) / len(gold)
        self.assertEqual((precision, recall), (1, 1))
        self.assertGreater(recall, 0)  # semillas fijas no incluyen estas etiquetas


if __name__ == "__main__":
    unittest.main()

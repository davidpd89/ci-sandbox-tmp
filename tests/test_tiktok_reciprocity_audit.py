import datetime
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import tiktok_reciprocity_audit as audit


class SourceParsingTests(unittest.TestCase):
    def test_bulk_sources_keep_seed_or_query(self):
        self.assertEqual(
            audit.source_from_notes("bulk:followers:@autora | transporte=android_native"),
            "followers:@autora",
        )
        self.assertEqual(
            audit.source_from_notes("bulk:mutual:escritores apoyémonos | transporte=android_native"),
            "mutual:escritores apoyémonos",
        )

    def test_followback_auto_and_unknown_are_separate(self):
        self.assertEqual(audit.source_from_notes("bulk:followback:nuevo_seguidor"), "followback")
        self.assertEqual(audit.source_from_notes("auto:T001:score=8"), "auto")
        self.assertEqual(audit.source_from_notes("manual"), "otros")


class FollowLogTests(unittest.TestCase):
    def test_first_confirmed_follow_per_handle_is_used(self):
        rows = [
            "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas",
            "2026-10-08,@Ana,follow,,,confirmado,bulk:mutual:q1",
            "2026-10-09,@ana,follow,,,confirmado,bulk:followers:@seed",
            "2026-10-08,@b,follow,,,fallo,bulk:mutual:q2",
            "2026-10-10,@c,like,,,confirmado,bulk:mutual:q3",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "registro.csv"
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            with mock.patch.object(audit.bulk, "REGISTRO_CSV", str(path)):
                out = audit.all_follows(datetime.date(2026, 10, 12))
        self.assertEqual(out, [("ana", "2026-10-08", "mutual:q1")])


class ObservationTests(unittest.TestCase):
    def test_first_observed_followback_never_moves_forward(self):
        follows = [("ana", "2026-10-08", "mutual:q")]
        observed_since, first = audit.update_back_observations(
            follows,
            {"ana"},
            {},
            datetime.date(2026, 10, 9),
        )
        self.assertEqual(observed_since, "2026-10-09")
        self.assertEqual(first["ana"], "2026-10-09")

        observed_since2, first2 = audit.update_back_observations(
            follows,
            {"ana"},
            {"observed_since": observed_since, "first_back_date": first},
            datetime.date(2026, 10, 12),
        )
        self.assertEqual(observed_since2, "2026-10-09")
        self.assertEqual(first2["ana"], "2026-10-09")

    def test_deadlines_use_real_first_seen_date_and_exclude_pre_observation_follows(self):
        follows = [
            ("old", "2026-10-01", "mutual:old"),
            ("fast", "2026-10-08", "mutual:q"),
            ("slow", "2026-10-08", "followers:@seed"),
            ("never", "2026-10-08", "followers:@seed"),
            ("young", "2026-10-14", "mutual:q"),
        ]
        first_back = {
            "old": "2026-10-08",
            "fast": "2026-10-09",
            "slow": "2026-10-12",
        }
        out = audit.deadline_summary(
            follows,
            first_back,
            observed_since="2026-10-08",
            today=datetime.date(2026, 10, 16),
        )

        self.assertNotIn("mutual:old", out["D+1"])
        self.assertEqual(out["D+1"]["mutual:q"], {"followed": 2, "back": 1, "rate": 0.5})
        self.assertEqual(out["D+1"]["followers:@seed"], {"followed": 2, "back": 0, "rate": 0.0})
        self.assertEqual(out["D+3"]["followers:@seed"], {"followed": 2, "back": 0, "rate": 0.0})
        self.assertEqual(out["D+7"]["followers:@seed"], {"followed": 2, "back": 1, "rate": 0.5})

    def test_young_follows_wait_until_their_deadline(self):
        follows = [("ana", "2026-10-15", "mutual:q")]
        out = audit.deadline_summary(
            follows,
            {"ana": "2026-10-16"},
            observed_since="2026-10-15",
            today=datetime.date(2026, 10, 16),
        )
        self.assertIn("mutual:q", out["D+1"])
        self.assertEqual(out["D+1"]["mutual:q"]["back"], 1)
        self.assertEqual(out["D+3"], {})
        self.assertEqual(out["D+7"], {})


class ObservationIntegrityTests(unittest.TestCase):
    def test_existing_follower_is_not_counted_as_new_acquisition(self):
        follows = [
            ("prior", "2026-10-08", "followback"),
            ("new", "2026-10-08", "mutual:lectura"),
        ]
        out = audit.deadline_summary(
            follows, {"prior": "2026-10-08", "new": "2026-10-09"},
            "2026-10-08", today=datetime.date(2026, 10, 16),
        )
        self.assertNotIn("followback", out["D+1"])
        self.assertEqual(out["D+1"]["mutual:lectura"], {"followed": 1, "back": 1, "rate": 1.0})

    def test_corrupt_existing_state_is_never_replaced_by_empty_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "reciprocity_audit.json"
            path.write_text('{"observed_since":"2026-10-08",', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ilegible"):
                audit.load_audit_state(str(path))
            self.assertTrue(path.read_text(encoding="utf-8").endswith(","))

    def test_partial_scan_preserves_positives_without_replacing_older_rates(self):
        state = {
            "observed_since": "2026-10-08",
            "first_back_date": {"antigua": "2026-10-09"},
            "sources": {"mutual:q": {"followed": 5, "back": 2, "rate": 0.4}},
            "deadlines": {"D+1": {"mutual:q": {"followed": 4, "back": 1, "rate": 0.25}}},
        }
        follows = [
            ("antigua", "2026-10-08", "mutual:q"),
            ("nueva", "2026-10-10", "followers:@semilla"),
        ]
        updated = audit.partial_snapshot_state(
            follows, ["nueva"], state, datetime.date(2026, 10, 11)
        )
        self.assertEqual(updated["first_back_date"]["antigua"], "2026-10-09")
        self.assertEqual(updated["first_back_date"]["nueva"], "2026-10-11")
        self.assertEqual(updated["sources"], state["sources"])
        self.assertEqual(updated["deadlines"], state["deadlines"])
        self.assertEqual(updated["last_partial_followers_read"], 1)

    def test_bad_state_schema_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "audit.json"
            for contents in ('[]', '{"observed_since": "oops"}', '{"first_back_date": []}'):
                path.write_text(contents, encoding="utf-8")
                with self.assertRaises(ValueError):
                    audit.load_audit_state(str(path))

    def test_atomic_save_preserves_old_file_after_write_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "audit.json"
            path.write_text('{"safe": true}', encoding="utf-8")
            with mock.patch.object(audit.json, "dump", side_effect=OSError("write failed")):
                with self.assertRaises(OSError):
                    audit.save_audit_state({"safe": False}, str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), '{"safe": true}')
            self.assertEqual([p.name for p in pathlib.Path(tmp).iterdir()], ["audit.json"])

    def test_atomic_save_succeeds_and_keeps_persisted_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "audit.json"
            path.write_text('{"old": 1}', encoding="utf-8")
            audit.save_audit_state({"observed_since": "2026-10-08",
                                    "first_back_date": {"ana": "2026-10-09"}}, str(path))
            self.assertEqual(audit.load_audit_state(str(path))["first_back_date"]["ana"], "2026-10-09")


<<<<<<< HEAD
=======

class SharedCohortIntegrationTests(unittest.TestCase):
    def test_partial_snapshot_preserves_complete_checkpoints_and_kpis(self):
        historic = {
            "observed_since": "2026-10-08",
            "first_back_date": {"original": "2026-10-09"},
            "complete_dates": ["2026-10-09"],
            "cohorts_v2": {"schema_version": 2, "windows": {"D+1": {"q": {"unknown": 1}}}},
            "deadlines": {"D+1": {"q": {"followed": 1, "back": 0, "rate": 0.0}}},
        }
        updated = audit.partial_snapshot_state([], {"partial"}, historic,
                                               datetime.date(2026, 10, 12))
        self.assertEqual(updated["complete_dates"], ["2026-10-09"])
        self.assertEqual(updated["cohorts_v2"], historic["cohorts_v2"])
        self.assertEqual(updated["deadlines"], historic["deadlines"])
        self.assertFalse(updated["coverage_complete"])

    def test_load_rejects_invalid_complete_dates_without_repairing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "audit.json"
            content = '{"observed_since":"2026-10-08","complete_dates":["nunca"]}'
            path.write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "complete_dates"):
                audit.load_audit_state(str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), content)


>>>>>>> origin/research/public-reuse-parent
class SeedPersistenceTests(unittest.TestCase):
    def test_corrupt_seed_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "bulk_seeds.json"
            path.write_text('{"seed":', encoding="utf-8")
            with mock.patch.object(audit.bulk, "SEEDS_PATH", str(path)):
                updated = audit.update_seeds({"followers:@autora": {"followed": 4, "back": 3, "rate": 0.75}})
            self.assertFalse(updated)
            self.assertEqual(path.read_text(encoding="utf-8"), '{"seed":')

    def test_seed_scores_are_updated_without_erasing_unrelated_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "bulk_seeds.json"
            path.write_text('{"autora":{"extra":1},"otra":{"yield":0.8}}', encoding="utf-8")
            with mock.patch.object(audit.bulk, "SEEDS_PATH", str(path)):
                self.assertTrue(audit.update_seeds({
                    "followers:@autora": {"followed": 5, "back": 2, "rate": 0.4},
                    "mutual:q": {"followed": 5, "back": 3, "rate": 0.6},
                }))
            import json
            updated = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(updated["autora"]["extra"], 1)
            self.assertEqual(updated["autora"]["followed"], 5)
            self.assertEqual(updated["otra"], {"yield": 0.8})
            self.assertEqual(list(pathlib.Path(tmp).iterdir()), [path])


class AdaptiveFollowerCoverageTests(unittest.TestCase):
    def test_row_budget_grows_with_profile_instead_of_freezing_at_400(self):
        self.assertEqual(audit.adaptive_row_budget(400, None), 400)
        self.assertEqual(audit.adaptive_row_budget(400, 100), 400)
        self.assertGreater(audit.adaptive_row_budget(400, 2100), 2100)
        self.assertGreater(audit.adaptive_row_budget(400, 4500), 4500)

    def test_profile_counter_separate_label_or_combined(self):
        import sys
        from types import SimpleNamespace

        def node(text, x, y):
            return {"rect": {"x": x, "y": y}, "text": text}

        source = SimpleNamespace(
            _norm=lambda x: x.strip().casefold(),
            _tiktok_elements=lambda tree: tree,
            clean=lambda x: x.strip(),
            element_texts=lambda e: [e["text"]],
            parse_count=lambda s: 1200 if s in ("1,2 mil", "1,2 mil seguidores") else
                905 if s == "Seguidores 905" else int(s) if s.isdigit() else None,
        )
        with mock.patch.dict(sys.modules, {"tiktok_mobile_nav": source}):
            self.assertEqual(audit.profile_follower_count([
                node("1,2 mil", 500, 434), node("Seguidores", 500, 510),
                node("Siguiendo", 260, 510),
            ]), 1200)
            self.assertEqual(audit.profile_follower_count([
                node("1,2 mil seguidores", 500, 510),
            ]), 1200)
            self.assertEqual(audit.profile_follower_count([
                node("Seguidores 905", 500, 510),
            ]), 905)
            self.assertEqual(audit.profile_follower_count([
                node("Seguidores", 500, 510),
                node("Seguidores", 500, 510),  # nodo accesible duplicado
                node("905", 500, 440),
            ]), 905)
            self.assertIsNone(audit.profile_follower_count([
                node("Seguidores", 500, 510), node("Siguiendo", 260, 510)
            ]))

    def test_renamed_handle_without_stable_id_does_not_invent_positive(self):
        follows = [("cuenta_original", "2026-10-08", "followers:@semilla")]
        observed = audit.update_back_observations(
            follows, {"nuevo_nombre"}, {}, datetime.date(2026, 10, 9)
        )[1]
        self.assertNotIn("cuenta_original", observed)
        # La equivalencia entre handles no se puede inferir: requiere un ID estable.
        historic = audit.deadline_summary(
            follows, observed, "2026-10-08", today=datetime.date(2026, 10, 16)
        )
        self.assertEqual(historic["D+1"]["followers:@semilla"]["back"], 0)

class FollowerTabCoverageTests(unittest.TestCase):
    def _scan(self, max_rows, batches, *, present=True, expected_count=None):
        import sys
        from types import SimpleNamespace

        header = {"rect": {"y": 100}, "text": "seguidores"}
        elements = (lambda _tree: [header] if present else [])
        dummy_mobile = SimpleNamespace(element_center=lambda target: (400, 200))
        dummy_nav_mod = SimpleNamespace(
            _norm=lambda x: x, _tiktok_elements=elements,
            clean=lambda x: x, element_texts=lambda el: [el["text"]],
        )
        client = SimpleNamespace(tap=mock.Mock(), swipe=mock.Mock())
        nav = SimpleNamespace(tree=lambda: [], c=client, device=SimpleNamespace(id="device"))
        with mock.patch.dict(sys.modules, {"mobile_client": dummy_mobile, "tiktok_mobile_nav": dummy_nav_mod}):
            with mock.patch.object(audit.bulk, "parse_follower_rows", side_effect=batches) as parse:
                with mock.patch.object(audit.time, "sleep"):
                    result = audit.read_tab(nav, "seguidores", max_rows, expected_count=expected_count)
        return result, parse.call_count

    def test_limit_reached_never_asserts_complete(self):
        rows, calls = self._scan(1, [[{"handle": "ana"}]])
        self.assertEqual(rows, (["ana"], False))
        self.assertGreaterEqual(calls, 1)
        # Este resultado parcial no debe alimentar tasas ni selección de semillas.
        self.assertFalse(self._scan(1, [[{"handle": "ana"}]])[0][1])

    def test_two_passes_without_new_handles_end_complete_snapshot(self):
        rows, count = self._scan(
            8,
            [[{"handle": "ana"}], [{"handle": "ana"}], [{"handle": "ana"}]],
            expected_count=1,
        )
        self.assertEqual(rows, (["ana"], True))
        self.assertGreaterEqual(count, 3)
        self.assertTrue(self._scan(
            8, [[{"handle": "ana"}], [{"handle": "ana"}], [{"handle": "ana"}]], expected_count=1
        )[0][1])

    def test_stalled_list_cannot_claim_coverage_when_profile_has_more_followers(self):
        rows, passes = self._scan(
            450,
            [[{"handle": "ana"}], [{"handle": "ana"}], [{"handle": "ana"}]],
            expected_count=1800,
        )
        self.assertEqual(rows, (["ana"], False))
        self.assertGreaterEqual(passes, 3)

    def test_no_profile_counter_does_not_assume_bottom_from_repeated_rows(self):
        rows, _ = self._scan(
            30, [[{"handle": "ana"}], [{"handle": "ana"}], [{"handle": "ana"}]],
            expected_count=None,
        )
        self.assertEqual(rows, (["ana"], False))

    def test_same_handle_twice_on_one_screen_is_counted_only_once(self):
        rows, calls = self._scan(
            10,
            [[{"handle": "@Ana"}, {"handle": "ana"}, {"handle": "ANA"}],
             [{"handle": "ana"}, {"handle": "b"}],
             [{"handle": "b"}, {"handle": "ana"}],
             [{"handle": "ana"}, {"handle": "b"}]],
            expected_count=2,
        )
        self.assertEqual(rows, (["ana", "b"], True))
        self.assertEqual(calls, 4)

    def test_two_declared_followers_one_seen_is_not_complete(self):
        rows, _ = self._scan(
            10,
            [[{"handle": "ana"}], [{"handle": "ana"}], [{"handle": "ana"}]],
            expected_count=2,
        )
        self.assertEqual(rows, (["ana"], False))

    def test_exact_counter_905_does_not_allow_850_rows(self):
        # Este contador aún no viene abreviado: faltan 55 seguidores.
        batches = [[{"handle": f"u{n}"} for n in range(850)]]
        batches.extend([[{"handle": "u849"}]] * 2)
        rows, calls = self._scan(1200, batches, expected_count=905)
        self.assertEqual(len(rows[0]), 850)
        self.assertFalse(rows[1])
        self.assertEqual(calls, 3)

    def test_duplicate_handles_cannot_fake_complete_scan(self):
        rows, _ = self._scan(
            10,
            [[{"handle": "a"}, {"handle": "a"}, {"handle": "a"}],
             [{"handle": "a"}], [{"handle": "a"}]],
            expected_count=3,
        )
        self.assertEqual(rows, (["a"], False))

    def test_large_screen_batch_stops_at_budget_without_false_complete(self):
        rows, calls = self._scan(
            2, [[{"handle": "a"}, {"handle": "b"}, {"handle": "c"}]],
            expected_count=3,
        )
        self.assertEqual(rows, (["a", "b"], False))
        self.assertEqual(calls, 1)

    def test_missing_followers_tab_is_incomplete(self):
        self.assertEqual(self._scan(8, [], present=False)[0], ([], False))


if __name__ == "__main__":
    unittest.main()

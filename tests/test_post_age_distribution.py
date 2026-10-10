"""Regresiones offline para la distribucion de edad de publicaciones (#61)."""
import contextlib
import datetime as dt
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import post_age_distribution as age

NOW = dt.datetime(2026, 10, 10, 12, 0, tzinfo=dt.timezone.utc)


def iso(hours, *, offset=dt.timezone.utc):
    return (NOW - dt.timedelta(hours=hours)).astimezone(offset).isoformat()


class AgeDistributionTests(unittest.TestCase):
    def test_all_nine_networks_and_absent_vs_empty(self):
        self.assertEqual(len(age.NETWORKS), 9)
        result = age.report_samples({"reddit": []}, now=NOW)
        self.assertEqual(result["reddit"]["estado"], "ok")
        self.assertEqual(result["reddit"]["total"], 0)
        for net in age.NETWORKS:
            if net != "reddit":
                self.assertEqual(result[net]["estado"], "sin_muestra")

    def test_windows_cumulative_edges_second_precision(self):
        samples = [
            {"post_created_at": iso(0)},
            {"post_created_at": iso(24)},
            {"post_created_at": iso(24 + 1 / 3600)},
            {"post_created_at": iso(72)},
            {"post_created_at": iso(72 + 1 / 3600)},
            {"post_created_at": iso(168)},
            {"post_created_at": iso(168 + 1 / 3600)},
            {},
        ]
        for net in age.NETWORKS:
            with self.subTest(net=net):
                result = age.distribution(net, samples, now=NOW)
                self.assertEqual((result["hasta_24h"], result["hasta_72h"], result["hasta_7d"]), (2, 4, 6))
                self.assertEqual(result["rangos"]["over_168h"], 1)
                self.assertEqual(result["rangos"]["unknown"], 1)
                self.assertEqual(sum(result["rangos"].values()), result["total"])

    def test_timezone_offsets_and_dst_transition(self):
        plus2 = dt.timezone(dt.timedelta(hours=2))
        minus4 = dt.timezone(dt.timedelta(hours=-4))
        # Dos offsets explicitos cruzan el cambio horario sin datetime local naive.
        for value in (
            iso(24, offset=plus2),
            iso(24, offset=minus4),
            dt.datetime.fromisoformat(iso(24, offset=plus2)),
            dt.datetime.fromisoformat(iso(24, offset=minus4)),
        ):
            self.assertEqual(age.classify("x", {"post_created_at": value}, now=NOW)[0], "0_24h")
        before_dst = dt.datetime(2026, 3, 29, 1, tzinfo=dt.timezone(dt.timedelta(hours=1)))
        after_dst = dt.datetime(2026, 3, 29, 3, tzinfo=dt.timezone(dt.timedelta(hours=2)))
        self.assertEqual((after_dst - before_dst.astimezone(dt.timezone.utc)).total_seconds(), 3600)

    def test_wrong_timezone_naive_does_not_gain_age(self):
        for value in ("2026-10-10T11:00:00", "2026-10-10", dt.datetime(2026, 10, 10, 11, 0), True, False):
            self.assertEqual(age.classify("threads", {"post_created_at": value}, now=NOW)[0], "unknown")

    def test_reddit_and_tiktok_api_epoch(self):
        ts = int((NOW - dt.timedelta(hours=72)).timestamp())
        self.assertEqual(age.classify("reddit", {"created_utc": ts}, now=NOW)[0], "24_72h")
        self.assertEqual(age.classify("tiktok", {"create_time": str(ts)}, now=NOW)[0], "24_72h")
        self.assertEqual(age.classify("tiktok", {"create_time": ts * 1000}, now=NOW)[0], "24_72h")

    def test_queued_time_indexed_time_first_seen_not_valid(self):
        for net in age.NETWORKS:
            for field in ("created_at", "createdAt", "indexedAt", "indexed_at",
                          "queued_at", "first_seen_at", "observed_at", "updated_at"):
                with self.subTest(net=net, field=field):
                    self.assertEqual(age.classify(net, {field: iso(1)}, now=NOW), ("unknown", "none"))

    def test_verified_scanner_root_post_can_use_created_at(self):
        result = age.classify("mastodon", {"source_kind": "post", "created_at": iso(2)}, now=NOW)
        self.assertEqual(result, ("0_24h", "post.created_at"))
        self.assertEqual(age.classify("mastodon", {"source_kind": "action", "created_at": iso(2)}, now=NOW)[0], "unknown")

    def test_nested_api_fields_with_origins(self):
        samples = (
            ("bluesky", {"post": {"record": {"createdAt": iso(2)}}}, "post.record.createdAt"),
            ("mastodon", {"status": {"created_at": iso(2)}}, "status.created_at"),
            ("facebook", {"post": {"created_time": iso(2)}}, "post.created_time"),
            ("instagram", {"media": {"timestamp": iso(2)}}, "media.timestamp"),
            ("pinterest", {"post": {"published_at": iso(2)}}, "post.published_at"),
            ("threads", {"record": {"createdAt": iso(2)}}, "record.createdAt"),
            ("x", {"post": {"created_at": iso(2)}}, "post.created_at"),
        )
        for net, item, source in samples:
            with self.subTest(net=net):
                self.assertEqual(age.classify(net, item, now=NOW), ("0_24h", source))

    def test_contradictory_origin_never_picks_newest(self):
        item = {"target_created_at": iso(2), "post": {"created_at": iso(200)}}
        for net in age.NETWORKS:
            self.assertEqual(age.classify(net, item, now=NOW), ("conflict", "multiple"))
        result = age.distribution("bluesky", [item], now=NOW)
        self.assertEqual(result["hasta_7d"], 0)
        self.assertEqual(result["rangos"]["conflict"], 1)

    def test_equal_dates_with_millisecond_drift_are_not_conflict(self):
        item = {"post_created_at": iso(1), "post": {"created_at": iso(1 + 0.5 / 3600)}}
        self.assertEqual(age.classify("instagram", item, now=NOW)[0], "0_24h")

    def test_far_future_is_not_fresh_and_small_clock_skew(self):
        self.assertEqual(age.classify("x", {"post_created_at": iso(-10 / 60)}, now=NOW)[0], "future")
        self.assertEqual(age.classify("x", {"post_created_at": iso(-4 / 60)}, now=NOW)[0], "0_24h")

    def test_invalid_epoch_overflow_and_boolean_are_unknown(self):
        values = (True, False, -12, 0, "100", "999999999999999999999999",
                  float("inf"), float("nan"), object())
        for value in values:
            with self.subTest(value=str(value)):
                self.assertEqual(age.classify("reddit", {"created_utc": value}, now=NOW)[0], "unknown")

    def test_post_id_is_not_timestamp(self):
        for net in ("x", "bluesky", "mastodon", "threads"):
            row = {"status_id": "123456789987654321", "post_url": "https://example.invalid/post/abc"}
            self.assertEqual(age.classify(net, row, now=NOW)[0], "unknown")

    def test_invalid_input_is_rejected_without_writes(self):
        with self.assertRaises(ValueError):
            age.report_samples({"made_up": []}, now=NOW)
        with self.assertRaises(ValueError):
            age.distribution("x", {}, now=NOW)
        with self.assertRaises(ValueError):
            age.classify("x", {}, now=dt.datetime(2026, 10, 10))

    def test_profile_actions_do_not_inflate_post_unknowns_across_networks(self):
        # Los planes reales mezclan follows a perfiles y acciones sobre posts.
        rows = [
            {"kind": "follow"},
            {"kind": "follow_external", "post_created_at": iso(1)},
            {"kind": "followback"},
            {"kind": "unfollow"},
            {"kind": "reply", "post_created_at": iso(3)},
            {"kind": "like"},  # Post destino sin fecha: unknown autentico.
        ]
        for net in age.NETWORKS:
            with self.subTest(net=net):
                report = age.distribution(net, rows, now=NOW)
                self.assertEqual(report["total"], 2)
                self.assertEqual(report["acciones_perfil_excluidas"], 4)
                self.assertEqual(report["hasta_24h"], 1)
                self.assertEqual(report["rangos"]["unknown"], 1)
                self.assertEqual(sum(report["rangos"].values()), report["total"])

    def test_instagram_follow_only_plan_has_no_post_target(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "SISTEMA_DIARIO_INSTAGRAM" / "instagram_plan.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps([{"kind": "follow", "handle": "ejemplo"}]), encoding="utf-8")
            os.utime(path, (NOW.timestamp(), NOW.timestamp()))
            record = age.audit_recent_plans(root, now=NOW)["instagram"]
            self.assertEqual(record["estado"], "ok")
            self.assertEqual(record["total"], 0)
            self.assertEqual(record["acciones_perfil_excluidas"], 1)
            self.assertEqual(record["rangos"]["unknown"], 0)
            self.assertIn("1 acciones de perfil excluidas", "\n".join(age.daily_lines(root, now=NOW)))

    def test_readonly_snapshot_windows_and_missing_routes(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "SISTEMA_DIARIO_THREADS" / "threads_plan.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps([{"post_created_at": iso(1)}, {}]), encoding="utf-8")
            os.utime(path, (NOW.timestamp(), NOW.timestamp()))
            stats = age.audit_recent_plans(root, now=NOW)
            self.assertEqual(stats["threads"]["hasta_24h"], 1)
            self.assertEqual(stats["threads"]["rangos"]["unknown"], 1)
            self.assertEqual(stats["reddit"]["estado"], "sin_ruta_verificada")
            self.assertEqual(stats["x"]["estado"], "sin_plan")
            lines = "\n".join(age.daily_lines(root, now=NOW))
            self.assertIn("threads: 2 candidatos", lines)
            self.assertIn("reddit: sin_ruta_verificada", lines)
            self.assertNotIn("post_created_at", lines)

    def test_stale_plan_is_not_empty(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "bluesky_mech_plan.json"
            path.write_text("[]", encoding="utf-8")
            os.utime(path, (NOW.timestamp() - 48 * 3600, NOW.timestamp() - 48 * 3600))
            self.assertEqual(age.audit_recent_plans(root, now=NOW)["bluesky"]["estado"], "plan_no_reciente")

    def test_malformed_non_array_and_oversized_plans_do_not_crash(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "mastodon_mech_plan.json"
            for payload in ("{not json", "{}", "x" * 4_000_001):
                with self.subTest(payload=payload[:8]):
                    path.write_text(payload, encoding="utf-8")
                    os.utime(path, (NOW.timestamp(), NOW.timestamp()))
                    self.assertEqual(age.audit_recent_plans(root, now=NOW)["mastodon"]["estado"], "plan_invalido")

    def test_cli_sample_aggregate_only_and_broken_input(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "synthetic.json"
            path.write_text(json.dumps({
                "threads": [{"post_created_at": iso(2), "url": "https://secret.invalid/id"},
                            {"created_at": iso(1)}],
            }), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(age.main(["--sample", str(path)]), 0)
            result = json.loads(buf.getvalue())
            self.assertEqual(result["threads"]["total"], 2)
            self.assertNotIn("secret.invalid", buf.getvalue())
            self.assertNotIn("url", buf.getvalue())
            path.write_text("{invalid", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(age.main(["--sample", str(path)]), 2)
            self.assertEqual(json.loads(buf.getvalue())["estado"], "entrada_invalida")

    def test_report_is_stable_without_network_or_credentials(self):
        rows = [{"post_created_at": iso(h)} for h in (1, 12, 26, 90, 240)]
        first = age.distribution("instagram", rows, now=NOW)
        self.assertEqual(first, age.distribution("instagram", rows, now=NOW))
        self.assertEqual((first["hasta_24h"], first["hasta_72h"], first["hasta_7d"]), (2, 3, 4))
        self.assertEqual(sum(first["origenes"].values()), 5)

    def test_future_and_old_do_not_enter_fresh_windows(self):
        rows = [{"post_created_at": iso(-48)}, {"post_created_at": iso(200)}, {}]
        result = age.distribution("pinterest", rows, now=NOW)
        self.assertEqual(result["hasta_7d"], 0)
        self.assertEqual(result["rangos"]["future"], 1)
        self.assertEqual(result["rangos"]["over_168h"], 1)


if __name__ == "__main__":
    unittest.main()

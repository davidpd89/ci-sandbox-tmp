"""Contratos de inventario de capacidades de las ocho redes (PR #47).

No hacen llamadas externas, ni abren sesión ni dan likes/follows.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import network_capabilities as cap


class CapabilityMatrixTests(unittest.TestCase):
    def test_coverage_is_exactly_nine_networks_including_instagram(self):
        from mechanical_round import PIPELINES
        matrix = cap.build_matrix()
        self.assertEqual(set(matrix), set(cap.NETWORKS))
        self.assertIn("instagram", matrix)
        # Algunas redes (p. ej. Reddit) usan una ruta propia fuera de
        # mechanical_round: inventariar ausencia no es un error del informe.
        for net in cap.NETWORKS:
            self.assertEqual(matrix[net]["pipeline"], net in PIPELINES, net)

    def test_flags_are_explicit_and_not_inferred_from_platform_name(self):
        matrix = cap.build_matrix()
        for net, features in matrix.items():
            self.assertEqual(set(features), set(cap.FEATURES), net)
            self.assertTrue(all(isinstance(v, bool) for v in features.values()), net)
            self.assertFalse(features["unfollow_scheduled"] and not features["unfollow_adapter"])
            self.assertFalse(features["loyalty_scheduled"] and not features["inbound_harvest"])

    def test_registry_changes_are_reflected_without_rewriting_the_matrix(self):
        from mechanical_round import PIPELINES
        from unfollow_cleanup import ADAPTERS
        from loyalty import HARVEST
        matrix = cap.build_matrix()
        for net in cap.NETWORKS:
            with self.subTest(network=net):
                self.assertEqual(matrix[net]["unfollow_adapter"], net in ADAPTERS)
                self.assertEqual(matrix[net]["inbound_harvest"], net in HARVEST)
                self.assertEqual(matrix[net]["pipeline"], net in PIPELINES)

        # Agregar una implementación nueva debe REPARAR una brecha, no
        # romper la suite por afirmar que esa red seguirá incompleta.
        sample = {
            "pinterest": {
                "pre": [["python", "tools/reply_writer.py", "pinterest"]],
                "post": [
                    ["python", "tools/unfollow_cleanup.py", "pinterest"],
                    ["python", "tools/loyalty.py", "pinterest"],
                ],
            }
        }
        added = cap.build_matrix(
            pipelines=sample,
            cleanup_adapters={"pinterest": object()},
            harvesters={"pinterest": lambda: []},
        )
        self.assertTrue(added["pinterest"]["unfollow_scheduled"])
        self.assertTrue(added["pinterest"]["loyalty_scheduled"])
        self.assertTrue(added["pinterest"]["gpt_writer_scheduled"])
        self.assertNotIn(
            "adaptador de unfollow no implementado", cap.gaps(added)["pinterest"]
        )

    def test_policy_constants_have_one_consistent_age(self):
        import growth_policy as gp
        import relationship_policy as rp
        self.assertEqual(gp.NONRECIPROCAL_DAYS, rp.GRACE_DAYS)
        self.assertEqual(gp.NONRECIPROCAL_DAYS, 7)

    def test_missing_adapter_cannot_be_marked_as_scheduled(self):
        sample = {
            "bluesky": {"pre": [], "post": [
                ["python", "tools/unfollow_cleanup.py", "bluesky"],
                ["python", "tools/loyalty.py", "bluesky"],
                ["python", "tools/reply_writer.py", "bluesky"],
            ]},
        }
        matrix = cap.build_matrix(pipelines=sample, cleanup_adapters={}, harvesters={})
        self.assertFalse(matrix["bluesky"]["unfollow_adapter"])
        self.assertFalse(matrix["bluesky"]["unfollow_scheduled"])
        self.assertFalse(matrix["bluesky"]["inbound_harvest"])
        self.assertFalse(matrix["bluesky"]["loyalty_scheduled"])
        self.assertTrue(matrix["bluesky"]["gpt_writer_scheduled"])

    def test_scheduler_requires_network_argument(self):
        sample = {"bluesky": {"post": [["python", "tools/unfollow_cleanup.py", "mastodon"]]}}
        matrix = cap.build_matrix(pipelines=sample, cleanup_adapters={"bluesky": object()}, harvesters={})
        self.assertFalse(matrix["bluesky"]["unfollow_scheduled"])

    def test_gaps_expose_missing_not_prove_impossible(self):
        matrix = cap.build_matrix(pipelines={}, cleanup_adapters={}, harvesters={})
        gaps = cap.gaps(matrix)
        self.assertEqual(set(gaps), set(cap.NETWORKS))
        self.assertIn("adaptador de unfollow no implementado", gaps["tiktok"])
        self.assertTrue(all("imposible" not in " ".join(lines) for lines in gaps.values()))

    def test_writer_only_counts_pre_not_post(self):
        sample = {"instagram": {"post": [["python", "tools/reply_writer.py", "instagram"]]}}
        matrix = cap.build_matrix(pipelines=sample, cleanup_adapters={}, harvesters={})
        self.assertFalse(matrix["instagram"]["gpt_writer_scheduled"])

    def test_command_parser_supports_windows_separators(self):
        pipe = {"pre": [["python.exe", "tools\\reply_writer.py", "x"]]}
        self.assertTrue(cap._scheduled(pipe, "reply_writer.py"))


if __name__ == "__main__":
    unittest.main()

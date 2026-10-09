import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import reciprocity_stats as rs


class StatsTests(unittest.TestCase):
    def test_table_credits_every_source_and_counts_followers(self):
        follows = {"@a": "2026-10-01", "@b@x.es": "2026-10-01", "@c": "2026-10-01"}
        followers = ["a", "b"]
        edges = [("a", "H1"), ("a", "H2"), ("b@x.es", "H1"), ("c", "H2")]
        table, total = rs.hub_table(follows, followers, edges, ["H1", "H2", "H3"])
        self.assertEqual(table, {"H1": [2, 2], "H2": [2, 1], "H3": [0, 0]})
        self.assertEqual(total, [3, 2])

    def test_decisions_need_samples_and_use_prior(self):
        table = {"bueno": [100, 60], "malo": [100, 2], "poco": [5, 0], "normal": [100, 33]}
        result, overall = rs.decide(table, [305, 100])
        self.assertAlmostEqual(overall, 100 / 305)
        self.assertEqual(result["bueno"]["decision"], "bueno")
        self.assertEqual(result["malo"]["decision"], "retirar")
        self.assertEqual(result["poco"]["decision"], "pocos_datos")
        self.assertEqual(result["normal"]["decision"], "seguir")


if __name__ == "__main__":
    unittest.main()


class RelationshipPolicyTests(unittest.TestCase):
    def _registro(self, rows):
        import csv, tempfile
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
        w = csv.writer(tmp)
        w.writerow(["fecha", "cuenta", "tipo", "post_resumen", "texto_usado", "resultado", "notas"])
        w.writerows(rows)
        tmp.close()
        return tmp.name

    def test_blocked_cooldown_blacklist_and_permanent(self):
        import datetime
        import relationship_policy as rp
        today = datetime.date(2026, 10, 7)
        reciprocity = "cleanup:no devuelve el follow tras 8 dias"
        path = self._registro([
            ["2026-10-01", "@reciente", "unfollow", "", "", "confirmado", reciprocity],        # en espera (6 dias < 21)
            ["2026-08-01", "@antigua", "unfollow", "", "", "confirmado", reciprocity],         # 1 intento y ya paso la espera: puede volver
            ["2026-07-01", "@tres", "unfollow", "", "", "confirmado", reciprocity],
            ["2026-08-01", "@tres", "unfollow", "", "", "confirmado", reciprocity],
            ["2026-09-01", "@tres", "unfollow", "", "", "confirmado", reciprocity],            # lista negra
            ["2026-09-30", "@idioma", "unfollow", "", "", "confirmado", "cleanup:biografia en otro idioma (en)"],   # permanente
            ["2026-09-30", "@fallo", "unfollow", "", "", "fallo:x", reciprocity],              # un intento fallido no excluye
        ])
        blocked = rp.blocked_accounts(path, today)
        self.assertEqual(blocked, {"reciente", "tres", "idioma"})
        self.assertEqual(rp.blacklist(path), {"tres": 3})

    def test_follow_allowance_and_comment_reciprocity(self):
        import os, tempfile
        import relationship_policy as rp
        self.assertIsNone(rp.follow_allowance(383, 2236, network="x"))              # 07/10: sin tope de proporcion (decision de David)
        self.assertEqual(rp.follow_allowance(383, 2236, ratio_cap=3.0), 0)            # el tope sigue disponible si se activa
        self.assertEqual(rp.follow_allowance(12, 142, ratio_cap=3.0), 158)            # suelo de 300
        self.assertIsNone(rp.follow_allowance(None, 5))
        path = self._registro([["2026-10-01", "@pepe", "reply", "", "x", "publicado", ""], ["2026-10-02", "@pepe", "reply", "", "y", "publicado", ""],
                               ["2026-10-02", "@ana", "reply", "", "z", "publicado", ""]])
        inbound = os.path.join(tempfile.mkdtemp(), "in.csv")
        self.assertTrue(rp.comment_allowed("x", "ana", path, inbound_path=inbound))        # primer paso: 1 < 2
        self.assertFalse(rp.comment_allowed("x", "pepe", path, inbound_path=inbound))      # ya 2 y nunca nos comenta
        rp.log_inbound("x", "pepe", "comment", path=inbound)
        self.assertTrue(rp.comment_allowed("x", "pepe", path, inbound_path=inbound))       # nos comento una vez: otro comentario nuestro

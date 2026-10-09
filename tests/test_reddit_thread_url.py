"""La escritura Reddit solo admite URLs canónicas de hilos, no comentarios."""
import ast
import csv
import pathlib
import re
import urllib.parse
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "reddit_interact.py"


class ThreadURLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        func = next(node for node in ast.parse(SOURCE.read_text(encoding="utf-8")).body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "_validated_thread_url")
        ns = {"re": re, "urllib": urllib}
        exec(compile(ast.Module(body=[func], type_ignores=[]), str(SOURCE), "exec"), ns)
        cls.validate = staticmethod(ns["_validated_thread_url"])

    def test_valid_thread(self):
        self.assertEqual(
            self.validate("https://www.reddit.com/r/libros/comments/abc123/titulo/"),
            "https://www.reddit.com/r/libros/comments/abc123/titulo/",
        )

    def test_redirect_must_retain_subreddit_and_post_id(self):
        nodes = [n for n in ast.parse(SOURCE.read_text(encoding="utf-8")).body
                 if isinstance(n, ast.FunctionDef)
                 and n.name == "_assert_thread_destination"]
        ns = {"urllib": urllib, "_validated_thread_url": self.validate}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), ns)
        actual = type("Page", (), {"url":
            "https://www.reddit.com/r/libros/comments/abc123/titulo_nuevo/"})()
        expected = "https://www.reddit.com/r/libros/comments/abc123/titulo_original/"
        ns["_assert_thread_destination"](actual, expected)
        actual.url = "https://www.reddit.com/r/libros/comments/otro/titulo/"
        with self.assertRaisesRegex(RuntimeError, "otro hilo"):
            ns["_assert_thread_destination"](actual, expected)
        actual.url = "https://www.reddit.com/r/otro/comments/abc123/titulo/"
        with self.assertRaisesRegex(RuntimeError, "otro hilo"):
            ns["_assert_thread_destination"](actual, expected)

    def test_exact_post_id_comes_from_validated_url(self):
        nodes = [n for n in ast.parse(SOURCE.read_text(encoding="utf-8")).body
                 if isinstance(n, ast.FunctionDef)
                 and n.name in ("_thread_post_id", "_visible_norm")]
        ns = {"urllib": urllib, "_validated_thread_url": self.validate}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), ns)
        self.assertEqual(
            ns["_thread_post_id"](
                "https://www.reddit.com/r/libros/comments/AbC123/titulo/"
            ),
            "abc123",
        )
        self.assertEqual(
            ns["_visible_norm"]("  Hola\n  MUNDO   "),
            "hola mundo",
        )

    def test_subreddit_prefix_normalization_does_not_eat_leading_r(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_normalize_subreddit_name")
        ns = {"re": re}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), ns)
        normalize = ns["_normalize_subreddit_name"]
        self.assertEqual(normalize("romance"), "romance")
        self.assertEqual(normalize("r/romance"), "romance")
        self.assertEqual(normalize("/r/romance"), "romance")
        with self.assertRaises(ValueError):
            normalize("../books")

    def test_reject_nested_comment_and_query(self):
        for url in (
            "https://www.reddit.com/r/libros/comments/abc123/titulo/commentabc/",
            "https://www.reddit.com/r/libros/comments/abc123/titulo/?comment=commentabc",
            "https://www.reddit.com/r/libros/comments/abc123/titulo/#commentabc",
            "https://reddit.com.evil.example/r/libros/comments/abc123/",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.validate(url)

    def test_accented_spanish_slug_is_accepted(self):
        # BUG REAL encontrado el 28/09/2026 probando esta PR con una URL real
        # de la sesión: el slug solo aceptaba ASCII, así que cualquier post en
        # español con tilde/eñe en el título (la inmensa mayoría en r/libros y
        # r/escribir) quedaba rechazado como si no fuera el hilo raíz - vote()
        # y comment() habrían dejado de funcionar en la práctica para casi
        # todo el contenido real de estas dos comunidades.
        url = (
            "https://www.reddit.com/r/libros/comments/1wppo25/"
            "si_han_leído_a_terry_pratchett_qué_orden/"
        )
        self.assertEqual(self.validate(url), url)


    def test_confirmed_comment_in_csv_blocks_duplicate_even_if_dom_would_hide_it(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        nodes = [
            n for n in tree.body
            if (
                isinstance(n, ast.FunctionDef)
                and n.name in (
                    "_validated_thread_url", "_thread_identity",
                    "_comment_history_state", "_already_commented_in_history",
                )
            ) or (
                isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_CONFIRMED_HISTORY_RESULTS"
                        for t in n.targets)
            )
        ]
        with tempfile.TemporaryDirectory() as td:
            registro = pathlib.Path(td) / "registro.csv"
            with registro.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["fecha", "subreddit", "hilo_url", "tipo",
                                 "texto_usado", "resultado", "notas"])
                writer.writerow([
                    "2026-09-25", "r/libros",
                    "https://www.reddit.com/r/libros/comments/abc123/titulo-viejo/",
                    "comentario", "texto", "confirmado", "",
                ])
            ns = {
                "re": re, "urllib": urllib, "os": __import__("os"),
                "csv": csv, "REGISTRO_CSV": str(registro),
            }
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), ns)
            self.assertTrue(ns["_already_commented_in_history"](
                "https://www.reddit.com/r/libros/comments/abc123/titulo-nuevo/"
            ))
            self.assertFalse(ns["_already_commented_in_history"](
                "https://www.reddit.com/r/libros/comments/otro/titulo/"
            ))

            with registro.open("a", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow([
                    "2026-09-25", "r/libros",
                    "https://www.reddit.com/r/libros/comments/dudoso/titulo/",
                    "comentario", "texto", "", "",
                ])
            self.assertEqual(
                ns["_comment_history_state"](
                    "https://www.reddit.com/r/libros/comments/dudoso/titulo/"
                ),
                "uncertain",
            )
            self.assertFalse(ns["_already_commented_in_history"](
                "https://www.reddit.com/r/libros/comments/dudoso/titulo/"
            ))



if __name__ == "__main__":
    unittest.main()

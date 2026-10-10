"""pinterest_execute (03/10): limites reales de Pinterest y avisos de SEO."""
import pathlib
import subprocess
import sys
import unittest

TOOLS = str(pathlib.Path(__file__).resolve().parents[1] / "tools")


def run_clean(code):
    proc = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {TOOLS!r})\n" + code],
                          capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, proc.stdout + proc.stderr


BASE = ("{'kind': 'manual_pin', 'text': %(text)r, 'media': ['a.png'], 'media_alt_text': ['Portada de un libro'],"
        " 'board_name': %(board)r, 'pin_title': %(title)r, 'pin_link': 'https://davidportodiaz.com/guias/lectura/'}")


class PinterestSeoTests(unittest.TestCase):
    def run_pin(self, text, title, board, extra=""):
        item = BASE % {"text": text, "title": title, "board": board}
        code = ("import pinterest_execute as p\n"
                f"r = p.run_plan([{item}])[0]\n{extra}\n"
                "print(r['resultado']); print(r.get('avisos_seo'))\n")
        rc, out = run_clean(code)
        self.assertEqual(rc, 0, out)
        return out

    def test_good_pin_has_no_seo_warnings(self):
        text = "Guía de lectura para empezar con la fantasía juvenil: cinco claves para elegir tu próximo libro sin perderte entre tantas sagas."
        out = self.run_pin(text, "Libros de fantasía juvenil para empezar", "Libros de fantasía en español")
        self.assertIn("listo_para_publicacion_manual", out)
        self.assertIn("[]", out)

    def test_generic_pin_gets_warnings_but_is_not_blocked(self):
        out = self.run_pin("Una imagen bonita.", "ATARDECER EN LA CIUDAD", "Inspiración")
        self.assertIn("listo_para_publicacion_manual", out)
        for fragment in ("termino de busqueda", "titulo", "descripcion", "mayusculas", "tablero"):
            self.assertIn(fragment, out)

    def test_hard_limits_block(self):
        out = self.run_pin("Libro de fantasía " + "x" * 800, "Libros " + "t" * 100, "Libros de fantasía")
        self.assertIn("invalido", out)
        self.assertIn("pin_title de", out)
        self.assertIn("text de", out)


if __name__ == "__main__":
    unittest.main()

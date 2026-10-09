"""08/10: un NameError en el paso `plan` de Pinterest (write_comments no existia) paso 1.100 tests y rompio rondas reales.
Este test busca estaticamente nombres sin definir en todo tools/ (pyflakes) para que no vuelva a pasar."""
import pathlib
import unittest

try:
    from pyflakes import api, messages, reporter
except ImportError:                                  # pragma: no cover
    api = None

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"


class _Collector(reporter.Reporter if api else object):
    def __init__(self):
        if api:
            super().__init__(open(__import__("os").devnull, "w"), open(__import__("os").devnull, "w"))
        self.found = []

    def flake(self, message):
        if isinstance(message, messages.UndefinedName):
            self.found.append(f"{message.filename}:{message.lineno}: {message.message % message.message_args}")


@unittest.skipIf(api is None, "pyflakes no instalado (requirements-ci.txt)")
class UndefinedNamesTests(unittest.TestCase):
    def test_no_undefined_names_in_tools(self):
        collector = _Collector()
        for path in sorted(TOOLS.glob("*.py")):
            api.check(path.read_text(encoding="utf-8"), str(path), collector)
        self.assertEqual(collector.found, [], "nombres sin definir:\n" + "\n".join(collector.found))


if __name__ == "__main__":
    unittest.main()

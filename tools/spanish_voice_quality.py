"""Auditoría offline no destructiva de español social, nueve redes y tres colas.

Implementación propia (stdlib), reutilizando opcionalmente spellcheck_es del mirror.
Solo ofrece diagnósticos editoriales con offsets; nunca modifica ni bloquea textos.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from functools import lru_cache

NETWORKS = frozenset({"x", "threads", "facebook", "pinterest", "reddit",
                       "bluesky", "mastodon", "tiktok", "instagram"})
QUEUES = frozenset({"WEB", "API", "MOBILE"})
PROTECTED = re.compile(
    r"!?\[[^\]\n]+\]\([^\)\n]+\)|https?://[^\s<>«»]+|www\.[^\s<>«»]+|"
    r"(?<![\w.])[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|"
    r"(?<!\w)@[\w.]+|(?<!\w)#[\wáéíóúüñÁÉÍÓÚÜÑ]+|"
    + re.escape(chr(96)) + r"[^" + re.escape(chr(96)) + r"\n]*" + re.escape(chr(96))
    + r'|«[^»\n]*»|“[^”\n]*”|"[^"\n]*"', re.UNICODE)
FENCED_CODE = re.compile(r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$")
HTML_TAG = re.compile(r"</?[A-Za-z][^<>\n]*>", re.UNICODE)

VARIANT_ES_ES = {
    "platicar": "conversar", "chambear": "trabajar", "checar": "comprobar",
    "computadora": "ordenador", "celular": "móvil", "carro": "coche",
}
CALQUES = (
    (re.compile(r"\bhace(?:n|mos|s)? sentido\b", re.I), "revisar «tener sentido»"),
    (re.compile(r"\ben base a\b", re.I), "revisar «sobre la base de»"),
)
SUSPECT_ENCODING = re.compile(r"\ufffd|Ã[¡-ÿ]|Â[¿¡]|â[€žœ™šŸ]")
WORD_PATTERN = re.compile(r"(?<!\w)[^\W\d_]+(?!\w)", re.UNICODE)
MISSING_SPACE = re.compile(r"(?<=[^\W\d_])\s+[,.;:](?=\s|$)", re.UNICODE)


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    start: int
    end: int
    advice: str


def _mask(text: str) -> str:
    """Protege formato nativo, enlaces, menciones, títulos/citas; preserva offsets."""
    chars = list(text)
    for match in (list(FENCED_CODE.finditer(text)) +
                  list(HTML_TAG.finditer(text)) + list(PROTECTED.finditer(text))):
        chars[match.start():match.end()] = [
            ch if ch in "\r\n" else " " for ch in text[match.start():match.end()]
        ]
    return "".join(chars)


@lru_cache(maxsize=1)
def _accent_checker():
    try:
        from spellcheck_es import check_missing_accents
    except ImportError:
        return None
    return check_missing_accents


def audit(text: str, *, network: str, locale: str = "es-ES", queue: str | None = None,
          check_accents: bool = True) -> dict:
    if not isinstance(text, str):
        raise TypeError("text debe ser str")
    if not isinstance(network, str) or network not in NETWORKS:
        raise ValueError("red desconocida")
    if queue is not None and (not isinstance(queue, str) or queue not in QUEUES):
        raise ValueError("cola desconocida")
    if locale not in ("es-ES", "es"):
        raise ValueError("locale desconocido")
    masked = _mask(text)
    findings: list[Finding] = []

    def add(code, level, start, end, advice):
        findings.append(Finding(code, level, start, end, advice))

    for match in SUSPECT_ENCODING.finditer(masked):
        add("encoding_corrupt", "error", match.start(), match.end(),
            "Comprobar codificación UTF-8 en el original")
    for match in MISSING_SPACE.finditer(masked):
        add("space_before_punctuation", "warning", match.start(), match.end(),
            "Revisar espacio antes del signo")
    segment_start = 0
    for i, ch in enumerate(masked):
        if ch in ".;\n":
            segment_start = i + 1
        elif ch == "?":
            if "¿" not in masked[segment_start:i]:
                add("question_opening", "warning", i, i + 1,
                    "Comprobar apertura «¿» en pregunta en español")
            segment_start = i + 1
        elif ch == "!":
            if "¡" not in masked[segment_start:i]:
                add("exclamation_opening", "warning", i, i + 1,
                    "Comprobar apertura «¡» en exclamación en español")
            segment_start = i + 1
    if locale == "es-ES":
        for match in WORD_PATTERN.finditer(masked):
            replacement = VARIANT_ES_ES.get(match.group().casefold())
            if replacement:
                add("locale_variant", "hint", match.start(), match.end(),
                    "Revisar variante peninsular si es voz propia: " + replacement)
    for pattern, advice in CALQUES:
        for match in pattern.finditer(masked):
            add("literal_translation", "hint", match.start(), match.end(), advice)
    checker = _accent_checker() if check_accents else None
    if checker is not None:
        # Indexación O(n), orden estable: varias sugerencias no dependen
        # del orden aleatorio del set ni del PYTHONHASHSEED del proceso.
        proposed = {}
        for wrong, suggestion in checker(masked):
            if isinstance(wrong, str) and isinstance(suggestion, str):
                proposed.setdefault(wrong.casefold(), set()).add(suggestion)
        for match in WORD_PATTERN.finditer(masked):
            alternatives = proposed.get(match.group().casefold())
            if alternatives:
                add("possible_missing_accent", "hint", match.start(), match.end(),
                    "Comprobar tilde según contexto: " + min(alternatives))
    if unicodedata.normalize("NFC", text) != text:
        add("unicode_normalization", "hint", 0, 0,
            "Comprobar NFC solo en texto propio, sin sustituir nombres o citas")
    findings.sort(key=lambda f: (f.start, f.end, f.code))
    return {
        "schema_version": 1, "network": network, "queue": queue, "locale": locale,
        "changed": False, "findings": [asdict(f) for f in findings],
        "accent_check": "enabled" if checker is not None else "unavailable_or_disabled",
        "counts": {level: sum(f.severity == level for f in findings)
                   for level in ("error", "warning", "hint")},
    }



def advisory(text, *, network, queue=None, log=print, label="[voz] revision_es"):
    """Un solo adaptador informativo para todas las redes y transportes.

    No reescribe, no bloquea, ni incorpora texto/autor/URL al log. Devuelve
    hallazgos para interfaz editorial, incluso cuando no se imprimen avisos.
    """
    if not isinstance(network, str) or network not in NETWORKS:
        return []

    def safe_log(message):
        # El registro es opcional: un logger roto no interrumpe la ronda.
        try:
            log(message)
        except Exception:
            pass

    try:
        findings = audit(text, network=network, queue=queue)["findings"]
    except Exception as exc:
        safe_log(label + " auditor_es_no_disponible: " + type(exc).__name__)
        return []
    if findings:
        safe_log(label + ": " + ",".join(sorted({issue["code"] for issue in findings})))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Auditoría offline no destructiva")
    parser.add_argument("--network", required=True, choices=sorted(NETWORKS))
    parser.add_argument("--queue", choices=sorted(QUEUES), default=None,
                        help="cola real; omitir si no se conoce")
    parser.add_argument("--locale", choices=["es-ES", "es"], default="es-ES")
    parser.add_argument("--text", help="Texto propio; si se omite, stdin")
    args = parser.parse_args(argv)
    raw = args.text if args.text is not None else sys.stdin.read()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(audit(raw, network=args.network, queue=args.queue,
                           locale=args.locale), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

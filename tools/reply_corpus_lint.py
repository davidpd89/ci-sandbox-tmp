"""Lint de variedad sobre las ULTIMAS N respuestas (03/10, propuesta de ChatGPT).

Lo detectable de un texto de IA en espanol no esta en una frase aislada sino en la
estandarizacion del conjunto: mismas aperturas, conectores de ensayo, simetrias, cierres
sentenciosos, frases de longitud uniforme. Esto mide el corpus real de replies (las 4 redes
del registro) y avisa; no sustituye a `reply_style_report` (por reply) ni bloquea nada.

    python tools/reply_corpus_lint.py [N]      # por defecto las ultimas 50
"""
import os
import re
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))

CONNECTORS = re.compile(
    r"\b(ademas|sin embargo|por otro lado|en definitiva|en ese sentido|lo cierto es que|"
    r"en conclusion|cabe destacar|no obstante|por tanto|asimismo)\b")
SYMMETRY = re.compile(r"\bno (?:solo|es)\b.{3,60}\bsino\b|\bpor un lado\b.{3,80}\bpor otro\b|\btanto\b.{3,50}\bcomo\b")
TRICOLON = re.compile(r"\b[\w]+, [\w ]{1,25}, (?:y|e) [\w]+")
CLOSING = re.compile(r"(?:al final|ahi esta|esa es la clave|justo eso|y punto|eso es todo)[.!]*$")
THRESHOLDS = {"opening_top_share": 0.20, "connector_share": 0.08, "colon_share": 0.15,
              "tricolon_share": 0.15, "closing_share": 0.10, "symmetry_share": 0.10,
              "sentence_len_stdev_min": 3.0}


def _plain(text):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def _share(flags):
    return sum(flags) / len(flags) if flags else 0.0


def lint(texts):
    """-> (metricas, avisos). Con menos de 10 textos no hay base para avisar."""
    plain = [_plain(t) for t in texts if t and t.strip()]
    if not plain:
        return {}, []
    first = Counter(" ".join(re.findall(r"\w+", t)[:1]) for t in plain)
    lengths = []
    for t in plain:
        for sentence in re.split(r"[.!?]+\s+", t):
            words = len(re.findall(r"\w+", sentence))
            if words:
                lengths.append(words)
    metrics = {
        "n": len(plain),
        "opening_top": first.most_common(1)[0],
        "opening_top_share": first.most_common(1)[0][1] / len(plain),
        "connector_share": _share([bool(CONNECTORS.search(t)) for t in plain]),
        "colon_share": _share([":" in t for t in plain]),
        "tricolon_share": _share([bool(TRICOLON.search(t)) for t in plain]),
        "closing_share": _share([bool(CLOSING.search(t.strip())) for t in plain]),
        "symmetry_share": _share([bool(SYMMETRY.search(t)) for t in plain]),
        "sentence_len_stdev": statistics.pstdev(lengths) if len(lengths) > 1 else 0.0,
        "micro_share": _share([len(re.findall(r"\w+", t)) <= 8 for t in plain]),
    }
    warnings = []
    if metrics["n"] < 10:
        return metrics, warnings
    if metrics["opening_top_share"] > THRESHOLDS["opening_top_share"]:
        word, count = metrics["opening_top"]
        warnings.append(f"{count} de {metrics['n']} respuestas empiezan por «{word}»: variar aperturas")
    for key, label in (("connector_share", "conectores de ensayo (ademas, sin embargo...)"),
                       ("colon_share", "dos puntos explicativos"),
                       ("tricolon_share", "enumeraciones de tres (X, Y y Z)"),
                       ("closing_share", "cierres sentenciosos (al final, esa es la clave...)"),
                       ("symmetry_share", "simetrias (no solo... sino, por un lado... por otro)")):
        if metrics[key] > THRESHOLDS[key]:
            warnings.append(f"{100 * metrics[key]:.0f} % de las respuestas llevan {label}")
    if metrics["sentence_len_stdev"] < THRESHOLDS["sentence_len_stdev_min"]:
        warnings.append(f"frases de longitud muy uniforme (desviacion {metrics['sentence_len_stdev']:.1f} palabras): mezclar cortas y largas")
    return metrics, warnings


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    limit = int(argv[0]) if argv else 50
    import check_language_variety as clv
    history = clv.load_recent(limit)
    metrics, warnings = lint([h["text"] for h in history])
    if not metrics:
        print("sin respuestas en el registro")
        return 1
    print(f"{metrics['n']} respuestas (4 redes). apertura mas repetida: {metrics['opening_top']}; "
          f"micro (<=8 palabras): {100 * metrics['micro_share']:.0f} %; "
          f"desviacion de longitud de frase: {metrics['sentence_len_stdev']:.1f}")
    print("\n".join(f"AVISO: {w}" for w in warnings) or "sin avisos de corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

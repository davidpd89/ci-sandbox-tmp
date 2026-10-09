"""
Chequeo de tildes que faltan en texto que va a render final.

No es un corrector ortografico general (el diccionario es de pyspellchecker
no cubre bien conjugaciones verbales y da falsos positivos). En su lugar,
para cada palabra sin tilde prueba variantes con tilde en cada vocal: si
alguna variante SI esta en el diccionario y la palabra original no, es una
tilde que falta con alta confianza (ej: "capitulo" -> "capitulo" no existe,
"capítulo" si).

Uso como libreria:
    from spellcheck_es import check_missing_accents
    problemas = check_missing_accents("Odiaba a ese personaje al leer el capitulo 3.")
"""
import re
from spellchecker import SpellChecker

_sp = SpellChecker(language="es")
_VOWELS = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}
# "publica": verbo ("quién la publica"). "londres": topónimo sin tilde que el
# diccionario confunde con "londrés" (falso positivo visto el 02/10).
_VALID_UNACCENTED = {"publica", "londres"}


def _accent_variants(word: str) -> list[str]:
    variants = []
    for idx, ch in enumerate(word):
        low = ch.lower()
        if low in _VOWELS:
            accented = _VOWELS[low] if ch.islower() else _VOWELS[low].upper()
            variants.append(word[:idx] + accented + word[idx + 1:])
    return variants


def check_missing_accents(text: str) -> list[tuple[str, str]]:
    """Devuelve lista de (palabra_sin_tilde, variante_con_tilde_sugerida)."""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"https?://\S+|www\.\S+", " ", clean)
    words = re.findall(r"[a-zA-ZÀ-ÿ]+", clean)
    problems = []
    for w in words:
        if len(w) < 3 or w.lower() in _sp or w.lower() in _VALID_UNACCENTED:
            continue
        for variant in _accent_variants(w):
            if variant.lower() in _sp:
                problems.append((w, variant))
                break
    return problems


if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:])
    problems = check_missing_accents(text)
    if not problems:
        print("OK: sin tildes faltantes detectadas.")
    else:
        print("Tildes que faltan:")
        for word, suggestion in problems:
            print(f"  - '{word}' -> '{suggestion}'")

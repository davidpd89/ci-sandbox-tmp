"""Mastodon: carga el vocabulario de GPT (05/10, consulta D de Bluesky + consulta F de Mastodon) en `SISTEMA_DIARIO_MASTODON/growth_config.json`.

Consulta F: «tenéis 28 términos y uno está duplicado (reseña)»; propone el esquema de familias de Bluesky (lectura/intención, TBR, reseña, fantasía, subgéneros,
escritura, librerías/editoriales, rol, cómic/manga, eventos y BookWyrm). Se reutilizan las 12 familias del vocabulario de Bluesky (frases en español, válidas en la
búsqueda de estados de Mastodon), los hashtags que no son propios de Bluesky, los hashtags que GPT propone como SUPOSICIÓN a medir para Mastodon (Leyendo, Lecturas,
Reseñas, LibrosRecomendados, CienciaFiccion, Terror, Comic, Manga, BookWyrm…) y los nombres propios de editoriales/ferias para la búsqueda de cuentas. Cada elemento se
mide por rendimiento (`discovery_metrics.csv`): los que no dan cuentas nuevas se aparcan solos. Idempotente; copia de seguridad la primera vez.

    python tools/mastodon_vocab_loader.py [--dry]
"""
import json
import os
import shutil
import sys
import unicodedata

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_MASTODON")
CONFIG = os.path.join(ROOT, "growth_config.json")
VOCAB = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY", "vocab_gpt_2026-10-05.json")
BACKUP = os.path.join(ROOT, "growth_config.backup_20261005.json")

BLUESKY_ONLY = ("sky", "bluesky")
GPT_F_HASHTAGS = ["Leyendo", "Lecturas", "Reseñas", "LibrosRecomendados", "CienciaFiccion", "Terror", "Comic", "Manga", "BookWyrm", "Fedilibros", "LecturaSocial",
                  "Microrrelatos", "RolDeMesa", "LoDelRol", "Worldbuilding", "Escritores", "AutoresIndie", "TBR", "WrapUp", "Bookstodon", "LiteraturaEnEspanol"]
NICHE_EXTRA = ["relato", "relatos", "cuento", "cuentos", "poesía", "poema", "poemas", "poeta", "cómic", "comics", "manga", "tbr", "wip", "saga", "bibliófilo", "bookstodon",
               "booktok", "ebook", "audiolibro", "novela gráfica", "juegos de rol", "tolkien", "sanderson", "mitología", "escribo", "escribiendo", "escribir", "narrativa",
               "novelista", "traductora", "traductor", "reseñas", "leyendo", "lecturas", "bestseller"]


def _norm(text):
    text = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def merge(config, vocab):
    """Devuelve (config nueva, resumen). No toca lo que ya hay: solo anade lo que falta."""
    out = json.loads(json.dumps(config))
    added = {"families": 0, "queries": 0, "hashtags": 0, "account_queries": 0, "niche_terms": 0}
    families = {f["name"]: f for f in out.get("query_families") or []}
    for name, queries in (vocab.get("families") or {}).items():
        fam = families.get(name)
        if fam is None:
            fam = {"name": name, "queries": []}
            out.setdefault("query_families", []).append(fam)
            added["families"] += 1
        known = {_norm(q) for q in fam["queries"]}
        for query in queries:
            if _norm(query) not in known:
                fam["queries"].append(query)
                known.add(_norm(query))
                added["queries"] += 1
    known_tags = {_norm(t) for t in out.get("hashtags") or []}
    for tag in list(vocab.get("hashtags") or []) + GPT_F_HASHTAGS:
        tag = str(tag).lstrip("#")
        if not tag or any(part in _norm(tag) for part in BLUESKY_ONLY) or _norm(tag) in known_tags:
            continue
        out.setdefault("hashtags", []).append(tag)
        known_tags.add(_norm(tag))
        added["hashtags"] += 1
    known_acc = {_norm(q) for q in out.get("account_queries") or []}
    for query in vocab.get("seed_actor_queries") or []:
        if _norm(query) not in known_acc:
            out.setdefault("account_queries", []).append(query)
            known_acc.add(_norm(query))
            added["account_queries"] += 1
    seen_terms, unique_terms = set(), []
    for term in list(out.get("niche_terms") or []) + NICHE_EXTRA:     # `reseña` aparecia dos veces
        if _norm(term) not in seen_terms:
            seen_terms.add(_norm(term))
            unique_terms.append(term)
    added["niche_terms"] = len(unique_terms) - len(out.get("niche_terms") or [])
    out["niche_terms"] = unique_terms
    return out, added


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    with open(CONFIG, encoding="utf-8") as stream:
        config = json.load(stream)
    with open(VOCAB, encoding="utf-8") as stream:
        vocab = json.load(stream)
    new, added = merge(config, vocab)
    print("anadido:", added)
    if "--dry" in argv:
        return 0
    if not os.path.exists(BACKUP):
        shutil.copy(CONFIG, BACKUP)
    with open(CONFIG, "w", encoding="utf-8") as stream:
        json.dump(new, stream, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

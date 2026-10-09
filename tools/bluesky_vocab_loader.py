"""Carga vocabulario curado en la configuracion de Bluesky (05/10/2026): hashtags, familias de consultas, feeds, starter packs y terminos de Jetstream.

Lee `SISTEMA_DIARIO_BLUESKY/vocab_gpt_2026-10-05.json` (la respuesta D de GPT, 05/10) y lo MEZCLA en `growth_config.json` sin duplicar:
  - `families`   -> `query_families` (una familia por tema; la procedencia `src` distingue cada una al medir rendimiento)
  - `hashtags`   -> `tag_queries` y `mined_terms` (Jetstream)
  - `feed_queries`, `starter_pack_queries` -> listas homonimas
  - `jetstream_extra_terms` -> `mined_terms`
Es idempotente y reversible (todo lo anadido lleva `"vocab": "<fichero>"`/queda en `mined_terms`). Los nombres propios de `seed_actor_queries` los lee
`bluesky_seed_wave.py` (searchActors -> perfil real; nunca se asume que un nombre existe).

    python tools/bluesky_vocab_loader.py            # aplica
    python tools/bluesky_vocab_loader.py --dry      # solo cuenta lo que anadiria
"""
import json
import os
import sys
import unicodedata

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY")
CONFIG = os.path.join(ROOT, "growth_config.json")
VOCAB = os.path.join(ROOT, "vocab_gpt_2026-10-05.json")


def _norm(text):
    text = unicodedata.normalize("NFKD", " ".join(str(text or "").casefold().split()))
    return "".join(c for c in text if not unicodedata.combining(c))


def merge(config, vocab, tag="vocab_gpt_2026-10-05"):
    """(config nueva, resumen). No muta la original."""
    out = json.loads(json.dumps(config))
    added = {"families": 0, "queries": 0, "tags": 0, "feeds": 0, "packs": 0, "jetstream_terms": 0}
    known = {_norm(q) for f in out.get("query_families", []) for q in f.get("queries", [])}
    families = {f["name"]: f for f in out.setdefault("query_families", [])}
    for name, queries in (vocab.get("families") or {}).items():
        fresh = [q for q in queries if _norm(q) not in known]
        if not fresh:
            continue
        if name in families:
            families[name]["queries"] += [q for q in fresh if _norm(q) not in {_norm(x) for x in families[name]["queries"]}]
        else:
            out["query_families"].append({"name": name, "queries": fresh, "vocab": tag})
            added["families"] += 1
        known.update(_norm(q) for q in fresh)
        added["queries"] += len(fresh)
    tags = {_norm(t.get("tag")) for t in out.setdefault("tag_queries", [])}
    mined = {_norm(t) for t in out.setdefault("mined_terms", [])}
    for hashtag in vocab.get("hashtags") or []:
        if _norm(hashtag) not in tags:
            out["tag_queries"].append({"tag": hashtag, "query": hashtag, "vocab": tag})
            tags.add(_norm(hashtag))
            added["tags"] += 1
        if _norm(hashtag) not in mined:
            out["mined_terms"].append(hashtag)
            mined.add(_norm(hashtag))
    for key, target, label in (("feed_queries", "feed_queries", "feeds"), ("starter_pack_queries", "starter_pack_queries", "packs")):
        have = {_norm(x) for x in out.setdefault(target, [])}
        for item in vocab.get(key) or []:
            if _norm(item) not in have:
                out[target].append(item)
                have.add(_norm(item))
                added[label] += 1
    for term in vocab.get("jetstream_extra_terms") or []:
        if _norm(term) not in mined:
            out["mined_terms"].append(term)
            mined.add(_norm(term))
            added["jetstream_terms"] += 1
    return out, added


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    with open(CONFIG, encoding="utf-8") as stream:
        config = json.load(stream)
    with open(VOCAB, encoding="utf-8") as stream:
        vocab = json.load(stream)
    new, added = merge(config, vocab)
    print(f"anadido: {added}")
    if "--dry" not in argv:
        with open(CONFIG, "w", encoding="utf-8") as stream:
            json.dump(new, stream, ensure_ascii=False, indent=2)
        print("growth_config.json actualizado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

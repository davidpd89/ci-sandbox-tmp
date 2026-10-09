"""Minero de vocabulario de Bluesky (05/10/2026): el sistema descubre solo nuevos hashtags y terminos del nicho.

David: «pregúntale a GPT más #, palabras clave, feeds…» — GPT propone, pero la fuente mas fiable de vocabulario es lo que de verdad escribe la gente
que habla del nicho. El recolector de Jetstream (`bluesky_jetstream_collect.py`) guarda a SQLite los posts en español que casan con los terminos de
`growth_config.json`; este minero los lee y busca lo que acompana a esos posts y aun no usamos:

  * hashtags (#BookSky, #FantasiaEpica…) usados por >=3 AUTORES distintos;
  * frases de 2-3 palabras frecuentes (p. ej. "reto de lectura", "mi tbr") entre >=4 autores.

Todo candidato pasa por el filtro comun (politica/ligue/sexo/activismo) y por una lista de ruido (spam de libros gratis, sorteos, apuestas, cripto).
`promote` anade los mejores a `growth_config.json` (`mined_terms` para Jetstream y `tag_queries` para el scan) con fecha; se revierte borrando
esas entradas. Sin IA, sin escribir en la cuenta.

    python tools/bluesky_vocab_miner.py mine [--hours 72]     # -> SISTEMA_DIARIO_BLUESKY/vocab_candidates.json + top en pantalla
    python tools/bluesky_vocab_miner.py promote [--hashtags 20 --phrases 20]
"""
import collections
import datetime
import json
import os
import re
import sqlite3
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY")
CONFIG = os.path.join(ROOT, "growth_config.json")
DB = os.path.join(ROOT, "cache", "jetstream.sqlite3")
OUT = os.path.join(ROOT, "vocab_candidates.json")

HASHTAG = re.compile(r"(?<![\w#])#([A-Za-zÁÉÍÓÚÜÑáéíóúüñ][\wÁÉÍÓÚÜÑáéíóúüñ]{2,40})")
NOISE = re.compile(r"(pdf|gratis|descarg|sorteo|giveaway|apuesta|casino|cripto|crypto|nft|follow ?back|f4f|l4l|sigueme|seguime|vendo|oferta|"
                   r"descuento|premium|onlyfans|18\+|nsfw|trump|vox\b|psoe|podemos|pp\b|elecciones|gaza|israel|ukraine|ucrania)", re.I)
STOP = set("de la el en y a los las un una que es se por con para del al lo como mas más pero sus le ya o este esta si me mi tu te nos muy "
           "hay son fue ser ha han he sin sobre entre cuando todo todos esa ese eso hoy aqui aquí asi así bien".split())
MIN_HASHTAG_AUTHORS, MIN_PHRASE_AUTHORS = 3, 4


def _norm(text):
    text = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


def extract_hashtags(text):
    return {m.group(1) for m in HASHTAG.finditer(text or "")}


def phrases(text, sizes=(2, 3)):
    words = [w for w in re.findall(r"[a-záéíóúüñ]+", (text or "").casefold()) if len(w) > 2]
    out = set()
    for n in sizes:
        for i in range(len(words) - n + 1):
            gram = words[i:i + n]
            if gram[0] in STOP or gram[-1] in STOP:
                continue
            if all(w in STOP for w in gram):
                continue
            out.add(" ".join(gram))
    return out


def mine(posts, known_terms=frozenset(), known_tags=frozenset()):
    """posts: iterable de (did, text). Devuelve {'hashtags': [...], 'phrases': [...]} ordenados por autores distintos."""
    tag_authors, tag_posts = collections.defaultdict(set), collections.Counter()
    phrase_authors, phrase_posts = collections.defaultdict(set), collections.Counter()
    known_terms = {_norm(t) for t in known_terms}
    known_tags = {_norm(t) for t in known_tags}
    for did, text in posts:
        if NOISE.search(text or ""):
            continue
        for tag in extract_hashtags(text):
            tag_authors[tag].add(did)
            tag_posts[tag] += 1
        for gram in phrases(text):
            phrase_authors[gram].add(did)
            phrase_posts[gram] += 1
    hashtags = []
    for tag, authors in tag_authors.items():
        if len(authors) >= MIN_HASHTAG_AUTHORS and _norm(tag) not in known_tags and _norm(tag) not in known_terms \
                and not NOISE.search(tag) and not sc.is_political(tag):
            hashtags.append({"term": tag, "authors": len(authors), "posts": tag_posts[tag]})
    phr = []
    for gram, authors in phrase_authors.items():
        if len(authors) >= MIN_PHRASE_AUTHORS and _norm(gram) not in known_terms and not sc.is_political(gram):
            phr.append({"term": gram, "authors": len(authors), "posts": phrase_posts[gram]})
    key = lambda r: (-r["authors"], -r["posts"], r["term"])
    return {"hashtags": sorted(hashtags, key=key), "phrases": sorted(phr, key=key)}


def known_vocabulary(config):
    terms = set()
    for family in config.get("query_families") or []:
        terms.update(family.get("queries") or [])
    terms.update(config.get("actor_queries") or [])
    terms.update(config.get("starter_pack_queries") or [])
    terms.update(config.get("mined_terms") or [])
    tags = {item.get("tag") for item in config.get("tag_queries") or [] if item.get("tag")}
    return terms, tags


def read_posts(hours=72, db=DB):
    try:
        conn = sqlite3.connect(db)
    except sqlite3.Error:
        return []
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)).isoformat()
    try:
        rows = conn.execute("SELECT did, text FROM posts WHERE created_at >= ?", (cutoff,)).fetchall()
    except sqlite3.Error:
        rows = []
    conn.close()
    return rows


def promote(config, candidates, hashtags=20, phrases_n=20, today=None):
    """Anade los mejores candidatos a la configuracion (copia). Devuelve (config, anadidos)."""
    today = (today or datetime.date.today()).isoformat()
    out = json.loads(json.dumps(config))
    terms, tags = known_vocabulary(out)
    added = {"hashtags": [], "phrases": []}
    for item in candidates["hashtags"][:hashtags]:
        if _norm(item["term"]) in {_norm(t) for t in tags}:
            continue
        out.setdefault("tag_queries", []).append({"tag": item["term"], "query": item["term"], "mined": today})
        out.setdefault("mined_terms", []).append(item["term"])
        added["hashtags"].append(item["term"])
    for item in candidates["phrases"][:phrases_n]:
        if _norm(item["term"]) in {_norm(t) for t in terms}:
            continue
        out.setdefault("mined_terms", []).append(item["term"])
        added["phrases"].append(item["term"])
    return out, added


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(__doc__)
        return 2
    with open(CONFIG, encoding="utf-8") as stream:
        config = json.load(stream)
    hours = int(argv[argv.index("--hours") + 1]) if "--hours" in argv else 72
    posts = read_posts(hours)
    terms, tags = known_vocabulary(config)
    found = mine(posts, terms, tags)
    with open(OUT, "w", encoding="utf-8") as stream:
        json.dump({"date": datetime.date.today().isoformat(), "posts_read": len(posts), **found}, stream, ensure_ascii=False, indent=1)
    print(f"posts leidos: {len(posts)} | hashtags nuevos: {len(found['hashtags'])} | frases nuevas: {len(found['phrases'])}")
    if argv[0] == "mine":
        for kind in ("hashtags", "phrases"):
            print(f"-- {kind} (top 25)")
            for item in found[kind][:25]:
                print(f"   {item['term']:<38} {item['authors']:>3} autores {item['posts']:>4} posts")
    elif argv[0] == "promote":
        n_tags = int(argv[argv.index("--hashtags") + 1]) if "--hashtags" in argv else 20
        n_phr = int(argv[argv.index("--phrases") + 1]) if "--phrases" in argv else 20
        new_config, added = promote(config, found, n_tags, n_phr)
        with open(CONFIG, "w", encoding="utf-8") as stream:
            json.dump(new_config, stream, ensure_ascii=False, indent=2)
        print(f"promovidos: {len(added['hashtags'])} hashtags y {len(added['phrases'])} frases -> growth_config.json")
        print("hashtags:", ", ".join(added["hashtags"]))
        print("frases:", "; ".join(added["phrases"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

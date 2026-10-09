"""Bluesky: directorio de editoriales/escritores/librerias (semillas) -> quien les comenta -> follow + like (05/10/2026).

David (05/10): "¿Sigues a todas las editoriales? ¿Revisas los posts de las editoriales y ves quien comenta? ¿Les sigues? Lo mismo con los
escritores y con la gente que habla de libros". El motor de crecimiento ya tiene unas 160 consultas por palabras clave, hashtags, starter packs,
feeds y comentaristas de hilos que salen de la busqueda, pero NO tenia una lista curada de semillas (editoriales, autores, librerias, resenadores)
ni la recorria por sus comentaristas. Esta herramienta lo anade, con las mismas reglas que Instagram (`instagram_commenters_scan.py`):

  1. DESCUBRIR semillas con `searchActors` (handles reales; nunca se adivinan nombres), clasificarlas por la biografia
     (editorial | libreria | autor | resenador | club) y guardarlas en `SISTEMA_DIARIO_BLUESKY/bluesky_seeds.json`.
  2. Las propias semillas son candidatas a seguir (editoriales, librerias y autores en espanol, de tamano razonable).
  3. De cada semilla del dia (rotan: la menos reciente primero; se aparcan las que no dan comentaristas) se leen sus ultimos posts, y de cada
     post con respuestas se leen los comentaristas (`getPostThread`): gente activa que ya lee y comenta en el nicho.
  4. Se verifica el perfil de cada comentarista (en espanol, del nicho, tamano razonable, sigue a gente, sin politica/ligue, que no sigamos ya)
     y se genera el plan: follow + like a su comentario (la combinacion que mas follow-back da: ~26 %, frente a 8,5 % del follow solo).

    python tools/bluesky_seed_wave.py discover            # solo lectura: busca y guarda semillas nuevas
    python tools/bluesky_seed_wave.py wave [--max-follows 25]   # escribe SISTEMA_DIARIO_BLUESKY/bluesky_seed_wave.json (plan para bluesky_execute.py)
    python tools/bluesky_execute.py SISTEMA_DIARIO_BLUESKY/bluesky_seed_wave.json
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY")
SEEDS_JSON = os.path.join(ROOT, "bluesky_seeds.json")
WAVE_JSON = os.path.join(ROOT, "bluesky_seed_wave.json")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
MY_HANDLE = (os.environ.get("BLUESKY_HANDLE") or "").casefold()   # se completa al iniciar sesion; vacio no excluye a nadie

SEED_QUERIES = [
    # editoriales, librerias, bibliotecas
    "editorial", "editorial libros", "editorial independiente", "editorial fantasía", "editorial juvenil", "editorial ciencia ficción",
    "editorial poesía", "editorial narrativa", "ediciones", "sello editorial", "librería", "librería independiente", "librería fantasía",
    "biblioteca", "biblioteca pública", "libros novedades", "novedades editoriales",
    # autores
    "escritor", "escritora", "novelista", "autora de novela", "autor de fantasía", "autora fantasía", "escritor indie", "autor autopublicado",
    "escritor ciencia ficción", "escritora juvenil", "poeta", "narrativa", "cuentista", "guionista", "autor español", "autora latinoamericana",
    # lectores, reseñadores, clubes
    "booksky", "reseñas de libros", "reseñador libros", "booktuber", "bookstagrammer", "club de lectura", "club de lectura fantasía", "lectora",
    "lector compulsivo", "blog literario", "literatura juvenil", "romantasy", "fantasía épica",
    # ferias, premios, comunidades
    "feria del libro", "festival literario", "premio literario", "taller de escritura", "comunidad de escritores", "nanowrimo",
    # nichos adyacentes que leen fantasia
    "rol", "juegos de rol", "rol de mesa", "dungeons and dragons", "cómic", "novela gráfica", "manga", "anime", "videojuegos narrativos",
    "mitología", "historia medieval", "cine fantástico", "podcast de libros",
]
def _extra_seed_queries():
    """Nombres propios (editoriales, ferias, festivales, librerias) del vocabulario de GPT 05/10: se buscan con searchActors; solo entran las que existen."""
    try:
        with open(os.path.join(ROOT, "vocab_gpt_2026-10-05.json"), encoding="utf-8") as stream:
            return json.load(stream).get("seed_actor_queries") or []
    except (OSError, ValueError):
        return []


SEED_QUERIES = SEED_QUERIES + [q for q in _extra_seed_queries() if q not in SEED_QUERIES]
SEED_QUERIES_PER_DAY = 10
SEEDS_PER_DAY = 12   # base; con la rampa de volumen (etapas 1-6) sube hasta 48 (ver seeds_per_day)
POSTS_PER_SEED = 8
MIN_SEED_FOLLOWERS, MAX_SEED_FOLLOWERS = 120, 400_000
MIN_SEED_YIELD = 2

def seeds_per_day():
    try:
        import volume_ramp
        return min(48, SEEDS_PER_DAY + 6 * volume_ramp.load()["stage"])
    except Exception:
        return SEEDS_PER_DAY


TYPES = [
    ("editorial", re.compile(r"(editorial|ediciones|sello editorial|publisher|publishing house|casa editorial)", re.I)),
    ("libreria", re.compile(r"(librer[ií]a|librero|librera|bookshop|bookstore)", re.I)),
    ("resenador", re.compile(r"(rese[ñn]|booktub|bookstagram|book ?blog|blog literari|bibli[oó]fil|lector(?:a)? compulsiv)", re.I)),
    ("club", re.compile(r"(club de lectura|club lectura|book ?club|lectura conjunta|buddy read)", re.I)),
    ("rol", re.compile(r"(juegos? de rol|\brol\b|dungeons|d&d|rpg|wargame|juegos de mesa)", re.I)),
    ("comic", re.compile(r"(c[oó]mic|novela gr[aá]fica|manga|anime|ilustrador|ilustradora)", re.I)),
    ("autor", re.compile(r"(escritor|escritora|novelista|autor(?:a)? de|autor indie|autora indie|poeta|narrador|"
                         r"mis novelas|mi novela|author|writer)", re.I)),
]
SPANISH = re.compile(r"\b(el|la|los|las|de|del|que|y|en|un|una|por|con|para|mi|soy|libros?|leer|lectur\w*|escrib\w*|novela\w*|"
                     r"editorial|autor\w*|historias?|fantas\w*|rese\w+)\b", re.I)
ENGLISH = re.compile(r"\b(the|and|of|to|is|my|for|with|you|your|books?|reader|reading|writer|author|love|life|i)\b", re.I)
NICHE = re.compile(r"(libro|lectur|leer|lector|novela|fantas|escrit|autor|poes|relato|cuento|literari|narrativa|editorial|"
                   r"rese[ñn]|saga|booksky|bookstagram|manuscrito|juegos? de rol|rol de mesa|c[oó]mic|manga|mitolog|medieval)", re.I)
BUSINESS = re.compile(r"(casino|bet\b|crypto|cripto|trading|forex|onlyfans|vendo |dropship|descuento|oferta|comprar|sorteo)", re.I)


# ------------------------------------------------------------------------------------ funciones puras
def classify(bio, name=""):
    """editorial | libreria | resenador | club | autor | None segun la biografia/nombre (el primero que coincide)."""
    text = f"{name} {bio}"
    for label, pattern in TYPES:
        if pattern.search(text):
            return label
    return None


def spanish_score(text):
    return len(SPANISH.findall(text or "")) - len(ENGLISH.findall(text or ""))


def seed_ok(profile, *, known=frozenset(), my_handle=MY_HANDLE):
    """(tipo, motivo): tipo si sirve como semilla; motivo si se descarta."""
    handle = (profile.get("handle") or "").casefold()
    bio = profile.get("description") or ""
    followers = profile.get("followersCount")
    if handle in known or handle == my_handle:
        return None, "ya es semilla"
    kind = classify(bio, profile.get("displayName") or "")
    if not kind:
        return None, "biografia sin tipo (editorial/autor/libreria/resenador)"
    if followers is None or not MIN_SEED_FOLLOWERS <= followers <= MAX_SEED_FOLLOWERS:
        return None, f"seguidores={followers}"
    if sc.is_political(bio) or sc.looks_activist(bio) or BUSINESS.search(bio):
        return None, "politica/activismo/ligue/negocio"
    if spanish_score(bio + " " + (profile.get("displayName") or "")) < 1:
        return None, "no es claramente en espanol"
    import bluesky_pool as pool
    if not pool.seed_quality({"bio": bio, "type": kind}):
        return None, "bio en ingles/portugues/catalan"
    if (profile.get("postsCount") or 0) < 15:
        return None, "pocos posts"
    return kind, ""


def commenter_ok(profile, comment, *, my_handle=MY_HANDLE):
    """(puntuacion, motivo_descarte) de alguien que comento en un post de una semilla."""
    bio = profile.get("description") or ""
    handle = (profile.get("handle") or "").casefold()
    followers, following = profile.get("followersCount") or 0, profile.get("followsCount") or 0
    viewer = profile.get("viewer") or {}
    if handle == my_handle or viewer.get("following") or viewer.get("blocking") or viewer.get("blockedBy") or viewer.get("muted"):
        return 0, "ya seguido/bloqueado/silenciado"
    if not 15 <= followers <= 12000:
        return 0, f"seguidores={followers}"
    if following < 40:
        return 0, f"sigue a pocos ({following})"
    if (profile.get("postsCount") or 0) < 5:
        return 0, "pocos posts"
    text = f"{bio} {comment or ''} {profile.get('displayName') or ''}"
    if sc.is_political(text) or sc.looks_activist(text) or BUSINESS.search(bio):
        return 0, "politica/ligue/activismo/negocio"
    spanish = spanish_score(f"{bio} {comment or ''}")
    if spanish < 1:
        return 0, "no es claramente en espanol"
    score = 10 + min(spanish, 6) + (6 if NICHE.search(f"{bio} {comment or ''}") else 0)
    ratio = following / max(followers, 1)
    score += 4 if 0.6 <= ratio <= 4 else 0       # sigue aprox. tanto como la siguen: probable follow back
    score += 2 if 100 <= followers <= 3000 else 0
    return score, ""


def pick_seeds(seeds, n=None):
    """Las menos recientemente escaneadas primero; a igualdad, las que mas comentaristas dieron; las que no dan, aparcadas."""
    def key(item):
        handle, rec = item
        return (rec.get("last_scanned") or "", -(rec.get("yield") or 0), handle)
    n = n or seeds_per_day()
    import bluesky_pool as pool
    spanish_only = {h: r for h, r in seeds.items() if pool.seed_quality(r)}   # 05/10: habia semillas de WIRED/Brasil: sus comentaristas no son lectores en espanol
    seeds = spanish_only or seeds
    useful = {h: r for h, r in seeds.items() if r.get("yield") is None or r["yield"] >= MIN_SEED_YIELD}
    pool = useful if len(useful) >= n else seeds
    return [handle for handle, _ in sorted(pool.items(), key=key)[:n]]


def day_queries(today=None, n=SEED_QUERIES_PER_DAY):
    day = (today or datetime.date.today()).toordinal()
    return [SEED_QUERIES[(day * n + i) % len(SEED_QUERIES)] for i in range(n)]


def build_plan(candidates, seed_follows, max_follows=25):
    """Plan para bluesky_execute: follow + like al comentario (los mejores primero) y follow a semillas afines."""
    plan, seen = [], set()
    for item in sorted(candidates, key=lambda c: -c["score"]):
        handle = item["handle"]
        if handle.casefold() in seen:
            continue
        seen.add(handle.casefold())
        plan.append({"handle": handle, "kind": "follow", "motivo": f"seed_wave:commenter:{item['source']}"})
        if item.get("url"):
            plan.append({"handle": handle, "kind": "like", "url": item["url"], "motivo": f"seed_wave:commenter:{item['source']}"})
        if len([p for p in plan if p["kind"] == "follow"]) >= max_follows:
            break
    for seed in seed_follows:
        if seed["handle"].casefold() not in seen:
            seen.add(seed["handle"].casefold())
            plan.append({"handle": seed["handle"], "kind": "follow", "motivo": f"seed_wave:seed:{seed['type']}"})
    return plan


# ------------------------------------------------------------------------------------------ API
def _load(path, default):
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return default


def _save(path, data):
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=1, sort_keys=True)


def _profiles(b, handles_or_dids):
    out = []
    for i in range(0, len(handles_or_dids), 25):
        chunk = handles_or_dids[i:i + 25]
        data = b._get(b.AUTH_BASE, "app.bsky.actor.getProfiles", {"actors": chunk}, auth=True)   # con sesion: trae `viewer` (ya seguido/bloqueado)
        out.extend(data.get("profiles", []))
    return out


def discover(b):
    seeds = _load(SEEDS_JSON, {})
    known = {h.casefold() for h in seeds}
    added = {}
    for query in day_queries():
        actors = b._search_actors(query, 40)
        handles = [a["handle"] for a in actors if a.get("handle") and a["handle"].casefold() not in known]
        for profile in _profiles(b, handles) if handles else []:
            kind, why = seed_ok(profile, known=known, my_handle=(b.HANDLE or "").casefold())
            print(f"  {'+' if kind else '-'} @{profile['handle']}: {profile.get('followersCount')} seg {kind or why}")
            if kind:
                seeds[profile["handle"]] = {"type": kind, "followers": profile.get("followersCount"), "did": profile.get("did"),
                                            "bio": (profile.get("description") or "")[:140], "query": query,
                                            "discovered": datetime.date.today().isoformat(), "last_scanned": None, "yield": None}
                known.add(profile["handle"].casefold())
                added[profile["handle"]] = kind
    _save(SEEDS_JSON, seeds)
    print(f"semillas nuevas: {len(added)} | total: {len(seeds)}")
    return seeds


MAX_POST_AGE_DAYS, MAX_COMMENT_AGE_DAYS = 120, 90


def _age_days(iso):
    try:
        when = datetime.datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
        return (datetime.datetime.now(datetime.timezone.utc) - when).days
    except ValueError:
        return 10**6


def _thread_commenters(b, uri):
    data = b._get(b.PUBLIC_BASE, "app.bsky.feed.getPostThread", {"uri": uri, "depth": 2, "parentHeight": 0}, auth=False)
    out = []
    for reply in (data.get("thread") or {}).get("replies") or []:
        post = reply.get("post") or {}
        author = post.get("author") or {}
        text = (post.get("record") or {}).get("text") or ""
        if _age_days((post.get("record") or {}).get("createdAt")) > MAX_COMMENT_AGE_DAYS:
            continue   # comentario antiguo: la persona puede haber dejado de usar la cuenta y dar like a algo de hace meses canta
        if author.get("handle") and text.strip():
            out.append((author["handle"], text, post.get("uri")))
    return out


def _post_url(handle, uri):
    return f"https://bsky.app/profile/{handle}/post/{uri.rsplit('/', 1)[-1]}"


def wave(b, max_follows=25):
    seeds = discover(b)   # barato (5 busquedas + perfiles): cada dia entran semillas nuevas
    registry_seen = {h.casefold().lstrip("@") for h in sc.known_accounts(REGISTRO_CSV)}
    todays = pick_seeds(seeds)
    print(f"semillas de hoy: {todays}")
    pool, seed_follow_handles = {}, []
    for seed in todays:
        found = 0
        feed = b._get(b.PUBLIC_BASE, "app.bsky.feed.getAuthorFeed",
                      {"actor": seed, "limit": 30, "filter": "posts_no_replies"}, auth=False)
        posts = [i["post"] for i in feed.get("feed", []) if not i.get("reason") and (i["post"].get("replyCount") or 0) > 0
                 and _age_days((i["post"].get("record") or {}).get("createdAt")) <= MAX_POST_AGE_DAYS]
        for post in posts[:POSTS_PER_SEED]:
            for handle, text, uri in _thread_commenters(b, post["uri"]):
                if handle.casefold() == seed.casefold() or handle.casefold() in registry_seen:
                    continue
                if handle.casefold() not in pool:
                    pool[handle.casefold()] = {"handle": handle, "comment": text, "url": _post_url(handle, uri), "source": f"{seeds[seed]['type']}:{seed}", "seed": seed}
                    found += 1
        seeds[seed]["last_scanned"] = datetime.date.today().isoformat()
        seeds[seed]["yield"] = found
        print(f"  @{seed} ({seeds[seed]['type']}): {len(posts)} posts con respuestas, {found} comentaristas nuevos")
    _save(SEEDS_JSON, seeds)
    candidates, rejected = [], {}
    entries = list(pool.values())
    for profile in _profiles(b, [e["handle"] for e in entries]) if entries else []:
        entry = pool[profile["handle"].casefold()]
        score, why = commenter_ok(profile, entry["comment"], my_handle=(b.HANDLE or "").casefold())
        if why:
            rejected[why.split(" (")[0].split("=")[0]] = rejected.get(why.split(" (")[0].split("=")[0], 0) + 1
        else:
            candidates.append({**entry, "score": score, "followers": profile.get("followersCount")})
    # semillas afines que aun no seguimos (editoriales, librerias, autores): el follow a la propia semilla
    seed_profiles = _profiles(b, [h for h, r in seeds.items() if r["type"] in ("editorial", "libreria", "autor", "resenador")][:100])
    seed_follows = [{"handle": p["handle"], "type": seeds[p["handle"]]["type"]} for p in seed_profiles
                    if p["handle"] in seeds and not (p.get("viewer") or {}).get("following")
                    and not (p.get("viewer") or {}).get("blocking") and p["handle"].casefold() not in registry_seen][:8]
    plan = build_plan(candidates, seed_follows, max_follows)
    _save(WAVE_JSON, plan)
    print(f"comentaristas {len(pool)} -> candidatos {len(candidates)} (descartes: {rejected}); plan: {len(plan)} acciones "
          f"({sum(1 for p in plan if p['kind'] == 'follow')} follows)")
    return plan


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(__doc__)
        return 2
    import bluesky_interact as b
    if argv[0] == "discover":
        discover(b)
    elif argv[0] == "wave":
        max_follows = int(argv[argv.index("--max-follows") + 1]) if "--max-follows" in argv else 25
        wave(b, max_follows)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

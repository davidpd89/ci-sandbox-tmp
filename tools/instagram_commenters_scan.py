"""Instagram: gente que comenta en posts de editoriales y cuentas de libros -> candidatos a follow (04/10/2026).

David (04/10): empezar Instagram poco a poco con 10 follows al dia a lectores que comentan en publicaciones de
editoriales/libros, que no sean cuentas grandes y que puedan seguirnos de vuelta; uso humano, parar ante cualquier aviso.

Flujo (solo lectura hasta el plan): para 3 cuentas semilla del dia (rotan) abre sus 3 ultimos posts, recoge los
comentaristas y visita cada perfil para leer seguidores/seguidos/biografia. Se queda con cuentas pequenas, activas,
en espanol y del nicho, publicas, sin ligue/politica/IA y que aun no seguimos. Escribe `instagram_candidates.json`.

    python tools/instagram_commenters_scan.py [--max-profiles N]
    python tools/instagram_build_plan.py        # -> instagram_plan.json (10 follows)
    python tools/instagram_execute.py SISTEMA_DIARIO_INSTAGRAM/instagram_plan.json
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_INSTAGRAM")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
CANDIDATES_JSON = os.path.join(ROOT, "instagram_candidates.json")

# Comprobadas en vivo el 04/10: editoriales grandes (comentan lectores de todo tipo) y bookstagrammers medianos
# (sus comentaristas suelen ser lectores pequenos que devuelven el follow).
SEEDS = ["penguinlibros", "editorialplaneta", "planetadelibros", "ediciones_urano", "booket_planeta",
         "rocaeditorial", "loqueleo_es", "quilaknabooks", "eli_libros"]   # verificadas en vivo; el resto se DESCUBRE (abajo)
SEEDS_JSON = os.path.join(ROOT, "instagram_seeds.json")
# 05/10 (David: "no busques en bucle nombres que no existen"): las semillas nuevas NO se adivinan por nombre; salen de la
# busqueda de cuentas de Instagram (handle real + biografia) con estas consultas, 2 por dia, y se verifican una vez.
SEED_QUERIES = ["editorial libros", "editorial fantasía", "editorial independiente", "ediciones literarias", "librería",
                "bookstagram España", "club de lectura", "booktok español", "literatura juvenil", "novela fantástica"]
SEED_QUERIES_PER_DAY = 2
MAX_NEW_SEEDS_PER_DAY = 6
SEED_MIN_FOLLOWERS, SEED_MAX_FOLLOWERS = 1500, 1_500_000   # menos de 1500: sin comentarios; mas de 1,5 M: ruido
SEED_BIO = re.compile(r"(editorial|ediciones|libros?|librer[ií]a|lectur|leer|bookstagram|booktok|novela|fantas|literatur|"
                      r"escritor|autor|rese[ñn]as|saga|poes)", re.I)
POSTS_PER_SEED = 3
SEEDS_PER_DAY = 3
MIN_SEED_YIELD = 3   # una semilla que dio <3 comentaristas utiles (p. ej. una tienda que no es editorial) se aparca

MIN_FOLLOWERS, MAX_FOLLOWERS = 40, 3000      # "no cuentas muy grandes": con menos de 3k es probable que devuelvan el follow
MIN_FOLLOWING = 120                          # quien sigue a mucha gente suele devolver el follow
MIN_POSTS = 6

SPANISH = re.compile(r"\b(el|la|los|las|de|del|que|y|en|un|una|por|con|para|mi|mis|su|es|soy|libros?|leer|lectur\w*|"
                     r"lectora|lector|escrib\w*|novela\w*|reseñ\w*|amante|vida|café|historias?|palabras?)\b", re.I)
ENGLISH = re.compile(r"\b(the|and|of|to|is|my|for|with|you|your|books?|reader|reading|writer|author|love|life)\b", re.I)
NICHE = re.compile(r"(libro|lectur|leer|lector|book|novela|escrit|autor|reseñ|bookstagram|booktok|fantas|poes|relat|"
                   r"biblio|narrativa|literatur|letras|romance|thriller|saga)", re.I)
BUSINESS = re.compile(r"(tienda|shop|store|comprar|sorteo|gratis|descuento|promo|marketing|agencia|casino|bet|crypto|"
                      r"cripto|inversi|trading|forex|dropship|onlyfans|vendo |ventas)", re.I)
HANDLE_RE = re.compile(r"^/([A-Za-z0-9._]{2,30})/$")


def parse_count(raw):
    """'9339' -> 9339, '17,2 mil' -> 17200, '561 mil' -> 561000, '1,2 M' -> 1200000, '1.234' -> 1234."""
    text = (raw or "").strip().lower().replace("\xa0", " ")
    match = re.match(r"^([\d.,]+)\s*(mil|k|m|millones)?$", text)
    if not match:
        return None
    number, unit = match.groups()
    if unit:
        value = float(number.replace(".", "").replace(",", ".")) if "," in number else float(number)
        return int(value * (1_000_000 if unit in ("m", "millones") else 1000))
    return int(re.sub(r"[.,]", "", number))


def parse_profile(header_text):
    """Lee el texto del <header> del perfil: nombre | N publicaciones | N seguidores | N seguidos | bio..."""
    lines = [line.strip() for line in (header_text or "").splitlines() if line.strip()]
    out = {"posts": None, "followers": None, "following": None, "bio": ""}
    bio_start = 0
    for index, line in enumerate(lines):
        match = re.match(r"^([\d.,]+(?:\s*(?:mil|k|m|millones))?)\s+(publicaciones|seguidores|seguidos)$", line, re.I)
        if match:
            key = {"publicaciones": "posts", "seguidores": "followers", "seguidos": "following"}[match.group(2).lower()]
            out[key] = parse_count(match.group(1))
            bio_start = index + 1
    bio = []
    for line in lines[bio_start:]:
        if re.search(r"(siguen? (esta|este)|seguido por|^seguir$|^mensaje$|^siguiendo$)", line, re.I):
            break
        bio.append(line)
    out["bio"] = " ".join(bio)[:300]
    return out


def spanish_score(text):
    return len(SPANISH.findall(text or "")) - len(ENGLISH.findall(text or ""))


def evaluate(handle, profile, comment, *, button, my_handle="davidportodiaz", discarded=frozenset(), known=frozenset()):
    """(puntuacion, motivo_descarte). Puntuacion mayor = mejor candidato; motivo != '' => descartado."""
    key = handle.casefold()
    if key == my_handle or key in discarded or key in known:
        return 0, "ya tratada/descartada"
    if button != "follow":
        return 0, f"boton={button}"            # ya seguida, pendiente o privada
    followers, following, posts = profile.get("followers"), profile.get("following"), profile.get("posts")
    if followers is None or following is None or posts is None:
        return 0, "perfil ilegible"
    if followers < MIN_FOLLOWERS or followers > MAX_FOLLOWERS:
        return 0, f"seguidores={followers}"
    if following < MIN_FOLLOWING:
        return 0, f"sigue a pocos ({following})"
    if posts < MIN_POSTS:
        return 0, f"pocas publicaciones ({posts})"
    text = f"{profile.get('bio', '')} {comment or ''} {handle}"
    if sc.is_political(text):
        return 0, "politica/ligue/adulto"
    if BUSINESS.search(profile.get("bio", "")):
        return 0, "negocio/promocion"
    spanish = spanish_score(f"{profile.get('bio', '')} {comment or ''}")
    if spanish < 1:
        return 0, "no es claramente en espanol"
    score = 10 + min(spanish, 6) + (6 if NICHE.search(text) else 0)
    ratio = following / max(followers, 1)
    score += 4 if 0.8 <= ratio <= 3 else 0     # sigue aprox. tanto como la siguen: probable follow back
    score += 2 if 200 <= followers <= 1500 else 0
    return score, ""


def load_seeds(path=SEEDS_JSON):
    """{handle: {followers, bio, discovered, last_scanned, yield}}; las semillas verificadas de SEEDS siempre estan."""
    try:
        with open(path, encoding="utf-8") as stream:
            seeds = json.load(stream)
    except (OSError, ValueError):
        seeds = {}
    for handle in SEEDS:
        seeds.setdefault(handle, {"followers": None, "bio": "", "discovered": "builtin", "last_scanned": None, "yield": None})
    return seeds


def save_seeds(seeds, path=SEEDS_JSON):
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(seeds, stream, ensure_ascii=False, indent=1, sort_keys=True)


def pick_seeds(seeds, n=SEEDS_PER_DAY):
    """Las n semillas menos recientemente escaneadas (nunca escaneadas primero); a igualdad, las que mas candidatos dieron."""
    def key(item):
        handle, rec = item
        return (rec.get("last_scanned") or "", -(rec.get("yield") or 0), handle)
    useful = {h: r for h, r in seeds.items() if r.get("yield") is None or r["yield"] >= MIN_SEED_YIELD}   # las que no dan comentaristas se aparcan
    pool = useful if len(useful) >= n else seeds
    return [handle for handle, _ in sorted(pool.items(), key=key)[:n]]


def seed_ok(handle, bio, followers, *, known=frozenset(), my_handle="davidportodiaz"):
    """(ok, motivo) para aceptar una cuenta hallada en la busqueda como semilla de comentaristas."""
    if handle.casefold() in known or handle.casefold() == my_handle:
        return False, "ya es semilla"
    if followers is None or not SEED_MIN_FOLLOWERS <= followers <= SEED_MAX_FOLLOWERS:
        return False, f"seguidores={followers}"
    if sc.is_political(bio or "") or not SEED_BIO.search(bio or ""):
        return False, "bio fuera del nicho"
    return True, ""


def day_seed_queries(today=None, n=SEED_QUERIES_PER_DAY):
    day = (today or datetime.date.today()).toordinal()
    return [SEED_QUERIES[(day * n + i) % len(SEED_QUERIES)] for i in range(n)]


def _commenters(page_text, anchors, seed, my_handle):
    """Pares (handle, comentario) del texto de un post: bloques 'handle / edad / texto / Responder'."""
    seen, out = set(), []
    valid = {a.casefold() for a in anchors}
    for block in re.split(r"\n\s*Responder\s*\n", page_text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if line.casefold() in valid and line.casefold() not in (seed.casefold(), my_handle):
                tail = lines[index + 1:]
                text = " ".join(t for t in tail if not re.match(r"^(\d+\s*(s|min|h|d|sem)|\d+ Me gusta|Editado|•|Ver las .*)$", t))
                if line.casefold() not in seen:
                    seen.add(line.casefold())
                    out.append((line, text[:200]))
                break
    return out


def _discover_seeds(pg, ig, seed_book, known):
    """Busca editoriales/cuentas de libros con la BUSQUEDA de Instagram (handles reales con biografia) y las anade como
    semillas tras mirar su perfil una vez. Nunca se prueba un nombre inventado: si no sale en la busqueda, no existe para nosotros."""
    added = 0
    for query in day_seed_queries():
        if added >= MAX_NEW_SEEDS_PER_DAY:
            break
        try:
            results = ig._search_accounts(pg, query)
        except ig.BotWarningDetected:
            raise
        except Exception as exc:
            print(f"  busqueda de semillas {query!r}: {type(exc).__name__}")
            continue
        print(f"=== semillas: busqueda {query!r} -> {len(results)} cuentas ===")
        for handle, text in results:
            if added >= MAX_NEW_SEEDS_PER_DAY or handle.casefold() in {h.casefold() for h in seed_book}:
                continue
            if not SEED_BIO.search(text or "") and not SEED_BIO.search(handle):
                continue
            pg.goto(f"https://www.instagram.com/{handle}/", wait_until="domcontentloaded", timeout=20000)
            pg.wait_for_timeout(2500)
            ig._check_bot_warning(pg)
            profile = parse_profile(pg.inner_text("header"))
            ok, why = seed_ok(handle, f"{profile.get('bio', '')} {text}", profile.get("followers"), known=known)
            print(f"  {'+' if ok else '-'} @{handle}: {profile.get('followers')} seg {why}")
            if ok:
                seed_book[handle] = {"followers": profile.get("followers"), "bio": profile.get("bio", "")[:120],
                                     "discovered": datetime.date.today().isoformat(), "last_scanned": None, "yield": None}
                added += 1
            sc.pause(3, 6)
    save_seeds(seed_book)


def scan(max_profiles=45):
    import instagram_interact as ig
    ig._refuse_if_paused()
    known = {h.casefold().lstrip("@") for h in sc.known_accounts(REGISTRO_CSV)}
    discarded = {h.casefold().lstrip("@") for h in sc.discarded_handles(REGISTRO_CSV)}
    seed_book = load_seeds()
    pool, rejected = {}, {}
    p, pg = ig._connect()
    try:
        ok, msg = ig._health_check(pg)
        print(msg)
        if not ok:
            return []
        _discover_seeds(pg, ig, seed_book, known | discarded)
        seeds = pick_seeds(seed_book)
        print(f"semillas de hoy: {seeds}")
        for seed in seeds:
            print(f"\n=== semilla @{seed} ===")
            pg.goto(f"https://www.instagram.com/{seed}/", wait_until="domcontentloaded", timeout=25000)
            pg.wait_for_timeout(3000)
            ig._check_bot_warning(pg)
            links = pg.eval_on_selector_all(
                'a[href*="/p/"], a[href*="/reel/"]', "els => els.map(e => e.getAttribute('href'))")
            links = [l for l in dict.fromkeys(links) if l.startswith(f"/{seed}/")][:POSTS_PER_SEED] or list(dict.fromkeys(links))[:POSTS_PER_SEED]
            for link in links:
                pg.goto("https://www.instagram.com" + link, wait_until="domcontentloaded", timeout=25000)
                pg.wait_for_timeout(3500)
                ig._check_bot_warning(pg)
                ig._jittery_scroll(pg, "down")
                anchors = [h for h in pg.eval_on_selector_all("a[role=link]", "els => els.map(e => e.getAttribute('href'))")
                           if h and HANDLE_RE.match(h)]
                handles = [HANDLE_RE.match(h).group(1) for h in anchors]
                for handle, comment in _commenters(pg.inner_text("body"), handles, seed, ig.MY_HANDLE.casefold()):
                    pool.setdefault(handle.casefold(), {"handle": handle, "comment": comment, "source": f"@{seed}"})
                print(f"  {link}: {len(pool)} comentaristas acumulados")
                sc.pause(3, 6)
            seed_book[seed]["last_scanned"] = datetime.date.today().isoformat()
            seed_book[seed]["yield"] = sum(1 for e in pool.values() if e["source"] == f"@{seed}")
            save_seeds(seed_book)
        print(f"\n=== PERFILES ({min(len(pool), max_profiles)} de {len(pool)}) ===")
        candidates = []
        for entry in list(pool.values())[:max_profiles]:
            handle = entry["handle"]
            try:
                pg.goto(f"https://www.instagram.com/{handle}/", wait_until="domcontentloaded", timeout=20000)
                pg.wait_for_timeout(2500)
                ig._check_bot_warning(pg)
                header = pg.inner_text("header")
                profile = parse_profile(header)
                state = ig._profile_follow_button_state(ig._top_profile_follow_button(pg))
                # 05/10 (David): una cuenta privada que comento en el nicho tambien vale; la solicitud pendiente cuenta
                score, why = evaluate(handle, profile, entry["comment"], button=state,
                                      my_handle=ig.MY_HANDLE.casefold(), discarded=discarded, known=known)
            except ig.BotWarningDetected:
                raise
            except Exception as exc:
                score, why, profile = 0, f"error {type(exc).__name__}", {}
            if why:
                rejected[why.split(" (")[0].split("=")[0]] = rejected.get(why.split(" (")[0].split("=")[0], 0) + 1
                print(f"  - @{handle}: {why}")
            else:
                print(f"  + @{handle}: puntos={score} seg={profile['followers']}/{profile['following']} | {profile['bio'][:60]}")
                candidates.append({**entry, **profile, "score": score,
                                   "niche": bool(NICHE.search(f"{profile.get('bio', '')} {entry['comment']} {handle}"))})
            sc.pause(3, 7)
    finally:
        p.stop()
    candidates.sort(key=lambda c: -c["score"])
    with open(CANDIDATES_JSON, "w", encoding="utf-8") as stream:
        json.dump(candidates, stream, ensure_ascii=False, indent=1)
    print(f"\nCANDIDATOS: {len(candidates)} | descartes: {rejected}")
    return candidates


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    import instagram_interact as ig
    max_profiles = int(argv[argv.index("--max-profiles") + 1]) if "--max-profiles" in argv else 45
    import action_ledger as al
    try:
        with al.browser_session():   # turno del Edge compartido
            ig.ensure_browser()
            scan(max_profiles)
    except ig.BotWarningDetected as exc:
        print(str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

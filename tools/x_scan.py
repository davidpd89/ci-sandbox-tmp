"""
Fase 1 del pipeline diario de X (anadido 22/09, reescrito a fondo el 23/09
en dos rondas de correccion directa de David en la misma sesion):

RONDA 1 (volumen): la sesion del 23/09 solo produjo 3 interacciones reales,
muy por debajo de los minimos de REGLAS.md (8-12 respuestas, 15-20 likes,
2-3 reposts, 3-5 follows), gastando un 13% de tokens en ello. Causa real:
notifications - maxima prioridad segun REGLAS.md - nunca traia URL/handle
estructurado (inaccionable en la practica), y Claude analizaba cada
candidato uno a uno en vez de tratar la mayoria como accion mecanica barata.

RONDA 2 (calidad de la repeticion, misma sesion, feedback tras ver el plan
de 55 items en marcha): David senalo tres fallos de fondo mas:
1. Nunca puede comentarse DOS VECES el mismo post (se nota) - necesita
   guardarse/comprobarse, no solo evitarse "de memoria". La comprobacion
   REAL vive en `x_interact.reply_to()` (`_already_commented`, escanea los
   comentarios visibles antes de escribir); este script anade una capa
   barata adicional via `scan_common.already_interacted_urls` para ni
   siquiera sugerir "reply" sobre algo ya comentado.
2. Repartir mal el esfuerzo: a quien YA tiene relacion con nosotros
   (nos sigue, nos comenta, notifications) hay que reforzarla; a quien
   todavia NO la tiene, el objetivo es DESCUBRIR gente nueva, no revisar
   siempre las mismas cuentas/posts. Antes, "comentaristas" siempre miraba
   el mismo puñado de posts (los primeros que aparecian) - ahora rota la
   fuente semilla por dia (`_pick_seed_urls`) y evita repetir un post ya
   usado como semilla en los ultimos dias (`comentaristas_seeds.csv`).
3. Demasiado pocas respuestas sugeridas, y con la barra puesta muy alta
   (¬"cualquier tipo de respuesta vale, no todo tiene que ser analitico").
   Ahora se sugiere "reply" tambien para comentaristas reales bajo un post
   de una editorial/autor del nicho y para posts que parecen buscar
   conversacion (contienen "?"), no solo para reciprocidad directa.

Filtrado automatico: politica (scan_common), dedupe por URL/handle,
[CONOCIDA fecha=...] / [NUEVA] contra registro_interacciones.csv, exclusion
de cuentas ya descartadas por no encajar en el nicho.

Las búsquedas de intención de TRIAL_SEARCH_POOL son SOLO medición: se ejecuta
una por sesión para observar descubrimiento, pero sus resultados no entran en
candidates ni seed_pool. "Elegible por filtros" no significa "buena cuenta"
ni promociona automáticamente la consulta.

Uso:
    python tools/x_scan.py
"""
import csv
import datetime
import json
import re
import sys
import os
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import x_interact as x
import scan_common as sc
import text_common as tc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_X")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
SEEDS_CSV = os.path.join(ROOT, "comentaristas_seeds.csv")
QUERY_TRIALS_CSV = os.path.join(ROOT, "query_trials.csv")
CANDIDATES_JSON = os.path.join(ROOT, "x_candidates.json")

# Ampliado 23/09 (ronda 2): mas variedad de hashtags/frases para no agotar
# siempre las dos mismas busquedas - rota 3/dia en vez de 2.
SEARCH_POOL = [
    '"fantasia juvenil" lang:es',
    "worldbuilding fantasia lang:es",
    '"saga familiar" novela lang:es',
    '"novela coral" lang:es',
    "#BookTok lang:es libros",
    "#LiteraturaFantastica lang:es",
    "#FantasiaJuvenil lang:es",
    "recomendacion lectura fantasia lang:es",
]

# discovery_terms se consume a través del adaptador común.
# El vocabulario dinámico se resuelve en cada ronda desde hashtag_query_consumers.

# Búsquedas de intención recogidas en HASHTAGS.md (21/09); todavía NO
# probadas en vivo. Rotar una por sesión junto a tres consultas históricas.
TRIAL_SEARCH_POOL = [
    '("recomendadme" OR "busco un libro") (fantasia OR novela) lang:es -filter:replies',
    '("acabo de terminar" OR "termine de leer") (fantasia OR novela) lang:es',
    '("termine mi novela" OR "he acabado el manuscrito") lang:es',
    '("no se como" OR "me cuesta") (dialogos OR personajes OR corregir) lang:es',
    '("historia familiar" OR "memoria familiar") (novela OR escribir OR recuerdos) lang:es',
    '("feria del libro" OR presentacion OR firma) (Madrid OR Galicia) lang:es',
]

# 06/10 (David: «quitale tanta restriccion y hagamos crecer X como Bluesky/Mastodon/Threads»): el scan lee tantas superficies como pide la ETAPA de la rampa (`volume_ramp.X_STAGES`):
# busquedas Recientes y Destacados con scroll, pestana Personas, listas de seguidores de las cuentas semilla y la reserva persistente (`x_pool.py`). Solo espanol.
SEARCH_POOL += [
    "libros recomendados lang:es", '"leyendo ahora" lang:es', '"reseña" libro lang:es', "fantasía novela lang:es", '"escribiendo mi novela" lang:es', '"mi tbr" lang:es',
    '"terminé de leer" lang:es', '"recomendadme" libro lang:es', "autopublicación libro lang:es", '"club de lectura" lang:es', "romantasy lang:es", "worldbuilding lang:es",
    '"mi primera novela" lang:es', "bookstagram lang:es", '"novela juvenil" lang:es', "dragones libro lang:es", '"saga de fantasía" lang:es', "escritora fantasía lang:es",
    "manuscrito novela lang:es", '"bloqueo del escritor" lang:es', "kindle unlimited lang:es", '"reto de lectura" lang:es', "ciencia ficción libros lang:es", '"libros de rol" lang:es',
    '"lectura conjunta" lang:es', '"feria del libro" lang:es', "trilogía fantasía lang:es", "autora indie lang:es", "relectura libro lang:es", '"libro favorito" lang:es',
    "literatura fantástica lang:es", '"qué estáis leyendo" lang:es', '"reseña sin spoilers" lang:es', '"escribiendo capítulo" lang:es', "booktuber lang:es", '"autores nuevos" lang:es',
]
CONVERSATION_SEARCHES = [
    '("recomendadme" OR "me recomendáis") (libro OR novela OR fantasía) lang:es -filter:replies',
    '("acabo de terminar" OR "terminé de leer" OR "he terminado") (libro OR novela OR saga) lang:es -filter:replies',
    '("estoy leyendo" OR "leyendo ahora") (fantasía OR novela OR saga) lang:es -filter:replies',
    '("terminé mi novela" OR "primer borrador" OR "mi manuscrito") lang:es -filter:replies',
    '("bloqueo del escritor" OR "no consigo escribir" OR "atascada con mi novela" OR "atascado con mi novela") lang:es -filter:replies',
    '"libro favorito" ("cuál es" OR "vuestro") lang:es -filter:replies',
    '("busco" OR "necesito") (novela OR libro) fantasía lang:es -filter:replies',
    '"mi próxima lectura" lang:es -filter:replies',
    '"qué estáis leyendo" lang:es -filter:replies',
    '"personaje favorito" lang:es -filter:replies',
    '"qué libro" ("os" OR "me") lang:es -filter:replies',
    '("busco" OR "propongo") "club de lectura" lang:es -filter:replies',
    '("escribiendo mi novela" OR "escribiendo mi libro") lang:es -filter:replies',
    '("qué estáis escribiendo" OR "en qué estáis trabajando") (novela OR historia) lang:es -filter:replies',
]
PROFILE_QUERIES = ["libros fantasía", "booktok español", "bookstagram", "reseñas libros", "editorial independiente", "escritora fantasía", "autor fantasía", "lectora fantasía",
                   "club de lectura", "librería", "booktuber", "novela juvenil", "autopublicada", "escritor indie", "lectora compulsiva", "romantasy", "libros y café", "fantasía épica",
                   "reseñas sin spoilers", "autora novela", "escritora", "escritor", "lectora", "libros", "booklover", "bibliófila", "worldbuilding", "rol y fantasía"]
import reciprocity as _recip
PROFILE_QUERIES += [q for q in _recip.FOLLOWBACK_QUERIES if q not in PROFILE_QUERIES]      # 07/10: bios que declaran follow-back (cultura de seguir y ser seguido)
SEED_HANDLES = []       # las semillas salen de la pestana Personas (cuentas cuya bio suma >=2 terminos del nicho) y de las listas fijas; se pueden anadir a mano aqui
SCAN_MAX_MINUTES = 30
SPANISH_LANGS = ("es", "gl")


def _spanish_post(post):
    """True si el post esta en espanol: el idioma que X le asigna manda (`es`, `gl`); sin idioma fiable (`und`), el texto."""
    lang = (post.get("lang") or "").casefold()
    if lang in SPANISH_LANGS:
        return True
    if lang and lang not in ("und", "qme", "qht", "zxx", "ca", "eu"):
        return False
    return not tc.foreign_language(post.get("text") or "")


def _rotate(pool, n, salt=0, round_index=None):
    """`n` elementos del pool que rotan por dia Y por ronda: con varias rondas al dia cada una prueba consultas distintas."""
    day = datetime.date.today().timetuple().tm_yday
    start = day * 3 + (round_index if round_index is not None else datetime.datetime.now().hour // 4) + salt
    return [pool[(start * n + i) % len(pool)] for i in range(n)]


def _stage():
    try:
        import volume_ramp
        return volume_ramp.current(network="x")
    except Exception:
        return {"searches": 4, "passes": 2, "profile_queries": 2, "seeds": 1}


DAILY_LISTS = x.DAILY_LISTS

EXCLUDED_HANDLES = {"magc13173"}

SEED_COOLDOWN_DAYS = 4  # no repetir el mismo post como semilla de comentaristas antes de esto


def _handle_from_text(text):
    m = re.search(r"@(\w+)", text)
    return m.group(0).lstrip("@") if m else None



def _canonical_post_url(url):
    parsed = urllib.parse.urlsplit(url or "")
    if (parsed.scheme != "https"
            or parsed.hostname not in ("x.com", "www.x.com", "twitter.com", "www.twitter.com")
            or parsed.username or parsed.password or parsed.port):
        return None
    parts = parsed.path.strip("/").split("/")
    if (len(parts) >= 3 and parts[1] == "status"
            and parts[0].casefold() not in ("i", "home", "search", "explore")
            and re.fullmatch(r"[A-Za-z0-9_]{1,15}", parts[0])
            and re.fullmatch(r"[0-9]+", parts[2])):
        return f"https://x.com/{parts[0]}/status/{parts[2]}"
    return None



def _author_from_post_url(url):
    """Priorizar el autor del permalink sobre las menciones del texto."""
    parsed = urllib.parse.urlsplit(url or "")
    if (parsed.scheme != "https"
            or parsed.hostname not in ("x.com", "www.x.com", "twitter.com", "www.twitter.com")
            or parsed.username or parsed.password or parsed.port):
        return None
    parts = parsed.path.strip("/").split("/")
    if (len(parts) >= 3 and parts[1] == "status"
            and parts[0].casefold() not in ("i", "home", "search", "explore")
            and re.fullmatch(r"[A-Za-z0-9_]{1,15}", parts[0])
            and re.fullmatch(r"[0-9]+", parts[2])):
        return parts[0]
    return None




def _eligible_discovery(url, text, excluded=frozenset()):
    canonical = _canonical_post_url(url)
    if not canonical or not isinstance(text, str) or not text.strip():
        return False
    handle = _author_from_post_url(canonical)
    if (not handle or handle.casefold() == "autorademodiaz"
            or handle.casefold() in excluded):
        return False
    return not sc.is_political(text) and not tc.foreign_language(text)



def _record_trial_result(path, query, discovered, eligible, *, date=None):
    """Guarda evidencia de una trial; 'elegible' no equivale a calidad editorial."""
    query = (query or "").strip()
    if not query:
        raise ValueError("query experimental vacía")
    when = date or datetime.date.today().isoformat()
    try:
        datetime.date.fromisoformat(when)
    except ValueError as exc:
        raise ValueError("fecha experimental inválida") from exc

    discovered = max(0, int(discovered))
    eligible = max(0, min(int(eligible), discovered))
    first = not os.path.exists(path) or os.path.getsize(path) == 0
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        if first:
            writer.writerow(["fecha", "query", "descubiertos", "elegibles"])
        writer.writerow([when, query, discovered, eligible])


def _trial_summary(path, query):
    """Última medición por día válido; tolera el encabezado legado 'aceptados'."""
    if not os.path.exists(path):
        return {"days": 0, "discovered": 0, "eligible": 0}
    latest_by_day = {}
    try:
        with open(path, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("query") != query:
                    continue
                when = (row.get("fecha") or "").strip()
                try:
                    datetime.date.fromisoformat(when)
                    discovered = max(0, int(row.get("descubiertos", 0)))
                    raw_eligible = row.get("elegibles")
                    if raw_eligible is None:
                        raw_eligible = row.get("aceptados", 0)
                    eligible = max(0, min(int(raw_eligible), discovered))
                except (TypeError, ValueError):
                    continue
                latest_by_day[when] = (discovered, eligible)
    except (OSError, csv.Error, UnicodeError):
        return {"days": 0, "discovered": 0, "eligible": 0}

    values = list(latest_by_day.values())
    return {
        "days": len(values),
        "discovered": sum(x[0] for x in values),
        "eligible": sum(x[1] for x in values),
    }



def _process_discovery_rows(rows, *, excluded, operational, emit=None):
    """Mide filas de descubrimiento y solo emite si la fuente es operativa."""
    rows = list(rows)
    eligible_rows = [
        (url, text)
        for url, text in rows
        if _eligible_discovery(url, text, excluded)
    ]
    novel = 0
    if operational:
        if emit is None:
            raise ValueError("Una fuente operativa necesita emit")
        novel = sum(bool(emit(url, text)) for url, text in eligible_rows)
    return {
        "discovered": len(rows),
        "eligible": len(eligible_rows),
        "novel": novel,
        "eligible_rows": eligible_rows,
    }



def _lexical_queries(budget):
    """Búsquedas del turno, con una plaza de hashtags si existen nuevos."""
    import hashtag_query_consumers as hqc
    tick = datetime.date.today().toordinal() * 6 + datetime.datetime.now().hour // 4
    tags = hqc.select("x", "hashtags", [], budget=1, tick=tick)
    return hqc.select("x", "busquedas", SEARCH_POOL,
                      budget=max(0, budget - len(tags)), tick=tick) + tags


def _rotate_queries(n=3):
    day = datetime.date.today().timetuple().tm_yday
    pool_n = len(SEARCH_POOL)
    return [SEARCH_POOL[(day + i) % pool_n] for i in range(n)]


def _seed_history(path):
    """URLs canónicas usadas con éxito dentro de la ventana de cooldown."""
    recent = set()
    if not os.path.exists(path):
        return recent
    cutoff = datetime.date.today() - datetime.timedelta(days=SEED_COOLDOWN_DAYS)
    try:
        with open(path, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                try:
                    when = datetime.date.fromisoformat((row.get("fecha") or "").strip())
                except ValueError:
                    continue
                canonical = _canonical_post_url(row.get("post_url"))
                if canonical and when >= cutoff:
                    recent.add(canonical)
    except (OSError, csv.Error, UnicodeError):
        return set()
    return recent


def _pick_seed_urls(pool, n=2):
    """Selecciona semillas sin consumir cooldown; el registro ocurre tras éxito."""
    n = max(0, int(n))
    if n == 0:
        return []

    canonical_pool = []
    seen = set()
    for raw in pool:
        canonical = _canonical_post_url(raw)
        if canonical and canonical not in seen:
            seen.add(canonical)
            canonical_pool.append(canonical)

    recent = _seed_history(SEEDS_CSV)
    fresh = [url for url in canonical_pool if url not in recent]
    if len(fresh) >= n:
        return fresh[:n]

    fallback = fresh + [url for url in canonical_pool if url in recent]
    return fallback[:n]


def _record_successful_seed(path, post_url, *, date=None):
    """Consume cooldown solo tras cargar un hilo verificable; idempotente por día."""
    canonical = _canonical_post_url(post_url)
    if not canonical:
        raise ValueError("semilla X no canónica")
    when = date or datetime.date.today().isoformat()
    try:
        datetime.date.fromisoformat(when)
    except ValueError as exc:
        raise ValueError("fecha de semilla inválida") from exc

    existing = set()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream):
                    raw_date = (row.get("fecha") or "").strip()
                    raw_url = _canonical_post_url(row.get("post_url"))
                    if raw_date and raw_url:
                        existing.add((raw_date, raw_url))
        except (OSError, csv.Error, UnicodeError):
            # Fallar cerrado: si no podemos leer el historial, no lo
            # sobrescribimos ni fingimos haber registrado cooldown.
            raise RuntimeError("No se pudo leer el historial de semillas")

    if (when, canonical) in existing:
        return False

    first = not os.path.exists(path) or os.path.getsize(path) == 0
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        if first:
            writer.writerow(["fecha", "post_url"])
        writer.writerow([when, canonical])
    return True


def _parse_dump_output(raw_output):
    """Convierte el formato URL:/--- de x_interact en posts aislados."""
    rows = []
    url, text_lines = None, []
    for line in (raw_output or "").splitlines():
        if line == "---":
            if url:
                rows.append((url, "\n".join(text_lines)))
            url, text_lines = None, []
        elif line.startswith("URL:"):
            if url:
                # Si faltó separador, no mezclar texto/URL de dos posts.
                rows.append((url, "\n".join(text_lines)))
                text_lines = []
            url = line[len("URL:"):].strip()
        else:
            text_lines.append(line)
    if url:
        rows.append((url, "\n".join(text_lines)))
    return rows


_suggest_kind = lambda *a, **k: sc.downgrade_for_opinion(_suggest_kind_raw(*a, **k), a[1], 'like')


def _suggest_kind_raw(source, text, already_commented_urls, url):
    """Ronda 2 (23/09): antes casi todo por defecto era 'like' salvo
    reciprocidad directa - ahora tambien se sugiere 'reply' para
    comentaristas reales y para posts que invitan a conversacion (heuristico
    compartido en scan_common.invites_conversation, 23/09), para subir el
    volumen de respuestas (David: "cualquier tipo de respuesta vale, no todo
    tiene que ser analitico") sin que cada una exija una redaccion
    elaborada."""
    if url and url in already_commented_urls:
        return "like"  # ya hay un comentario nuestro ahi - degradar de reply a like
    if source == "notif:reply_recibido":
        return "reply"
    if source == "notif:nuevo_seguidor":
        return "follow"
    if source == "notif:reciprocidad_sin_url":
        return "follow"
    if source == "comentaristas" and sc.invites_conversation(text):
        return "reply"
    if source.startswith("search:") and sc.invites_conversation(text):
        return "reply"
    return "like"


def scan():
    known = {h.casefold(): fecha for h, fecha in sc.known_accounts(REGISTRO_CSV).items()}
    already_commented_urls = {
        canonical
        for raw in sc.already_interacted_urls(REGISTRO_CSV)
        if (canonical := _canonical_post_url(raw))
    }
    # EXCLUDED_HANDLES (manual, fragil - facil de olvidar) fusionado 23/09 con
    # sc.discarded_handles() (automatico via cualquier "unfollow" logueado en
    # registro_interacciones.csv) - mismo bug real encontrado el mismo dia en
    # Bluesky (una cuenta descartada por bot/spam volvio a sugerirse porque el
    # scan no cruzaba contra esa decision ya tomada).
    excluded = {h.casefold() for h in EXCLUDED_HANDLES | sc.discarded_handles(REGISTRO_CSV)}
    seen_handles = set()
    seen_urls = set()
    candidates = []  # (source, url, handle, text, kind_sugerida)

    # Un scan que falla a medias (navegador cerrado, health KO) no debe dejar
    # el volcado de una ejecucion anterior: x_build_plan.py lo trataria como
    # actual (visto el 02/10 al caerse el navegador compartido).
    if os.path.exists(CANDIDATES_JSON):
        os.remove(CANDIDATES_JSON)

    p, pg = x._connect()
    try:
        print("=== HEALTH ===")
        ok, msg = x._health_check(pg)
        print(msg)
        if not ok:
            print("\nParando aqui - resolver esto antes de nada mas.")
            return

        def add(source, url, handle, text):
            handle = (handle or "").lstrip("@").casefold()
            if url:
                canonical = _canonical_post_url(url)
                author = _author_from_post_url(canonical)
                if not canonical or not author:
                    return False
                author = author.casefold()
                # La URL es la identidad autoritativa del post. Nunca aceptar
                # un handle distinto aunque el caller lo haya inferido del texto.
                if handle and handle != author:
                    return False
                handle = author
                if not _eligible_discovery(canonical, text, excluded):
                    return False
                url = canonical
                if url in seen_urls:
                    return False
                seen_urls.add(url)
            else:
                if (not handle or handle == "autorademodiaz"
                        or handle in excluded
                        or not isinstance(text, str) or not text.strip()
                        or sc.is_political(text)):
                    return False
                if handle in seen_handles:
                    return False

            seen_handles.add(handle)
            kind = _suggest_kind(source, text, already_commented_urls, url)
            candidates.append(
                (source, url, handle, text[:160].replace("\n", " "), kind)
            )
            return True

        # --- 1) NOTIFICATIONS: maxima prioridad, con handle/URL real ---
        print("\n=== NOTIFICATIONS (reciprocidad - maxima prioridad, REFORZAR relacion existente) ===")
        notif_followers = []
        x.start_watchdog(420)
        try:
            notif_items = x._notification_candidates(pg)
        except Exception as exc:       # 07/10: una carga lenta de Notificaciones tumbaba toda la ronda de X (35 min perdidos): se sigue con el descubrimiento
            if "BotWarning" in type(exc).__name__ or "WrongAccount" in type(exc).__name__:
                raise
            print(f"(notificaciones omitidas: {type(exc).__name__}: {str(exc)[:100]})")
            notif_items = []
        for item in notif_items:
            source = f"notif:{item.get('kind_hint', 'sin_clasificar')}"
            item_url = item.get("url")
            text = item.get("text") or ""
            handles = [
                h for h in item.get("handles", [])
                if isinstance(h, str) and h.strip()
            ]
            author = _author_from_post_url(item_url) if item_url else None
            if item_url:
                # Una celda puede mostrar varios avatares/menciones. Una URL
                # de post pertenece al autor de SU permalink, no a todos los
                # avatares de la notificación. Si no coinciden, omitirla.
                normalized_handles = {h.strip().lstrip("@").casefold() for h in handles}
                if author and author.casefold() in normalized_handles:
                    add(source, item_url, author, text)
            else:
                for h in handles:
                    add(source, None, h, text)
            try:       # 07/10: lo que hacen por nosotros alimenta la reciprocidad de acciones (relationship_policy.py)
                import relationship_policy as _rp
                low = text.casefold()
                kind_in = ("follow" if item.get("kind_hint") == "nuevo_seguidor" or "followed you" in low or "te sigue" in low or "seguirte" in low
                           else "comment" if item.get("kind_hint") == "reply_recibido" or "replied to you" in low
                           else "repost" if "repost" in low or "retuit" in low or "republic" in low else "like" if "liked" in low or "me gusta" in low or "gust" in low
                           else "like" if item.get("kind_hint") == "reciprocidad_sin_url" else None)
                if kind_in:
                    for h in handles:
                        _rp.log_inbound("x", h, kind_in)
            except Exception:
                pass
            if item.get("kind_hint") == "nuevo_seguidor":       # quien acaba de seguirnos: follow-back con prioridad maxima (se vetan idioma y nicho al ejecutar)
                for h in handles:
                    notif_followers.append((h, "", "", "backfollow", None))
        print(f"{len(notif_items)} notificaciones con contenido real procesadas.")
        try:       # 07/10: fidelizacion; las cuentas que mas han hecho por nosotros entran como candidatas prioritarias (like en su ultimo post, follow de vuelta, comentario si la politica lo permite)
            import loyalty
            notif_followers += [(h, "", "", "backfollow", None) for h in loyalty.loyal_handles("x", 15)]
        except Exception:
            pass

        # --- 2) Descubrimiento habitual: following, listas, busquedas ---
        print("\n=== DESCUBRIMIENTO (following, listas, busquedas - priorizar gente NUEVA) ===")
        seed_pool = []  # URLs candidatas a semilla de comentaristas (mas variedad que antes)

        def _emit_discovery(source, url, text):
            handle = _author_from_post_url(url)
            if not handle:
                return False
            if source.startswith(("search", "following")) and tc.niche_hits(text) < 1:
                return False       # 06/10: una busqueda amplia («libro favorito») trae de todo; solo entra lo que habla de libros/escritura/fantasia (las listas curadas ya son del nicho)
            if add(source, url, handle, text):
                canonical = _canonical_post_url(url)
                if canonical:
                    seed_pool.append(canonical)
                return True
            return False

        def collect(source, dump_fn, *args, operational=True):
            """Ejecuta una fuente; las trials se miden sin tocar candidates/seed_pool."""
            import io
            import contextlib

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                dump_fn(pg, *args)

            rows = _parse_dump_output(buf.getvalue())
            return _process_discovery_rows(
                rows,
                excluded=excluded,
                operational=operational,
                emit=(
                    (lambda url, text: _emit_discovery(source, url, text))
                    if operational
                    else None
                ),
            )

        stage = _stage()
        passes = stage["passes"]
        started = datetime.datetime.now()
        pool_posts, account_rows = [], []      # lo que se ve va a la reserva (x_pool.py): el plan elige despues entre TODO lo acumulado

        def time_left():
            return (datetime.datetime.now() - started).total_seconds() < SCAN_MAX_MINUTES * 60

        def collect_posts(source, navigate, *args, limit=60):
            """Superficie de posts con scroll: solo los que estan en espanol entran como candidatos; todos (con su idioma) van a la reserva."""
            import io
            import contextlib
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    navigate(pg, *args)
                posts = x.collect_posts_scrolling(pg, passes=passes, limit=limit)
            except (x.BotWarningDetected, x.WrongAccountActive):
                raise
            except Exception as exc:
                print(f"(superficie omitida {source}: {type(exc).__name__}: {str(exc)[:100]})")
                return
            pool_posts.append((source, posts))
            kept = [post for post in posts if _spanish_post(post)]
            novel = sum(bool(_emit_discovery(source, post["url"], post["text"])) for post in kept)
            print(f"  {source}: {len(posts)} posts, {len(kept)} en espanol, {novel} candidatos nuevos")

        collect_posts("following-feed", x._dump_following_feed)
        for name, url in DAILY_LISTS:
            collect_posts(f"lista:{name}", x._dump_list_feed, url)
        for q in _lexical_queries(stage["searches"]):
            for mode in ("live", "top"):
                if time_left():
                    collect_posts(f"search:validada:{q}" if mode == "live" else f"search:destacados:{q}", x.open_search, q, mode, limit=80)
        for q in _rotate(PROFILE_QUERIES, stage["profile_queries"], salt=7):
            if not time_left():
                break
            try:
                x.open_search(pg, q, "user")
                rows = x.collect_account_rows(pg, passes=passes, limit=60)
                account_rows += [(h, n, b, f"profiles:{q}", None) for h, n, b in rows]
                print(f"  personas '{q}': {len(rows)} cuentas")
            except (x.BotWarningDetected, x.WrongAccountActive):
                raise
            except Exception as exc:
                print(f"(personas omitidas '{q}': {type(exc).__name__}: {str(exc)[:100]})")

        # 06/10 (GPT + pesos del algoritmo): busquedas de INTENCION CONVERSACIONAL —gente que pide recomendaciones, termina o empieza un libro, escribe o se atasca—. Sus posts van a la
        # reserva y el plan responde a los que encajan con una intencion (`x_replies.py`); antes estas consultas estaban en cuarentena y la ronda solo daba likes.
        for q in _rotate(CONVERSATION_SEARCHES, max(3, stage["searches"] // 2), salt=3):
            if time_left():
                collect_posts(f"search:conv:{q}", x.open_search, q, "live", limit=60)

        trial = TRIAL_SEARCH_POOL[
            datetime.date.today().timetuple().tm_yday % len(TRIAL_SEARCH_POOL)
        ]
        print(f"Consulta de intención NO validada: {trial}")
        trial_run = collect(
            f"search:prueba_no_validada:{trial}",
            x._dump_search,
            trial,
            "live",
            operational=False,
        )
        _record_trial_result(
            QUERY_TRIALS_CSV,
            trial,
            trial_run["discovered"],
            trial_run["eligible"],
        )
        stats = _trial_summary(QUERY_TRIALS_CSV, trial)
        rate = (
            stats["eligible"] / stats["discovered"]
            if stats["discovered"]
            else 0.0
        )
        sample = ", ".join(
            "@" + (_author_from_post_url(url) or "?").casefold()
            for url, _ in trial_run["eligible_rows"][:5]
        ) or "(ninguna)"
        print(
            f"RESULTADO TRIAL X: {trial_run['eligible']}/"
            f"{trial_run['discovered']} elegibles por filtros. "
            f"Muestra: {sample}."
        )
        print(
            f"EVIDENCIA ACUMULADA: {stats['days']} día(s), "
            f"{stats['eligible']}/{stats['discovered']} elegibles ({rate:.0%}). "
            "TRIAL NO OPERATIVA: no entra en candidates ni seed_pool y no "
            "se promociona automáticamente; revisar calidad editorial tras >=3 días."
        )

        # --- 3) Comentaristas: la comunidad real de un post no es solo quien lo escribio ---
        # Ronda 2: rota la semilla por dia y evita repetir una usada hace poco,
        # para no mirar siempre a los mismos comentaristas.
        print("\n=== COMENTARISTAS (comunidad real bajo posts frescos, semilla rotativa) ===")
        seeds = _pick_seed_urls(seed_pool, n=2)
        for post_url in seeds:
            try:
                x._goto_status(pg, post_url)
            except x.ActionTargetNotFound as e:
                # Post semilla borrado/inaccesible: no es un fallo del scan,
                # es un dato sobre esa URL concreta. No poner en cooldown
                # (mismo criterio que "hilo sin articulos verificables" mas
                # abajo) y seguir con la siguiente semilla en vez de tumbar
                # el resto del scan (bug real encontrado en vivo el 29/09).
                print(f"AVISO: post semilla no encontrado, se salta: {post_url} ({e})")
                continue
            pg.wait_for_timeout(1200)
            articles = x._extract_articles(pg, limit=10)
            # No poner en cooldown si la navegación devolvió feed vacío o
            # el post no cargó: el mismo URL podrá recuperarse mañana.
            if not any(_author_from_post_url(
                    f"https://x.com{href}" if href and href.startswith("/") else href
                    ) for href, _ in articles):
                print(f"AVISO: hilo semilla sin artículos verificables: {post_url}")
                continue
            _record_successful_seed(SEEDS_CSV, post_url)
            for href, text in articles:
                url2 = f"https://x.com{href}" if href and href.startswith("/") else href
                handle2 = _author_from_post_url(url2)
                if handle2 and handle2.casefold() != "autorademodiaz":
                    add("comentaristas", url2, handle2, text)
        if seeds:
            print(f"Semillas usadas hoy: {seeds}")

        # --- 4) Seguidores de las cuentas semilla (lectores y autores recientes del nicho) y reserva persistente ---
        try:
            import x_pool as pool
            db = pool.connect()
            try:
                account_rows += notif_followers
                pool.add_seeds(db, SEED_HANDLES)
                if account_rows:       # las semillas nacidas de la pestana Personas de esta ronda se pueden leer ya
                    pool.record_accounts(db, account_rows)
                    account_rows = []
                for seed in pool.due_seeds(db, stage["seeds"]):
                    if not time_left():
                        break
                    print(f"\n=== SEGUIDORES de @{seed} ===")
                    try:
                        info, rows = x.collect_followers(pg, seed, passes=10, limit=150)
                        pool.mark_seed(db, seed, followers=info.get("followers"))
                        account_rows += [(h, n, b, f"followers:{seed}", seed) for h, n, b in rows]
                        print(f"  {len(rows)} cuentas ({info.get('followers')} seguidores)")
                    except (x.BotWarningDetected, x.WrongAccountActive):
                        raise
                    except Exception as exc:
                        print(f"(semilla omitida: {type(exc).__name__}: {str(exc)[:100]})")
                added = sum(pool.record_posts(db, posts, source) for source, posts in pool_posts)
                seen = sum(len(posts) for _, posts in pool_posts)
                new_accounts = pool.record_accounts(db, account_rows) if account_rows else 0
                print(f"\n=== RESERVA: {added} posts nuevos de {seen} vistos; {new_accounts} cuentas nuevas de {len(account_rows)}; {pool.stats(db)} ===")
            finally:
                db.close()
        except (x.BotWarningDetected, x.WrongAccountActive):
            raise
        except Exception as exc:
            print(f"(reserva no disponible: {type(exc).__name__}: {exc})")

        print(f"\n=== CANDIDATOS FILTRADOS: {len(candidates)} (tras dedupe/politica/exclusion) ===")
        by_kind = {}
        for source, url, handle, text, kind in candidates:
            by_kind[kind] = by_kind.get(kind, 0) + 1
            known_tag = f"[CONOCIDA fecha={known[handle]}] " if handle in known else "[NUEVA] "
            ya_comentado = " [YA_COMENTADO_AHI]" if url in already_commented_urls else ""
            print(f"{known_tag}sugerido={kind} | @{handle} | {source} | {url or '(sin URL - accion sobre la cuenta)'}{ya_comentado}")
            print(f"   {text}")

        # Volcado estructurado (02/10, a peticion explicita de David: "mayor
        # interaccion, menor coste" - revisar candidato a candidato a mano es
        # el coste real, no la API). x_build_plan.py lee esto y construye
        # plan.json mecanicamente para follow/like (ya viene todo decidido
        # en 'kind' desde _suggest_kind) - solo las 'reply' quedan aparte
        # para redactar texto real, que es lo unico que de verdad necesita
        # criterio humano/editorial.
        with open(CANDIDATES_JSON, "w", encoding="utf-8") as stream:
            json.dump(
                [
                    {
                        "source": source,
                        "url": url,
                        "handle": handle,
                        "text": text,
                        "kind": kind,
                        "known_date": known.get(handle),
                        "ya_comentado": url in already_commented_urls,
                    }
                    for source, url, handle, text, kind in candidates
                ],
                stream,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\nVolcado estructurado: {CANDIDATES_JSON} (usar con x_build_plan.py)")

        print(f"\nResumen por kind sugerida: {by_kind}")
        print(
            "\nRecordatorio (REGLAS.md, corregido 23/09): minimos diarios 8-12 "
            "replies, 15-20 likes, 2-3 reposts, 3-5 follows. Con notificaciones "
            "(reforzar) reciprocidad esta bien repetir cuenta; en descubrimiento "
            "(following/listas/busquedas/comentaristas) preferir [NUEVA] sobre "
            "[CONOCIDA] - el objetivo ahi es llegar a gente distinta, no revisar "
            "siempre lo mismo. Nunca sugerir reply sobre algo marcado "
            "[YA_COMENTADO_AHI] (la comprobacion real y definitiva es en vivo, "
            "dentro de reply_to())."
        )

        print("\n=== EXPLORE (tendencias - filtrado, corto) ===")
        x._dump_explore(pg)
    finally:
        p.stop()


if __name__ == "__main__":
    try:
        x.ensure_browser()
        scan()
    except x.BotWarningDetected as e:
        print(str(e))
        sys.exit(2)
    except x.WrongAccountActive as e:
        print(str(e))
        sys.exit(3)

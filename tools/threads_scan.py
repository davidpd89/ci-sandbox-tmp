"""
Fase 1 del pipeline diario de Threads (22/09, fuentes ampliadas 24/09) - mismo
patron que `tools/x_scan.py`: una conexion, recoge todo, filtra
automaticamente antes de que Claude lea nada, saca una lista corta de
candidatos.

Fuentes: notifications (reciprocidad), feed "Para ti" (via `_extract_posts`,
mezcla comunidades tematicas reales sin buscar nada), y 2 busquedas del pool
diario (rotan por dia del año, mismo criterio que bluesky_scan.py/
mastodon_scan.py). Antes solo habia una busqueda fija ("Book Threads") - a
peticion explicita de David (24/09: "Threads podria aprovecharse mas...
revisar funcionalidades, hashtags, para ver como mejorar y llegar a mas") se
probaron en vivo las 12 consultas sin validar que ya estaban anotadas en
CUENTAS_VIGILAR.md (banco traido de THREADS.md, nunca probado) mas las
comunidades organicas detectadas ("Author Threads", "Librosthreads"). De las
probadas, 2 dieron contenido real y en español que vale la pena rotar
ademas de Book Threads - "worldbuilding" tenia contenido excelente pero
mayoritariamente en ingles (no encaja con el foco hispanohablante del resto
del sistema) y "fantasia juvenil española"/"club de lectura"/"memoria
familiar" dieron demasiado ruido (contenido politico/identitario o
sensible colado, o un unico resultado) - ver diario/2026-09-24.md para el
detalle completo de las 6 consultas probadas.

Filtrado automatico: dedupe por handle dentro de la pasada, descarta
contenido politico (heuristico), descarta nuestro propio handle, marca
[NUEVA]/[CONOCIDA fecha=...] contra registro_interacciones.csv.

Kind sugerida (anadido 23/09, mismo criterio que x_scan.py/instagram_scan.py -
corregido el mismo dia tras detectar que Threads nunca habia recibido esta
mejora pese a haberla aplicado ya a X): cada candidato de feed/busqueda sale
con una sugerencia mecanica ("reply" si el texto invita a conversacion via
"?"/"¿", "like" en el resto) para que decidir sea sobre todo transcribir, no
redactar cada vez desde cero. Las notifications de reciprocidad ("Ahora te
sigue(n)") siguen siendo texto sin estructurar (ver PENDIENTES.md, pendiente
de mas trabajo) - Claude las lee a mano, son pocas por sesion.

Uso:
    python tools/threads_scan.py
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import threads_interact as t
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_THREADS")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")

# Pool de busqueda ampliado 24/09 - "Book Threads" es la comunidad original
# (895 mil miembros, ver CUENTAS_VIGILAR.md); "Author Threads" y "autores
# indie españa" son las 2 consultas nuevas validadas en vivo ese dia (real,
# en español, sin ruido politico/sensible - ver docstring del modulo).
SEARCH_POOL = ["Book Threads", "Author Threads", "autores indie españa",
               # 03/10 (David: "si no encuentras es fallo del script"): el scan solo daba ~14 candidatos por
               # ronda con 2 busquedas rotativas; se amplia el pool en español y se usan 4 por ronda.
               "libros recomendados", "leyendo ahora", "reseña libro", "fantasía novela", "escribiendo mi novela",
               "booktok español", "club de lectura", "lectura del día"]


SEARCH_POOL += ["recomendadme un libro", "terminé de leer", "mi tbr", "reseña sin spoilers", "novela de fantasía", "autora indie", "escritora de fantasía",
                "leyendo fantasía", "wip novela", "cómic recomendado", "libros de rol", "ciencia ficción libros"]   # 05/10: vocabulario de GPT (consulta D) en espanol

# 06/10 (David: «amplia, no te autolimites»): mas consultas en espanol (Threads las trae en pestanas Principales y Recientes) y consultas de PERFILES.
SEARCH_POOL += ["reseña de libro", "fantasía juvenil", "saga de fantasía", "novela juvenil", "bookstagram", "libro favorito", "mi lectura actual", "qué estáis leyendo",
                "recomendación de fantasía", "autores nuevos", "autopublicación", "kindle unlimited", "mi primera novela", "reto de lectura", "lectura conjunta",
                "libros de magia", "dragones libro", "romantasy", "fantasía épica", "worldbuilding", "mapa de mi mundo", "manuscrito", "escribiendo capítulo", "bloqueo del escritor",
                "corrección de novela", "novela autopublicada", "feria del libro", "booktuber", "libros que me marcaron", "tbr pile", "relectura", "trilogía de fantasía"]
# discovery_terms se consume a través del adaptador común.
# Consumo dinámico en _rotate_searches.
PROFILE_QUERIES = ["libros fantasía", "booktok español", "bookstagram", "reseñas libros", "editorial independiente", "escritora fantasía", "autor fantasía", "lectora fantasía",
                   "club de lectura", "librería", "booktuber", "novela juvenil", "autopublicada", "escritor indie", "lectora compulsiva", "romantasy", "libros y café",
                   "fantasía épica", "reseñas sin spoilers", "autora novela", "escritora", "escritor", "lectora", "libros", "booklover", "bibliófila"]
import reciprocity as _recip
PROFILE_QUERIES += [q for q in _recip.FOLLOWBACK_QUERIES if q not in PROFILE_QUERIES]      # 07/10: bios que declaran follow-back (cultura de seguir y ser seguido)
SEED_HANDLES = ["el_bookle"]       # semillas iniciales; las demas salen de la pestana Perfiles (cuentas cuya bio suma >=2 terminos del nicho)
SCAN_MAX_MINUTES = 28


def _rotate(pool, n, round_index=None, salt=0):
    day = datetime.date.today().timetuple().tm_yday
    start = day * 3 + (round_index if round_index is not None else datetime.datetime.now().hour // 6) + salt
    return [pool[(start * n + i) % len(pool)] for i in range(n)]


def _rotate_searches(n=4, round_index=None):
    """`n` busquedas del pool que rotan por dia Y por ronda: con 3-5 rondas al dia cada una prueba consultas distintas."""
    day = datetime.date.today().timetuple().tm_yday
    start = day * 3 + (round_index if round_index is not None else datetime.datetime.now().hour // 6)
    import hashtag_query_consumers as hqc
    tick = start
    tags = hqc.select("threads", "hashtags", [], budget=min(1, max(0, n)), tick=tick)
    return hqc.select("threads", "busquedas", SEARCH_POOL,
                      budget=max(0, n - len(tags)), tick=tick) + tags


_suggest_kind = lambda *a, **k: sc.downgrade_for_opinion(_suggest_kind_raw(*a, **k), a[0], 'like')


def _suggest_kind_raw(text):
    return "reply" if sc.invites_conversation(text) else "like"


def _candidate_key(handle, permalink, text):
    """Deduplica publicaciones, no autores: una cuenta puede aportar varios posts."""
    if permalink:
        return ("post", permalink.rstrip("/"))
    normalized_text = " ".join((text or "").split()).casefold()
    return ("fallback", (handle or "").casefold(), normalized_text)


def _previously_replied_urls(registro_csv):
    return {
        url.rstrip("/")
        for url in sc.already_interacted_urls(registro_csv)
        if url
    }


CANDIDATES_JSON = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_THREADS", "threads_candidates.json")


def scan():
    known = sc.known_accounts(REGISTRO_CSV)
    discarded = sc.discarded_handles(REGISTRO_CSV)
    previously_replied = _previously_replied_urls(REGISTRO_CSV)
    seen_posts = set()
    candidates = []  # (source, handle, permalink, text, kind)

    try:
        import volume_ramp
        stage = volume_ramp.current(network="threads")
        n_searches, passes = stage["searches"], stage["passes"]
        n_profile_queries, n_seeds = stage.get("profile_queries", 2), stage.get("seeds", 1)
    except Exception:
        n_searches, passes, n_profile_queries, n_seeds = 4, 1, 2, 1
    account_rows = []     # (handle, nombre, bio, fuente, semilla): cuentas de la pestana Perfiles y de las listas de seguidores
    started = datetime.datetime.now()

    def time_left():
        return (datetime.datetime.now() - started).total_seconds() < SCAN_MAX_MINUTES * 60
    pool_rows = []        # (handle, permalink, texto, fuente) de TODO lo que se ve: la reserva decide despues (threads_pool.py)

    p, pg = t._connect()
    t.start_watchdog(420)
    try:
        print("=== HEALTH ===")
        ok, msg = t._health_check(pg)
        print(msg)
        if not ok:
            print("\nParando aqui - resolver esto antes de nada mas.")
            return

        print("\n=== NOTIFICATIONS (reciprocidad - maxima prioridad) ===")
        t._dump_notifications(pg)
        try:       # quien acaba de seguirnos: follow-back con prioridad maxima (06/10)
            followers_now = t.new_followers(pg)
            account_rows += [(h, "", "", "backfollow", None) for h in followers_now]
            try:       # 07/10: fidelizacion; registra quien nos sigue y mete a las cuentas fieles como candidatas prioritarias
                import loyalty
                import relationship_policy as _rp
                for h in followers_now:
                    _rp.log_inbound("threads", h, "follow")
                account_rows += [(h, "", "", "backfollow", None) for h in loyalty.loyal_handles("threads", 15)]
            except Exception:
                pass
            print(f"  nuevos seguidores visibles en Actividad: {followers_now}")
        except (t.BotWarningDetected, t.WrongAccountActive):
            raise
        except Exception as exc:
            print(f"(seguidores nuevos omitidos: {type(exc).__name__}: {str(exc)[:100]})")

        def collect(source, posts):
            for handle, permalink, text in posts:
                if handle and handle != t.MY_HANDLE and handle not in discarded:
                    pool_rows.append((handle, permalink, text, source))
                if not handle or handle == t.MY_HANDLE or handle in discarded:
                    continue
                if permalink and permalink.rstrip("/") in previously_replied:
                    continue
                key = _candidate_key(handle, permalink, text)
                if key in seen_posts:
                    continue
                seen_posts.add(key)
                if sc.is_political(text):
                    continue
                kind = _suggest_kind(text)
                candidates.append((source, handle, permalink, text[:160].replace("\n", " "), kind))

        print("\n=== RECOLECTANDO CANDIDATOS (feed) ===")
        pg.goto("https://www.threads.com/", wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(2500)
        collect("feed", t.collect_posts_scrolling(pg, passes=passes, limit=60))

        for query in _rotate_searches(n_searches):
            for mode, label in (("top", "search"), ("recent", "recent")):       # 06/10: «Recientes» da posts de hace minutos que «Principales» no muestra
                if not time_left():
                    break
                print(f"\n=== RECOLECTANDO CANDIDATOS ({label}: '{query}') ===")
                try:
                    t.open_search(pg, query, mode)
                    collect(f"{label}:{query}", t.collect_posts_scrolling(pg, passes=passes, limit=80))
                except (t.BotWarningDetected, t.WrongAccountActive):
                    raise
                except Exception as exc:
                    print(f"(superficie omitida: {type(exc).__name__}: {str(exc)[:120]})")

        for query in _rotate(PROFILE_QUERIES, n_profile_queries, salt=7):
            if not time_left():
                break
            print(f"\n=== CUENTAS (pestana Perfiles: '{query}') ===")
            try:
                t.open_search(pg, query, "profiles")
                rows = t.collect_account_rows(pg, passes=passes, limit=60)
                account_rows += [(h, n, b, f"profiles:{query}", None) for h, n, b in rows]
                print(f"  {len(rows)} cuentas")
            except (t.BotWarningDetected, t.WrongAccountActive):
                raise
            except Exception as exc:
                print(f"(superficie omitida: {type(exc).__name__}: {str(exc)[:120]})")

        try:       # listas de seguidores de las cuentas del nicho: lectores y autores recientes, el equivalente a «los que siguen a las editoriales» en Bluesky
            import threads_pool as pool
            db = pool.connect()
            try:
                pool.add_seeds(db, SEED_HANDLES)
                if account_rows:       # las semillas nacidas de la pestana Perfiles de esta misma ronda se pueden leer ya
                    pool.record_accounts(db, account_rows)
                    account_rows = []
                import threads_discovery_quality as _discovery_quality
                historically_blocked = _discovery_quality.quarantined_pool_handles(db)
                for seed in pool.due_seeds(db, n_seeds):
                    if not time_left():
                        break
                    if str(seed).lstrip("@").casefold() in historically_blocked:
                        continue
                    print(f"\n=== SEGUIDORES de @{seed} ===")
                    try:
                        info, rows = t.collect_followers(pg, seed, passes=10, limit=150)
                        pool.mark_seed(db, seed, followers=info.get("followers"))
                        account_rows += [(h, n, b, f"followers:{seed}", seed) for h, n, b in rows]
                        print(f"  {len(rows)} cuentas ({info.get('followers')} seguidores)")
                    except (t.BotWarningDetected, t.WrongAccountActive):
                        raise
                    except Exception as exc:
                        print(f"(semilla omitida: {type(exc).__name__}: {str(exc)[:120]})")
            finally:
                db.close()
        except (t.BotWarningDetected, t.WrongAccountActive):
            raise
        except Exception as exc:
            print(f"(semillas no disponibles: {type(exc).__name__}: {exc})")

        # Detectar campañas de texto duplicado entre cuentas ANTES de escribir
        # en la reserva y antes de entregar candidatos al builder. Es una
        # barrera adicional; los filtros de seguridad del ejecutor permanecen.
        import threads_pool as _tp
        import threads_discovery_quality as _dq
        suspect = _dq.blocked_handles(
            [{"handle": h, "text": _tp.body_of(body)}
             for h, _url, body, _source in pool_rows]
        )
        if suspect:
            pool_rows = [r for r in pool_rows if r[0].lstrip("@").casefold() not in suspect]
            candidates = [r for r in candidates if r[1].lstrip("@").casefold() not in suspect]
            account_rows = [r for r in account_rows if r[0].lstrip("@").casefold() not in suspect]
            print(f"[threads] cuentas omitidas por señuelo/campaña repetida: {len(suspect)}")

        try:       # reserva persistente de posts (threads_pool.py): lo visto hoy sigue disponible para las proximas rondas
            import threads_pool as pool
            db = pool.connect()
            try:
                if suspect:
                    pool.quarantine_handles(db, suspect)
                added = pool.record_posts(db, pool_rows)
                new_accounts = pool.record_accounts(db, account_rows) if account_rows else 0
                print(f"\n=== RESERVA: {added} posts nuevos de {len(pool_rows)} vistos; {new_accounts} cuentas nuevas de {len(account_rows)}; {pool.stats(db)} ===")
            finally:
                db.close()
        except Exception as exc:
            print(f"(reserva no disponible: {type(exc).__name__}: {exc})")
        print(f"\n=== CANDIDATOS FILTRADOS: {len(candidates)} (tras dedupe/politica) ===")
        by_kind = {}
        for source, handle, permalink, text, kind in candidates:
            by_kind[kind] = by_kind.get(kind, 0) + 1
            known_tag = f"[CONOCIDA fecha={known[handle]}] " if handle in known else "[NUEVA] "
            print(f"{known_tag}sugerido={kind} | @{handle} | {source} | {permalink or '(sin permalink)'}")
            print(f"   {text}")
        print(f"\nResumen por kind sugerida: {by_kind}")
        # Volcado estructurado (03/10): threads_build_plan.py construye el plan mecanico de likes/follows
        # sin transcribir candidatos a mano (mismo patron que x_candidates.json).
        with open(CANDIDATES_JSON, "w", encoding="utf-8") as stream:
            json.dump([{"source": source, "handle": handle, "permalink": permalink, "text": text, "kind": kind,
                        "known_date": known.get(handle)} for source, handle, permalink, text, kind in candidates],
                      stream, ensure_ascii=False, indent=1)
    finally:
        p.stop()


if __name__ == "__main__":
    try:
        t.ensure_browser()
        scan()
    except t.BotWarningDetected as e:
        print(str(e))
        sys.exit(2)
    except t.WrongAccountActive as e:
        print(str(e))
        sys.exit(3)

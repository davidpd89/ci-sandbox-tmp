"""
LEGACY / DIAGNÓSTICO RÁPIDO.

Desde 29/09/2026 el sistema diario entra por `tools/bluesky_growth_flow.py`, que orquesta `tools/bluesky_growth_scan.py`.
Este fichero se conserva para regresiones y diagnóstico puntual. NO debe usarse para
concluir que no hace falta explorar: su `DISCOVERY_SCAN_TARGET` pertenece al diseño
anterior que podía cortar búsquedas cuando notifications/timeline llenaban el cupo.

Historia del scanner original (22/09, reescrito 23/09):

1. Notifications ahora se convierte en candidatos REALES (antes solo se
   imprimia texto crudo, sin URL/handle accionable para las de tipo
   like/repost/follow - igual fallo estructural que tenia X). Cada reason
   de Bluesky (`reply`, `mention`, `quote`, `like`, `repost`, `follow`) se
   traduce a una accion sugerida via `_suggest_kind`.
2. Nueva fuente "comentaristas": quien responde a un post de timeline/
   busqueda es cantera real de lectores activos en el nicho (a peticion
   explicita de David) - se usa `getPostThread` (ya existe en
   bluesky_interact.py) sobre 1-2 posts semilla, rotando cual se usa cada
   dia igual que x_scan.py (evita mirar siempre a los mismos comentaristas).
3. `kind` sugerida por candidato para que decidir sea mecanico: like/follow
   por defecto (barato), reply reservado a reciprocidad directa y a
   comentaristas/busquedas que parecen buscar conversacion.
4. Reforzar (notifications) vs descubrir (timeline/busqueda/comentaristas):
   en descubrimiento se prioriza gente [NUEVA], en notifications repetir
   cuenta es correcto.

Filtrado automatico: descarta nuestro propio handle, contenido politico,
dedupe por handle, [NUEVA]/[CONOCIDA fecha=...], nunca sugiere reply sobre
un post donde `scan_common.already_interacted_urls` diga que ya comentamos
(la garantia real sigue siendo la comprobacion en vivo dentro de
`bluesky_interact.reply_to()`, via `_already_commented`).

Uso diagnóstico:
    python tools/bluesky_scan.py

Uso diario:
    python tools/bluesky_growth_scan.py --json
"""
import contextlib
import csv
import datetime
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import bluesky_interact as b
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
SEEDS_CSV = os.path.join(ROOT, "comentaristas_seeds.csv")
QUERY_HISTORY_CSV = os.path.join(ROOT, "query_history.csv")
SEED_COOLDOWN_DAYS = 4
DISCOVERY_SCAN_TARGET = 8  # presupuesto de lectura, NO cuota de acciones

QUERY_POOL = [
    ("fantasia juvenil", "es"),
    ("romantasy", "es"),
    ("saga familiar novela", "es"),
    ("novela coral", "es"),
    ("recomendacion lectura", "es"),
]

# Pool EXPERIMENTAL de hashtags para medir descubrimiento. No se afirma que
# sean los más activos: se combinan con palabra española + lang=es y su valor
# se decidirá por candidatos reales obtenidos, no por la etiqueta en sí.
TAG_QUERY_POOL = [
    ("BookSky", "fantasía"),
    ("fantasybooks", "fantasía"),
    ("WriterSky", "escribir"),
    ("ReaderSky", "lectura"),
    ("writingcommunity", "novela"),
]


def _query_key(kind, item):
    return kind + ":" + "|".join(str(part).casefold() for part in item)


def _query_last_used():
    history = {}
    if not os.path.exists(QUERY_HISTORY_CSV) or os.path.getsize(QUERY_HISTORY_CSV) == 0:
        return history
    with open(QUERY_HISTORY_CSV, encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or ()) != {"fecha", "query"}:
            raise RuntimeError("query_history.csv debe tener cabecera fecha,query")
        for line_no, row in enumerate(reader, start=2):
            raw_date = (row.get("fecha") or "").strip()
            key = (row.get("query") or "").strip()
            if not raw_date or not key:
                raise RuntimeError(
                    f"query_history.csv inválido en línea {line_no}: fecha/query vacía"
                )
            try:
                used = datetime.date.fromisoformat(raw_date)
            except ValueError as exc:
                raise RuntimeError(
                    f"query_history.csv inválido en línea {line_no}: {raw_date!r}"
                ) from exc
            if key not in history or used > history[key]:
                history[key] = used
    return history


def _pick_least_recent(pool, n, kind):
    """Elegir consultas por antigüedad real, no por módulo del día.

    Así una ejecución tardía o repetida no vuelve cíclicamente a las mismas
    palabras cada cinco días. Las nunca usadas van primero.
    """
    history = _query_last_used()
    floor = datetime.date.min
    ranked = sorted(
        pool,
        key=lambda item: (
            history.get(_query_key(kind, item), floor),
            _query_key(kind, item),
        ),
    )
    return ranked[:max(0, int(n))]


def _record_query_use(kind, item):
    exists = os.path.exists(QUERY_HISTORY_CSV) and os.path.getsize(QUERY_HISTORY_CSV) > 0
    with open(QUERY_HISTORY_CSV, "a", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        if not exists:
            writer.writerow(["fecha", "query"])
        writer.writerow([datetime.date.today().isoformat(), _query_key(kind, item)])


def _post_url(post):
    author = post.get("author") or {}
    return _post_url_from_uri(post.get("uri"), author.get("handle"))


def _pick_seeds(pool, n=2):
    """Elige semillas evitando repetir una usada en los ultimos
    SEED_COOLDOWN_DAYS dias. Logica compartida en scan_common.pick_seeds
    (23/09) - `pool` son tuplas (uri, url), asi que se pasa `key_fn` para
    comparar/registrar solo el `uri` (BUG REAL corregido al centralizar:
    la version anterior comparaba la tupla completa contra un set de uris
    sueltos y nunca excluia nada)."""
    return sc.pick_seeds(SEEDS_CSV, pool, n=n, cooldown_days=SEED_COOLDOWN_DAYS,
                          id_field="uri", key_fn=lambda item: item[0], record=False)


_suggest_kind = lambda *a, **k: sc.downgrade_for_opinion(_suggest_kind_raw(*a, **k), a[1], 'like')


def _suggest_kind_raw(
    source,
    text,
    url,
    already_commented_urls,
    *,
    raw_uri=None,
    own_reply_parents=frozenset(),
):
    # El CSV histórico no siempre contiene URL. El repo propio es la fuente
    # autoritativa y se carga UNA vez al empezar el scan.
    if raw_uri and raw_uri in own_reply_parents:
        return "like"
    if url and url in already_commented_urls:
        return "like"
    if source == "notif:contenido":
        # Un emoji/asentimiento/despedida breve no necesita otra respuesta.
        return "like" if sc.is_conversation_closer(text) else "reply"
    if source == "notif:reciprocidad_sin_contenido":
        return "follow"
    if source == "comentaristas" and sc.invites_conversation(text):
        return "reply"
    if source.startswith("search:") and sc.invites_conversation(text):
        return "reply"
    return "like"


def scan():
    known = {h.casefold(): fecha for h, fecha in sc.known_accounts(REGISTRO_CSV).items()}
    already_commented_urls = sc.already_interacted_urls(REGISTRO_CSV)
    discarded = {h.casefold() for h in sc.discarded_handles(REGISTRO_CSV)}
    seen = set()
    seen_notification_posts = set()  # varias respuestas distintas del mismo autor no se ocultan entre sí
    follow_state = {}
    profile_cache = {}
    candidates = []

    print("=== HEALTH ===")
    ok, msg, profile = b._health_check()
    print(msg)
    if not ok:
        raise RuntimeError(msg)

    # Una sola lectura paginada del repo propio sustituye la inspección manual
    # de cada hilo y evita N recorridos completos de _already_commented().
    own_reply_parents = b._own_reply_parent_uris()
    my_handle = profile["handle"].casefold()

    def emit(source, handle, url, text, raw_uri=None):
        handle = (handle or "").strip().lstrip("@").casefold()
        is_content_notification = source == "notif:contenido"
        if not handle or handle == my_handle:
            return False
        if source in ("timeline", "comentaristas") or source.startswith(("search:", "tag:", "domain:")):
            if not url:
                return False
        if is_content_notification:
            if not url or url in seen_notification_posts:
                return False
        elif handle in seen:
            return False
        if handle in discarded:
            return False
        if sc.is_political(text):
            return False

        kind = _suggest_kind(
            source,
            text,
            url,
            already_commented_urls,
            raw_uri=raw_uri,
            own_reply_parents=own_reply_parents,
        )
        if kind in {"like", "repost", "reply", "quote"} and not url:
            return False

        profile_summary = None
        if kind == "follow":
            if handle not in profile_cache:
                try:
                    profile_cache[handle] = b._get(
                        b.AUTH_BASE,
                        "app.bsky.actor.getProfile",
                        {"actor": handle},
                        auth=True,
                    )
                except b.RateLimitExceeded:
                    raise
                except Exception as exc:
                    print(f"OMITIDO follow @{handle}: no se pudo verificar relación: {exc}")
                    return False
            target = profile_cache[handle]
            viewer = target.get("viewer")
            if not isinstance(viewer, dict):
                print(f"OMITIDO follow @{handle}: falta viewer; no se supone que no seguimos")
                return False
            follow_state[handle] = bool(viewer.get("following"))
            if follow_state[handle]:
                print(f"OMITIDO follow @{handle}: ya se sigue (viewer.following)")
                return False
            profile_summary = {
                "display_name": target.get("displayName") or "",
                "description": (target.get("description") or "")[:300],
                "followers": target.get("followersCount"),
                "following": target.get("followsCount"),
                "posts": target.get("postsCount"),
            }

        seen.add(handle)
        if is_content_notification:
            seen_notification_posts.add(url)
        candidates.append({
            "source": source,
            "handle": handle,
            "url": url,
            "uri": raw_uri,
            "text": (text or "")[:220].replace("\n", " "),
            "kind": kind,
            "known_date": known.get(handle),
            "profile": profile_summary,
        })
        return True

    print("\n=== NOTIFICATIONS (reciprocidad - maxima prioridad, REFORZAR relacion existente) ===")
    notifications = b._get_notifications()
    notifications.sort(
        key=lambda item: 0 if item.get("reason") in ("reply", "mention", "quote") else 1
    )
    for n in notifications:
        reason = n["reason"]
        author = n["author"]["handle"]
        record = n.get("record", {}) or {}
        text = record.get("text", "") or f"({reason})"
        raw_uri = n.get("uri")
        if reason in ("reply", "mention", "quote"):
            emit(
                "notif:contenido",
                author,
                _post_url_from_uri(raw_uri, author),
                text,
                raw_uri=raw_uri,
            )
        elif reason in ("like", "repost", "follow"):
            emit("notif:reciprocidad_sin_contenido", author, None, text)

    print("\n=== DESCUBRIMIENTO (adaptativo: parar cuando ya hay material suficiente) ===")
    seed_pool = []

    def discovery_count():
        return sum(
            1 for item in candidates
            if not item["source"].startswith("notif:")
        )

    def add_posts(posts, source):
        for post in posts:
            url = _post_url(post)
            raw_uri = post.get("uri")
            author = post.get("author", {}).get("handle")
            text = (post.get("record", {}) or {}).get("text", "")
            if emit(source, author, url, text, raw_uri=raw_uri) and raw_uri:
                seed_pool.append((raw_uri, url))

    # Señal fuerte y barata: alguien enlazando la web propia.
    try:
        domain_posts = b._search_posts(
            "davidportodiaz.com", "all", limit=10,
            domain="davidportodiaz.com", sort="latest",
        )
    except b.RateLimitExceeded:
        raise
    except Exception as exc:
        print(f"AVISO búsqueda de dominio propio: {exc}")
        domain_posts = []
    add_posts(domain_posts, "domain:davidportodiaz.com")

    # Timeline antes de búsquedas abiertas: ya contiene afinidad previa.
    add_posts(b._get_timeline(), "timeline")

    def run_text_query(item):
        q, lang = item
        try:
            posts = b._search_posts(q, lang)
        except b.RateLimitExceeded:
            raise
        except Exception as exc:
            print(f"AVISO búsqueda {q!r}: {exc}")
            return
        _record_query_use("q", item)
        add_posts(posts, f"search:{q}")

    def run_tag_query(item):
        tag, q = item
        try:
            posts = b._search_posts(q, "es", tag=[tag], sort="latest")
        except b.RateLimitExceeded:
            raise
        except Exception as exc:
            print(f"AVISO tag #{tag}: {exc}")
            return
        _record_query_use("tag", item)
        add_posts(posts, f"tag:{tag}")

    # No hacer tres búsquedas por rutina. Abrir superficies solo si las
    # anteriores no han producido suficiente material revisable.
    if discovery_count() < DISCOVERY_SCAN_TARGET:
        for item in _pick_least_recent(QUERY_POOL, 1, "q"):
            run_text_query(item)
    if discovery_count() < DISCOVERY_SCAN_TARGET:
        for item in _pick_least_recent(TAG_QUERY_POOL, 1, "tag"):
            run_tag_query(item)
    if discovery_count() < DISCOVERY_SCAN_TARGET:
        for item in _pick_least_recent(QUERY_POOL, 1, "q"):
            run_text_query(item)

    print("\n=== COMENTARISTAS (solo 1 semilla; ampliar solo si falta material) ===")
    seed_n = 1 if discovery_count() >= DISCOVERY_SCAN_TARGET else 2
    seeds = _pick_seeds(seed_pool, n=seed_n)
    for uri, url in seeds:
        try:
            data = b._get(
                b.PUBLIC_BASE,
                "app.bsky.feed.getPostThread",
                {"uri": uri, "depth": 3},
                auth=False,
            )
        except b.RateLimitExceeded:
            raise
        except Exception as e:
            print(f"AVISO: no se pudo leer el hilo semilla {url}: {e}")
            continue
        thread = data.get("thread") if isinstance(data, dict) else None
        if not isinstance(thread, dict) or not isinstance(thread.get("post"), dict):
            print(f"AVISO: hilo semilla incompleto {url}; no registrar cooldown")
            continue
        sc.record_successful_seed(SEEDS_CSV, uri, id_field="uri")
        for reply in thread.get("replies", []) or []:
            rpost = reply.get("post", {})
            rauthor = rpost.get("author", {}).get("handle")
            rtext = (rpost.get("record", {}) or {}).get("text", "")
            emit(
                "comentaristas",
                rauthor,
                _post_url(rpost),
                rtext,
                raw_uri=rpost.get("uri"),
            )
    if seeds:
        print(
            "Semillas intentadas hoy (solo las descargadas entran en cooldown): "
            f"{[u for _, u in seeds]}"
        )

    print(f"\n=== CANDIDATOS FILTRADOS: {len(candidates)} (tras politica/dedupe) ===")
    by_kind = {}
    for item in candidates:
        kind = item["kind"]
        by_kind[kind] = by_kind.get(kind, 0) + 1
        known_tag = (
            f"[CONOCIDA fecha={item['known_date']}] "
            if item["known_date"] else "[NUEVA] "
        )
        print(
            f"{known_tag}sugerido={kind} | @{item['handle']} | "
            f"{item['source']} | {item['url'] or '(sin URL)'}"
        )
        print(f"   {item['text']}")

    print(f"\nResumen por kind sugerida: {by_kind}")
    print(
        "\nLa salida --json separa acciones mecánicas de los pocos casos "
        "que todavía necesitan criterio/texto."
    )
    return candidates


def prepare_for_ai(candidates):
    """Reducir la fase IA a excepciones, no a repasar toda la ronda.

    Likes de reciprocidad o de cuentas ya conocidas son acciones no textuales
    con suficiente contexto mecánico después de filtros/dedupe. Likes sobre
    descubrimiento nuevo, follows y cualquier reply/quote siguen en revisión.
    """
    auto_plan = []
    needs_ai = []
    for item in candidates or []:
        source = item["source"]
        known = bool(item.get("known_date"))
        if item["kind"] == "like" and (known or source.startswith("notif:")):
            auto_plan.append({
                "handle": item["handle"],
                "kind": "like",
                "url": item["url"],
                "motivo": "reciprocidad" if source.startswith("notif:") else "relacion_conocida",
            })
            continue
        needs_ai.append({
            key: item.get(key)
            for key in (
                "handle", "kind", "url", "text", "source", "known_date", "profile"
            )
        })
    return {
        "auto_plan": auto_plan,
        "needs_ai": needs_ai,
        "counts": {
            "candidates": len(candidates or []),
            "auto": len(auto_plan),
            "needs_ai": len(needs_ai),
        },
    }


def _post_url_from_uri(uri, author):
    """Convertir notificación ATProto en permalink para registro anti-duplicados."""
    if not uri or not author:
        return None
    parts = uri.split("/")
    if not uri.startswith("at://") or len(parts) < 5 or parts[-2] != "app.bsky.feed.post":
        return None
    rkey = parts[-1]
    if not rkey or "/" in author:
        return None
    return f"https://bsky.app/profile/{author}/post/{rkey}"


if __name__ == "__main__":
    json_mode = "--json" in sys.argv
    try:
        if json_mode:
            # El runner diario no necesita leer el log completo. Conservamos
            # únicamente avisos accionables para que compactar stdout no oculte
            # fallos parciales de discovery.
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                result = scan()
            payload = prepare_for_ai(result)
            payload["issues"] = [
                line.strip()
                for line in buffer.getvalue().splitlines()
                if line.strip().startswith("AVISO")
            ]
            print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        else:
            scan()
    except Exception as exc:
        if json_mode:
            print(json.dumps(
                {"error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
                separators=(",", ":"),
            ))
        else:
            print(str(exc))
        sys.exit(2)

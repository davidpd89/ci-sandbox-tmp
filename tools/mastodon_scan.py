"""
LEGACY / DIAGNÓSTICO COMPACTO.

El flujo diario ampliado usa `tools/mastodon_growth_flow.py prepare`; este scanner
se conserva para consultas rápidas y pruebas de compatibilidad.

Fase 1 del pipeline diario de Mastodon (22/09, ampliado 24/09). Hasta el
23/09 MASTODON.md seccion 13.3 prohibia automatizar follow/favorito/boost,
asi que este scan solo buscaba conversaciones para responder. A peticion
explicita de David (24/09): esa prohibicion no venia de ningun riesgo real
de deteccion de bots de mastodon.social (a diferencia de TikTok/Instagram/
Pinterest, que si han mostrado friccion real) - se retiro, y ahora este scan
tambien sugiere follow/favourite mecanicamente, igual que el resto de redes.

Fuentes:
- Notificaciones con contenido (reciprocidad, maxima prioridad) - reply/
  favorito/boost sobre algo que publicamos.
- Notificaciones de follow SIN contenido ("X te siguio") - anadido 24/09,
  antes invisibles para el scan (ver get_follow_notifications_data en
  mastodon_interact.py) - se sugiere follow de vuelta.
- 5 hashtags del pool diario (rotan por dia del año igual que
  bluesky_scan.py) sobre el listado con actividad real confirmada en la
  investigacion (MASTODON.md seccion 7.1) mas 3 temas añadidos el 24/09.

Sugerencia mecanica de kind (igual que las otras 8 redes): "reply" si el
texto invita a conversar (scan_common.invites_conversation), si no
"favourite" (accion barata, igual que "like" en el resto) - la decision fina
de cuando ademas seguir a la cuenta la toma Claude en la fase 2, no el scan.

Filtrado: descarta nuestro propio handle, cuentas descartadas
(scan_common.discarded_handles), contenido politico, dedupe por handle,
marca [CONOCIDA fecha=...]/[NUEVA] contra registro_interacciones.csv.

Uso:
    python tools/mastodon_scan.py
"""
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import mastodon_interact as m
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_MASTODON")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")

HASHTAG_POOL = [
    "Libros", "Literatura", "Lectura", "LiteraturaFantastica",
    "Escritura", "ClubDeLectura", "Bibliotecas", "Novela", "FantasiaEpica",
    # comunidades amplias con actividad reciente en Mastodon:
    "Bookstodon", "Books", "Reading", "WritingCommunity", "Fantasy",
]

SEARCH_POOL = [
    "fantasía juvenil",
    "romantasy",
    "novela fantástica",
    "club de lectura",
    "recomendación libros",
]

NICHE_TREND_HINTS = (
    "book", "read", "writ", "fant", "liter", "novel",
    "libro", "lect", "escrit",
)


def _rotate_hashtags(n=5):
    day = datetime.date.today().timetuple().tm_yday
    return [HASHTAG_POOL[(day + i) % len(HASHTAG_POOL)] for i in range(n)]


def _rotate_searches(n=2):
    day = datetime.date.today().timetuple().tm_yday
    return [SEARCH_POOL[(day + i) % len(SEARCH_POOL)] for i in range(n)]


_suggest_kind = lambda *a, **k: sc.downgrade_for_opinion(_suggest_kind_raw(*a, **k), a[0], 'favourite')


def _suggest_kind_raw(text):
    return "reply" if sc.invites_conversation(text) else "favourite"


def _handle_from_url(url):
    if not url:
        return None
    match = re.search(r"/@([^/]+)/\d+$", url)
    return match.group(1) if match else None


def scan():
    known = {h.casefold(): fecha for h, fecha in sc.known_accounts(REGISTRO_CSV).items()}
    discarded = {h.casefold() for h in sc.discarded_handles(REGISTRO_CSV)}
    own_handles = {m.HANDLE.casefold(), f"{m.HANDLE}@mastodon.social".casefold()}
    seen = set(own_handles)
    candidates = []  # (source, handle, url, text, kind)

    def emit_status(source, status):
        account = status.get("account") or {}
        handle = str(account.get("acct") or "").casefold()
        url = status.get("url") or status.get("uri")
        text = m._plain_text(status.get("content", ""))
        if not handle or handle in seen or handle in discarded or handle in own_handles:
            return False
        if not url or sc.is_political(text):
            return False
        seen.add(handle)
        candidates.append((
            source, handle, url,
            text[:200].replace("\n", " "), _suggest_kind(text),
        ))
        return True

    print("=== HEALTH ===")
    m.health()

    print("\n=== NOTIFICACIONES CON CONTENIDO (reciprocidad - maxima prioridad) ===")
    # BUG REAL encontrado en vivo el 24/09 al migrar a la API: en una
    # notificacion de tipo "favourite"/"reblog", el "status" que devuelve la
    # API es NUESTRO PROPIO post (el que marcaron/impulsaron) - correcto como
    # dato, pero tratarlo como candidato de "reply" haria que respondieramos
    # a nuestro propio post. Solo "mention" (alguien nos escribio de verdad)
    # es un candidato de contenido real; favourite/reblog son reciprocidad
    # SIN contenido nuevo, igual que un follow - se juntan en el mismo cubo.
    reciprocidad_sin_contenido = set()
    for url, text, handle, ntype in m.get_notifications_data():
        print("---", ntype, "por", handle)
        print("URL:", url)
        print(text[:200])
        handle = (handle or "").casefold()
        if not handle or handle in seen or handle in discarded or handle in own_handles:
            continue
        if ntype != "mention":
            reciprocidad_sin_contenido.add(handle)
            continue
        seen.add(handle)
        if sc.is_political(text):
            continue
        candidates.append(("notificaciones", handle, url, text[:200].replace("\n", " "), _suggest_kind(text)))

    print("\n=== NOTIFICACIONES DE FOLLOW/FAVORITO/BOOST SIN CONTENIDO (devolver el gesto) ===")
    reciprocidad_sin_contenido.update(m.get_follow_notifications_data())
    for handle in reciprocidad_sin_contenido:
        print("-", handle)
        handle = (handle or "").casefold()
        if handle in seen or handle in discarded or handle in own_handles:
            continue
        seen.add(handle)
        candidates.append(("notif:reciprocidad_sin_contenido", handle, None, "(follow)", "follow"))

    # Señal de máxima afinidad después de notificaciones: alguien que ya
    # enlaza contenido del autor, aunque no haya mencionado la cuenta.
    try:
        data = m.search("autorademodiaz.com", "statuses", limit=20)
        for status in data.get("statuses", []):
            emit_status("search:autorademodiaz.com", status)
    except Exception as exc:
        print(f"AVISO search dominio propio: {exc}")

    hashtags_hoy = _rotate_hashtags()
    print(f"\n=== HASHTAGS DEL DIA: {hashtags_hoy} ===")
    for tag in hashtags_hoy:
        try:
            statuses = m.get_hashtag_statuses(tag)
        except Exception as exc:
            print(f"AVISO hashtag #{tag}: {exc}")
            continue
        for status in statuses:
            emit_status(f"hashtag:{tag}", status)

    # Consulta combinada: el hashtag base debe coexistir con alguno de estos
    # términos, reduciendo ruido de etiquetas globales muy amplias.
    try:
        for status in m.get_hashtag_statuses(
                "Bookstodon", limit=20,
                any_tags=["Fantasy", "Books", "Reading"]):
            emit_status("hashtag:Bookstodon+(Fantasy|Books|Reading)", status)
    except Exception as exc:
        print(f"AVISO hashtag combinado: {exc}")

    print("\n=== TENDENCIAS DE NICHO (máx. 2) ===")
    try:
        trend_names = []
        for tag in m.trending_tags(20):
            name = str(tag.get("name") or "")
            folded = name.casefold()
            if name and any(hint in folded for hint in NICHE_TREND_HINTS):
                if folded not in {x.casefold() for x in hashtags_hoy}:
                    trend_names.append(name)
            if len(trend_names) >= 2:
                break
        for tag in trend_names:
            for status in m.get_hashtag_statuses(tag, limit=12):
                emit_status(f"trend:{tag}", status)
    except Exception as exc:
        print(f"AVISO tendencias: {exc}")

    searches = _rotate_searches()
    print(f"\n=== BUSQUEDA STATUS: {searches} ===")
    for query in searches:
        try:
            data = m.search(query, "statuses", limit=20)
        except Exception as exc:
            # La búsqueda de statuses depende del backend de índice de la
            # instancia. No perder hashtags/notificaciones si ese backend falla.
            print(f"AVISO search {query!r}: {exc}")
            continue
        for status in data.get("statuses", []):
            emit_status(f"search:{query}", status)

    print(f"\n=== CANDIDATOS FILTRADOS: {len(candidates)} (tras politica/dedupe/descartados) ===")
    for source, handle, url, text, kind in candidates:
        known_tag = f"[CONOCIDA fecha={known[handle]}] " if handle in known else "[NUEVA] "
        print(f"{known_tag}sugerido={kind} | @{handle} | {source} | {url}")
        print(f"   {text}")

    resumen = {}
    for *_ , kind in candidates:
        resumen[kind] = resumen.get(kind, 0) + 1
    print(f"\nResumen por kind sugerida: {resumen}")
    print(
        "\nRecordatorio: reply/favourite/follow/boost son acciones sobre API "
        "oficial. Quote, poll y post original existen en el ejecutor, pero no nacen "
        "mecánicamente del scan: requieren una decisión editorial."
    )


if __name__ == "__main__":
    try:
        scan()
    except m.BotWarningDetected as e:
        print(str(e))
        sys.exit(2)
    except m.WrongAccountActive as e:
        print(str(e))
        sys.exit(2)

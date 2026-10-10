"""
Fase 1 del pipeline diario de Instagram (22/09, ampliado el mismo dia tras
un aviso real de David: la primera version solo miraba notifications+feed
y encontro demasiado poco - "es ridiculo" que Instagram no encuentre nada
un dia cualquiera). Mismo patron que `tools/x_scan.py`/`threads_scan.py`:
una conexion, recoge todo, filtra automaticamente antes de que Claude lea
nada, saca una lista corta de candidatos.

Fuentes:
- notifications (panel de campana - reciprocidad y sugerencias por
  conexion mutua, texto crudo porque el DOM no es tan estructurado como en
  X/Threads).
- feed "Para ti" (via `_extract_posts`, estructurado: handle + permalink +
  texto por post), con un scroll extra antes de leer para no quedarse solo
  con los 3-4 posts que cargan de entrada.
- **busqueda de cuentas por tema** (via `_search_accounts`, NUEVO): la
  pieza que faltaba. Confirmado en vivo el 22/09 que la barra de Buscar de
  Instagram, con una consulta tematica (no un nombre de cuenta), devuelve
  handle + bio + senal de conexion mutua directamente - mucho mas rico que
  el feed. Consultas ya validadas en vivo abajo (`QUERY_POOL`), rotan por
  dia del anio. Tambien expone un aviso real util para filtrar solo:
  "contenido generado con ia".

La busqueda por HASHTAG (`explore/tags/`, distinta de la busqueda de
cuentas de arriba) se queda fuera del scan a proposito: confirmado en vivo
que el grid de un hashtag da posts pero NO el handle de la cuenta sin abrir
cada uno por separado - mal encaje para un pipeline de bajo consumo. Sigue
disponible como `instagram_interact.py explore <tag>` para uso manual, y
el hallazgo esta anotado en `RADAR.md`.

Filtrado automatico: descarta nuestro propio handle, contenido politico
(heuristico, `scan_common.py`), cuentas marcadas por Instagram como
"contenido generado con IA", y marca [NUEVA]/[CONOCIDA fecha=...] contra
registro_interacciones.csv.

Las consultas de `TRIAL_QUERY_POOL` son solo un experimento de descubrimiento:
se ejecuta una por sesión y se mide cuántos perfiles superan los filtros
automáticos, pero sus resultados **no entran en la cola operativa de
candidatos**. Una ratio de "elegibles" no equivale a calidad editorial ni
promueve automáticamente una consulta.

Uso:
    python tools/instagram_scan.py
"""
import csv
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import instagram_interact as ig
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_INSTAGRAM")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
QUERY_TRIALS_CSV = os.path.join(ROOT, "query_trials.csv")

# Validadas en vivo el 22/09 (ver diario) - dan cuentas reales y afines
# (autores de fantasia, clubes de lectura de fantasia). Descartadas de la
# lista original de RADAR.md por dar ruido: "fantasia juvenil española"
# (trae instituciones genericas por "española") y "portal fantasy" (mezcla
# demasiado contenido en ingles no afin).
# Las 3 consultas originales están comprobadas en vivo en RADAR.md (22/09).
QUERY_POOL = [
    "bookstagram España",
    "club de lectura fantasia",
    "autores españoles fantasia",
]

# Banco de RADAR.md aún NO validado en vivo. Se prueba UNA consulta por
# sesión, sin sustituir las dos fuentes cuya calidad sí está documentada.
TRIAL_QUERY_POOL = [
    "libros de fantasía en español",
    "lectura juvenil Madrid",
    "libros con memoria familiar",
    "objetos heredados historia",
    "escritura creativa España",
    "feria del libro",
    "bibliotecas Madrid",
]


# Instagram usa mas de una redaccion para el mismo aviso segun el contexto
# (perfil vs. post individual) - confirmado en vivo el 22/09: la busqueda
# de cuentas da "Perfil con contenido generado con IA", pero el mismo
# aviso en un post del feed aparece solo como "Contenido de IA". Cubrir
# las dos variantes conocidas, no solo la primera vista.
AI_CONTENT_SIGNALS = ("contenido generado con ia", "contenido de ia")


def _rotate_queries(n=2):
    """Dos consultas validadas + una experimental, sin sustituir las primeras."""
    if not QUERY_POOL or not TRIAL_QUERY_POOL:
        raise RuntimeError("Los pools de consultas no pueden estar vacíos")
    n = max(0, min(int(n), len(QUERY_POOL)))
    day = datetime.date.today().timetuple().tm_yday
    verified = [QUERY_POOL[(day + i) % len(QUERY_POOL)] for i in range(n)]
    import hashtag_query_consumers as hqc
    # Las etiquetas son consultas de prueba de cuentas, no tags verificados.
    def vocabulary(network, kind):
        from discovery_terms import terms
        values = terms(network, kind)
        if kind == "busquedas":
            values += terms(network, "hashtags")
        return values
    # Tick de seis horas: una cuota unitaria no debe omitir un snapshot
    # que expira antes de la siguiente rotación diaria.
    trial_tick = day * 4 + datetime.datetime.now().hour // 6
    trial = hqc.select("instagram", "busquedas", TRIAL_QUERY_POOL,
                       budget=1, tick=trial_tick, reader=vocabulary)[0]
    return [(q, "validada") for q in verified] + [(trial, "prueba_no_validada")]


def _record_trial_result(path, query, discovered, eligible, *, date=None):
    """Guarda evidencia de una consulta experimental; nunca la promociona sola."""
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
            writer.writerow(["fecha", "query", "descubiertas", "elegibles"])
        writer.writerow([when, query, discovered, eligible])


def _trial_summary(path, query):
    """Última medición por día válido; tolera el encabezado legado 'aceptadas'."""
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
                    discovered = max(0, int(row.get("descubiertas", 0)))
                    raw_eligible = row.get("elegibles")
                    if raw_eligible is None:
                        raw_eligible = row.get("aceptadas", 0)
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


def _eligible_candidate(handle, text, *, my_handle, discarded):
    """Calidad intrínseca del resultado, independiente del dedupe entre fuentes."""
    handle = (handle or "").strip().lstrip("@").casefold()
    text = (text or "").strip()
    if not handle or not text:
        return False
    if not sc.is_valid_candidate(handle, text, my_handle, discarded):
        return False
    if any(sig in text.casefold() for sig in AI_CONTENT_SIGNALS):
        return False
    return True


def _process_query_results(
    discovered,
    *,
    my_handle,
    discarded,
    operational,
    emit=None,
    source=None,
):
    """Mide una búsqueda y solo emite candidatos si es una fuente validada."""
    rows = list(discovered)
    eligible_rows = [
        (handle, text)
        for handle, text in rows
        if _eligible_candidate(
            handle,
            text,
            my_handle=my_handle,
            discarded=discarded,
        )
    ]

    novel = 0
    if operational:
        if emit is None or not source:
            raise ValueError("Una consulta operativa necesita emit y source")
        novel = sum(
            bool(emit(source, handle, text))
            for handle, text in eligible_rows
        )

    return {
        "discovered": len(rows),
        "eligible": len(eligible_rows),
        "novel": novel,
        "eligible_rows": eligible_rows,
    }


def _previously_commented_urls(registro_csv):
    return {
        url.rstrip("/")
        for url in sc.already_interacted_urls(registro_csv)
        if url
    }

def _candidate_key(handle, permalink, text):
    """Deduplica posts por URL; las búsquedas de cuentas siguen siendo por handle."""
    if permalink:
        return ("post", permalink.rstrip("/"))
    return ("account", (handle or "").strip().lstrip("@").casefold())


def scan():
    # BUG REAL encontrado en vivo el 29/09 (introducido por la PR #27,
    # "Auditoria: preflight transaccional...", fusionada el mismo dia): esta
    # funcion _candidate_key quedo insertada A MITAD del cuerpo de scan(),
    # sin cerrar scan() antes ni volver a abrirlo despues. Python no lo
    # marca como error de sintaxis - queda como codigo valido pero MUERTO,
    # atrapado dentro de _candidate_key tras su primer return, asi que
    # scan() en la practica se reducia a una sola linea (calcular `known` y
    # nada mas): no conectaba con el navegador, no imprimia nada, no
    # escaneaba nada, y salia con exit code 0 como si todo hubiera ido bien
    # - el peor tipo de fallo silencioso, indistinguible de "hoy no hay
    # candidatos" sin leer el codigo fuente. _candidate_key movida arriba
    # como funcion propia; el resto de este cuerpo, restaurado continuo.
    ig._refuse_if_paused()
    known = {h.casefold(): fecha for h, fecha in sc.known_accounts(REGISTRO_CSV).items()}
    discarded = {h.casefold() for h in sc.discarded_handles(REGISTRO_CSV)}
    previously_commented = _previously_commented_urls(REGISTRO_CSV)
    seen = set()
    candidates = []  # (source, handle, text)

    p, pg = ig._connect()
    try:
        print("=== HEALTH ===")
        ok, msg = ig._health_check(pg)
        print(msg)
        if not ok:
            print("\nParando aqui - resolver esto antes de nada mas.")
            return

        print("\n=== NOTIFICATIONS (reciprocidad + sugerencias por conexion mutua) ===")
        ig._dump_notifications(pg)

        def emit(source, handle, text, permalink=None):
            handle = (handle or "").strip().lstrip("@").casefold()
            key = _candidate_key(handle, permalink, text)
            if key in seen:
                return False
            if permalink and permalink.rstrip("/") in previously_commented:
                return False
            if not _eligible_candidate(
                handle, text, my_handle=ig.MY_HANDLE.casefold(),
                discarded=discarded,
            ):
                return False
            # Una coincidencia descartada en feed no debe ocultar un post
            # posterior del mismo autor que sí supere los filtros.
            seen.add(key)
            # kind sugerida (23/09, mismo criterio de x_scan.py): con
            # permalink real se puede sugerir like/comment (comment si el
            # texto invita a conversacion, heuristico compartido en
            # scan_common); sin el (caso de busqueda de cuentas, que no da
            # un post concreto), solo follow.
            if not permalink:
                kind = "follow"
            elif sc.invites_conversation(text) and not sc.asks_for_opinion(text):
                kind = "comment"
            else:
                kind = "like"
            candidates.append((source, handle, (text or "")[:160].replace("\n", " "), permalink, kind))
            return True

        print("\n=== RECOLECTANDO CANDIDATOS (feed) ===")
        pg.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(2000)
        ig._jittery_scroll(pg, "down")
        ig._jittery_scroll(pg, "down")
        for handle, permalink, text in ig._extract_posts(pg, limit=15):
            # BUG REAL corregido 23/09: el permalink ya venia de
            # _extract_posts pero se descartaba aqui sin usarlo - un
            # candidato de "feed" nunca podia convertirse en like/comment
            # real en plan.json sin ir a buscar el permalink a mano.
            emit("feed", handle, text, permalink)

        for q, verification in _rotate_queries():
            operational = verification == "validada"
            label = "OPERATIVA" if operational else "TRIAL SOLO MEDICIÓN"
            print(f"\n=== BUSQUEDA {label}: {q!r} ===")
            discovered = ig._search_accounts(pg, q)
            stats_run = _process_query_results(
                discovered,
                my_handle=ig.MY_HANDLE.casefold(),
                discarded=discarded,
                operational=operational,
                emit=emit if operational else None,
                source=f"busqueda:{verification}:{q}" if operational else None,
            )
            print(
                f"CALIDAD {verification}: "
                f"{stats_run['eligible']}/{stats_run['discovered']} elegibles "
                f"por filtros automáticos; {stats_run['novel']} nuevas operativas "
                "tras dedupe."
            )

            if not operational:
                _record_trial_result(
                    QUERY_TRIALS_CSV,
                    q,
                    stats_run["discovered"],
                    stats_run["eligible"],
                )
                stats = _trial_summary(QUERY_TRIALS_CSV, q)
                rate = (
                    stats["eligible"] / stats["discovered"]
                    if stats["discovered"]
                    else 0.0
                )
                sample = ", ".join(
                    "@" + (handle or "").strip().lstrip("@").casefold()
                    for handle, _ in stats_run["eligible_rows"][:5]
                ) or "(ninguna)"
                print(
                    f"EVIDENCIA TRIAL: {stats['days']} día(s), "
                    f"{stats['eligible']}/{stats['discovered']} elegibles "
                    f"por filtros ({rate:.0%}). Muestra hoy: {sample}."
                )
                print(
                    "TRIAL NO OPERATIVO: estos perfiles NO entran en candidates, "
                    "NO consumen cupo de selección y NO se promocionan "
                    "automáticamente. Revisar calidad editorial humana tras >=3 días."
                )

        print(f"\n=== CANDIDATOS FILTRADOS: {len(candidates)} (tras politica/IA/dedupe) ===")
        by_kind = {}
        for source, handle, text, permalink, kind in candidates:
            by_kind[kind] = by_kind.get(kind, 0) + 1
            known_tag = f"[CONOCIDA fecha={known[handle]}] " if handle in known else "[NUEVA] "
            print(f"{known_tag}sugerido={kind} | @{handle} | {source} | {permalink or '(sin permalink - solo follow)'}")
            print(f"   {text}")
        print(f"\nResumen por kind sugerida: {by_kind}")
    finally:
        p.stop()


if __name__ == "__main__":
    try:
        ig.ensure_browser()
        scan()
    except ig.BotWarningDetected as e:
        print(str(e))
        sys.exit(2)

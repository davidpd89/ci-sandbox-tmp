"""
Fase 1 del pipeline diario de Reddit (22/09) - mismo patron que
`tools/x_scan.py`/`threads_scan.py`/`instagram_scan.py`/`bluesky_scan.py`,
adaptado a que aqui NO hay follows ni notifications (ver REGLAS.md: "no se
sigue a cuentas, se participa en comunidades") - la unica accion real es
`comment`, y la disciplina propia de esta red es "hasta 5 hilos leidos a
fondo por sesion, hasta 3 comentarios reales" (presupuesto de calidad, no
cuota).

Fuentes: los dos subreddits ya mapeados y con normas confirmadas en
`COMUNIDADES.md` (hoy r/libros y r/filosofia_en_espanol), via `_extract_threads` (atributos
reales de `<shreddit-post>`, sin parsear texto). NO incluye busqueda
todavia - el banco de `RADAR.md` sigue sin validar en vivo, mejor no
automatizar consultas que nadie ha confirmado que den resultado real.

Filtrado automatico: descarta contenido politico (heuristico,
`scan_common.py`), cruza el historial por identidad canónica `(subreddit, ID)` del
hilo, no por slug literal ni por autor. Así un cambio de título/slug no resucita como
nuevo un hilo ya comentado.

Uso:
    python tools/reddit_scan.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import reddit_interact as r
import scan_common as sc
import unicodedata

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_REDDIT")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")

# Solo comunidades ya mapeadas y con normas revisadas en COMUNIDADES.md -
# anadir aqui solo tras verificar una nueva en vivo (misma disciplina que
# CUENTAS_VIGILAR.md de X, nunca dar una comunidad por buena sin comprobarla).
# Nuevo scope (03/10, decision de David): Reddit solo para (a) preguntas propias de
# opinion/lista corta ("tres poetas favoritos") y (b) responder con microrrespuestas
# (1-5 palabras, sin justificar) en hilos de ese mismo tipo. r/escribir sale: alli
# piden opiniones desarrolladas y una microrrespuesta seria mala educacion.
# r/filosofia_en_espanol: pendiente de leer sus normas en vivo antes del primer
# comentario (ver COMUNIDADES.md).
SUBREDDITS = ["libros", "filosofia_en_espanol"]


def _discovery_sources(today=None, reader=None, round_index=None):
    """Dos lecturas por ronda; búsqueda léxica en la mitad de los turnos."""
    import hashtag_query_consumers as hqc
    today = today or datetime.date.today()
    # Alternar por ronda (no por día): cuatro franjas de seis horas.
    round_index = datetime.datetime.now().hour // 6 if round_index is None else int(round_index)
    tick = today.toordinal() * 4 + round_index
    _, terms = hqc.combine("reddit", "busquedas", [], reader=reader)
    if not terms or tick % 2 == 0:
        return [("subreddit", name) for name in SUBREDDITS]
    return [("subreddit", SUBREDDITS[(tick // 2) % len(SUBREDDITS)]),
            ("search", terms[(tick // 2) % len(terms)])]

_QUESTION_STARTS = ("cual", "cuales", "que ", "quien", "quienes", "como ", "donde", "cuando",
                    "por que", "cuanto", "recomend", "alguien", "algun")


def is_short_answer_thread(title):
    """Hilos de pregunta/lista cuya respuesta natural es corta ("Escribir.",
    tres nombres). Descarta peticiones de opinion sobre trabajo propio."""
    if sc.asks_for_opinion(title):
        return False
    folded = "".join(ch for ch in unicodedata.normalize("NFD", (title or "").lower().strip("¿¡ "))
                     if unicodedata.category(ch) != "Mn")
    return "?" in title or "¿" in title or folded.startswith(_QUESTION_STARTS)


def _thread_key(url):
    """Identidad canónica compartida con la capa de escritura."""
    try:
        return r._thread_identity(url)
    except (TypeError, ValueError):
        return None


def _thread_history():
    """Separa identidades confirmadas de inciertas; nunca por URL literal."""
    confirmed, uncertain = set(), set()
    if not os.path.exists(REGISTRO_CSV):
        return confirmed, uncertain
    import csv
    with open(REGISTRO_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("tipo") or "").strip().casefold() not in (
                "comentario", "comment", "reply", "respuesta"
            ):
                continue
            url = (row.get("hilo_url") or "").strip()
            key = _thread_key(url)
            if key is None:
                continue
            outcome = (row.get("resultado") or "").strip().casefold()
            if outcome in ("confirmado", "publicado"):
                confirmed.add(key)
                uncertain.discard(key)
            elif key not in confirmed:
                uncertain.add(key)
    return confirmed, uncertain


def _known_threads():
    """Compatibilidad: solo hilos cuyo comentario está explícitamente confirmado."""
    return _thread_history()[0]


def _uncertain_threads():
    """Hilos con alguna fila de comentario no confirmada y sin confirmación posterior."""
    return _thread_history()[1]


def scan():
    known, uncertain = _thread_history()
    candidates = []  # (subreddit, title, url, comment_count, score)

    p, pg = r._connect()
    try:
        print("=== HEALTH ===")
        ok, msg = r._health_check(pg)
        print(msg)
        if not ok:
            print("\nParando aqui - resolver esto antes de nada mas.")
            return

        for source, name in _discovery_sources():
            print(f"\n=== RECOLECTANDO CANDIDATOS (r/{name}) ===")
            if source == "subreddit":
                r._dump_subreddit(pg, name, "hot")
            else:
                r._dump_search(pg, name)
            for t in r._extract_threads(pg, limit=15):
                if sc.is_political(t["title"]):
                    continue
                key = _thread_key(t.get("url"))
                if key is None:
                    print(f"OMITIDO: permalink de hilo no validable: {t.get('url')!r}")
                    continue
                candidates.append({**t, "_thread_key": key})

        # Hilos con conversacion real primero (REGLAS.md: "Reddit
        # recompensa conocer la conversacion, no responder a toda
        # coincidencia lexica") - ordenar por comment_count no decide solo,
        # pero ayuda a leer primero donde ya hay algo vivo que aportar.
        candidates.sort(key=lambda t: t["comment_count"], reverse=True)

        print(f"\n=== CANDIDATOS FILTRADOS: {len(candidates)} (tras politica) ===")
        for t in candidates:
            key = t["_thread_key"]
            if key in known:
                history_tag = "[YA COMENTADO] "
            elif key in uncertain:
                history_tag = "[REVISAR HISTORIAL — NO REINTENTAR] "
            else:
                history_tag = "[NUEVO] "
            print(f"{history_tag}{t['subreddit']} | {t['comment_count']} comentarios | score {t['score']}")
            print(f"   {t['title']}")
            print("   [RESPUESTA: 1-5 palabras, sin justificar, sin pregunta ni enlace]")
            print(f"   {t['url']}")
    finally:
        p.stop()


if __name__ == "__main__":
    try:
        r.ensure_browser()
        scan()
    except r.BotWarningDetected as e:
        print(str(e))
        sys.exit(2)

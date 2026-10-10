"""Pinterest: interaccion humana y gradual por navegador (04/10/2026, David: "Pinterest podemos interactuar, montalo").

El 03/10 se dejo Pinterest sin interaccion por una conclusion mia (la API v5 no tiene comentarios), no por decision de David.
La API no hace falta: se opera como una persona en el Edge del 9223 (cuenta autorademodiaz, sesion abierta).

Acciones (de menos a mas riesgo; por ahora sin comentarios):
  - react   : "Reaccionar" (corazon) a pines en espanol del nicho.
  - save    : "Guardar" el pin en el tablero que le corresponde (fantasia / lugares literarios).
  - follow  : seguir a creadores pequenos en espanol cuyos pines son del nicho (cuenta nueva: hoy seguimos a 0).

Pipeline (cada paso escribe un JSON en SISTEMA_DIARIO_PINTEREST/):
    python tools/pinterest_growth.py scan                    # busquedas del dia -> pinterest_candidates.json (solo lectura)
    python tools/pinterest_growth.py plan [--follows 10 --saves 10 --reacts 15]   # -> pinterest_plan.json
    python tools/pinterest_growth.py run                     # ejecuta el plan con pausas humanas; para ante cualquier aviso

Reglas: nada de politica/ligue/sexo (`scan_common.is_political`), nada de tiendas/afiliados, solo contenido en espanol,
un pin por autor y accion, lo ya hecho (registro) no se repite, pausas 20-50 s, un solo Playwright en el Edge (turno `browser_session`).
"""
import csv
import datetime
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_PINTEREST")
CANDIDATES_JSON = os.path.join(ROOT, "pinterest_candidates.json")
PLAN_JSON = os.path.join(ROOT, "pinterest_plan.json")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
METRICAS_CSV = os.path.join(ROOT, "metricas.csv")
ESTADO_MD = os.path.join(ROOT, "ESTADO.md")

CDP_URL = "http://127.0.0.1:9223"
MY_HANDLE = "autorademodiaz"
BASE = "https://es.pinterest.com"

FANTASY = "Fantasía juvenil española"
PLACES = "Lugares literarios, bibliotecas y librerías"
WRITERS = "Recursos para escritores"
READING = "Lecturas y reseñas de libros"
# 06/10 (David: «informate bien y ajusta los tableros, asignalos bien»): el tablero lo decide el CONTENIDO del pin (`board_for`), no la consulta que lo encontro. Segun las guias de 2026 el
# Pinterest recomienda palabras clave relevantes en el titulo y la descripcion del Pin y del tablero (no publica ponderaciones; el «20 %» que habia aqui era una suposicion): nombres claros y buscables, no creativos. Los tableros nuevos se crean con
# `pinterest_boards.py` (nombre + descripcion con palabras clave).
BOARD_RULES = [      # (tablero, patron sobre titulo+descripcion del pin); gana el primero que case
    (PLACES, re.compile(r"(biblioteca|librer[ií]a|rinc[oó]n de lectura|estanter[ií]a|lugares? literari|caf[eé] literari|sala de lectura)", re.I)),
    (WRITERS, re.compile(r"(escribir|escritura|escritor|manuscrito|worldbuilding|construcci[oó]n de mundos|personajes|trama|narrador|bloqueo|corrector|edici[oó]n de|autopublic)", re.I)),
    (FANTASY, re.compile(r"(fantas[ií]a|fantas[ií]|saga|drag[oó]n|dragones|magia|[eé]pic|romantasy|juvenil|elfos?|portal)", re.I)),
    (READING, re.compile(r"(rese[ñn]a|lectura|libros?|leer|novela|club de lectura|reto de lectura|recomendaci)", re.I)),
]


def board_for(text, fallback=None):
    for board, pattern in BOARD_RULES:
        if pattern.search(text or ""):
            return board
    return fallback


QUERY_POOL = [      # 06/10 (GPT, intencion de busqueda): ~75 % consultas de descubrimiento/recomendacion del nicho + ~25 % de exploracion (inspiracion visual y escritura)
    ("libros de fantasía", None), ("libros de fantasía juvenil", None), ("libros de fantasía en español", None), ("libros de fantasía recomendados", None), ("novelas de fantasía", None),
    ("novelas de fantasía juvenil", None), ("libros de magia", None), ("sagas de fantasía", None), ("libros parecidos a Harry Potter", None), ("libros para adolescentes", None),
    ("libros juveniles recomendados", None), ("libros que tienes que leer", None), ("recomendaciones de libros", None), ("qué libro leer", None), ("lista de libros para leer", None),
    ("reto de lectura", None), ("tbr libros", None), ("reseñas de libros", None), ("libros españoles", None), ("autores de fantasía españoles", None), ("fantasía española", None),
    ("mundos de fantasía", None), ("mapas de fantasía", None), ("worldbuilding", None), ("construcción de mundos", None),
    ("escritura creativa", None), ("consejos para escritores", None), ("consejos para escribir una novela", None), ("cómo escribir un libro", None), ("cómo crear personajes de fantasía", None),
    ("bloqueo del escritor", None), ("rutina de escritura", None), ("inspiración para escritores", None),
    ("rincón de lectura", None), ("bibliotecas bonitas", None), ("club de lectura", None), ("frases de libros", None),
]
import discovery_terms
QUERY_POOL += [(q, None) for q in discovery_terms.terms("pinterest", "busquedas", skip=[q for q, _ in QUERY_POOL])]      # 07/10: consulta M a GPT (tableros grupales/colaborativos, estetica de lectura, escritura)
# #125: ampliar intención lectora conservando el pool, su rotación y cuotas.
import pinterest_niche
QUERY_POOL = pinterest_niche.merge_queries(QUERY_POOL)
QUERIES_PER_DAY = 8          # por RONDA (3 rondas al dia): rotan por dia y por ronda
PINS_PER_QUERY = 8
MAX_PROFILE_VISITS = 40
PENDING_TEXT = "(pendiente de ChatGPT)"      # 08/10: ya no hay banco de comentarios; los escribe ChatGPT (write_comments) y el ejecutor rechaza texto que no venga de ahi
BOARD_TOPIC = {FANTASY: "fantasia", PLACES: "lugares", WRITERS: "escritura", READING: "lectura"}
MAX_FOLLOWERS = 30000

SPANISH = re.compile(r"\b(el|la|los|las|de|del|que|y|en|un|una|por|con|para|mi|su|es|libros?|leer|lectur\w*|novela\w*|"
                     r"escrib\w*|fantas\w*|historias?|biblioteca\w*|librer\w*|consejos|ideas|sagas?)\b", re.I)
ENGLISH = re.compile(r"\b(the|and|of|to|is|my|for|with|you|your|books?|reading|best|top|ideas|tips)\b", re.I)
COMMERCIAL = re.compile(r"(amazon|temu|aliexpress|shein|comprar|oferta|descuento|cupon|cupón|rebajas|envío gratis|"
                        r"dropship|tienda|shop\b|store\b|affiliate|afiliad|pdf gratis|descarga gratis|drive\.google)", re.I)
NICHE = re.compile(r"(libro|lectur|leer|novela|fantas|saga|escrit|escribir|autor|biblioteca|librer|poes|relato|cuento|"
                   r"literari|narrativa|manuscrito|capitulo|capítulo|romantasy|fantasía romántica)", re.I)
BOT_SIGNALS = ["actividad inusual", "unusual activity", "verifica que eres", "verify you are", "tu cuenta ha sido",
               "cuenta suspendida", "account suspended", "has superado el límite", "try again later",
               "inténtalo de nuevo más tarde", "temporalmente bloquead", "temporarily blocked",
               "no puedes realizar esta acción", "demasiadas solicitudes"]


class BotWarningDetected(RuntimeError):
    pass


# ------------------------------------------------------------------------------------ funciones puras
def parse_followers(text):
    """'5 seguidores' -> 5; '1,2 mil seguidores' -> 1200; '10,5 mil' -> 10500; '2 M' -> 2.000.000; None si no hay."""
    match = re.search(r"(\d[\d.,]*)\s*(mil|k|m|millones)?\s*seguidores", (text or "").lower().replace("\xa0", " "))
    if not match:
        return None
    number, unit = match.groups()
    value = float(number.replace(".", "").replace(",", ".")) if "," in number else float(number.replace(".", ""))
    return int(value * (1_000_000 if unit in ("m", "millones") else 1000 if unit else 1))


def is_spanish(text):
    return len(SPANISH.findall(text or "")) >= 2 and len(SPANISH.findall(text or "")) > len(ENGLISH.findall(text or ""))


def pin_ok(title, description):
    """Un pin sirve para reaccionar/guardar: en espanol, del nicho, sin comercio ni politica/ligue."""
    text = f"{title} {description}"
    if sc.is_political(text) or COMMERCIAL.search(text):
        return False
    return is_spanish(text) and bool(NICHE.search(text))


def author_ok(handle, bio, followers, *, known=frozenset(), sample_text=""):
    """(ok, motivo) para seguir a un creador."""
    if not handle or handle.casefold() in known or handle.casefold() == MY_HANDLE:
        return False, "ya tratado"
    if followers is None or followers > MAX_FOLLOWERS:
        return False, f"seguidores={followers}"
    text = f"{bio} {sample_text}"
    if sc.is_political(text) or COMMERCIAL.search(text):
        return False, "comercial/politica/ligue"
    if not (is_spanish(text) or NICHE.search(bio or "")):
        return False, "no es en espanol/nicho"
    return True, ""


def day_queries(today=None, n=QUERIES_PER_DAY, round_index=0):
    """`n` consultas del pool que rotan por dia y por ronda (3 rondas/dia: cada una prueba consultas distintas)."""
    day = (today or datetime.date.today()).toordinal()
    return [QUERY_POOL[(day * n * 3 + round_index * n + i) % len(QUERY_POOL)] for i in range(n)]


def build_plan(candidates, max_follows=10, max_saves=10, max_reacts=15, max_comments=0, done_comments=frozenset(), rng=None):
    """Plan a partir de candidatos {pins:[...], authors:[...]}. Un pin y un autor una sola vez por accion."""
    plan, seen_pin_react, seen_pin_save, seen_follow, authors_used = [], set(), set(), set(), set()
    pins = [p for p in candidates.get("pins", []) if p.get("ok") and not p.get("done_react") ]
    for pin in pins:
        if len([a for a in plan if a["kind"] == "react"]) >= max_reacts:
            break
        if pin["url"] not in seen_pin_react:
            seen_pin_react.add(pin["url"])
            caption = f"{pin.get('title') or ''} {pin.get('desc') or ''}".strip()
            plan.append({"kind": "react", "url": pin["url"], "title": (pin.get("title") or "")[:80],
                         "post_text": caption[:600], "media_present": True})
    for pin in pins:
        if len([a for a in plan if a["kind"] == "save"]) >= max_saves:
            break
        author = (pin.get("author") or "").casefold()
        if pin.get("board") and not pin.get("done_save") and pin["url"] not in seen_pin_save and author not in authors_used:
            seen_pin_save.add(pin["url"])
            authors_used.add(author)
            plan.append({"kind": "save", "url": pin["url"], "board": pin["board"], "title": pin["title"][:80]})
    commented, used_texts, comment_authors = set(), set(), set()
    for pin in pins:       # comentarios: pins del nicho con tablero asignado, un comentario corto por pin y por autor
        if len(commented) >= max_comments:
            break
        author = (pin.get("author") or "").casefold()
        if pin["url"] in done_comments or pin["url"] in commented or not pin.get("board") or (author and author in comment_authors):
            continue
        text = PENDING_TEXT
        commented.add(pin["url"])
        comment_authors.add(author)
        plan.append({"kind": "comment", "url": pin["url"], "text": text, "title": pin["title"][:80], "desc": (pin.get("desc") or "")[:300], "author": pin.get("author") or ""})
    for author in sorted(candidates.get("authors", []), key=lambda a: -a.get("score", 0)):
        if len([a for a in plan if a["kind"] == "follow"]) >= max_follows:
            break
        handle = author["handle"]
        if handle.casefold() not in seen_follow:
            seen_follow.add(handle.casefold())
            plan.append({"kind": "follow", "handle": handle, "motivo": f"creador pequeno del nicho ({author.get('followers')} seguidores)"})
    return plan


def write_comments(plan, candidates=None, log=print):
    """08/10: los comentarios de Pinterest ya no salen de un banco: los escribe ChatGPT (cola de respuestas, sin esperar el navegador) a partir del titulo y la descripcion del pin.
    Un comentario sin texto escrito todavia se quita del plan y se hara en una ronda posterior (queda encolado). (Esta funcion faltaba: el plan fallaba con NameError.)"""
    pending = [a for a in plan if a.get("kind") == "comment"]
    if not pending:
        return plan
    got = {}
    try:
        import reply_queue
        items = []
        for action in pending:
            title = " ".join(str(action.get("title") or "").split())
            desc = " ".join(str(action.get("desc") or "").split())
            text = f"{title}. {desc}".strip(". ") if desc else title
            if len(re.findall(r"\w+", text)) < 4:
                continue                      # pin sin texto concreto al que responder
            items.append({"id": action["url"], "network": "pinterest", "author": action.get("author") or "", "text": text[:600],
                          "context": "pin de Pinterest: comentario muy breve sobre lo que dicen el titulo y la descripcion, sin suponer nada de la imagen"})
        got = reply_queue.get_or_enqueue(items, "pinterest", log) if items else {}
    except Exception as exc:
        log(f"[pinterest] comentarios sin escribir ({type(exc).__name__}: {str(exc)[:80]}): no se comenta esta ronda")
    out = []
    for action in plan:
        if action.get("kind") == "comment":
            written = got.get(action["url"])
            if not written:
                continue
            action = {**action, "text": written}
        out.append(action)
    return out


def done_comments(registro_csv=REGISTRO_CSV):
    """URLs de pines ya comentados (registro, tipo `comment`)."""
    out = set()
    if os.path.exists(registro_csv):
        with open(registro_csv, encoding="utf-8") as stream:
            for row in csv.reader(stream):
                if len(row) >= 6 and row[2] == "comment" and row[5] in ("confirmado", "ya_hecho"):
                    out.add(row[3])
    return out


def done_sets(registro_csv=REGISTRO_CSV):
    """(pines reaccionados, pines guardados, cuentas seguidas) segun el registro."""
    reacted, saved, followed = set(), set(), set()
    if os.path.exists(registro_csv):
        with open(registro_csv, encoding="utf-8") as stream:
            for row in csv.reader(stream):
                if len(row) < 6 or row[5] not in ("confirmado", "ya_hecho"):
                    continue
                kind, ref = row[2], row[3]
                if kind == "react":
                    reacted.add(ref)
                elif kind == "save":
                    saved.add(ref)
                elif kind == "follow":
                    followed.add(row[1].lstrip("@").casefold())
    return reacted, saved, followed


# --------------------------------------------------------------------------------------- navegador
def _connect():
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0]
    pg = ctx.new_page()   # pagina propia: no se toca ninguna pestana de otra red
    return p, pg


def _captcha_visible(pg):
    try:
        return bool(pg.evaluate("""() => {
          for (const el of document.querySelectorAll('[class*="captcha" i], [id*="captcha" i], iframe[src*="captcha" i], iframe[src*="recaptcha" i]')) {
            const r = el.getBoundingClientRect(), st = getComputedStyle(el);
            if (r.width >= 120 && r.height >= 60 && st.display !== 'none' && st.visibility !== 'hidden') return true;
          }
          return false; }"""))
    except Exception:
        return True


def _check_bot_warning(pg):
    if _captcha_visible(pg):
        raise BotWarningDetected("captcha/verificacion visible en Pinterest: parar (lo resuelve David, no se reintenta)")
    try:
        text = pg.inner_text("body").lower()
    except Exception as exc:
        raise BotWarningDetected("no se pudo leer la pantalla para comprobar avisos; parar") from exc
    for signal in BOT_SIGNALS:
        if signal in text:
            raise BotWarningDetected(f"aviso de Pinterest en pantalla: {signal!r}; parar y avisar a David")
    if "/login" in pg.url:
        raise BotWarningDetected(f"Pinterest pide iniciar sesion ({pg.url}); parar")


def _assert_account(pg):
    link = pg.locator('[data-test-id="header-profile"] a[href*="/autorademodiaz"], a[href="/autorademodiaz/"]')
    if link.count() == 0:
        raise BotWarningDetected("no se confirma la sesion de @autorademodiaz; parar")


def search_pins(pg, query, limit=PINS_PER_QUERY * 2):
    pg.goto(f"{BASE}/search/pins/?q={urllib.parse.quote(query)}", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(4500)
    _check_bot_warning(pg)
    _assert_account(pg)
    for _ in range(2):
        pg.mouse.wheel(0, 1400)
        pg.wait_for_timeout(1500)
    rows = pg.eval_on_selector_all(
        'a[href*="/pin/"]', "els => els.map(e => [e.getAttribute('href'), e.getAttribute('aria-label') || ''])")
    out, seen = [], set()
    for href, label in rows:
        match = re.match(r"^/pin/(\d+)/?", href or "")
        if not match or match.group(1) in seen:
            continue
        seen.add(match.group(1))
        out.append({"url": f"{BASE}/pin/{match.group(1)}/", "title": re.sub(r"^Página del Pin\s*", "", label).strip()})
        if len(out) >= limit:
            break
    return out


def pin_details(pg, url):
    pg.goto(url, wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_timeout(3500)
    _check_bot_warning(pg)
    info = pg.evaluate("""() => {
      const body = document.querySelector('[data-test-id="closeup-body"]') || document.body;
      const author = [...body.querySelectorAll('a[href^="/"]')].map(a => a.getAttribute('href'))
          .find(h => /^\\/[A-Za-z0-9_.-]+\\/$/.test(h) && !/^\\/(pin|search|ideas|today|business)\\//.test(h));
      const desc = document.querySelector('[data-test-id="description-content-container"]');
      const title = document.querySelector('h1');
      const react = document.querySelector('[data-test-id="react-button"]');
      return {author: author || null, title: title ? title.innerText : '', desc: desc ? desc.innerText : '',
              reacted: react ? react.getAttribute('aria-pressed') === 'true' : null,
              saved: [...document.querySelectorAll('button')].some(b => (b.getAttribute('aria-label') || '') === 'Pin guardado')};
    }""")
    info["author"] = (info["author"] or "").strip("/")
    return info


def profile_details(pg, handle):
    pg.goto(f"{BASE}/{handle}/", wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_timeout(3500)
    _check_bot_warning(pg)
    text = pg.inner_text("body")
    follow_btn = pg.get_by_role("button", name=re.compile(r"^(Seguir|Siguiendo)$"))
    state = follow_btn.first.inner_text().strip() if follow_btn.count() else None
    bio_match = re.search(r"visualizaciones mensuales\s*\n(.+)", text)
    return {"followers": parse_followers(text), "state": state, "bio": (bio_match.group(1) if bio_match else "")[:240]}


def react(pg, url):
    pg.goto(url, wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_timeout(3500)
    _check_bot_warning(pg)
    _assert_account(pg)
    button = pg.locator('[data-test-id="react-button"]').first
    if button.count() == 0:
        raise RuntimeError("no hay boton Reaccionar")
    if button.get_attribute("aria-pressed") == "true":
        return "already"
    pg.wait_for_timeout(1200)
    button.click()
    pg.wait_for_timeout(1800)
    _check_bot_warning(pg)
    if button.get_attribute("aria-pressed") != "true":
        raise RuntimeError("reaccion no confirmada")
    return "done"


def save(pg, url, board):
    pg.goto(url, wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_timeout(3500)
    _check_bot_warning(pg)
    _assert_account(pg)
    if pg.locator('button[aria-label="Pin guardado"]').count():
        return "already"
    pg.locator('[data-test-id="PinBetterSaveDropdown"]').first.click()
    pg.wait_for_timeout(1800)
    row = pg.locator(f'[data-test-id="board-row-{board}"]').first
    if row.count() == 0:
        raise RuntimeError(f"no aparece el tablero {board!r}")
    row.locator('[data-test-id="board-row-save-button-container"]').first.click()
    pg.wait_for_timeout(2500)
    _check_bot_warning(pg)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(800)
    if pg.locator('button[aria-label="Pin guardado"]').count() == 0:
        raise RuntimeError("guardado no confirmado")
    return "done"


def comment(pg, url, text):
    """Comenta un pin (caja «Añade un comentario…» del cierre del pin). Devuelve 'done' o 'already' (ya hay un comentario nuestro con ese texto)."""
    pg.goto(url, wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_timeout(4000)
    _check_bot_warning(pg)
    _assert_account(pg)
    if pg.inner_text("body").count(text) >= 1:
        return "already"
    box = pg.locator('[data-test-id="comment-editor-container"] [contenteditable="true"], [data-test-id="comment-editor-container"] [role="textbox"]').first
    if box.count() == 0:
        box = pg.get_by_label("Añade un comentario para compartir tus pensamientos").first
    if box.count() == 0:
        raise RuntimeError("no hay caja de comentario en este pin (comentarios desactivados)")
    box.click()
    pg.wait_for_timeout(600)
    pg.keyboard.type(text, delay=45)
    pg.wait_for_timeout(900)
    pg.locator('[data-test-id="activity-item-create-submit"] button, button[aria-label="Crear publicación"]').first.click()       # boton rojo de enviar (comprobado en vivo 06/10)
    pg.wait_for_timeout(3500)
    _check_bot_warning(pg)
    # confirmacion: el cuadro vuelve a quedar vacio (el texto escrito tambien cuenta en el body, por eso no basta con buscarlo) y el comentario aparece publicado
    still_typed = (box.inner_text() or "").strip() == text
    if still_typed or pg.inner_text("body").count(text) < 1:
        raise RuntimeError("comentario no confirmado (el texto sigue en el cuadro o no aparece publicado)")
    return "done"


def follow(pg, handle):
    pg.goto(f"{BASE}/{handle}/", wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_timeout(3500)
    _check_bot_warning(pg)
    _assert_account(pg)
    button = pg.get_by_role("button", name=re.compile(r"^(Seguir|Siguiendo)$")).first
    if button.count() == 0:
        raise RuntimeError("no hay boton Seguir")
    if button.inner_text().strip() == "Siguiendo":
        return "already"
    sc.human_pause(1.5, 3.5)
    button.click()
    pg.wait_for_timeout(2000)
    _check_bot_warning(pg)
    after = pg.get_by_role("button", name=re.compile(r"^(Seguir|Siguiendo)$")).first
    if after.count() == 0 or after.inner_text().strip() != "Siguiendo":
        raise RuntimeError("follow no confirmado")
    return "done"


# ------------------------------------------------------------------------------------------ comandos
def cmd_scan():
    import action_ledger as al
    reacted, saved, followed = done_sets()
    commented_urls = done_comments()
    pins, authors = [], {}
    with al.browser_session():
        p, pg = _connect()
        try:
            for query, board in day_queries(round_index=datetime.datetime.now().hour // 8):
                print(f"\n=== {query!r} (tablero: {board or 'solo reaccionar/seguir'}) ===")
                try:
                    found = search_pins(pg, query)
                except Exception as exc:     # 04-05/10: un timeout de navegacion en UNA busqueda tumbaba el scan entero (la ronda programada fallo dos dias seguidos)
                    if isinstance(exc, BotWarningDetected):
                        raise
                    print(f"  (busqueda omitida: {type(exc).__name__}: {str(exc)[:90]})")
                    continue
                taken = 0
                for item in found:
                    if taken >= PINS_PER_QUERY:
                        break
                    if not is_spanish(item["title"]) and not item["title"]:
                        continue
                    try:
                        details = pin_details(pg, item["url"])
                    except Exception as exc:          # 07/10: una carga lenta de UN pin (timeout de 30 s) mataba el scan entero y la ronda (13:28)
                        if isinstance(exc, BotWarningDetected):
                            raise
                        print(f"  (pin omitido: {type(exc).__name__})")
                        continue
                    sc.pause(2, 5)
                    title = item["title"] or details["title"]   # el <h1> de la pagina del pin es la cabecera "Pinterest"
                    ok = pin_ok(title, details["desc"])
                    author = details["author"]
                    pin_board = board_for(f"{title} {details['desc']}", board)
                    print(f"  {'+' if ok else '-'} {item['title'][:60]!r} autor={author}")
                    pins.append({"url": item["url"], "title": title, "author": author, "ok": ok,
                                 "board": pin_board, "desc": details["desc"][:300], "query": query, "done_react": item["url"] in reacted or details["reacted"],
                                 "done_save": item["url"] in saved or details["saved"], "done_comment": item["url"] in commented_urls})
                    if ok and author and author.casefold() not in followed and author.casefold() != MY_HANDLE:
                        authors.setdefault(author.casefold(), {"handle": author, "sample": title + " " + details["desc"]})
                    taken += 1
            print(f"\n=== PERFILES ({min(len(authors), MAX_PROFILE_VISITS)} de {len(authors)}) ===")
            good = []
            for entry in list(authors.values())[:MAX_PROFILE_VISITS]:
                try:
                    prof = profile_details(pg, entry["handle"])
                except Exception as exc:
                    if isinstance(exc, BotWarningDetected):
                        raise
                    print(f"  (perfil omitido: @{entry['handle']} {type(exc).__name__})")
                    continue
                ok, why = author_ok(entry["handle"], prof["bio"], prof["followers"], known=followed, sample_text=entry["sample"])
                if ok and prof["state"] != "Seguir":
                    ok, why = False, f"boton={prof['state']}"
                print(f"  {'+' if ok else '-'} @{entry['handle']}: {prof['followers']} seg | {why or prof['bio'][:60]}")
                if ok:
                    score = 10 + (6 if NICHE.search(prof["bio"] or "") else 0) + (4 if (prof["followers"] or 0) <= 5000 else 0)
                    good.append({"handle": entry["handle"], "followers": prof["followers"], "bio": prof["bio"], "score": score})
                sc.pause(3, 7)
        finally:
            p.stop()
    with open(CANDIDATES_JSON, "w", encoding="utf-8") as stream:
        json.dump({"date": datetime.date.today().isoformat(), "pins": pins, "authors": good}, stream, ensure_ascii=False, indent=1)
    print(f"\nPINES utiles: {sum(1 for x in pins if x['ok'])}/{len(pins)} | AUTORES para seguir: {len(good)}")


def cmd_plan(argv):
    def opt(name, default):
        return int(argv[argv.index(name) + 1]) if name in argv else default
    with open(CANDIDATES_JSON, encoding="utf-8") as stream:
        candidates = json.load(stream)
    plan = build_plan(candidates, opt("--follows", 25), opt("--saves", 25), opt("--reacts", 40), opt("--comments", 6), done_comments())
    plan = write_comments(plan, candidates)
    with open(PLAN_JSON, "w", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=1)
    counts = {}
    for item in plan:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    print(json.dumps({"plan": "SISTEMA_DIARIO_PINTEREST/pinterest_plan.json", "actions": len(plan), **counts}))


def _append_registro(rows):
    new = not os.path.exists(REGISTRO_CSV)
    with open(REGISTRO_CSV, "a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        if new:
            writer.writerow(["fecha", "cuenta", "tipo", "post_resumen", "texto_usado", "resultado", "notas"])
        writer.writerows(rows)


def cmd_run():
    import action_ledger as al
    import circuit_breaker as cb
    allowed, why = cb.check(ROOT)
    if not allowed:
        print(f"cortacircuitos de Pinterest ABIERTO: {why}")
        return 1
    with open(PLAN_JSON, encoding="utf-8") as stream:
        plan = json.load(stream)
    import reply_writer as _rw
    plan = _rw.require_gpt(plan, "pinterest")      # 08/10: nunca se publica texto que no venga de ChatGPT
    today, rows, results, stopped = datetime.date.today().isoformat(), [], {}, False
    with al.browser_session():
        p, pg = _connect()
        try:
            for index, item in enumerate(plan, 1):
                kind = item["kind"]
                import conversation_turn_policy as ctp
                permitted, reason = ctp.check_execution("pinterest", item)
                if not permitted:
                    print(f"[{index}/{len(plan)}] comentario omitido: {reason}")
                    results["omitido_cierre_conversacion"] = results.get("omitido_cierre_conversacion", 0) + 1
                    continue
                if kind == "react":
                    import like_context_policy as lcp
                    allowed, why = lcp.check_execution("pinterest", item)
                    if not allowed:
                        print(f"[{index}/{len(plan)}] react omitido: {why}")
                        results["omitido_like_sin_contexto"] = results.get("omitido_like_sin_contexto", 0) + 1
                        continue
                label = item.get("handle") or item["url"]
                try:
                    if kind == "react":
                        outcome = react(pg, item["url"])
                    elif kind == "save":
                        outcome = save(pg, item["url"], item["board"])
                    elif kind == "comment":
                        outcome = comment(pg, item["url"], item["text"])
                    elif kind == "follow":
                        outcome = follow(pg, item["handle"])
                    else:
                        raise ValueError(kind)
                except BotWarningDetected as exc:
                    print(f"PARADA TOTAL: {exc}")
                    cb.record(ROOT, False, signal="auth", reason=str(exc)[:80])
                    stopped = True
                    break
                except Exception as exc:
                    print(f"[{index}/{len(plan)}] {kind} {label}: FALLO {type(exc).__name__}: {exc}")
                    results[f"fallo_{kind}"] = results.get(f"fallo_{kind}", 0) + 1
                    sc.pause(8, 15)
                    continue
                print(f"[{index}/{len(plan)}] {kind} {label}: {outcome}")
                results[kind] = results.get(kind, 0) + 1
                ref = item.get("url") or ""
                rows.append([today, "@" + (item.get("handle") or MY_HANDLE), kind, ref, item.get("text") or item.get("board", ""),
                             "confirmado" if outcome == "done" else "ya_hecho", item.get("title") or item.get("motivo", "")])
                if index < len(plan):
                    sc.pause(7, 18)      # 07/10: era 20-50 s (rondas de 85 min por 66 acciones); David pide mas movimiento
            followers = following = None
            if not stopped:
                prof = profile_details(pg, MY_HANDLE)
                followers = prof["followers"]
        finally:
            p.stop()
    _append_registro(rows)
    if followers is not None:
        with open(METRICAS_CSV, "a", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerow([today, followers, "", "", f"Interaccion 04/10: {results}"])
    print("\n=== RESUMEN ===")
    for row in rows:   # mismo formato que los otros ejecutores: lo lee mechanical_round.summarize
        if row[5] == "confirmado":
            print(f"confirmado {row[2]} {row[1] if row[2] == 'follow' else row[3]}")
        else:
            print(f"saltado_ya_hecho {row[2]}")
    print(f"RESUMEN: {results}" + (" (PARADA)" if stopped else ""))
    return 5 if stopped else 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(__doc__)
        return 2
    try:
        if argv[0] == "scan":
            cmd_scan()
        elif argv[0] == "plan":
            cmd_plan(argv)
        elif argv[0] == "run":
            return cmd_run()
        else:
            print(__doc__)
            return 2
    except BotWarningDetected as exc:
        print(f"PARADA: {exc}")
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

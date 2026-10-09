"""Pinterest: Pines propios nuevos cada dia desde las paginas de autorademodiaz.com (07/10/2026).

David (07/10): «Pinterest tiene 0 movimiento y el perfil no esta completo; mira lo de "Crea tu primer Pin", ordena mi contenido». Lo que mas mueve Pinterest es el contenido PROPIO nuevo y
regular (GPT 06/10, guias de 2026); con 1 ficha al dia el perfil sigue casi vacio. La web tiene ~210 paginas utiles (herramientas, guias, perfiles de editoriales para escritores,
cuaderno de lectura): cada una es un Pin posible. Aqui se genera una imagen vertical 2:3 (1000x1500) con el titulo de la pagina, se toma el titulo y la descripcion REALES de
la pagina (nada inventado), se elige el tablero por contenido y se publica con el mismo publicador que las fichas (`pinterest_publish.publish_pin`).

    python tools/pinterest_daily_pins.py [--max 2] [--apply]     # sin --apply: prepara y muestra, no publica
"""
from __future__ import annotations

import csv
import datetime
import glob
import hashlib
import json
import html as htmllib
import os
import random
import re
import sys
import textwrap
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))

ROOT = os.path.join(os.path.dirname(__file__), "..")
SITE = "https://autorademodiaz.com"
OUT_DIR = os.path.join(ROOT, "SISTEMA_DIARIO_PINTEREST", "pins_auto")
LOG = os.path.join(ROOT, "SISTEMA_DIARIO_PINTEREST", "pins_auto.csv")
PUBLISH_LOG = os.path.join(ROOT, "00_OPERATIVO", "publicaciones_automaticas.csv")
NETWORK_DIR = os.path.join(ROOT, "SISTEMA_DIARIO_PINTEREST")
LOG_HEADER = ("fecha_hora", "pagina", "titulo", "tablero", "pin_url", "resultado")
DAILY_MAX = 5
SKIP_PREFIX = ("/accesibilidad", "/ai", "/autor.html", "/mapa-del-sitio", "/prensa.html", "/eventos.html", "/ferias.html", "/premios.html", "/empieza-aqui")
PRIORITY = ("/herramientas", "/cuaderno", "/recomendaciones", "/clubes-de-lectura", "/lectores-beta", "/convocatorias-escritores", "/metodologia-editorial", "/recursos", "/fragmento", "/universo", "/las-manecillas-del-recuerdo")
BOARD_BY_PATH = (
    ("/editoriales", "Recursos para escritores"), ("/herramientas", "Recursos para escritores"), ("/recursos", "Recursos para escritores"), ("/lectores-beta", "Recursos para escritores"),
    ("/convocatorias-escritores", "Recursos para escritores"), ("/metodologia-editorial", "Recursos para escritores"),
    ("/cuaderno", "Lecturas y reseñas de libros"), ("/recomendaciones", "Lecturas y reseñas de libros"), ("/clubes-de-lectura", "Lecturas y reseñas de libros"),
    ("/las-manecillas-del-recuerdo", "Lecturas y reseñas de libros"), ("/fragmento", "Samuel entre mundos"), ("/universo", "Samuel entre mundos"),
)
KICKER = {"Recursos para escritores": "PARA ESCRITORES", "Lecturas y reseñas de libros": "LECTURAS", "Samuel entre mundos": "SAMUEL ENTRE MUNDOS", "Fantasía juvenil española": "FANTASÍA JUVENIL"}
PALETTE = {"Recursos para escritores": ("#16324f", "#f2c14e", "#f7f3e8"), "Lecturas y reseñas de libros": ("#3b2f4a", "#e9a8a0", "#fbf4ee"),
           "Samuel entre mundos": ("#10202b", "#7fd1c7", "#f1f5f2"), "Fantasía juvenil española": ("#2a1f3d", "#f0b66b", "#f8f1e7")}


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; autorademodiaz-pins)"})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def sitemap_urls():
    return re.findall(r"<loc>([^<]+)</loc>", _get(f"{SITE}/sitemap.xml"))


def meta(html):
    """(titulo, descripcion) reales de la pagina: og:title/og:description o <title>/meta description."""
    def tag(prop):
        for pattern in (rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']*)["\']', rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']{prop}["\']'):
            found = re.search(pattern, html, re.I)
            if found:
                return htmllib.unescape(found.group(1)).strip()
        return ""
    title = tag("og:title") or (htmllib.unescape(re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S).group(1)).strip() if re.search(r"<title", html, re.I) else "")
    desc = tag("og:description") or tag("description")
    return clean_title(title), " ".join(desc.split())


def clean_title(title):
    title = " ".join((title or "").split())
    title = re.sub(r"\s*[|\u2013\u2014-]\s*(Autora Demo D[ií]az.*|autorademodiaz\.com)$", "", title).strip()
    return re.sub(r"\s*\|\s*(Herramientas|Cuaderno|Recursos|Editoriales|Recomendaciones)$", "", title).strip()


def _log_rows(path=None):
    """CSV como fuente de verdad: jamás convertir corrupción en estado vacío."""
    try:
        with open(path or LOG, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            names = reader.fieldnames
            if (not names or len(names) != len(set(names))
                    or not set(LOG_HEADER).issubset(names)):
                raise ValueError("pins_auto.csv sin cabeceras únicas y reconocibles")
            rows = list(reader)
            if any(None in row or any(row.get(field) is None for field in LOG_HEADER)
                   or not row["fecha_hora"] or not row["pagina"] or not row["resultado"]
                   for row in rows):
                raise ValueError("pins_auto.csv contiene filas incompletas")
            return rows
    except csv.Error as exc:
        raise ValueError("pins_auto.csv tiene formato CSV inválido") from exc
    except FileNotFoundError:
        return []


def used_links():
    used = set()
    for path in glob.glob(os.path.join(ROOT, "publicaciones Pinterest GPT", "*", "publicacion.md")):
        try:
            with open(path, encoding="utf-8") as stream:
                for link in re.findall(r"\*\*Enlace:\*\*\s*(\S+)", stream.read()):
                    used.add(link.rstrip("/"))
        except FileNotFoundError:
            # La ficha pudo desaparecer entre glob y open; es una carrera
            # inocua. Los demás errores se propagan para no inventar estado.
            continue
    # Un envío con confirmación perdida puede haberse publicado realmente.
    # Hasta reconciliarlo en Pinterest, NUNCA se reenvía automáticamente.
    for row in _log_rows():
        if row["resultado"] in ("publicado", "ensayo_ok", "pendiente_verificacion"):
            used.add(row["pagina"].rstrip("/"))
    return used


def board_for_url(url, text=""):
    import pinterest_growth as pg
    path = url.replace(SITE, "")
    if path.startswith(("/cuaderno", "/recomendaciones", "/clubes-de-lectura")):
        by_text = pg.board_for(text, None)           # fantasia / lugares segun el contenido; si no, el tablero de lecturas
        if by_text:
            return by_text
    for prefix, board in BOARD_BY_PATH:
        if path.startswith(prefix):
            return board
    return pg.board_for(text, "Lecturas y reseñas de libros")


def candidates(urls, used, rng):
    """Paginas aun sin Pin: primero las de contenido (herramientas, cuaderno...), luego los perfiles de editoriales, mezcladas."""
    pool = [u for u in urls if u.rstrip("/") not in used and u.rstrip("/") != SITE and not u.replace(SITE, "").startswith(SKIP_PREFIX)]
    first = [u for u in pool if u.replace(SITE, "").startswith(PRIORITY)]
    rest = [u for u in pool if u not in first]
    rng.shuffle(first)
    rng.shuffle(rest)
    return first + rest


def render(title, board, out_path):
    """Imagen vertical 1000x1500: kicker, titulo grande y la web. Tipografia Georgia (en Windows)."""
    from PIL import Image, ImageDraw, ImageFont
    bg, accent, ink = PALETTE.get(board, PALETTE["Lecturas y reseñas de libros"])
    img = Image.new("RGB", (1000, 1500), bg)
    d = ImageDraw.Draw(img)
    fonts = r"C:\Windows\Fonts"
    big = ImageFont.truetype(os.path.join(fonts, "georgiab.ttf"), 92)
    small = ImageFont.truetype(os.path.join(fonts, "georgia.ttf"), 38)
    kick = ImageFont.truetype(os.path.join(fonts, "georgiab.ttf"), 34)
    d.rectangle([80, 140, 220, 150], fill=accent)
    d.text((80, 175), KICKER.get(board, "LECTURAS"), font=kick, fill=accent)
    size = 92
    lines = textwrap.wrap(title, width=18)
    while len(lines) > 8 and size > 56:
        size -= 6
        big = ImageFont.truetype(os.path.join(fonts, "georgiab.ttf"), size)
        lines = textwrap.wrap(title, width=int(18 * 92 / size))
    y = 330
    for line in lines[:9]:
        d.text((80, y), line, font=big, fill=ink)
        y += int(size * 1.22)
    d.rectangle([80, 1290, 920, 1296], fill=accent)
    d.text((80, 1330), "autorademodiaz.com", font=small, fill=ink)
    d.text((80, 1385), "Autora Demo Díaz · Escritor", font=small, fill=accent)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)
    return out_path


def slug(url):
    return re.sub(r"[^a-z0-9]+", "-", url.replace(SITE, "").lower()).strip("-") or "inicio"


def _scheduled_pin_count(today):
    """Contar también Pines confirmados por content_publisher; CSV separado."""
    try:
        with open(PUBLISH_LOG, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            names = reader.fieldnames
            required = ("fecha_hora", "red", "ficha", "programada", "url")
            if not names or len(names) != len(set(names)) or not set(required).issubset(names):
                raise ValueError("publicaciones_automaticas.csv: cabecera inválida")
            rows = list(reader)
            if any(None in row or any(row.get(field) is None for field in required)
                   or not row["fecha_hora"] or not row["red"] or not row["url"]
                   for row in rows):
                raise ValueError("publicaciones_automaticas.csv: fila incompleta")
    except FileNotFoundError:
        return 0
    except csv.Error as exc:
        raise ValueError("publicaciones_automaticas.csv: CSV inválido") from exc
    return sum(1 for row in rows
               if row["red"].casefold() == "pinterest"
               and row["fecha_hora"].startswith(today))


def today_count(today=None):
    today = (today or datetime.date.today()).isoformat()
    todays = [r for r in _log_rows() if r["fecha_hora"].startswith(today)]
    confirmed = [r for r in todays if r["resultado"] == "publicado"]
    pending = {r["pagina"].rstrip("/") for r in todays
               if r["resultado"] == "pendiente_verificacion"}
    published_pages = {r["pagina"].rstrip("/") for r in confirmed}
    # Una intención sin confirmar puede haber creado un Pin; reservar cupo.
    # La otra ruta de publicación tiene su CSV propio y también consume cupo.
    return (len(confirmed) + len(pending - published_pages)
            + _scheduled_pin_count(today))


FAILED_HOLD_COUNT = 3    # criterio operativo, no cuota oficial de Pinterest
FAILED_HOLD_HOURS = 24  # revisión posterior; evita repetir un Pin roto cada ronda


def failed_cooldowns(now=None, path=None):
    """3 fallos en alguna ventana de 24h => pausa hasta 24h tras el último.

    Conservar 48h de historia es necesario: la pausa sigue vigente aunque
    el fallo más antiguo haya salido de la primera ventana móvil.
    """
    now = now or datetime.datetime.now()
    window = datetime.timedelta(hours=FAILED_HOLD_HOURS)
    if now.tzinfo is not None and now.utcoffset() is not None:
        now = now.astimezone().replace(tzinfo=None)
    by_page = {}
    for row in _log_rows(path):
        if not row["resultado"].startswith("fallo:"):
            continue
        try:
            at = datetime.datetime.fromisoformat(row["fecha_hora"])
            if at.tzinfo is not None and at.utcoffset() is not None:
                at = at.astimezone().replace(tzinfo=None)
        except (ValueError, TypeError) as exc:
            raise ValueError("pins_auto.csv tiene un fallo con fecha inválida") from exc
        if now - 2 * window <= at <= now:
            by_page.setdefault(row["pagina"].rstrip("/"), []).append(at)

    held = {}
    for page, times in by_page.items():
        times.sort()
        left = 0
        for right, at in enumerate(times):
            while at - times[left] > window:
                left += 1
            if right - left + 1 >= FAILED_HOLD_COUNT and now < at + window:
                held[page] = at + window
    return held


def _append(row):
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as stream:
        w = csv.writer(stream)
        if new:
            w.writerow(["fecha_hora", "pagina", "titulo", "tablero", "pin_url", "resultado"])
        w.writerow(row)
        stream.flush()
        os.fsync(stream.fileno())  # intención persistida ANTES del clic remoto


def prepare(url, rng=None):
    """Dict listo para publicar o None si la pagina no sirve (sin titulo/descripcion suficientes o con fallos de ortografia)."""
    import x_interact as x
    html = _get(url)
    title, desc = meta(html)
    if len(title) < 12 or len(desc) < 60:
        return None
    desc = desc if len(desc) <= 480 else desc[:477].rsplit(" ", 1)[0] + "…"
    desc = f"{desc} Más en autorademodiaz.com."
    board = board_for_url(url, f"{title} {desc}")
    try:
        x._check_spanish_orthography(title + "\n" + desc)
    except ValueError:
        return None
    return {"url": url, "title": title[:100], "description": desc, "board": board, "alt": f"Imagen con el título: {title[:100]}"}


def _owned_page(url):
    """Solo enlaces HTTPS del dominio propio, sin consulta ni fragmento."""
    try:
        p = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    return (p.scheme == "https" and p.netloc == "autorademodiaz.com"
            and p.path not in ("", "/") and not p.query and not p.fragment)


def approval_token(item):
    """Huella estable del Pin revisado: URL, título, texto, tablero y ALT."""
    fields = {key: item[key] for key in ("url", "title", "description", "board", "alt")}
    data = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def selected_pin_approvals(argv):
    """--approve-pin URL TOKEN, repetible. No es un token de autenticación."""
    approved = {}
    for index, arg in enumerate(argv):
        if arg != "--approve-pin":
            continue
        if index + 2 >= len(argv):
            raise ValueError("--approve-pin requiere URL y código de revisión")
        url, token = argv[index + 1].rstrip("/"), argv[index + 2].lower()
        if not _owned_page(url) or not re.fullmatch("[a-f0-9]{16}", token):
            raise ValueError("--approve-pin requiere una URL propia HTTPS y huella de 16 caracteres")
        if url in approved and approved[url] != token:
            raise ValueError("dos aprobaciones incompatibles para la misma URL")
        approved[url] = token
    return approved


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    apply = "--apply" in argv
    try:
        approved = selected_pin_approvals(argv) if apply else {}
    except ValueError as exc:
        print(f"[pinterest] aprobación inválida: {exc}")
        return 2
    if apply and not approved:
        print("[pinterest] no se publica sin selección específica de cada Pin. "
              "Ejecutar primero sin --apply y usar --approve-pin URL CODIGO para cada uno")
        return 2
    limit = int(argv[argv.index("--max") + 1]) if "--max" in argv else 2
    limit = min(limit, max(0, DAILY_MAX - today_count()))
    if limit <= 0:
        print(f"[pinterest] ya hay {DAILY_MAX} Pines propios automaticos hoy")
        return 0
    rng = random.Random()
    held = failed_cooldowns()
    pool = [u for u in candidates(sitemap_urls(), used_links(), rng)
            if _owned_page(u) and u.rstrip("/") not in held
            and (not apply or u.rstrip("/") in approved)]
    if held:
        print(f"[pinterest] {len(held)} página(s) en enfriamiento por fallos repetidos (24 h)")
    prepared = []
    for url in pool:
        if len(prepared) >= limit:
            break
        try:
            item = prepare(url)
        except Exception as exc:
            print(f"  {url}: {type(exc).__name__}")
            continue
        if item:
            token = approval_token(item)
            if apply and approved[url.rstrip("/")] != token:
                print(f"  {url}: el contenido cambió desde su revisión; NO se publica "
                      f"(nuevo código {token})")
                continue
            item["review_token"] = token
            item["image"] = render(item["title"], item["board"], os.path.join(OUT_DIR, slug(url) + ".png"))
            prepared.append(item)
    print(f"[pinterest] {len(prepared)} Pin(es) preparados de {len(pool)} paginas sin Pin")
    for it in prepared:
        print(f"  {it['board']} | {it['title']} | {it['url']} | revisión: {it['review_token']}")
        if not apply:
            print(f"    Descripción: {it['description']}")
            print(f"    Texto alternativo: {it['alt']}")
    if not apply or not prepared:
        return 0
    import action_ledger
    import pinterest_publish as pp
    import circuit_breaker as breaker
    for i, it in enumerate(prepared):
        try:
            with action_ledger.browser_session(wait_minutes=90):
                # Revalidación de la decisión bajo exclusión, por cada Pin.
                allowed, why = breaker.check(NETWORK_DIR)
                if not allowed:
                    print(f"[pinterest] cortacircuitos abierto: {why}; no se publica")
                    break
                if today_count() >= DAILY_MAX:
                    print(f"[pinterest] cupo diario de {DAILY_MAX} alcanzado durante la espera")
                    break
                if it["url"].rstrip("/") in used_links():
                    print(f"[pinterest] página publicada o pendiente de verificar: {it['url']}")
                    continue
                if it["url"].rstrip("/") in failed_cooldowns():
                    print("[pinterest] Pin omitido: 3 fallos recientes, pausa 24 h")
                    continue
                now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
                started = False

                def before_submit():
                    nonlocal started
                    # El publicador invoca esto DESPUÉS de validar el formulario
                    # e INMEDIATAMENTE ANTES del clic que puede tener efecto remoto.
                    # Si falla la escritura, el botón jamás se pulsa.
                    _append([now, it["url"], it["title"], it["board"], "",
                             "pendiente_verificacion"])
                    started = True

                try:
                    pin = pp.publish_pin(
                        it["image"], it["title"], it["description"],
                        it["url"], it["alt"], it["board"],
                        apply=True, before_submit=before_submit)
                except Exception as exc:
                    # Si se llegó al clic, no se puede distinguir publicado de
                    # rechazado sin comprobar Pinterest. Mantener intención.
                    if not started:
                        _append([now, it["url"], it["title"], it["board"], "",
                                 f"fallo:{type(exc).__name__}:{str(exc)[:120]}"])
                    print(f"  FALLO: {type(exc).__name__}: {exc}")
                    message = str(exc).casefold()
                    # 'aviso de Pinterest' y 'pide iniciar sesion' son emitidos
                    # solo por las guardas explícitas del publicador.
                    auth = any(s in message for s in (
                        "captcha", "verifica que eres una persona",
                        "tu cuenta ha sido suspendida", "aviso de pinterest",
                        "pide iniciar sesion"))
                    signal = breaker.worst([breaker.detect(str(exc)),
                                            "auth" if auth else None])
                    if signal:
                        breaker.record(NETWORK_DIR, ok=False, signal=signal,
                                       reason="señal de seguridad al publicar Pin")
                        print(f"[pinterest] cortacircuitos activado: {signal}")
                    if started:
                        print("[pinterest] ENVÍO INCIERTO: revisar tablero y CSV "
                              "antes de reintentar esa URL")
                        return 2
                    if signal:
                        break
                else:
                    if not started or not isinstance(pin, str) or "/pin/" not in pin:
                        print("[pinterest] ENVÍO INCIERTO: falta marcador o URL "
                              "verificable; detener y revisar")
                        return 2
                    try:
                        _append([now, it["url"], it["title"], it["board"],
                                 pin, "publicado"])
                    except OSError as exc:
                        print(f"[pinterest] Pin confirmado {pin}, pero el CSV "
                              f"no se actualizó ({type(exc).__name__}). "
                              "Marcador pendiente intacto; no repetir")
                        return 2
                    print(f"  PUBLICADO: {it['title']} -> {pin}")
        except action_ledger.RoundBusy:
            print("[pinterest] Edge ocupado tras esperar 90 min; tanda omitida sin publicar")
            return 0
        # Nunca ocupar Edge durante la pausa; las omisiones no duermen.
        if started and i < len(prepared) - 1:
            import time
            time.sleep(random.uniform(60, 150))
    return 0


if __name__ == "__main__":
    sys.exit(main())

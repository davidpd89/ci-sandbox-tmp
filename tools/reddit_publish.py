"""Reddit: publicaciones propias SENCILLAS en varias comunidades en espanol (06/10/2026).

David (06/10): «la idea es crear posts en diversas comunidades con preguntas basicas de debate, preguntando opiniones, sin escribir IA: muy poco texto para que sea humano y natural; preguntas
normales de lectura, juegos con libros… cosas muy planas, neutras, positivas». Aqui NO se publican las fichas largas de GPT: se publica de un BANCO de preguntas cortas
(`00_OPERATIVO/reddit_preguntas.json`, escritas a mano, una frase, sin enlaces ni promocion, sin mencionar los libros de David).

Reglas de cadencia (no parecer un bot): como mucho 1 post al dia y 4 a la semana, nunca dos veces en la misma comunidad en 7 dias, nunca la misma pregunta, a horas variables (la tarea
la lanza el programador una vez al dia con retraso aleatorio). Cada comunidad tiene su etiqueta (flair) real y, si lo exige, una linea de cuerpo. Se relee todo antes de publicar y se para
ante cualquier aviso/captcha. Registro: `SISTEMA_DIARIO_REDDIT/preguntas_publicadas.csv` y `registro_interacciones.csv` (tipo `post`).

    python tools/reddit_publish.py [--apply]       # sin --apply solo dice que publicaria (y comprueba el formulario sin enviarlo con --check)
"""
import csv
import datetime
import json
import os
import random
import re
import sys
import tempfile
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(__file__))

ROOT = os.path.join(os.path.dirname(__file__), "..")
BANK = os.path.join(ROOT, "00_OPERATIVO", "reddit_preguntas.json")
LOG = os.path.join(ROOT, "SISTEMA_DIARIO_REDDIT", "preguntas_publicadas.csv")
BLOCKED = os.path.join(ROOT, "SISTEMA_DIARIO_REDDIT", "cache", "comunidades_en_observacion.json")      # {sub: motivo}: una pregunta filtrada/retirada pone la comunidad en observacion
STATES = os.path.join(ROOT, "00_OPERATIVO", "reddit_comunidades.json")      # estado por comunidad (DISCOVERED/COMMENTING/POST_ELIGIBLE...); solo se publica en POST_ELIGIBLE
MY_USER = "DavidPortoEscritor"
REGISTRO = os.path.join(ROOT, "SISTEMA_DIARIO_REDDIT", "registro_interacciones.csv")
CDP_URL = "http://127.0.0.1:9223"
MAX_PER_DAY, MAX_PER_WEEK, SUB_COOLDOWN_DAYS = 2, 8, 7      # 07/10: David pide ir publicando tambien para subir karma (antes 1/dia y 4/semana)
TITLE_MAX = 300


INTENTS = os.path.join(ROOT, "SISTEMA_DIARIO_REDDIT", "cache", "post_intents.json")


def _read_intents():
    """Identificadores con envío iniciado/confirmado, sin títulos ni textos."""
    try:
        with open(INTENTS, encoding="utf-8") as stream:
            state = json.load(stream)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, UnicodeError) as exc:
        # Un registro corrupto NO autoriza reenvío. Fallar cerrado.
        raise RedditPublishError("no se puede leer post_intents.json; revisión manual antes de publicar") from exc
    if not isinstance(state, dict):
        raise RedditPublishError("post_intents.json no es un objeto; no se publicará")
    return state


def _mark_intent(item_id, state, url=""):
    """Persistir el intento ANTES del envío y confirmarlo ANTES del CSV."""
    intents = _read_intents()
    intents[str(item_id)] = {
        "state": state, "url": url,
        "at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    os.makedirs(os.path.dirname(INTENTS), exist_ok=True)
    tmp = f"{INTENTS}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as stream:
            json.dump(intents, stream, ensure_ascii=False, indent=1)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, INTENTS)
    finally:
        try:
            os.remove(tmp)
        except FileNotFoundError:
            pass


class RedditPublishError(RuntimeError):
    pass


def load_bank(path=None):
    with open(path or BANK, encoding="utf-8") as stream:
        return json.load(stream)


def read_log(path=None):
    """Registro conservador: un CSV roto no puede habilitar una repetición."""
    rows = []
    try:
        with open(path or LOG, encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or not {"fecha", "id", "sub"}.issubset(reader.fieldnames):
                raise RedditPublishError("cabecera inválida en preguntas_publicadas.csv")
            for row in reader:
                if not all(isinstance(row.get(field), str) and row[field].strip()
                           for field in ("fecha", "id", "sub")):
                    raise RedditPublishError("fila incompleta en preguntas_publicadas.csv")
                try:
                    when = datetime.date.fromisoformat(row["fecha"])
                except ValueError as exc:
                    raise RedditPublishError("fecha inválida en preguntas_publicadas.csv") from exc
                rows.append({**row, "when": when})
    except FileNotFoundError:
        return []
    except (OSError, UnicodeError, csv.Error) as exc:
        raise RedditPublishError("no se puede leer preguntas_publicadas.csv; no publicar") from exc
    return rows


def eligible_subs(path=None):
    """Solo comunidades POST_ELIGIBLE. Si falta el estado, no publicar."""
    try:
        with open(path or STATES, encoding="utf-8") as stream:
            states = json.load(stream)
    except (OSError, ValueError, UnicodeError):
        # Antes devolvía None y choose() lo interpretaba como permiso
        # universal. Un fichero perdido NO autoriza publicar en r/libros
        # u otra comunidad sin verificar sus reglas/participación.
        return set()
    if not isinstance(states, dict):
        return set()
    return {name.casefold() for name, info in states.items()
            if isinstance(name, str) and isinstance(info, dict)
            and info.get("state") == "POST_ELIGIBLE"}


def read_blocked(path=None):
    path = path or BLOCKED
    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, UnicodeError) as exc:
        raise RedditPublishError("comunidades_en_observacion.json ilegible; no publicar") from exc
    if not isinstance(data, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                           for k, v in data.items()):
        raise RedditPublishError("esquema inválido en comunidades_en_observacion.json; no publicar")
    return {k.casefold(): v for k, v in data.items()}


def write_blocked(blocked, path=None):
    """Sustitución atómica: una interrupción no trunca los bloqueos existentes."""
    path = path or BLOCKED
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=directory, prefix=".reddit_blocked_",
                                         suffix=".tmp", delete=False) as stream:
            tmp = stream.name
            json.dump(blocked, stream, ensure_ascii=False, indent=1)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass


def my_recent_posts(pg, limit=15):
    """[{sub, title, url, removed}] de nuestros ultimos posts (JSON de Reddit con la sesion abierta). `removed`: motivo (automod_filtered, moderator…) o None."""
    rows = pg.evaluate("""async (args) => { const r = await fetch('/user/' + args.user + '/submitted.json?limit=' + args.limit); if (!r.ok) return [];
        const j = await r.json(); return (j.data.children || []).map(c => ({sub: c.data.subreddit, title: c.data.title, url: c.data.permalink, removed: c.data.removed_by_category, created: c.data.created_utc})); }""",
                       {"user": MY_USER, "limit": limit})
    return rows or []


def refresh_blocked(posts, bank_titles, blocked, now=None):
    """Toda retirada reciente bloquea; solo sin retiradas puede liberarse."""
    import time as _time
    now = _time.time() if now is None else now
    out = dict(blocked)
    removed = {}
    approved = set()
    for post in posts:
        if post["title"] not in bank_titles or now - post["created"] > 14 * 86400:
            continue
        key = post["sub"].casefold()
        if post["removed"]:
            if key not in removed or post["created"] > removed[key]["created"]:
                removed[key] = post
        else:
            approved.add(key)
    for key in approved:
        if key not in removed:
            out.pop(key, None)
    for key, post in removed.items():
        out[key] = f"«{post['title'][:50]}» {post['removed']}"
    return out


def choose(bank, log, today=None, rng=None, blocked=(), allowed=None):
    """Pregunta a publicar hoy o (None, motivo): respeta tope diario/semanal, enfriamiento por comunidad y no repite preguntas."""
    today = today or datetime.date.today()
    rng = rng or random
    if sum(1 for r in log if r["when"] == today) >= MAX_PER_DAY:
        return None, "ya se publico una hoy"
    if sum(1 for r in log if (today - r["when"]).days < 7) >= MAX_PER_WEEK:
        return None, f"ya hay {MAX_PER_WEEK} en los ultimos 7 dias"
    done = {r["id"] for r in log}
    recent_subs = {r["sub"].casefold() for r in log if (today - r["when"]).days < SUB_COOLDOWN_DAYS}
    blocked = {str(b).casefold() for b in blocked}
    options = [q for q in bank if q["id"] not in done and q["sub"].casefold() not in recent_subs and q["sub"].casefold() not in blocked
               and (allowed is None or q["sub"].casefold() in allowed)]
    if not options:
        return None, "no queda ninguna pregunta nueva en una comunidad sin enfriar"
    return rng.choice(options), ""


def _check(pg):
    try:
        text = pg.inner_text("body").lower()
    except Exception as exc:
        raise RedditPublishError("no se pudo leer la pantalla; parar") from exc
    for signal in ("unusual activity", "actividad inusual", "verify you're human", "verifica que eres humano", "has sido bloqueado", "you are doing that too much",
                   "estás haciendo eso demasiado", "cuenta suspendida", "account suspended", "captcha"):
        if signal in text:
            raise RedditPublishError(f"aviso de Reddit en pantalla ({signal!r}); parar y avisar a David")


def _validate(item):
    import x_interact as x
    title = item["title"].strip()
    if not title or len(title) > TITLE_MAX:
        raise RedditPublishError("titulo vacio o demasiado largo")
    if re.search(r"https?://|www\.|davidporto", f"{title} {item.get('body', '')}", re.I):
        raise RedditPublishError("las preguntas no llevan enlaces ni mencionan a David")
    x._check_spanish_orthography(title)
    if item.get("body"):
        x._check_spanish_orthography(item["body"])


def _valid_permalink(url, sub):
    """Aceptar solo el permalink HTTPS de una publicación de la comunidad elegida."""
    if not isinstance(url, str):
        return False
    parsed = urlsplit(url.strip())
    if parsed.scheme != "https" or parsed.netloc.casefold() not in ("reddit.com", "www.reddit.com"):
        return False
    parts = parsed.path.split("/")
    return (len(parts) >= 5 and parts[1].casefold() == "r"
            and parts[2].casefold() == str(sub).casefold()
            and parts[3].casefold() == "comments"
            and re.fullmatch(r"[a-z0-9]+", parts[4], re.I) is not None)


def publish_post(item, apply=False, log=print, before_submit=None):
    """Publica una pregunta (dict del banco). Devuelve (URL del post, motivo de retirada o None) o ('ensayo', None)."""
    from playwright.sync_api import sync_playwright
    _validate(item)
    p = sync_playwright().start()
    try:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        pg = browser.contexts[0].new_page()
        pg.set_default_timeout(15000)
        try:
            pg.goto(f"https://www.reddit.com/r/{item['sub']}/submit/?type=TEXT", wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(6000)
            _check(pg)
            if "/login" in pg.url:
                raise RedditPublishError("Reddit pide iniciar sesion; parar")
            title_box = pg.locator('textarea[name="title"], [name="title"] textarea').first
            if title_box.count() == 0:
                title_box = pg.get_by_placeholder(re.compile("^Título", re.I)).first
            title_box.click()
            title_box.fill(item["title"])
            if item.get("body"):
                body = pg.get_by_label("Campo de texto del cuerpo de la publicación").first
                body.click()
                pg.keyboard.type(item["body"], delay=25)
            if item.get("flair"):
                pg.get_by_text("Añadir marcas y etiquetas", exact=False).first.click()
                pg.wait_for_timeout(1500)
                pg.locator('faceplate-radio-input[name="flairId"]').filter(has_text=item["flair"].strip()).first.click()
                pg.wait_for_timeout(600)
                pg.get_by_role("button", name=re.compile(r"^(Añadir|Aplicar|Guardar)$")).last.click()
                pg.wait_for_timeout(1200)
            pg.wait_for_timeout(1000)
            # releer: lo escrito debe ser exactamente lo del banco
            typed = title_box.input_value().strip()
            if typed != item["title"].strip():
                raise RedditPublishError("el titulo escrito no coincide con el del banco; no se publica")
            if item.get("flair") and pg.get_by_text(item["flair"].strip(), exact=True).count() == 0:       # la etiqueta elegida sale como chip (dentro de un componente web: no esta en inner_text del body)
                raise RedditPublishError("la etiqueta no consta tras elegirla; no se publica")
            if not apply:
                log("  ensayo: formulario rellenado y verificado (no se envia)")
                return "ensayo", None
            button = pg.get_by_role("button", name="Publicar", exact=True).last
            if not button.is_enabled():
                raise RedditPublishError("el boton Publicar esta desactivado (falta un campo obligatorio o la comunidad exige algo mas); no se publica")
            import voice_output_finalization as voice
            voice.inspect_fields({"titulo": item["title"], "cuerpo": item.get("body") or ""},
                                 network="reddit", queue="WEB", log=log)
            if before_submit is not None:
                # Reservar DURABLEMENTE solo al terminar los controles de
                # formulario y justo antes del clic. Si falla la validación
                # del flair/login, no se deja una intención huérfana.
                before_submit()
            button.click()
            for _ in range(10):
                pg.wait_for_timeout(2500)
                _check(pg)
                for post in my_recent_posts(pg, 5):
                    if post["title"] == item["title"] and post["sub"].casefold() == item["sub"].casefold():
                        if post["removed"]:
                            log(f"  AVISO: Reddit lo ha filtrado o retirado ({post['removed']}): la comunidad queda en observacion")
                        return "https://www.reddit.com" + post["url"].split("?")[0], post["removed"]
            raise RedditPublishError("no se confirma la publicacion (no aparece en nuestros posts); comprobar el perfil antes de repetir")
        except Exception:
            try:       # captura del estado para depurar un formulario que cambio
                os.makedirs(os.path.join(ROOT, "SISTEMA_DIARIO_REDDIT", "cache"), exist_ok=True)
                pg.screenshot(path=os.path.join(ROOT, "SISTEMA_DIARIO_REDDIT", "cache", "ultimo_error_publicar.png"))
            except Exception:
                pass
            raise
        finally:
            pg.close()
    finally:
        p.stop()


def record(item, url, today=None):
    today = (today or datetime.date.today()).isoformat()
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        if new:
            writer.writerow(["fecha", "id", "sub", "titulo", "url"])
        writer.writerow([today, item["id"], item["sub"], item["title"], url])
    with open(REGISTRO, "a", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerow([today, f"r/{item['sub']}", url, "post", item["title"], "confirmado", "pregunta sencilla del banco (reddit_publish.py)"])


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    apply, check = "--apply" in argv, "--check" in argv
    bank = load_bank()
    blocked = read_blocked()
    if apply or check:        # salud de las comunidades: lo ya publicado puede haber sido filtrado/retirado despues
        from playwright.sync_api import sync_playwright
        import action_ledger
        try:
            with action_ledger.browser_session(wait_minutes=40):
                p = sync_playwright().start()
                try:
                    pg = p.chromium.connect_over_cdp(CDP_URL).contexts[0].new_page()
                    try:
                        pg.goto("https://www.reddit.com/", wait_until="domcontentloaded", timeout=45000)
                        pg.wait_for_timeout(3000)
                        blocked = refresh_blocked(my_recent_posts(pg, limit=50), {q["title"] for q in bank}, blocked)
                        write_blocked(blocked)
                    finally:
                        pg.close()
                finally:
                    p.stop()
        except action_ledger.RoundBusy:
            print("[reddit] Edge ocupado durante la comprobación de comunidades: no se publica")
            return 0
    if blocked:
        print("[reddit] comunidades en observacion: " + ", ".join(f"r/{k} ({v})" for k, v in blocked.items()))
    # También en preview y --check: no anunciar una pregunta cuyo clic
    # anterior ya pudo llegar a Reddit aunque aún falte en el CSV.
    pending = _read_intents()
    safe_bank = [entry for entry in bank if str(entry["id"]) not in pending]
    item, why = choose(safe_bank, read_log(), blocked=blocked, allowed=eligible_subs())
    if item is None:
        print(f"[reddit] no se publica: {why}")
        return 0
    label = f"r/{item['sub']} [{item.get('flair', '')}] «{item['title']}»"
    if not (apply or check):
        print(f"[reddit] publicaria: {label}")
        return 0
    import action_ledger
    try:
        with action_ledger.browser_session(wait_minutes=40):
            if apply:
                # Revalidar tras la espera, sin elegir ítems con un envío
                # anterior confirmado O incierto (aunque falte en el CSV).
                latest_blocked = {**blocked, **read_blocked()}
                already_attempted = _read_intents()
                # El banco editorial también puede haber cambiado mientras
                # se esperaba el Edge (retirada/corrección de una pregunta).
                # Nunca publicar la instantánea vieja tras el segundo lock.
                latest_bank = load_bank()
                safe_bank = [entry for entry in latest_bank
                             if str(entry["id"]) not in already_attempted]
                item, why = choose(safe_bank, read_log(), blocked=latest_blocked,
                                   allowed=eligible_subs())
                if item is None:
                    print(f"[reddit] no se publica tras esperar el Edge: {why}")
                    return 0
                label = f"r/{item['sub']} [{item.get('flair', '')}] «{item['title']}»"
            # Una caída después de pulsar Publicar es ambigua. El callback
            # se invoca justo antes del clic (ya validado el formulario).
            if apply:
                import circuit_breaker as cb
                allowed, reason = cb.write_preflight("reddit")
                if not allowed:
                    print(f"[reddit] NO se publica: cortacircuitos ABIERTO ({reason})")
                    return 0
                url, removed = publish_post(
                    item, apply=True,
                    before_submit=lambda: _mark_intent(item["id"], "uncertain"))
            else:
                url, removed = publish_post(item, apply=False)
            if apply:
                if not _valid_permalink(url, item["sub"]):
                    print("[reddit] ENVÍO INCIERTO: permalink ausente o incompatible con la comunidad; "
                          "queda bloqueado para revisión manual")
                    return 2
                try:
                    _mark_intent(item["id"], "confirmed", url)
                    record(item, url)
                except Exception as exc:
                    print(f"[reddit] PUBLICADO pero no se pudo registrar en CSV/intent "
                          f"({type(exc).__name__}); NO repetir: {url}")
                    return 2
                if removed:
                    blocked[item["sub"].casefold()] = f"«{item['title'][:50]}» {removed}"
                    write_blocked(blocked)
    except action_ledger.RoundBusy:
        print("[reddit] Edge ocupado hasta agotar la espera: no se publica")
        return 0
    if apply:
        print(f"[reddit] PUBLICADA: {label} -> {url}" + (f" (filtrada: {removed})" if removed else ""))
    else:
        print(f"[reddit] ensayo OK: {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Reddit: comentarios cortos y positivos en hilos sencillos (07/10/2026).

David (07/10): «hay mucha gente que pone fotos de sus estanterias; comentarios positivos, motivadores y breves; que no se note lenguaje IA; como el hilo de libros que
pusimos, donde la gente comenta una frasecita. Seguir las comunidades para que cuente el tiempo.» El karma y la antiguedad de la cuenta se ganan participando: un comentario breve
y amable en un hilo reciente y con pocas respuestas (se ve) vale mas que una pregunta propia en una comunidad que no nos conoce.

Reglas de oficio (REGLAS.md + investigacion 06/10): solo titulos sencillos (foto de estanteria, compras, libro terminado, logro o atasco de escritura, presentaciones);
nada de politica ni de contenido adulto; nunca en hilos que piden opinion sobre un texto propio; sin preguntas, enlaces ni experiencias personales inventadas;
una frase de 1-8 palabras elegida del banco SIN repetir en los ultimos 40 comentarios; un hilo y una comunidad pocas veces por ronda; hilos de menos de 24 h con pocas respuestas.

    python tools/reddit_comments.py [--apply] [--max 3] [--per-sub 2] [--join]
        sin --apply: escanea y muestra el plan, no comenta ni se une a nada
"""
from __future__ import annotations

import csv
import datetime
import json
import os
import random
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(__file__))
import reply_writer as rw

ROOT = os.path.join(os.path.dirname(__file__), "..")
STATES = os.path.join(ROOT, "00_OPERATIVO", "reddit_comunidades.json")
REGISTRO = os.path.join(ROOT, "SISTEMA_DIARIO_REDDIT", "registro_interacciones.csv")
MAX_AGE_HOURS = 24
MAX_COMMENTS_IN_THREAD = 40
REUSE_WINDOW = 40            # comentarios de Reddit recientes cuyas frases no se repiten
DEFAULT_SUBS = ["libros", "escribir", "escritura", "LectoresArg", "ClubdelecturaChile", "libros_arg", "cosmere_es", "filosofia_en_espanol"]

INTENTS = (
    # (intencion, patron sobre el titulo sin tildes ni mayusculas); gana la primera que encaja
    ("writing_win", re.compile(r"(termine (mi |el |la )?(novela|borrador|manuscrito|libro|relato)|acabe (mi |el |la )?(novela|borrador|manuscrito)|primer borrador|mi primera novela|he publicado|publique (mi|mi primera)|por fin (termine|acabe|publique))")),
    ("writing_struggle", re.compile(r"(bloqueo|no consigo (escribir|avanzar)|me cuesta (escribir|seguir)|atascad[oa]|no me sale|sin inspiracion|no se como seguir)")),
    ("shelf", re.compile(r"(estanteria|estanterias|biblioteca (de |en )?(casa|mi)|mi biblioteca|mi coleccion|mis libros|rincon de lectura|mi rincon|mi libreria|mi pared de libros|mi cuarto de lectura|mini biblioteca|libritos|mis nuevos libros)")),
    ("haul", re.compile(r"(ultima compra|mis compras|nueva adquisicion|nuevas adquisiciones|haul|joyitas|me han regalado|me regalaron|llegaron|me llego|mi pila|pila de pendientes|tbr|encontre en|feria del libro|compre hoy|de segunda mano|mi botin|lecturas? de (septiembre|octubre|noviembre|diciembre|enero|febrero|marzo|abril|mayo|junio|julio|agosto)|(septiembre|octubre|noviembre|agosto) en lecturas|se retoma la lectura)")),
    ("finished", re.compile(r"(acabo de (terminar|leer|acabar)|termine de leer|he terminado|recien terminad|por fin lei|ya lei |resena de|reseña de)")),
    ("birthday", re.compile(r"(mi cumpleanos|mejor cumpleanos|cumpleanos feliz|de cumple)")),
    ("welcome", re.compile(r"(me presento|nuevo por aqui|nueva por aqui|nuevo en (este|el) (sub|grupo|foro)|primer post|primera publicacion|hola a todos|hola a todas|hola comunidad)")),
)

PENDING_TEXT = "(pendiente de ChatGPT)"      # 08/10: ya no existe ningun banco de frases; el texto de TODO comentario lo escribe ChatGPT (reply_writer/reply_queue) y el ejecutor rechaza el que no venga de ahi


# Respuestas a quien comenta en NUESTROS hilos (07/10, David: «la gente ha comentado bastante en el hilo de los finales: darles protagonismo, generar comunidad»).
EMOTIVE = re.compile(r"(dolio|duele|llore|llorar|lloro|tristeza|triste|enoje|decepcion|impact|devast|desgarr|golpe|sin aliento|me marco|aun pienso|todavia pienso|no lo esperaba|tremend)")
FUNNY = re.compile(r"(jaja|jeje|xd|😂|🤣)")


def _fold(text):
    return "".join(ch for ch in unicodedata.normalize("NFD", (text or "").lower()) if unicodedata.category(ch) != "Mn")


REQUEST = re.compile(r"(recomi?end|vale la pena|recs\b|sugerenc|busco (un |algun |alguna )?(libro|novela|saga|lectura)|que (libro|novela|saga)s? (leer|leo|empiezo)|necesito (un|una) (libro|novela|saga)|algun libro para)")
GENRES = (
    ("romantasy", re.compile(r"(romantasy|acotar|romance fantas)")),
    ("fantasia", re.compile(r"(fantasia|fantasy|magia|dragones|epic[ao])")),
    ("terror", re.compile(r"(terror|horror|gotico)")),
    ("misterio", re.compile(r"(misterio|policial|thriller|detective|novela negra|crimen)")),
    ("scifi", re.compile(r"(ciencia ficcion|sci-?fi|distopi)")),
    ("asiatica", re.compile(r"(asiatic|japon|coreano|china)")),
    ("juvenil", re.compile(r"(adolescent|joven adulto|young adult|juvenil)")),
    ("inicio", re.compile(r"(iniciar|empezar (en|a)|primer libro|no soy (muy )?lector|volver a leer|quiero leer mas)")),
)
# titulos reales y conocidos por genero (recomendar un libro no inventa ninguna experiencia propia)


def genre_of(title):
    folded = _fold(title)
    for genre, pattern in GENRES:
        if pattern.search(folded):
            return genre
    return None


def classify(title, post_type=""):
    """Intencion del hilo por su titulo o None. Excluye preguntas, peticiones de opinion, politica y contenido adulto."""
    import scan_common as sc
    if not title or sc.asks_for_opinion(title) or sc.is_political(title):
        return None
    folded = _fold(title)
    if re.search(r"(megahilo|hilo (semanal|mensual|diario)|normas|reglas|moderador|\bmods?\b)", folded):
        return None
    if REQUEST.search(folded) and genre_of(title):
        return "recommend"
    if "?" in title or "¿" in title:
        return None
    for intent, pattern in INTENTS:
        if pattern.search(folded):
            return intent
    return None


def _norm(text):
    return " ".join((text or "").casefold().split()).strip(" .,!;")


def recent_texts(registro=REGISTRO, window=REUSE_WINDOW):
    used = []
    try:
        with open(registro, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("tipo") in ("comentario", "comment", "respuesta") and row.get("resultado") in ("confirmado", "publicado") and (row.get("texto_usado") or "").strip():
                    used.append(_norm(row["texto_usado"]))
    except OSError:
        pass
    return set(used[-window:])


def commented_today(registro=REGISTRO, today=None):
    """{subreddit: comentarios confirmados hoy} y total de hoy."""
    today = (today or datetime.date.today()).isoformat()
    per_sub, total = {}, 0
    try:
        with open(registro, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("fecha") == today and row.get("tipo") in ("comentario", "comment") and row.get("resultado") in ("confirmado", "publicado"):
                    sub = (row.get("subreddit") or "").strip()
                    per_sub[sub] = per_sub.get(sub, 0) + 1
                    total += 1
    except OSError:
        pass
    return per_sub, total


def _age_hours(stamp, now=None):
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        when = datetime.datetime.fromisoformat(re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", stamp.replace("Z", "+00:00")))
        # Las horas locales sin zona no certifican fecha del post.
        if when.tzinfo is None or when.utcoffset() is None:
            return None
        now = now or datetime.datetime.now(datetime.timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            return None
        return (now - when).total_seconds() / 3600
    except (ValueError, TypeError, OverflowError):
        return None

def build_plan(threads, *, max_comments, per_sub=2, used=frozenset(), done_keys=frozenset(), rng=None, now=None, my_user="AutoraDemoEscritor", checker=None):
    """threads: dicts con subreddit, title, url, author, comment_count, post_type, created. Devuelve acciones `comment` de frase corta del banco."""
    rng = rng or random
    used = set(used)
    per, plan = {}, []
    ordered = sorted(threads, key=lambda t: (t.get("comment_count", 0) > 15, t.get("comment_count", 0)))     # primero los que casi no tienen respuestas
    for t in ordered:
        if len(plan) >= max_comments:
            break
        sub = str(t.get("subreddit", "")).replace("r/", "")
        if per.get(sub, 0) >= per_sub or str(t.get("author", "")).casefold() == my_user.casefold():
            continue
        if t.get("comment_count", 0) > MAX_COMMENTS_IN_THREAD or t.get("url") in done_keys:
            continue
        age = _age_hours(t.get("created"), now)
        if age is None or age > MAX_AGE_HOURS:
            continue  # sin fecha del post no preparar texto que el ejecutor omitirá
        intent = classify(t.get("title"), t.get("post_type"))
        if not intent:
            continue
        per[sub] = per.get(sub, 0) + 1
        plan.append({"kind": "comment", "subreddit": sub, "url": t["url"], "post_created_at": t.get("created"), "text": PENDING_TEXT, "motivo": f"karma:{intent}:{t.get('title', '')[:60]}"})      # el texto lo escribe ChatGPT despues (write_comment_texts)
    return plan


def post_text_for_gpt(sub, title, body=""):
    """08/10: ChatGPT recibe el TÍTULO y el TEXTO del post (no solo el título: «Audiolibros» a secas daba comentarios sin sentido).
    Devuelve (texto, contexto) o ("", "") si no hay nada concreto a lo que responder (título vago y sin texto)."""
    title, body = " ".join(str(title or "").split()), " ".join(str(body or "").split())[:600]
    if len(re.findall(r"\w+", body)) >= 8:
        return f"{title}. {body}" if title else body, f"post de r/{str(sub).replace('r/', '')}: se da el título y el texto; comentario suelto muy breve sobre lo que cuenta"
    if len(re.findall(r"\w+", title)) >= 4:
        return title, f"post de r/{str(sub).replace('r/', '')} (solo hay título); comentario suelto muy breve sobre lo que dice el título, sin suponer nada más"
    return "", ""


def write_comment_texts(plan, threads, log=print):
    """07/10: los comentarios sueltos ya no salen del banco de frases: los escribe ChatGPT (cola de respuestas, sin esperar el navegador) a partir del TITULO del hilo. Un comentario sin texto
    escrito todavia se quita del plan y se hara en una ronda posterior (se encolo)."""
    if not plan:
        return plan
    try:
        import reply_queue
        by_url = {t["url"]: t for t in threads}
        items = []
        for a in plan:
            thread = by_url.get(a["url"], {})
            text, context = post_text_for_gpt(a.get("subreddit", ""), thread.get("title", ""), thread.get("body", ""))
            if text:
                items.append({"id": a["url"], "network": "reddit_micro", "author": thread.get("author", ""), "text": text, "context": context})
        got = reply_queue.get_or_enqueue(items, "reddit_micro", log)
    except Exception as exc:
        log(f"[reddit] comentarios sin escribir ({type(exc).__name__}: {str(exc)[:80]}): no se comenta esta ronda")
        got = {}
    return [{**a, "text": got[a["url"]]} for a in plan if got.get(a["url"])]


def load_states():
    try:
        with open(STATES, encoding="utf-8") as stream:
            return {k: v for k, v in json.load(stream).items() if not k.startswith("_")}
    except (OSError, ValueError):
        return {}


def active_subs(states=None):
    """Comunidades donde se comenta: las que no estan solo DISCOVERED, mas las de DEFAULT_SUBS."""
    states = states if states is not None else load_states()
    names = [n for n, v in states.items() if isinstance(v, dict) and v.get("state") in ("COMMENTING", "POST_ELIGIBLE")]
    for n in DEFAULT_SUBS:
        if n not in names and states.get(n, {}).get("state") != "DISCOVERED":
            names.append(n)
    return names


_JS_THREADS = """() => [...document.querySelectorAll('shreddit-post')].slice(0, 40).map(e => ({
    permalink: e.getAttribute('permalink'), title: e.getAttribute('post-title'), author: e.getAttribute('author'),
    comments: e.getAttribute('comment-count'), score: e.getAttribute('score'), type: e.getAttribute('post-type'),
    created: e.getAttribute('created-timestamp'), sub: e.getAttribute('subreddit-prefixed-name'),
    body: ((e.querySelector('[slot="text-body"]') || {}).innerText || '').trim().slice(0, 600)}))"""


def scan_threads(pg, names, log=print):
    import reddit_interact as r
    threads = []
    for name in names:
        try:
            r._dump_subreddit(pg, name, "new")
            pg.wait_for_timeout(1500)
            rows = pg.evaluate(_JS_THREADS)
        except r.BotWarningDetected:
            raise
        except Exception as exc:
            log(f"  r/{name}: {type(exc).__name__}")
            continue
        got = 0
        for row in rows:
            if not row.get("permalink"):
                continue
            threads.append({"subreddit": row.get("sub") or f"r/{name}", "title": row.get("title") or "", "url": f"https://www.reddit.com{row['permalink']}", "author": row.get("author") or "",
                            "comment_count": int(row.get("comments") or 0), "score": int(row.get("score") or 0), "post_type": row.get("type") or "", "created": row.get("created") or "", "body": row.get("body") or ""})
            got += 1
        log(f"  r/{name}: {got} hilos nuevos leidos")
    return threads


def join_subreddit(pg, name, log=print):
    """Se une a la comunidad (cuenta la antiguedad de membresia). Devuelve 'unido', 'ya' o 'no_encontrado'.
    Solo toca el boton de ESTA comunidad (`shreddit-join-button[name=...]`): la barra lateral muestra botones de otras."""
    import reddit_interact as r
    r._dump_subreddit(pg, name, "new")
    pg.wait_for_timeout(2000)
    host = pg.locator(f'shreddit-join-button[name="{name}" i]').first
    if not host.count():
        return "no_encontrado"
    button = host.locator("button").first
    label = (button.inner_text() or "").strip()
    if re.match(r"^(Miembro|Unido|Joined|Member)$", label, re.I):
        return "ya"
    if not re.match(r"^(Unirse|Join)$", label, re.I):
        return "no_encontrado"
    button.click()
    pg.wait_for_timeout(2500)
    r._check_bot_warning(pg)
    after = (host.locator("button").first.inner_text() or "").strip()
    return "unido" if re.match(r"^(Miembro|Unido|Joined|Member)$", after, re.I) else "no_confirmado"


def check_reply(text):
    """Una respuesta nuestra a un comentario: una sola linea de hasta 14 palabras y 100 caracteres, como mucho UNA pregunta, sin enlaces ni listas."""
    stripped = (text or "").strip()
    words = re.findall(r"[^\W_]+", stripped)
    problems = []
    if not words or len(words) > 24:
        problems.append(f"{len(words)} palabras (1-24)")
    if len(stripped) > 160:
        problems.append("mas de 160 caracteres")
    if "\n" in stripped or stripped.count("?") > 1 or re.search(r"https?://|www\.", stripped):
        problems.append("una linea, una pregunta como mucho, sin enlaces")
    if problems:
        raise ValueError("respuesta no valida: " + "; ".join(problems))


def reply_kind(text):
    """Banco de respuesta para un comentario ajeno o None si no conviene responder (preguntas, enlaces, autopromocion, otro idioma, demasiado largo o vacio)."""
    import scan_common as sc
    raw = (text or "").strip()
    folded = _fold(raw)
    if not (4 <= len(raw) <= 400) or "?" in raw or re.search(r"(https?://|www\.|\binstagram\b|\bagreg|\bsigueme\b|\bmi canal\b|\bmi libro\b|\bmi novela\b)", folded):
        return None
    if sc.is_political(raw) or sc.asks_for_opinion(raw):
        return None
    if re.search(r"\b(eu|nao|realmente nao|the|and|was|this)\b", folded):
        return None          # portugues / ingles: no se responde con frases en castellano
    if FUNNY.search(folded) and len(raw) < 80:
        return "humor"
    if EMOTIVE.search(folded):
        return "empathic"
    return "title" if len(raw.split()) <= 7 else "explained"


_JS_COMMENTS = """() => [...document.querySelectorAll('shreddit-comment')].map(e => ({id: e.getAttribute('thingid'), author: e.getAttribute('author'), depth: parseInt(e.getAttribute('depth') || '0', 10),
    created: e.getAttribute('created-timestamp') || e.querySelector('time[datetime]')?.getAttribute('datetime') || '',
    text: ((e.querySelector('[slot=comment]') || {}).innerText || '').trim()}))"""


def replied_comment_ids(registro=REGISTRO):
    """Identificadores de comentarios ajenos a los que ya respondimos (clave `<hilo>#<id>` en la columna de URL)."""
    done = set()
    try:
        with open(registro, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("tipo") == "respuesta" and "#" in (row.get("hilo_url") or ""):
                    done.add(row["hilo_url"].split("#", 1)[1])
    except OSError:
        pass
    return done


def plan_replies(comments, *, done_ids=frozenset(), used=frozenset(), max_replies=4, rng=None, me="AutoraDemoEscritor"):
    """comments: dicts id/author/depth/text en orden de pagina. Respuestas a comentarios raiz de otros que aun no tienen respuesta nuestra (ni en el registro ni en la pagina)."""
    import conversation_turn_policy as ctp
    rng = rng or random
    used = set(used)
    mine_after = set()
    for i, c in enumerate(comments):                    # un hijo nuestro justo despues del padre => ya respondido
        if str(c.get("author", "")).casefold() == me.casefold() and i > 0:
            mine_after.add(comments[i - 1].get("id"))
    plan = []
    for c in comments:
        if len(plan) >= max_replies:
            break
        author = str(c.get("author") or "")
        if c.get("depth", 0) != 0 or not c.get("id") or author.casefold() in (me.casefold(), "automoderator", "[deleted]", ""):
            continue
        cid = str(c["id"])
        if cid in done_ids or cid in mine_after:
            continue
        kind = reply_kind(c.get("text"))
        if not kind or ctp.is_closed_turn(c.get("text")):
            continue                     # 08/10: «gracias», «jaja», «genial»... cierran la conversación: no se contesta por contestar
        plan.append({"id": cid, "author": author, "text": PENDING_TEXT, "kind": kind, "post_created_at": c.get("created") or c.get("created_at") or "", "snippet": (c.get("text") or "")[:60], "full": (c.get("text") or "")[:500]})
    return plan


def _own_thread_urls(registro=REGISTRO, days=14, today=None):
    today = today or datetime.date.today()
    urls = []
    try:
        with open(registro, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("tipo") != "post" or row.get("resultado") not in ("confirmado", "publicado"):
                    continue
                try:
                    when = datetime.date.fromisoformat(row.get("fecha", ""))
                except ValueError:
                    continue
                if (today - when).days <= days and row.get("hilo_url") not in urls:
                    urls.append(row["hilo_url"])
    except OSError:
        pass
    return urls


def upvote_comment(node):
    """Voto positivo al comentario si aun no lo tiene (da movimiento y es de buena educacion con quien participa). No falla si el boton no aparece."""
    try:
        button = node.get_by_role("button", name=re.compile(r"(Votar a favor|Upvote)", re.I)).first
        if button.count() and (button.get_attribute("aria-pressed") or "false") != "true":
            button.click(timeout=5000)
            return True
    except Exception:
        pass
    return False


def _check_own_thread_reply_age(item):
    """Comprueba la fecha del COMENTARIO entrante, nunca la del hilo propio."""
    import conversation_turn_policy as ctp
    return ctp.check_execution("reddit", {
        "kind": "reply", "reply_to_us": True,
        "post_created_at": item.get("post_created_at"),
        "post_text": item.get("full"),
        "target_post_id": item.get("id"),
    })


def reply_in_thread(pg, thread_url, item, log=print):
    """Vota a favor y responde al comentario `item['id']` del hilo abierto. Limpia el borrador (Reddit lo guarda y el texto se concatenaba: «Qué buen libro.Qué buen libro.», 07/10),
    comprueba que lo escrito es EXACTAMENTE la frase y verifica tras recargar que aparece como respuesta nuestra. Devuelve True/False."""
    import reddit_interact as r
    allowed, why = _check_own_thread_reply_age(item)
    if not allowed:
        log(f"[reddit] respuesta en hilo propio omitida: {why}")
        return False
    check_reply(item["text"])
    r._check_spanish_orthography(item["text"].replace("¿", "").replace("?", ""))
    node = pg.locator(f'shreddit-comment[thingid="{item["id"]}"]').first
    if not node.count():
        return False
    node.scroll_into_view_if_needed()
    node.hover()
    pg.wait_for_timeout(1200)
    # Al responder no se vota automáticamente a favor.
    button = node.get_by_role("button", name="Responder")
    if not button.count():
        return False
    button.first.click(timeout=10000)
    pg.wait_for_timeout(1500)
    box = node.locator("shreddit-composer [contenteditable='true']").first
    box.click(timeout=10000)
    pg.keyboard.press("Control+A")
    pg.keyboard.press("Delete")
    box.type(item["text"], delay=9)
    pg.wait_for_timeout(500)
    typed = " ".join((box.inner_text() or "").split())
    if typed != " ".join(item["text"].split()):
        node.locator("shreddit-composer button").filter(has_text="Cancelar").first.click(timeout=5000)
        log(f"   borrador distinto de la frase ({typed[:50]!r}): no se envia")
        return False
    send = node.locator("shreddit-composer button[type='submit']").last          # el texto del boton lleva espacios/saltos: no se filtra por texto (probado en vivo 07/10)
    send.click(timeout=10000)
    pg.wait_for_timeout(2500)
    r._check_bot_warning(pg)
    pg.reload(wait_until="domcontentloaded", timeout=25000)
    pg.wait_for_timeout(3000)
    r._check_bot_warning(pg)
    snippet = _norm(item["text"])
    for c in pg.evaluate(_JS_COMMENTS):
        if str(c.get("author", "")).casefold() == r.MY_USERNAME.casefold() and c.get("depth", 0) >= 1 and _norm(c.get("text")) == snippet:
            return True
    return False


def _gpt_comment(sub, title, author, log=print, context=None):
    """Comentario suelto de ChatGPT (cola de respuestas, sin esperar el navegador) para un hilo concreto; None si todavia no esta escrito o ChatGPT no ve nada que decir."""
    try:
        import reply_queue
        got = reply_queue.get_or_enqueue([{"id": "e", "network": "reddit_micro", "author": author, "text": title,
                                           "context": context or f"post de r/{sub} (solo hay título); comentario suelto muy breve"}], "reddit_micro", log)
        return got.get("e")
    except Exception as exc:
        log(f"[reddit] comentario sin escribir ({type(exc).__name__}: {str(exc)[:60]})")
        return None


def engage_user(pg, username, log=print):
    """Tras responder a quien comenta en nuestro hilo: seguirle (si no le seguimos) y, si tiene una publicacion reciente (<= 5 dias) en una de nuestras comunidades que encaje con una intencion
    sencilla (estanteria, compra, libro terminado...), dejarle un comentario breve. Devuelve ('seguido'|'ya'|'no', url_comentada|None)."""
    import reddit_interact as r
    followed = "no"
    pg.goto(f"https://www.reddit.com/user/{username}/", wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_timeout(3000)
    r._check_bot_warning(pg)
    if pg.get_by_role("button", name=re.compile(r"^Dejar de seguir$", re.I)).count():
        followed = "ya"
    else:
        button = pg.get_by_role("button", name=re.compile(r"^Seguir$", re.I))
        if button.count():
            button.first.click(timeout=8000)
            pg.wait_for_timeout(2000)
            followed = "seguido" if pg.get_by_role("button", name=re.compile(r"^Dejar de seguir$", re.I)).count() else "no"
    pg.goto(f"https://www.reddit.com/user/{username}/submitted/", wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_timeout(3000)
    posts = pg.evaluate("""() => [...document.querySelectorAll('shreddit-post')].slice(0, 6).map(e => ({title: e.getAttribute('post-title') || '', sub: (e.getAttribute('subreddit-prefixed-name') || '').replace('r/', ''),
        created: e.getAttribute('created-timestamp') || '', permalink: e.getAttribute('permalink') || '', type: e.getAttribute('post-type') || '',
        body: ((e.querySelector('[slot="text-body"]') || {}).innerText || '').trim().slice(0, 600)}))""")
    allowed = {n.casefold() for n in active_subs()}
    import post_age_policy as age_policy
    max_age_h = age_policy.MAX_AGE_DAYS["comment"] * 24
    used = recent_texts()
    for post in posts:
        age = _age_hours(post.get("created"))
        if age is None or age > max_age_h or post["sub"].casefold() not in allowed or not post["permalink"]:
            continue
        intent = classify(post["title"], post.get("type"))
        if not intent:
            continue
        if intent == "recommend":
            continue                      # en el hilo de otra persona no se recomienda a ciegas
        text, context = post_text_for_gpt(post["sub"], post["title"], post.get("body", ""))
        if not text:
            continue                      # titulo vago («Audiolibros») y sin texto: no hay nada concreto a lo que responder
        written = _gpt_comment(post["sub"], text, username, log, context=context)
        if not written:
            continue                      # sin texto de ChatGPT no se comenta (el follow ya esta hecho)
        return followed, {"url": f"https://www.reddit.com{post['permalink']}", "text": written,
                          "post_created_at": post["created"], "intent": intent,
                          "title": post["title"]}
    return followed, None


def _publish_profile_comment(extra, *, log=print, publish=None):
    """Apply the shared policy immediately before the secondary comment."""
    import conversation_turn_policy as ctp
    # Sin kind, el contrato común consideraba esta escritura una acción sin límite.
    extra = {**extra, "kind": "comment"}
    permitted, reason = ctp.check_execution("reddit", extra)
    if not permitted:
        log(f"[reddit] comentario en perfil omitido: {reason}")
        return False
    if publish is None:
        import reddit_interact as ri
        publish = ri.comment
    publish(extra["url"], extra["text"])
    return True


def run_replies(pg, max_replies=4, apply=False, rng=None, log=print):
    """Respuestas breves a quienes comentan en nuestros hilos de los ultimos 14 dias. Devuelve el numero confirmado."""
    import reddit_interact as r
    import scan_common as sc
    done = replied_comment_ids()
    confirmed = 0
    engaged = 0
    for thread in _own_thread_urls():
        if confirmed >= max_replies:
            break
        pg.goto(thread, wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(3500)
        r._check_bot_warning(pg)
        comments = pg.evaluate(_JS_COMMENTS)
        plan = plan_replies(comments, done_ids=done, used=recent_texts(), max_replies=max_replies - confirmed, rng=rng)
        if plan and apply:
            try:
                title = pg.evaluate("() => (document.querySelector('shreddit-post') || {getAttribute: () => ''}).getAttribute('post-title') || ''")
                # 08/10: ChatGPT NO se invoca desde aqui (dentro de este navegador Playwright fallaba con «Sync API inside the asyncio loop» y con el banco quitado no se
                # respondia nunca): se encola en la cola de respuestas, que escribe el trabajador aparte, y la respuesta se publica en la siguiente ejecucion.
                import reply_queue
                written = reply_queue.get_or_enqueue([{"id": f"c{n}", "network": "reddit", "author": item["author"], "reply_to_us": True, "text": item["full"],
                                                       "context": f"comentario de esta persona en NUESTRO hilo de Reddit «{title}»; respóndele a lo que dice ella (si es un cierre o no aporta nada nuevo, null)"}
                                                      for n, item in enumerate(plan)], "reddit", log)
                for n, item in enumerate(plan):
                    if f"c{n}" in written:
                        item["text"] = written[f"c{n}"]
                        item["gpt"] = True
            except Exception as exc:
                log(f"[reddit] escritor no disponible ({type(exc).__name__}); no se responde")
            # 08/10 (David vio en directo respuestas sin sentido, p. ej. «¿lo recomiendas sin spoilers?» a quien puso «Audiolibros»): NUNCA se publica una frase de banco; solo lo escrito por ChatGPT con el contexto del comentario
            plan = [item for item in plan if item.get("gpt")]
        log(f"[reddit] {thread}: {len(comments)} comentarios, {len(plan)} respuestas planeadas")
        for item in plan:
            log(f"   -> {item['author']}: «{item['snippet']}» => {item['text']}")
            if not apply:
                continue
            try:
                ok = reply_in_thread(pg, thread, item, log)
            except r.BotWarningDetected:
                raise
            except Exception as exc:
                log(f"   FALLO: {type(exc).__name__}: {str(exc)[:120]}")
                ok = False
            if ok:
                confirmed += 1
                done.add(item["id"])
                if apply and engaged < 4:
                    engaged += 1
                    try:
                        followed, extra = engage_user(pg, item["author"], log)
                        log(f"   usuario {item['author']}: {followed}" + (f"; comentario en su publicacion: {extra['text']}" if extra else ""))
                        with open(REGISTRO, "a", newline="", encoding="utf-8") as stream:
                            if followed == "seguido":
                                csv.writer(stream).writerow([datetime.date.today().isoformat(), f"u/{item['author']}", "", "seguir_usuario", "", "confirmado", "karma:autor_de_comentario"])
                        if extra:
                            if not _publish_profile_comment(extra, log=log, publish=r.comment):
                                extra = None
                        if extra:
                            with open(REGISTRO, "a", newline="", encoding="utf-8") as stream:
                                csv.writer(stream).writerow([datetime.date.today().isoformat(), "r/" + extra["url"].split("/r/")[1].split("/")[0], extra["url"], "comentario", extra["text"], "confirmado",
                                                             f"karma:perfil:{extra['intent']}"])
                    except r.BotWarningDetected:
                        raise
                    except Exception as exc:
                        log(f"   (seguir/comentar a {item['author']} fallo: {type(exc).__name__})")
                    pg.goto(thread, wait_until="domcontentloaded", timeout=30000)
                    pg.wait_for_timeout(3000)
                new = not os.path.exists(REGISTRO)
                with open(REGISTRO, "a", newline="", encoding="utf-8") as stream:
                    csv.writer(stream).writerow([datetime.date.today().isoformat(), thread.split("/comments/")[0].split("reddit.com/")[-1], f"{thread}#{item['id']}", "respuesta", item["text"],
                                                 "confirmado", f"karma:respuesta:{item['kind']}"])
            sc.pause(45, 90)
    return confirmed


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    apply = "--apply" in argv
    max_comments = int(argv[argv.index("--max") + 1]) if "--max" in argv else 3
    per_sub = int(argv[argv.index("--per-sub") + 1]) if "--per-sub" in argv else 2
    daily_cap = int(argv[argv.index("--daily-cap") + 1]) if "--daily-cap" in argv else 12
    do_join = "--join" in argv
    import reply_hold
    if reply_hold.held():
        print("[reddit] respuestas EN REVISION (respuestas_en_revision.flag): hoy no se comenta ni se responde")
        return 0
    import action_ledger
    import reddit_interact as r
    import reddit_execute as ex
    names = active_subs()
    rng = random.Random()
    rng.shuffle(names)
    names = names[:5]                     # 5 comunidades por ronda, rotando
    per_today, total_today = commented_today()
    if total_today >= daily_cap:
        print(f"[reddit] hoy ya hay {total_today} comentarios (tope {daily_cap}); solo respuestas en nuestros hilos")
        names = []
    max_comments = max(0, min(max_comments, daily_cap - total_today))
    with action_ledger.browser_session(wait_minutes=60):
        r.ensure_browser()
        p, pg = r._connect()
        try:
            ok, msg = r._health_check(pg)
            print(msg)
            if not ok:
                return 1
            if do_join and apply:
                for name in names:
                    print(f"[reddit] r/{name}: {join_subreddit(pg, name)}")
            threads = scan_threads(pg, names)
            if "--no-replies" not in argv:
                replies_done = run_replies(pg, max_replies=int(argv[argv.index("--max-replies") + 1]) if "--max-replies" in argv else 12, apply=apply)
                print(f"[reddit] respuestas a comentarios de nuestros hilos: {replies_done}")
        finally:
            p.stop()
        scan_common_done = set()
        try:
            import reddit_scan
            confirmed, uncertain = reddit_scan._thread_history()
            for t in threads:
                key = reddit_scan._thread_key(t["url"])
                if key in confirmed or key in uncertain:
                    scan_common_done.add(t["url"])
        except Exception:
            pass
        plan = build_plan(threads, max_comments=max_comments, per_sub=per_sub, used=recent_texts(), done_keys=scan_common_done, rng=rng, checker=r._check_micro_comment)
        plan = write_comment_texts(plan, threads)
        print(f"[reddit] {len(threads)} hilos leidos; plan de comentarios: {len(plan)}")
        for item in plan:
            print(f"  r/{item['subreddit']} | {item['text']} | {item['url']}")
            print(f"     {item['motivo']}")
        if not apply or not plan:
            return 0
        plan = ex._preflight_plan(plan)
        results = ex.run_plan(plan, prevalidated=True)
        ex._append_registro(results)
        ex._append_metricas(results)
        print("[reddit] " + ", ".join(f"{x['resultado']}" for x in results))
    return 0


if __name__ == "__main__":
    sys.exit(main())

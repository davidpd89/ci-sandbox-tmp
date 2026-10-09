"""X: replies automaticas por INTENCION del post (06/10/2026).

Diagnostico (GPT, 06/10, pesos publicados del algoritmo de X + nuestros datos): la ronda hacia ~90 % de «me gusta» y las replies —la accion visible que mas pesa y la que
muestra a David como lector/escritor con quien conversar— quedaban fuera del plan mecanico (redaccion editorial manual). Aqui se cierra esa salida con PRECISION por delante de
volumen: solo se responde cuando el post encaja claramente en una intencion y la respuesta de esa intencion tiene sentido sin conocer el resto del texto.

Reglas: frases cortas y neutras, sin experiencias personales inventadas (decision de David 03/10), sin enlaces ni mencion a libros propios; ninguna frase se repite antes de
`REUSE_DAYS` dias; nada de pedir opinion sobre trabajo propio (`scan_common.asks_for_opinion` ya descarta esos posts); un reply por cuenta y dia.
"""
from __future__ import annotations

import csv
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

REUSE_DAYS = 7
# publicidad de editoriales/autores (el reply con «¿lo recomendarias?» a un anuncio queda absurdo) y posts con enlace
MARKETING = re.compile(r"(https?://|nuestr[oa]s?|hemos |preventa|a la venta|ya disponible|disponible en|descuento|gratis|enlace en|link en|suscrib|sorteo|te recomiendo|os recomiendo|te recomendaria|recomendamos)")
QUESTION_INTENTS = {"favorite_question"}      # exige pregunta dirigida a la audiencia
BOOKS = r"(libro|libros|novela|novelas|saga|trilogia|lectura|leer|leyendo|fantasia|relato|manuscrito|borrador|capitulo|historia|escrib)"

# (intencion, patron sobre texto sin tildes ni mayusculas); el orden manda: gana la primera que encaja
INTENTS = (
    ("recommendation_request", re.compile(r"(me recomend\w*|alguna recomendacion|recomendadme|recomendaciones\?|busco (un |una |algun |alguna )?(libro|novela|saga|lectura|fantasia)|necesito (un |una )?(libro|novela|saga|recomendacion)|que (libro|novela|saga) (me )?(leo|leer|empiezo))")),
    ("finished_book", re.compile(r"(acabo de (terminar|leer|acabar)|termine de leer|he terminado (de leer )?|recien terminad[oa]|ya termine (el|la|de)|he leido|ya lei |me ha encantado|me encanto|resena de)")),
    ("writing_struggle", re.compile(r"(bloqueo|no consigo|no se como (seguir|continuar|escribir)|me cuesta (escribir|seguir)|atascad[oa]|no me sale)")),
    ("wip_milestone", re.compile(r"(termine (mi|el|la) (novela|manuscrito|borrador|capitulo)|acabe (mi|el|la) (novela|manuscrito|borrador|capitulo)|primer borrador|escribiendo mi (novela|libro)|mi primera novela)")),
    ("reading_now", re.compile(r"(estoy leyendo|leyendo ahora|mi lectura de (hoy|esta semana)|empece (el|la|un|una) (libro|novela|saga)|releyendo)")),
    ("favorite_question", re.compile(r"(cual es (tu|vuestro|vuestra) (libro|saga|personaje)|(vuestro|vuestra|tu) (libro|saga|personaje) favorit|que (libro|saga|personaje) (os|te|les|le) |que estais (leyendo|escribiendo)|que estas (leyendo|escribiendo)|que leeis)")),
)

PENDING_TEXT = "(pendiente de ChatGPT)"      # 08/10 (David): ya no existe ningun banco de frases. El constructor solo decide A QUIEN y con que intencion; el texto lo escribe ChatGPT (reply_writer) y el ejecutor rechaza cualquier texto que no venga de ahi.


def _fold(text):
    return sc._fold(text)


def classify(text):
    """Intencion del post o None. Exige tema de libros/escritura Y que no sea una peticion de opinion sobre trabajo propio ni politica."""
    if not text or sc.asks_for_opinion(text) or sc.is_political(text):
        return None
    folded = _fold(text)
    folded = re.sub(r"(aun |todavia |nunca )?no (he|hemos|lo he|la he|las he|los he|has|ha) (leido|terminado|acabado|visto)", " ", folded)      # «no he leído la saga» no es «he leído»
    if MARKETING.search(folded) or not re.search(BOOKS, folded):
        return None
    for intent, pattern in INTENTS:
        if pattern.search(folded):
            if intent in QUESTION_INTENTS and "?" not in text:
                continue
            return intent
    return None


def recent_phrases(registro_csv, today=None, days=REUSE_DAYS):
    """Textos de reply/comentario usados en los ultimos `days` dias segun el registro (clave: texto sin tildes ni mayusculas)."""
    today = today or datetime.date.today()
    out = set()
    try:
        with open(registro_csv, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("tipo") not in ("reply", "comment", "comentario", "comment_external"):
                    continue
                try:
                    when = datetime.date.fromisoformat(row.get("fecha", ""))
                except ValueError:
                    continue
                if (today - when).days <= days and row.get("texto_usado"):
                    out.add(_fold(row["texto_usado"]).strip())
    except OSError:
        pass
    return out


def choose_phrase(intent, used, rng):
    """Marcador de texto pendiente para una intencion conocida (None si no hay intencion): nunca una frase hecha."""
    return PENDING_TEXT if intent in {name for name, _ in INTENTS} else None


MAX_REPLY_AGE_HOURS = 30      # una reply a un post de hace dos dias casi no la lee nadie


def build_replies(rows, *, max_replies, used, done_urls=frozenset(), recent_handles=frozenset(), rng=None, allow=None):
    """rows: dicts de la reserva (`handle`, `permalink`, `text`, `score`...). Devuelve hasta `max_replies` acciones `reply` con intencion y frase distintas, un reply por cuenta."""
    import random
    rng = rng or random
    plan, handles, used = [], set(recent_handles), set(used)
    for row in rows:
        if len(plan) >= max_replies:
            break
        handle = str(row["handle"]).casefold()
        url = (row.get("permalink") or row.get("url") or "").rstrip("/")
        if not url or url in done_urls or handle in handles or (allow and not allow(handle)):      # 07/10: reciprocidad de comentarios (relationship_policy.comment_filter)
            continue
        if "first_seen" in row:
            import browser_pool
            if browser_pool.estimated_age_hours(row) > MAX_REPLY_AGE_HOURS:
                continue
        intent = classify(row.get("text"))
        if not intent:
            continue
        phrase = choose_phrase(intent, used, rng)
        if not phrase:
            continue
        used.add(_fold(phrase).strip())
        handles.add(handle)
        plan.append({"kind": "reply", "url": url, "handle": row["handle"], "text": phrase, "bank": True, "post_text": (row.get("text") or "")[:500], "motivo": f"growth:reply:{intent}:src={row.get('source', '')}"})
    return plan


REPLIES_BY_STAGE = {0: 4, 1: 6, 2: 8, 3: 8, 4: 10, 5: 10}      # por ronda; GPT propone ~10-15 replies/dia al principio: 4 rondas x 3 = 12


def replies_per_round(stage):
    return REPLIES_BY_STAGE.get(int(stage), 3)


def replied_handles(registro_csv, today=None, days=3):
    """Cuentas (minusculas) a las que ya respondimos en los ultimos `days` dias (el registro guarda la URL del post: x.com/<cuenta>/status/<id>)."""
    today = today or datetime.date.today()
    out = set()
    try:
        with open(registro_csv, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("tipo") != "reply":
                    continue
                try:
                    when = datetime.date.fromisoformat(row.get("fecha", ""))
                except ValueError:
                    continue
                match = re.match(r"https://x\.com/([^/]+)/status/", row.get("post_resumen") or "")
                if match and (today - when).days <= days:
                    out.add(match.group(1).casefold())
    except OSError:
        pass
    return out

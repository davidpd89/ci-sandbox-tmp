"""Utilidades compartidas por las 9 redes - extraido el 22/09 al construir
el tercer scan (Instagram) y ver que las mismas funciones se iban a copiar
literal. Ampliado a fondo el 23/09 (a peticion explicita de David: "actua
como buen arquitecto... que lo que invirtamos en una beneficie al resto")
tras encontrar el mismo bug corregido por separado en Threads e Instagram
el mismo dia (silent-failure en like/reply/follow) y una excepcion
(AlreadyCommented) definida 8 veces con el mismo codigo exacto. Ahora
tambien vive aqui: las excepciones compartidas (ActionTargetNotFound,
AlreadyCommented), el heuristico de "invita a conversacion" y el filtro
unico de candidato (is_valid_candidate). Nunca importar nada de aqui que
sea especifico de una sola red - si hace falta, ese trozo se queda en su
propio *_scan.py/*_interact.py. Un fix aqui se propaga solo a las 9 redes
la proxima vez que corran; no hace falta ir fichero por fichero cuando
aparezca el mismo tipo de bug otra vez.
"""
import csv
import re
import unicodedata

import os
import random
import time

import adult_filter

# Frases inequívocas y raíces con límite de palabra: evita que «pp » salte
# dentro de «app » o que «vox» coincida dentro de otra palabra.
# El texto se normaliza para detectar Sánchez/Feijóo con o sin tildes.
POLITICAL_TERMS = (
    r"\b(?:psoe|vox|partido podemos|movimiento sumar|coalicion sumar|"
    r"grupo parlamentario plurinacional sumar|partido popular|"
    r"junts(?: per catalunya)?|erc|esquerra republicana(?: de catalunya)?|"
    r"eh bildu|eaj-pnv|pnv|bng|bloque nacionalista galego|"
    r"coalicion canaria|upn|union del pueblo navarro|grupo parlamentario republicano|grupo mixto|"
    r"pedro sanchez|feijoo|abascal|ayuso|almeida|yolanda diaz|irene montero|netanyahu|trump|biden|"
    r"franco|franquismo|franquista|dictadura|genocidi\w*|"
    r"palestin\w*|israel\w*|ucrani\w*|ukrain\w*|"
    r"elecciones\b|eleccion (?:general|presidencial|autonomica|municipal|europea)|campana electoral|"
    r"referendum|referendo|mocion de censura|partido politico|grupo parlamentario|"
    r"pleno del congreso|sesion parlamentaria de control|control al gobierno|"
    r"real decreto-ley|decreto-ley|"
    r"actualidad politica|debate politico|crisis politica|"
    r"politica (?:espanola|nacional|internacional|electoral)|"
    r"gobierno (?:anuncia|aprueba|propone|presenta|negocia|rechaza)|"
    r"consejo de ministros|congreso de los diputados|senado espanol|"
    r"parlamento europeo|tribunal constitucional|union europea|otan|moncloa|"
    r"presupuestos generales del estado|gobierno de espana|gobierno espanol|"
    r"diputad\w*|senador(?:a|es|as)?|parlament\w*|"
    r"ministr[oa]s?|presidente del gobierno|"
    r"desahuci\w*|desalojos? forzos\w*|"
    r"ley de vivienda|ley de alquileres|"
    r"extrema derecha|extrema izquierda|"
    r"gobierno traidor|invasores|inmigracion ilegal)\b"
)
_POLITICAL_RE = re.compile(POLITICAL_TERMS)


# Apellidos ambiguos: solo filtrar cuando aparecen cerca de un contexto
# institucional/político. Así "María Sánchez publica una novela" no cae,
# pero "Sánchez responde en el Congreso" sí.
_CASE_SENSITIVE_POLITICAL_RE = re.compile(
    r"\bNATO\b|\bPP\b(?!\s*\.?\s*\d)"
)


_CONTEXTUAL_POLITICAL_RE = re.compile(
    r"\bsanchez\b(?=.{0,80}\b(?:psoe|gobierno|presidente|moncloa|congreso|senado|"
    r"eleccion\w*|politic\w*|ministr[oa]s?)\b)|"
    r"\b(?:psoe|gobierno|presidente|moncloa|congreso|senado|eleccion\w*|politic\w*|"
    r"ministr[oa]s?)\b.{0,80}\bsanchez\b"
)


# "Sumar" y "Podemos" son también verbos comunes. Solo tratarlos como
# partidos cuando el entorno textual aporta una señal política/institucional.
_AMBIGUOUS_PARTY_RE = re.compile(
    r"\b(?:sumar|podemos|pp)\b(?=.{0,80}\b(?:partido|coalicion|grupo parlamentario|"
    r"gobierno|congreso|diputad\w*|eleccion\w*|politic\w*|ministr[oa]s?|"
    r"feijoo|propone|negocia|vota|aprueba|rechaza)\b)|"
    r"\b(?:partido|coalicion|grupo parlamentario|gobierno|congreso|diputad\w*|"
    r"eleccion\w*|politic\w*|ministr[oa]s?|feijoo|propone|negocia|vota|"
    r"aprueba|rechaza)\b.{0,80}\b(?:sumar|podemos|pp)\b"
)


# Excepciones muy estrechas para el nicho de fantasía del proyecto.
# No basta con que aparezca "novela": eso podría envolver política real.
#
# Ampliado 28/09/2026 al revisar la PR en vivo (probando casos reales, no
# solo los tests que ya traía): "parlamento"/"senador" también aparecen en
# literatura clásica y ficción histórica sin ser política real -
# "El Parlamento de las Aves" (Chaucer) o un senador romano en una novela
# histórica se filtraban como si fueran actualidad política. Las dos
# excepciones nuevas son igual de estrechas que las que ya había (un motivo
# literario/histórico concreto, no "novela" en general) para no reabrir el
# hueco que esta PR cerró con "Sumar"/"Podemos"/apellidos ambiguos.
_FICTIONAL_POLITICAL_RE = re.compile(
    r"\b(?:parlament\w* (?:elfic\w*|magic\w*)|"
    r"parlament\w* (?:del|de la|de los|de las) (?:reino|imperio|mundo|universo|magos|hechiceros)|"
    r"parlament\w* (?:de|del) (?:el |la |los |las )?(?:aves|pajaros|animales|bestias|dragones|criaturas)|"
    r"dictadura (?:de|del|de la|de los|de las) (?:los )?(?:magos|hechiceros|reino|imperio)|"
    r"ministr[oa] (?:de magia|del reino|del imperio)|"
    r"senador\w* (?:galactic\w*|del reino|del imperio|romano\w*|de roma)|"
    r"senado romano|"
    r"diputad\w* (?:del reino|del imperio))\b"
)


def is_political(text):
    """Filtro de 'no tocar este contenido': politica/activismo (heuristico) Y ligue/sexo/chat de citas
    (`adult_filter`, 03/10/2026, pedido de David tras likes a cuentas de ligue). Sirve tambien para biografias.
    """
    return _is_political_core(text) or adult_filter.is_adult_or_dating(text)


def _is_political_core(text):
    """Filtro conservador de cribado: incluye noticia/cita/repost textual.

    La clasificación no sustituye la lectura editorial. Un repost sin texto
    original disponible no se puede evaluar: la capa de scan debe aportar el
    texto del contenido citado, no solo el del autor que lo comparte.
    """
    if text is None or text == "":
        return False
    if not isinstance(text, str):
        # Un candidato externo con texto de tipo inesperado no debe saltarse
        # silenciosamente un filtro conservador. Se descarta antes de sugerirlo.
        return True
    case_sensitive_hit = bool(_CASE_SENSITIVE_POLITICAL_RE.search(text))
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = " ".join(normalized.split())  # noticias/quotes pueden partir nombres en líneas
    if _FICTIONAL_POLITICAL_RE.search(normalized):
        # Solo se exime la construcción ficticia concreta. Si el mismo texto
        # contiene además un término político inequívoco, se mantiene el filtro.
        stripped = _FICTIONAL_POLITICAL_RE.sub(" ", normalized)
        return bool(
            case_sensitive_hit
            or _POLITICAL_RE.search(stripped)
            or _CONTEXTUAL_POLITICAL_RE.search(stripped)
            or _AMBIGUOUS_PARTY_RE.search(stripped)
        )
    return bool(
        case_sensitive_hit
        or _POLITICAL_RE.search(normalized)
        or _CONTEXTUAL_POLITICAL_RE.search(normalized)
        or _AMBIGUOUS_PARTY_RE.search(normalized)
    )


def already_interacted_urls(registro_csv_path):
    """URLs donde una conversación quedó realmente confirmada/publicada.

    Un fallo, pendiente, estado incierto o resultado vacío NO acredita que
    hayamos respondido. La comprobación en vivo de cada red sigue siendo la
    garantía final; esta capa solo evita resugerencias obvias.
    """
    urls = set()
    if not os.path.exists(registro_csv_path):
        return urls
    with open(registro_csv_path, encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            kind = (row.get("tipo") or "").strip().casefold()
            if kind not in ("reply", "quote", "comment", "comentario", "comment_external"):
                continue
            outcome = (row.get("resultado") or "").strip().casefold()
            if outcome not in (
                "confirmado",
                "publicado",
                "publicado y fijado",
                "saltado_ya_comentado",
            ):
                continue
            for field in ("url", "post_url", "post_resumen", "resumen"):
                url = (row.get(field) or "").strip()
                if url.startswith(("https://", "http://")):
                    urls.add(url)
                    break
    return urls

def discarded_handles(registro_csv_path):
    """Cuentas que los scans no deben proponer (07/10, regulador de relaciones `relationship_policy.py`): unfollow por otra causa (idioma, bot, spam) o bloqueo = para siempre;
    unfollow por no devolver el follow = en espera 21 dias (segunda oportunidad) y, tras 3 intentos, lista negra. Un intento fallido o pendiente no excluye nada."""
    import relationship_policy as rp
    if not os.path.exists(registro_csv_path):
        return set()
    return rp.blocked_accounts(registro_csv_path)


def known_accounts(registro_csv_path):
    """Handle (sin @) -> fecha de la ULTIMA fila con ese handle en
    registro_interacciones.csv de esa red (mismo comportamiento que tenian
    x_scan.py/threads_scan.py antes de extraer esto: como el CSV se lee en
    orden y el dict se sobrescribe, la fecha que queda es la de la
    interaccion mas reciente, no la primera). Vacio si el fichero no
    existe todavia."""
    known = {}
    if not os.path.exists(registro_csv_path):
        return known
    with open(registro_csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            h = (row.get("cuenta") or "").strip().lstrip("@")
            if h:
                known[h] = row.get("fecha")
    return known


def invites_conversation(text):
    """Heuristico compartido (antes copiado literal en x_scan.py/
    threads_scan.py/instagram_scan.py/facebook_scan.py/tiktok_scan.py/
    bluesky_scan.py, unificado el 23/09 a peticion explicita de David:
    "no puedes actuar como buen arquitecto... lo que invirtamos en una que
    beneficie al resto"). Un texto con "?"/"¿" suele buscar opinion o
    respuesta real - promueve un candidato de 'like' a 'reply'/'comment'."""
    return "?" in text or "¿" in text


def _normalize_handle(value):
    if not isinstance(value, str):
        return None
    normalized = value.strip().lstrip("@").casefold()
    return normalized or None


def is_valid_candidate(handle, text, my_handle, discarded_handles=frozenset()):
    """Filtro único de candidato con comparación de handles normalizada.

    Sin texto evaluable no se puede comprobar el filtro político. Se omite
    el candidato en vez de tratar la ausencia de datos como contenido seguro.
    """
    normalized = _normalize_handle(handle)
    mine = _normalize_handle(my_handle)
    if not normalized or not mine or normalized == mine:
        return False
    if not isinstance(text, str) or not text.strip():
        return False
    discarded = {
        h for h in (_normalize_handle(value) for value in discarded_handles) if h
    }
    if normalized in discarded:
        return False
    if is_political(text):
        return False
    return True


class ActionTargetNotFound(RuntimeError):
    """Excepcion compartida (antes definida por separado en cada
    *_interact.py, empezando a duplicarse el mismo 23/09 entre
    threads_interact.py e instagram_interact.py - corregido antes de que
    se repitiera una tercera vez). Se lanza cuando una funcion de escritura
    (like/reply/comment/follow) no encuentra el post/boton/cuadro de texto
    que necesita para actuar - NUNCA hacer `print(aviso); return` en su
    lugar, porque un return normal no lanza excepcion y el execute.py de
    turno lo registraria como "confirmado" sin haber hecho nada (bug real
    visto primero en Threads, luego confirmado tambien posible en
    Instagram)."""


class AlreadyCommented(RuntimeError):
    """Excepcion compartida (antes una copia identica de esta clase vacia
    en cada *_interact.py que soporta reply/comment). La deteccion de "ya
    comentamos aqui" SI es especifica de cada red (DOM/API/heuristico de
    texto, no se puede unificar), pero el tipo de excepcion que se lanza al
    final no tiene por que duplicarse."""



_CLOSER_PHRASES = (
    "exacto", "exactamente", "tal cual", "totalmente", "de acuerdo",
    "gracias", "muchas gracias", "si", "claro", "desde luego",
    "te lo dire", "ya te contare", "lo hare", "veremos", "jajaja", "jeje",
)


def is_conversation_closer(text):
    """Heurístico conservador para no convertir cierres breves en otra respuesta.

    No decide si un contenido es interesante. Solo detecta casos de muy baja
    información (emoji, asentimiento o despedida breve) donde una reacción es
    normalmente más natural que forzar otro texto. Cualquier pregunta explícita
    queda fuera del cierre.
    """
    if not isinstance(text, str):
        return False
    raw = " ".join(text.strip().split())
    if not raw or "?" in raw or "¿" in raw:
        return False
    normalized = unicodedata.normalize("NFKD", raw.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", normalized)
    if not words:
        return True
    if len(words) > 6:
        return False
    plain = " ".join(words)
    # Igualdad deliberada: "Exactamente" cierra; "Exactamente, por eso no
    # funciona" ya aporta una idea y no debe degradarse a like.
    return plain in _CLOSER_PHRASES

def suggest_kind(source, text, *, reply_sources=(), follow_sources=(),
                  url=None, already_commented_urls=frozenset(),
                  cheap="like", rich="reply"):
    """Sugerencia de kind unificada (23/09). No sustituye toda la logica de
    _suggest_kind de cada red (algunas tienen fuentes propias como
    'comentaristas' con reglas particulares), pero cubre el caso comun:
    notificaciones de reciprocidad con contenido -> `rich` (reply/comment),
    notificaciones de reciprocidad sin contenido -> follow, cualquier fuente
    que invite a conversacion -> `rich`, resto -> `cheap`. Cada *_scan.py
    puede llamar a esto como base y solo anadir sus propios casos especiales
    encima, en vez de reescribir la funcion entera."""
    if url and url in already_commented_urls:
        return cheap
    if source in follow_sources:
        return "follow"
    if source in reply_sources:
        return rich
    if invites_conversation(text):
        return rich
    return cheap


def check_length(text, limit):
    """Comprobacion de longitud unificada (23/09) - antes 7 copias
    identicas de `if len(text) > limit: raise ValueError(...)` en cada
    *_interact.py, solo con el `limit` cambiando por red (280 X, 300
    Bluesky, 500 Threads, 2200 Instagram, 150 TikTok comentario, 8000
    Facebook, 10000 Reddit - esos numeros SI son especificos de cada red y
    se quedan alli como constante, ver sus propios _check_length). Lo unico
    que se centraliza es la comprobacion en si, no el limite."""
    if len(text) > limit:
        raise ValueError(
            f"texto de {len(text)} caracteres, {len(text) - limit} por encima "
            f"del limite de {limit} - acortalo antes de reintentar"
        )


def human_pause(a=1.5, b=5.0, doubt=0.12, stall=0.03):
    """Pausa entre acciones con rafagas, dudas y algun paron (volume_shape.human_gap): para
    rondas de volumen alto que no deben parecer un metronomo."""
    from volume_shape import human_gap
    tt = human_gap(a=a, b=b, doubt=doubt, stall=stall)
    print(f"(pausa {tt:.0f}s)")
    time.sleep(tt)


def pause(a, b):
    """Pausa con ritmo humano, compartida (23/09) - antes 8 copias
    identicas de random.uniform+print+sleep en cada *_execute.py, solo con
    el rango (a, b) cambiando por red segun su propio riesgo/rate-limit
    real (esos rangos SI son especificos de cada red y se quedan alli)."""
    tt = random.uniform(a, b)
    print(f"(pausa {tt:.0f}s)")
    time.sleep(tt)


def drop_stacked_actions(plan, *, cheap_kinds=("like",), rich_kinds=("reply", "quote", "comment"),
                          key="handle", normalize=None):
    """Quita del plan una accion barata (like/repost) sobre un objetivo que
    ya tiene una accion mas rica (reply/quote/comment) en el mismo plan -
    antes 4 copias casi identicas en bluesky/instagram/threads/x_execute.py
    (y ausente por completo en facebook/tiktok, que tambien soportan
    like+comment sobre el mismo target y podian apilar sin que nada lo
    evitara). A peticion explicita de David: "si ya tienen una interaccion
    no necesitan mas". `key` es el campo que identifica al mismo objetivo
    (normalmente "handle"; X usa "url" porque el mismo handle puede
    aparecer varias veces con URLs distintas mientras que apilar solo
    importa sobre el MISMO post). `cheap_kinds` acepta mas de un kind barato
    a la vez (X degrada tanto "like" como "repost"). `normalize` es una
    funcion opcional aplicada al valor de `key` antes de comparar (Threads
    necesita `str.lstrip("@")` porque un handle puede llegar con o sin @)."""
    # BUG REAL evitado antes de que se propagara (23/09): usar `and p.get(key)`
    # como filtro de "tiene valor" trata un `key` valido pero falsy (ej.
    # Facebook usa "index": 0 para el primer post) como si no existiera -
    # habria dejado el post en indice 0 sin proteccion nunca. Comprobar `key
    # in p and p[key] is not None` en su lugar.
    norm = normalize or (lambda v: v)
    targeted = {norm(p[key]) for p in plan if p.get("kind") in rich_kinds and key in p and p[key] is not None}
    kept, dropped = [], []
    for p in plan:
        has_key = key in p and p[key] is not None
        if p.get("kind") in cheap_kinds and has_key and norm(p[key]) in targeted:
            dropped.append(p)
        else:
            kept.append(p)
    for p in dropped:
        print(f"OMITIDO antes de ejecutar: {p.get('kind')} sobre {p.get(key)} - ya tiene una accion mas rica en este plan.")
    return kept


def pick_seeds(seeds_csv_path, pool, *, n=2, cooldown_days=4,
               id_field="url", key_fn=None, record=False):
    """Selecciona semillas únicas, priorizando las fuera de cooldown.

    El pool se deduplica por clave. Si no hay suficientes semillas frescas,
    se completa con recientes sin repetir ninguna dentro de la sesión.
    Con record=False el cooldown se registra solo después de recuperar el
    hilo con éxito mediante record_successful_seed().
    """
    key_fn = key_fn or (lambda item: item)
    import datetime

    try:
        n = max(0, int(n))
        cooldown_days = max(0, int(cooldown_days))
    except (TypeError, ValueError) as exc:
        raise ValueError("n/cooldown_days inválidos") from exc
    if n == 0:
        return []

    recent = set()
    if os.path.exists(seeds_csv_path) and os.path.getsize(seeds_csv_path) > 0:
        cutoff = datetime.date.today() - datetime.timedelta(days=cooldown_days)
        with open(seeds_csv_path, encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = set(reader.fieldnames or ())
            required = {"fecha", id_field}
            if not required.issubset(fields):
                raise RuntimeError(
                    f"CSV de semillas inválido: faltan columnas {sorted(required - fields)}"
                )
            for line_no, row in enumerate(reader, start=2):
                raw_date = (row.get("fecha") or "").strip()
                key = (row.get(id_field) or "").strip()
                if not raw_date or not key:
                    raise RuntimeError(
                        f"CSV de semillas inválido en línea {line_no}: fecha/clave vacía"
                    )
                try:
                    fecha = datetime.date.fromisoformat(raw_date)
                except ValueError as exc:
                    raise RuntimeError(
                        f"CSV de semillas inválido en línea {line_no}: fecha {raw_date!r}"
                    ) from exc
                if fecha >= cutoff:
                    recent.add(key)

    unique = []
    seen = set()
    for item in pool:
        key = key_fn(item)
        if key is None:
            continue
        key = str(key).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append((item, key))

    fresh = [pair for pair in unique if pair[1] not in recent]
    fallback = [pair for pair in unique if pair[1] in recent]
    rng = random.Random(datetime.date.today().toordinal())
    rng.shuffle(fresh)
    rng.shuffle(fallback)
    chosen_pairs = (fresh + fallback)[:n]
    chosen = [item for item, _ in chosen_pairs]

    if chosen_pairs and record:
        today = datetime.date.today().isoformat()
        for _, key in chosen_pairs:
            record_successful_seed(
                seeds_csv_path,
                key,
                id_field=id_field,
                date=today,
            )
    return chosen



def record_successful_seed(seeds_csv_path, key, *, id_field="url", date=None):
    """Registra una semilla exitosa una sola vez por fecha+clave."""
    import datetime

    key = str(key or "").strip()
    if not key:
        raise ValueError("No se puede registrar una semilla sin clave")
    when = date or datetime.date.today().isoformat()
    try:
        datetime.date.fromisoformat(when)
    except ValueError as exc:
        raise ValueError("Fecha de semilla inválida") from exc

    existing = set()
    first = (
        not os.path.exists(seeds_csv_path)
        or os.path.getsize(seeds_csv_path) == 0
    )
    if not first:
        with open(seeds_csv_path, encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = set(reader.fieldnames or ())
            required = {"fecha", id_field}
            if not required.issubset(fields):
                raise RuntimeError(
                    f"CSV de semillas inválido: faltan columnas {sorted(required - fields)}"
                )
            for line_no, row in enumerate(reader, start=2):
                raw_date = (row.get("fecha") or "").strip()
                raw_key = (row.get(id_field) or "").strip()
                if not raw_date or not raw_key:
                    raise RuntimeError(
                        f"CSV de semillas inválido en línea {line_no}: fecha/clave vacía"
                    )
                try:
                    datetime.date.fromisoformat(raw_date)
                except ValueError as exc:
                    raise RuntimeError(
                        f"CSV de semillas inválido en línea {line_no}: fecha {raw_date!r}"
                    ) from exc
                existing.add((raw_date, raw_key))

    if (when, key) in existing:
        return False

    parent = os.path.dirname(seeds_csv_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(seeds_csv_path, "a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        if first:
            writer.writerow(["fecha", id_field])
        writer.writerow([when, key])
    return True


# Pistas de activismo en biografias que is_political() no cubre (hashtags
# geopoliticos, sindicatos, etc.). Vistas el 02/10: una cuenta sindical y un
# post solo de hashtags (#freepalestine...) pasaron el filtro. Se usa solo
# para decidir A QUIEN SEGUIR; no cambia is_political().
ACTIVIST_HINTS = (
    "sindicat", "huelga", "manifestaci", "okupa", "antifascis", "franquis",
    "genocidi", "palestin", "israel", "ultraderecha", "extrema derecha",
    "trump", "gaza", "politic", "polític", "vox ", "psoe", "activis",
    "biden", "boicot",
    "antifa", "anarquis", "comunist", "de izquierda", "de derecha", "fascis", "derechos lgbt",       # 06/10: «Antifa… derechos LGBT+» y «anarquista… de izquierda» pasaban el filtro de bienvenidas
)
# Excluidas a proposito por chocar con el nicho: "podemos" (verbo), "maga"
# (maga/mago en fantasia), "resist" (resistencia en ficcion), "feminis".


def looks_activist(text):
    low = (text or "").lower()
    return any(hint in low for hint in ACTIVIST_HINTS)


BRIDGE_MARKERS = ("brid.gy", "bridgy")


def is_feed_bridge(handle):
    """Cuentas que no son personas: puentes ActivityPub<->Bluesky (brid.gy) y
    puentes RSS/blog (usuario y dominio iguales, p. ej.
    `blog.wordpress.com@blog.wordpress.com`). Nadie lee sus respuestas ni
    devuelven un follow, asi que una reply/follow/boost ahi es accion perdida
    (02/10: una reply a un puente de blog gasto una de las 10 replies de la
    ronda)."""
    low = _normalize_handle(handle) or ""
    if any(marker in low for marker in BRIDGE_MARKERS):
        return True
    local, _, domain = low.partition("@")
    return bool(domain) and local == domain


# --- Estilo de replies (02/10) -------------------------------------------
# Medido sobre las replies propias: las que terminan en pregunta reciben
# respuesta ~1.6x mas (50% vs 31%, Bluesky) y el 39% llevaba un guion largo
# como muletilla, que delata texto generado. Es un aviso, nunca un bloqueo.
REPLY_IDEAL_MAX = 200
QUESTION_SHARE_MIN = 0.3
DASH_SHARE_MAX = 0.2


# Muletillas de texto generado medidas sobre 185 respuestas propias (03/10):
# "Que + verbo" abre el 10%, "de verdad" 8%, "casi siempre/nunca" 5%, "no es X, es Y" y
# "es de esas..." 3% cada una, guion largo 23%. Cada una es un aviso, nunca un bloqueo.
_TELLS = (
    (re.compile(r"^que \w+", re.I), "abre con 'Que + verbo' (muletilla repetida)"),
    (re.compile(r"\bes de (?:esas?|esos?) ", re.I), "'es de esas/os...' suena a plantilla"),
    (re.compile(r"\bno es [^.,]{2,50}, (?:es|sino)\b", re.I), "'no es X, es Y' suena a plantilla"),
    (re.compile(r"\bdice (?:mucho|bastante|más)\b", re.I), "'dice mucho' es un comodin"),
    (re.compile(r"\bde verdad\b", re.I), "'de verdad' como relleno"),
    (re.compile(r"\b(?:casi siempre|casi nunca)\b", re.I), "generalizacion tipo 'casi siempre/nunca'"),
    (re.compile(r"\bjusto (?:ahí|eso|lo que)\b", re.I), "'justo ahi/eso' como comodin"),
    (re.compile(r"\b(?:buen|mejor) (?:síntoma|señal|argumento)\b", re.I), "'buen sintoma/senal' como cierre"),
    # 05/10 (David: "no siempre tan profunda o filosofica"): sentencias de aforismo y evaluaciones genericas
    (re.compile(r"\bvale (?:más|mas) que cualquier\b|\bpesa distinto\b|\btiene algo que (?:casi )?(?:ningún|ninguno|nadie)\b", re.I), "frase de aforismo ('vale mas que cualquier...', 'pesa distinto...'): suena a plantilla filosofica"),
    (re.compile(r"\bya promete\b|\bes un buen comienzo\b|\bbuena forma de\b|\bsiempre pide hueco\b", re.I), "evaluacion generica ('ya promete', 'buen comienzo', 'buena forma de...')"),
)
MEDIAN_LEN_MAX = 150
COLON_SHARE_MAX = 0.25


# Formatos de reply (05/10). Una persona no contesta siempre igual: reaccion, pregunta suelta, dato concreto, opinion corta, observacion + pregunta.
FORMAT_SHARE_MAX = 0.4   # ningun formato debe pasar del 40 % de un lote (>=6)


def reply_format(text):
    """Clasifica una reply: micro | exclamacion | pregunta | observacion_pregunta | afirmacion."""
    t = " ".join((text or "").split())
    words = len(t.split())
    if words <= 6 and "?" not in t:
        return "micro"
    if t.startswith("¡") or t.endswith("!"):
        return "exclamacion"
    sentences = [x for x in re.split(r"(?<=[.!?])\s+", t) if x]
    if t.endswith("?"):
        return "pregunta" if len(sentences) == 1 else "observacion_pregunta"
    return "afirmacion"


def reply_format_notes(texts):
    texts = [t for t in texts if t and t.strip()]
    if len(texts) < 6:
        return []
    counts = {}
    for t in texts:
        counts[reply_format(t)] = counts.get(reply_format(t), 0) + 1
    notes = []
    kind, n = max(counts.items(), key=lambda kv: kv[1])
    if n / len(texts) > (0.55 if kind == "micro" else FORMAT_SHARE_MAX):   # 'micro' agrupa reacciones y agradecimientos: se tolera mas
        notes.append(f"{n}/{len(texts)} replies tienen el mismo formato ('{kind}'): mezclar reaccion corta, pregunta suelta, "
                     "dato concreto, opinion de una frase y alguna observacion+pregunta (ver GUIA_VOZ_REPLIES, 'menu de formatos')")
    if len(counts) < 3:
        notes.append(f"solo {len(counts)} formatos distintos en {len(texts)} replies: una persona alterna mas")
    periods = sum(t.rstrip().endswith(".") for t in texts)
    if periods / len(texts) > 0.7:
        notes.append(f"{periods}/{len(texts)} acaban en punto: alternar con ?, !, frases sin punto final o con emoji suelto")
    return notes


def reply_style_report(texts):
    """Avisos de estilo para un lote de replies (lista de strings)."""
    texts = [t for t in texts if t and t.strip()]
    if not texts:
        return []
    notes = []
    long_ones = sum(len(t) > REPLY_IDEAL_MAX for t in texts)
    if long_ones:
        notes.append(f"{long_ones}/{len(texts)} replies pasan de {REPLY_IDEAL_MAX} caracteres (mejor cortas)")
    lengths = sorted(len(t) for t in texts)
    if len(texts) >= 4 and lengths[len(lengths) // 2] > MEDIAN_LEN_MAX:
        notes.append(f"mediana de {lengths[len(lengths) // 2]} caracteres: una persona contesta mas corto (objetivo ~100)")
    dashes = sum((" - " in t) or (" — " in t) or (" – " in t) for t in texts)
    if dashes / len(texts) > DASH_SHARE_MAX:
        notes.append(f"{dashes}/{len(texts)} usan guion como muletilla (delata texto generado; usar punto o coma)")
    # "Observacion: desarrollo. ¿Pregunta?" repetido es el molde mas reconocible (medido 02/10: 28 %
    # de las replies del corpus llevaban dos puntos explicativos).
    colons = sum(bool(re.search(r"\w: \w", t)) for t in texts)
    if len(texts) >= 4 and colons / len(texts) > COLON_SHARE_MAX:
        notes.append(f"{colons}/{len(texts)} usan dos puntos explicativos ('X: Y'): partir en dos frases o reformular")
    questions = sum("?" in t for t in texts)
    if len(texts) >= 3 and questions / len(texts) < QUESTION_SHARE_MIN:
        notes.append(f"solo {questions}/{len(texts)} terminan en pregunta (objetivo ~30-40%, solo si es una pregunta real sobre un detalle del post, nunca un cierre por inercia: con pregunta reciben ~1.6x mas respuesta)")
    micro = sum(len(t.split()) <= 8 for t in texts)
    if len(texts) >= 3 and micro / len(texts) < 0.2:
        notes.append(f"{micro}/{len(texts)} micro-replies (<= 8 palabras): meter ~30 % ('Qué bueno.', una reaccion "
                     "corta con detalle). Es mas humano, gasta menos tokens y es el brazo que falta del experimento "
                     "micro vs elaborada (`growth_attribution.py`)")
    for pattern, message in _TELLS:
        hits = [t for t in texts if pattern.search(t)]
        if hits:
            notes.append(f"{len(hits)}/{len(texts)}: {message}")
    openers = [t.split()[0].casefold() for t in texts]
    if len(texts) >= 4:
        word, count = max(((w, openers.count(w)) for w in set(openers)), key=lambda x: x[1])
        if count / len(texts) > 0.34:
            notes.append(f"{count}/{len(texts)} empiezan por '{word}': variar las aperturas")
    notes.extend(reply_format_notes(texts))
    return notes


# --- Peticiones de opinion sobre trabajo propio (03/10) --------------------
# "Lee mi texto", "que os parece mi relato", "feedback sobre mi novela": una
# opinion real exige leerlo y no podemos inventar que lo hemos leido, ni
# criticar. Por defecto se IGNORA; si se responde, solo una linea breve,
# positiva y neutra ("Tiene buena pinta, deseando leer mas.").
_OWN_WORK = (r"(?:mi|mis|nuestro|nuestra|nuestros|nuestras)\s+(?:\w+\s+)?"
             r"(?:texto|textos|relato|relatos|cuento|cuentos|microrrelato\w*|micro|poema|poemas|novela|novelas|"
             r"libro|libros|capitulo|capitulos|historia|historias|escrito|escritos|manuscrito|borrador|obra|saga|"
             r"trabajo|proyecto|prologo|sinopsis|portada|dibujo|ilustracion|blog|articulo|resena)(?![a-z])"
             r"(?!\s+(?:favorit|preferid))")
# Imperativos plurales (sin ambiguedad) valen en cualquier posicion; los singulares ("lee",
# "revisa", "mira") solo al principio de frase o tras "por favor"/"y", porque "Mi editor revisa mi
# manuscrito" o "Mira, mi libro del año es..." no piden nada.
_IMP_PLURAL = r"(?:leed|leedme|leeme|echad|echadle|echale|revisad|opinad|comentad|valorad|criticad|mirad(?!,))"
_IMP_SING = r"(?:^|[.!?¡¿\n]\s*|por favor,?\s+|\by\s+)(?:lee|echa|revisa|opina|comenta|valora|critica|mira(?!,))"
_OPINION_PATTERNS = [re.compile(p) for p in (
    r"\b" + _IMP_PLURAL + r"\b.{0,45}?" + _OWN_WORK,
    _IMP_SING + r"\b.{0,45}?" + _OWN_WORK,
    r"\b(?:podeis|podrias|podriais|puedes|quereis|quieres|animais|animas)\b.{0,20}?\b(?:leer|echar|mirar|revisar|opinar|valorar)\b.{0,45}?" + _OWN_WORK,
    _OWN_WORK + r".{0,40}?\b(?:valorad\w*|opinad\w*|comentad\w*|leedl\w*|leel\w*|echadle|criticad\w*)\b",
    r"\b(?:opinion|opiniones|feedback|critica|criticas|valoracion|valoraciones|impresion|impresiones|"
    r"sugerencia|sugerencias|comentarios?)\b.{0,25}?\b(?:sobre|de|acerca de|para)\b.{0,15}?" + _OWN_WORK,
    r"\bque\s+(?:os|te|le|les)?\s*(?:parece|parecen|pensais|piensas|opinais|opinas)\b.{0,45}?" + _OWN_WORK,
    _OWN_WORK + r".{0,60}?(?:\bque\s+(?:os|te|le)?\s*(?:parece|parecen|opinais|opinas|pensais|piensas)\b|\bopiniones\b|\bfeedback\b|\b(?:os|te)\s+gusta\b)",
    r"\b(?:os|te)\s+gusta\b.{0,40}?" + _OWN_WORK,
    r"\bque\s+tal\b.{0,15}?" + _OWN_WORK,
    r"\b(?:he escrito|acabo de escribir|escribi|termine)\b.{0,60}?(?:\bopiniones\b|\bfeedback\b|\bque\s+(?:os|te)\s+parece)",
    r"\b(?:necesito|busco|quiero|agradezco|pido|pedir)\b.{0,20}?\b(?:opiniones|opinion|feedback|criticas)\b.{0,50}?\b(?:mi|mis|nuestr\w+)\b",
    r"\bbusco\s+(?:feedback|opiniones|criticas)\b(?!.{0,30}?\b(?:sobre|del|de la|de los)\b)",
    r"\b(?:necesito|busco|quiero)\b.{0,20}?\b(?:lectores? beta|betas?|beta ?lectores?)\b",
    r"\b(?:read|check out|critique|review|rate)\s+my\b",
    r"\b(?:feedback|thoughts|opinions?)\s+(?:on|about)\s+my\b",
    r"\b(?:i(?:'| a)?m looking for|need|seeking)\s+(?:beta readers?|feedback|critique)\b",
)]
_NEGATIVE_CUES = ("pero", "aunque", "mejor", "mejorar", "falta", "sin embargo", "no me", "cambiaria",
                  "deberias", "podrias", "consejo", "critica", "flojo", "confus", "aburrid")
_POSITIVE_CUES = ("gust", "buena pinta", "ganas", "interesante", "bonito", "bien", "entretenid", "curios",
                  "enhorabuena", "animo", "suerte", "genial", "encanta", "deseando", "atractiv", "prometedor")
OPINION_REPLY_MAX = 110


def _fold(text):
    return "".join(ch for ch in unicodedata.normalize("NFD", (text or "").lower())
                   if unicodedata.category(ch) != "Mn")


def asks_for_opinion(text):
    """True si el post pide una opinion/lectura/feedback sobre trabajo propio."""
    folded = _fold(text)
    if "gracias por" in folded or "gracias a " in folded:
        return False  # agradecer comentarios recibidos no es pedirlos
    return any(pattern.search(folded) for pattern in _OPINION_PATTERNS)


def check_opinion_reply(reply_text):
    """Problemas de una reply a una peticion de opinion (lista vacia = valida)."""
    folded = _fold(reply_text)
    problems = []
    if len(reply_text) > OPINION_REPLY_MAX:
        problems.append(f"larga ({len(reply_text)} > {OPINION_REPLY_MAX} caracteres)")
    if "?" in reply_text:
        problems.append("no preguntar: abre una conversacion que no podemos sostener")
    if any(cue in folded for cue in _NEGATIVE_CUES):
        problems.append("no criticar ni aconsejar sobre un texto que no hemos leido")
    if not any(cue in folded for cue in _POSITIVE_CUES):
        problems.append("debe ser breve y positiva")
    return problems


def opinion_guard(post_text, reply_text):
    """Lanza ValueError si se responde mal a una peticion de opinion."""
    if not asks_for_opinion(post_text):
        return
    problems = check_opinion_reply(reply_text)
    if problems:
        raise ValueError(
            "el post pide opinion sobre trabajo propio (" + "; ".join(problems) + "). "
            "Ignorarlo o responder solo algo como: 'Tiene buena pinta, deseando leer mas.'"
        )


# --- Aplicacion global del filtro de opinion (03/10) -----------------------
RICH_KINDS = {"reply", "comment", "comment_external", "quote"}
_CHEAP_FOR = {"comment_external": "like_external"}
_CONTEXT_FIELDS = ("post_text", "text_fragment", "resumen", "post_resumen", "title", "context", "contexto")


def downgrade_for_opinion(kind, text, cheap="like"):
    """Si el post pide opinion sobre trabajo propio, una reply/comment sugerido
    baja a la accion barata (like/favourite); el resto de kinds no cambia."""
    if kind in RICH_KINDS and asks_for_opinion(text):
        return _CHEAP_FOR.get(kind, cheap)
    return kind


def opinion_safe(suggest, text_index=0, cheap="like"):
    """Envuelve un `_suggest_kind` de scanner; `text_index` = posicion del texto."""
    def wrapper(*args, **kwargs):
        return downgrade_for_opinion(suggest(*args, **kwargs), args[text_index], cheap)
    wrapper.__name__ = getattr(suggest, "__name__", "suggest_kind")
    return wrapper


def plan_action_duplicate_key(item, *, stable_target_fields=()):
    """Clave común de duplicación: ID remoto verificable antes que extracto.

    El identificador estable evita confundir posts diferentes con idéntico
    inicio; sin ID, se conserva el criterio histórico autor + fragmento.
    La identidad del ID es opaca y no debe normalizarse por casefold().
    """
    kind = item.get("kind")
    for field in stable_target_fields:
        target = item.get(field)
        if isinstance(target, (str, int)) and not isinstance(target, bool):
            target = str(target).strip()
            if target:
                return (kind, "stable_target", target)
    return (kind, "excerpt_target",
            str(item.get("handle") or "").lstrip("@").casefold(),
            str(item.get("text_fragment") or "").strip().casefold())


def guard_plan_item(item, index=None):
    """Barrera comun en los preflight de TODOS los ejecutores: una reply/comment
    a un post que pide opinion solo pasa si es breve, positiva y neutra. El
    contexto sale de los campos del plan que describen el post objetivo."""
    if item.get("kind") not in RICH_KINDS or not item.get("text"):
        return
    context = " ".join(str(item.get(k) or "") for k in _CONTEXT_FIELDS).strip()
    if not context:
        # Sin descripcion del post objetivo el filtro no puede comprobar nada. Una
        # respuesta breve es inocua; una larga se avisa para revisarla a mano.
        if len(item["text"]) > OPINION_REPLY_MAX:
            import sys
            print(f"AVISO: elemento {index}: sin contexto del post objetivo, el filtro de opinion no puede "
                  "comprobarse (anadir post_text/resumen al plan)", file=sys.stderr)
        return
    try:
        opinion_guard(context, item["text"])
    except ValueError as exc:
        prefix = f"elemento {index}: " if index is not None else ""
        raise ValueError(prefix + str(exc)) from None


def structural_notes(texts, history=None):
    """Avisos estructurales de `check_language_variety.analyze` (apertura repetida,
    modo analitico saturado, andamio y cadencia repetidos, texto casi igual a uno
    reciente...) para cada reply, comparando con el historial real de las redes.
    Antes solo se podia lanzar a mano y nadie lo hacia."""
    try:
        import check_language_variety as clv
        history = clv.load_recent() if history is None else history
    except Exception:
        return []
    notes = []
    for text in texts:
        try:
            result = clv.analyze(text, history)
        except Exception:
            continue
        snippet = text[:38].rstrip() + ("..." if len(text) > 38 else "")
        notes += [f"«{snippet}»: {warning}" for warning in result.get("warnings", [])]
    if notes:
        try:
            notes.append("registros infrautilizados (probar uno): " + ", ".join(clv.recommend_modes(history)))
        except Exception:
            pass
    return notes


def report_plan_style(plan, out=None):
    """Imprime los avisos de estilo (`reply_style_report`) de las replies/comments
    de un plan ya validado. Comun a todos los ejecutores (03/10); solo avisa."""
    import sys
    out = out or (lambda line: print(line, file=sys.stderr))
    texts = [item.get("text") for item in plan
             if isinstance(item, dict) and item.get("kind") in RICH_KINDS and item.get("text")]
    for note in reply_style_report(texts) + structural_notes(texts):
        out(f"ESTILO: {note}")


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# Compartir (repost / boost) de posts ajenos (06/10/2026): los criterios vivian solo en bluesky_growth_scan; ahora los usan Bluesky y Mastodon.
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
SELF_PROMO_HINTS = ("compra mi", "mi libro ya", "ya disponible", "amazon", "preventa", "pre-order", "buy my", "link en bio")
_SHARE_BAD = re.compile(r"https?://|www\.|[a-z0-9]\.(?:com|me|es|org|net|cc|io)(?![a-z])|€|\$|suscrip|descuento|oferta", re.I)


def _fold(text):
    import unicodedata
    value = unicodedata.normalize("NFKD", " ".join(str(text or "").casefold().split()))
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def looks_self_promo(text):
    value = _fold(text)
    return any(_fold(term) in value for term in SELF_PROMO_HINTS)


def share_worthy(text, *, spanish, niche_hits, followers=None, age_days=None, min_words=8, max_words=70, max_age_days=3, followers_range=(30, 5000)):
    """Un repost/boost solo si el post es claramente del nicho (>=2 terminos), explicitamente en espanol, reciente, con texto propio (sin enlaces, precios ni autopromocion) y de una
    cuenta pequena (30-5.000 seguidores). Decision comun a Bluesky y Mastodon: `spanish`, `niche_hits` y `followers` los calcula cada red a su manera."""
    text = str(text or "")
    words = len(text.split())
    low, high = followers_range
    return bool(
        spanish is True
        and not text.lstrip().startswith("@")                    # una respuesta a otra persona no se comparte
        and len(re.findall(r"(?<!\w)#\s?\w+", text)) <= 3          # mas de tres etiquetas = post de promocion o de bot
        and niche_hits >= 2
        and min_words <= words <= max_words
        and (age_days is None or age_days <= max_age_days)
        and (followers is None or low <= int(followers) <= high)
        and not looks_activist(text)
        and not looks_self_promo(text)
        and not _SHARE_BAD.search(str(text or ""))
    )

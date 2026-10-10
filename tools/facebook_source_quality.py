"""Clasificador pasivo para observaciones Facebook; nunca concede permiso de escritura.

Las métricas son de candidatos observados, NO de acciones posibles ni de grupos
visitados. Una URL pública no acredita permisos para interactuar como Página.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re
import unicodedata
from collections import defaultdict
from urllib.parse import unquote, urlsplit

_TOPIC = re.compile(r"\b(?:libros?|lectur(?:a|as|as?)|lector(?:a|es|as)?|novelas?|fantas[ií]a|romantasy|escritor(?:a|es|as)?|rese[nñ]as?|club de lectura|sagas?)\b", re.I)
_SPAM = re.compile(r"(?:\b(?:casino|apuestas|criptomonedas?|empleo|contratando|vacantes|cv|curr[ií]culum)\b|\b(?:gana dinero|trabaja desde casa|oferta de trabajo|descuento exclusivo|plazas limitadas)\b|(?:t\.me/|wa\.me/|bit\.ly/))", re.I)
_AI_MARKER = re.compile(r"(?:generad[oa]s? (?:con|por) (?:ia|inteligencia artificial)|contenido generado por ia)", re.I)
_SOURCE = frozenset(("search", "hashtag"))


def _source_name(value):
    """Igual normalización que discovery_attribution, sin guardar texto raw."""
    if not isinstance(value, str):
        return "unknown"
    normalized = " ".join(unicodedata.normalize("NFKC", value).casefold().split())
    return normalized if normalized and len(normalized) <= 512 and "\x00" not in normalized else "unknown"


def _date(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        value = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return value.astimezone(dt.timezone.utc) if value.tzinfo else None
    except (ValueError, OverflowError, OSError):
        return None


def _surface(url):
    """Clasifica solo URL; no deduce visibilidad o pertenencia de la Página."""
    if not isinstance(url, str) or len(url) > 2048:
        return "invalid"
    try:
        p = urlsplit(url)
        if p.scheme != "https" or p.hostname not in ("facebook.com", "www.facebook.com") or p.username or p.password or p.port:
            return "invalid"
        path = unquote(p.path).casefold()
        query = unquote(p.query).casefold()
    except (ValueError, UnicodeError):
        return "invalid"
    if re.search(r"(?:^|/)groups(?:/|$)", path) or re.search(r"(?:^|&)group_id=", query):
        return "group"
    # Photo/story pueden representar compartidos de grupos: no autorizar.
    if path in ("/photo", "/photo.php", "/story.php", "/watch"):
        return "ambiguous"
    if re.fullmatch(r"/[^/]+/(?:posts|permalink)/[a-z0-9._-]+/?", path):
        return "post"
    return "unknown"


def page_post_url_shape(url, *, source=None):
    """Comprobación SINTÁCTICA previa a acciones; NO acredita permisos.

    Las URLs `photo`/`story` admiten contenido compartido desde grupos
    sin que la URL revele el origen. Se dejan para revisión humana.
    """
    if isinstance(source, str) and source.split(":", 1)[0].strip().casefold() in {"group", "groups"}:
        return False
    if _surface(url) != "post":
        return False
    # URLs de acción deben apuntar directamente a un post, no wrappers ni
    # redirecciones suministradas por parámetros de consulta.
    parsed = urlsplit(url)
    return not parsed.query and not parsed.fragment


def require_page_post_url_shape(url):
    """Nunca abrir navegador para enlaces de grupo/ambigüedad/desconocidos."""
    if not page_post_url_shape(url):
        raise ValueError("superficie Facebook no acreditada: solo enlace directo de post de página")
    return url



def hard_exclusion_reason(text):
    """Solo señales explícitas; revisión semántica humana fuera de este módulo."""
    if not isinstance(text, str):
        return None
    sample = text[:2000]
    if _SPAM.search(sample):
        return "spam_or_job"
    if _AI_MARKER.search(sample):
        return "ai_generated_label"
    return None


def assess(observation, *, now=None):
    """Resultado privado reducido a códigos, sin URL ni texto identificativo."""
    if not isinstance(observation, dict):
        return {"decision": "reject", "reason": "invalid_observation", "action_allowed": False}
    url_kind = _surface(observation.get("permalink"))
    source = _source_name(observation.get("source") or observation.get("tag"))
    prefix = source.split(":", 1)[0]
    text = observation.get("text") or observation.get("post_text")
    if url_kind == "group" or prefix in {"group", "groups"}:
        return {"decision": "reject", "reason": "group_not_authorized", "action_allowed": False}
    if url_kind == "invalid":
        return {"decision": "reject", "reason": "invalid_url", "action_allowed": False}
    if not isinstance(text, str):
        return {"decision": "review", "reason": "missing_text", "action_allowed": False}
    text = text[:2000]
    excluded = hard_exclusion_reason(text)
    if excluded:
        return {"decision": "reject" if excluded == "spam_or_job" else "review",
                "reason": excluded, "action_allowed": False}
    if not _TOPIC.search(text):
        return {"decision": "review", "reason": "non_literary", "action_allowed": False}
    if not page_post_url_shape(observation.get("permalink"), source=source) or prefix not in _SOURCE:
        return {"decision": "review", "reason": "surface_unverified", "action_allowed": False}
    published = _date(observation.get("created_at") or observation.get("post_created_at"))
    current = now or dt.datetime.now(dt.timezone.utc)
    if not isinstance(current, dt.datetime) or current.tzinfo is None:
        raise ValueError("now debe tener zona horaria")
    if published is None or published > current + dt.timedelta(minutes=5):
        return {"decision": "review", "reason": "age_unknown", "action_allowed": False}
    age = (current - published).total_seconds()
    if age > 3 * 86400:
        return {"decision": "review", "reason": "not_recent_for_comment", "action_allowed": False}
    return {"decision": "candidate", "reason": "fresh_literary_observation", "action_allowed": False}


def summary(observations, *, hmac_key=None, now=None):
    """Agrega métricas sin exponer queries, autores, textos ni permalinks."""
    if isinstance(observations, (str, bytes)) or not isinstance(observations, (tuple, list)):
        raise ValueError("se requiere lista de observaciones")
    if len(observations) > 10000:
        raise ValueError("lote excesivo")
    if hmac_key is not None and (not isinstance(hmac_key, bytes) or len(hmac_key) < 16):
        raise ValueError("la clave HMAC debe tener al menos 16 bytes")
    groups = defaultdict(list)
    for row in observations:
        source = _source_name(row.get("source") or row.get("tag") if isinstance(row, dict) else None)
        kind = source.split(":", 1)[0]
        # Sin clave solo métricas agregadas por superficie, no por consulta.
        token = (hmac.new(hmac_key, ("facebook/source\x00" + source).encode("utf-8"), hashlib.sha256).hexdigest()[:24]
                 if hmac_key is not None else None)
        groups[(kind if kind in _SOURCE else "other", token)].append(row)
    result = []
    for (kind, token), rows in sorted(groups.items(), key=lambda pair: (pair[0][0], pair[0][1] or "")):
        counts = defaultdict(int)
        unique = set()
        candidate_unique = set()
        duplicates = 0
        for row in rows:
            info = assess(row, now=now)
            counts[info["reason"]] += 1
            counts[info["decision"]] += 1
            url = row.get("permalink") if isinstance(row, dict) else None
            if isinstance(url, str) and _surface(url) != "invalid":
                if url in unique:
                    duplicates += 1
                unique.add(url)
                if info["decision"] == "candidate":
                    candidate_unique.add(url)
        result.append({"surface": kind, "source_key": token, "observed": len(rows),
                       "unique_post_urls": len(unique), "candidate": counts["candidate"],
                       "unique_candidate_urls_in_batch": len(candidate_unique),
                       "duplicate_observations_in_batch": duplicates,
                       "review": counts["review"], "rejected": counts["reject"],
                       "group_blocked": counts["group_not_authorized"],
                       "spam_blocked": counts["spam_or_job"],
                       "ai_generated_review": counts["ai_generated_label"],
                       "age_unknown": counts["age_unknown"],
                       "action_permission_verified": False})
    return {"network": "facebook", "measurement_only": True, "sources": result}

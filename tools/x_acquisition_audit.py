"""Auditoría X sin escrituras remotas: fuente, candidatos y dedupe de historial.

No infiere follows vigentes de una cuenta 'conocida' ni convierte una intención
con ACK incierto en confirmación. Las métricas son sobre datos LOCALES.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit


class HistoryReadError(RuntimeError):
    """El historial no es fiable: bloquear el plan, no suponer que está vacío."""


_ACTION_RESULTS = {"confirmado", "publicado", "pendiente_verificacion"}
_OBSERVED = {"follow": "saltado_ya_seguido", "like": "saltado_ya_like",
             "reply": "saltado_ya_comentado", "repost": "saltado_ya_reposteado"}
_FOLLOW_RESULTS = _ACTION_RESULTS | {"pendiente_aprobacion", _OBSERVED["follow"]}
_POST_KINDS = {"like", "reply", "quote", "repost"}
_BLOCKED_LATEST_PREFIX = "like_latest:"
_HEADER = ("fecha", "cuenta", "tipo", "post_resumen", "texto_usado",
           "resultado", "notas")


def status_id(url):
    """Devuelve ID canónico solo para permalinks de posts X verificables."""
    if not isinstance(url, str):
        return None
    try:
        parts = urlsplit(url.strip())
        if (parts.scheme != "https"
                or parts.hostname not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
                or parts.username or parts.password or parts.port):
            return None
    except ValueError:
        return None
    path = parts.path.strip("/").split("/")
    if (len(path) != 3 or path[1] != "status"
            or not re.fullmatch(r"[A-Za-z0-9_]{1,15}", path[0])
            or not re.fullmatch(r"[0-9]+", path[2])):
        return None
    return path[2].lstrip("0") or "0"


def source_family(source):
    """Familia agregada; nunca imprime consultas, handles ni semillas."""
    raw = str(source or "").casefold()
    if raw.startswith("growth:") and "src=" in raw:
        raw = raw.split("src=", 1)[1]
    elif raw.startswith("growth:"):
        raw = raw.split(":", 2)[1]
    # Los planes solo guardan la familia, no la búsqueda original.
    already_bucketed = {
        "lista", "notificaciones", "busqueda", "perfiles", "seguidores_semilla",
        "siguiendo", "comentaristas", "reciprocidad", "reserva_posts",
        "reserva_cuentas", "respuestas",
    }
    if raw in already_bucketed:
        return raw
    if raw.startswith("lista:"):
        return "lista"
    if raw.startswith("notif:"):
        return "notificaciones"
    if raw.startswith("search:"):
        return "busqueda"
    if raw.startswith("profiles:"):
        return "perfiles"
    if raw.startswith("followers:"):
        return "seguidores_semilla"
    if raw.startswith("following"):
        return "siguiendo"
    if raw.startswith("comentaristas"):
        return "comentaristas"
    if raw.startswith("backfollow"):
        return "reciprocidad"
    if raw.startswith("pool"):
        return "reserva_posts"
    if raw.startswith("acct"):
        return "reserva_cuentas"
    if raw.startswith("reply"):
        return "respuestas"
    return "sin_fuente"


def candidate_summary(candidates):
    """Únicos por fuente; nueva = ausencia de registro, NO seguimiento nuevo."""
    groups = defaultdict(lambda: {"propuestas": 0, "nuevas_en_registro": set(),
                                  "conocidas_en_registro": set()})
    for row in candidates:
        if not isinstance(row, dict):
            continue
        handle = str(row.get("handle") or "").strip().lstrip("@").casefold()
        if not handle:
            continue
        family = source_family(row.get("source"))
        entry = groups[family]
        entry["propuestas"] += 1
        key = "conocidas_en_registro" if row.get("known_date") else "nuevas_en_registro"
        entry[key].add(handle)
    return {
        name: {"propuestas": entry["propuestas"],
               "cuentas_sin_registro": len(entry["nuevas_en_registro"]),
               "cuentas_con_registro": len(entry["conocidas_en_registro"])}
        for name, entry in sorted(groups.items())
    }


def read_history(path):
    """Historial solo lectura; los pending conocidos bloquean replay."""
    follows, posts = set(), set()
    path = Path(path)
    try:
        if not path.exists():
            # Perder el registro no es prueba de cero acciones anteriores.
            raise HistoryReadError("registro X ausente: no se puede deduplicar")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            header = reader.fieldnames or []
            # El ejecutor siempre escribe siete columnas en ESTE orden.
            # Detectarlo antes del tap evita ejecutar sin poder registrar.
            if tuple(header) != _HEADER:
                raise HistoryReadError("cabecera X incompatible: revisión manual")
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    raise HistoryReadError("fila X truncada o con columnas sobrantes")
                kind = (row.get("tipo") or "").strip().casefold()
                result = (row.get("resultado") or "").strip().casefold()
                if kind == "follow" and result in _FOLLOW_RESULTS:
                    handle = (row.get("cuenta") or "").strip().lstrip("@").casefold()
                    if not handle:
                        raise HistoryReadError("follow registrado sin cuenta")
                    follows.add(handle)
                elif kind == "like_latest" and result in (
                        "pendiente_verificacion", "saltado_ya_like", "confirmado"):
                    # El último post real se descubrió en la UI; el plan no
                    # conoce su URL. Bloquear esa cuenta hasta revisión o
                    # una nueva decisión explícita sobre la reserva.
                    handle = (row.get("cuenta") or "").strip().lstrip("@").casefold()
                    if not handle:
                        raise HistoryReadError("like_latest incierto sin cuenta")
                    posts.add(_BLOCKED_LATEST_PREFIX + handle)
                elif kind in _POST_KINDS and (
                        result in _ACTION_RESULTS or result == _OBSERVED.get(kind)):
                    ident = status_id(row.get("post_resumen"))
                    if ident:
                        posts.add(ident)
                    elif kind == "like" and result in ("confirmado", "saltado_ya_like"):
                        # Compatibilidad: antiguos like_latest se guardaban
                        # como kind=like con fragmento y SIN URL.
                        handle = (row.get("cuenta") or "").strip().lstrip("@").casefold()
                        if handle:
                            posts.add(_BLOCKED_LATEST_PREFIX + handle)
                    elif result == "pendiente_verificacion":
                        # ACK incierto sin destino inequívoco: no proseguir.
                        raise HistoryReadError("ACK pendiente sin permalink verificable")
    except (OSError, csv.Error, UnicodeError) as exc:
        raise HistoryReadError("registro X no legible") from exc
    return follows, posts


def observed_results(path, *, today=None):
    """Resultados LOCALES persistidos hoy. Fallos/ya_hecho no escritos = desconocidos.

    Solo se puede atribuir por familia cuando las notas guardaron procedencia.
    No calcula tasa de conversion ni afirma estado actual de follow.
    """
    import datetime
    today = today or datetime.date.today()
    # El mismo contrato de lectura usado por el filtro debe cumplirse aquí.
    read_history(path)
    out = defaultdict(lambda: {"confirmadas": 0, "pendientes": 0,
                               "ya_observadas": 0})
    if not Path(path).exists():
        return {}
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, strict=True):
            if (row.get("fecha") or "").strip() != today.isoformat():
                continue
            result = (row.get("resultado") or "").strip().casefold()
            kind = (row.get("tipo") or "").strip().casefold()
            observed = result == (
                "saltado_ya_like" if kind == "like_latest" else _OBSERVED.get(kind))
            if not observed and result not in _ACTION_RESULTS | {"pendiente_aprobacion"}:
                continue
            family = source_family(row.get("notas"))
            field = ("ya_observadas" if observed else
                     "confirmadas" if result in {"confirmado", "publicado"} else "pendientes")
            out[family][field] += 1
    return {family: dict(counts) for family, counts in sorted(out.items())}


def filter_known_plan(plan, follows, posts):
    """No altera orden, texto ni proveniencia. Nunca abre navegador/red."""
    kept, by_source = [], defaultdict(lambda: {"propuestas": 0, "descartadas_registro": 0})
    for item in plan:
        family = source_family(item.get("motivo") or item.get("source"))
        by_source[family]["propuestas"] += 1
        kind = item.get("kind")
        blocked = (kind == "follow" and
                   str(item.get("handle") or "").lstrip("@").casefold() in follows)
        if kind == "like_latest":
            handle = str(item.get("handle") or "").strip().lstrip("@").casefold()
            blocked = _BLOCKED_LATEST_PREFIX + handle in posts
        elif kind in _POST_KINDS:
            identifier = status_id(item.get("url"))
            blocked = identifier is not None and identifier in posts
        if blocked:
            by_source[family]["descartadas_registro"] += 1
        else:
            kept.append(item)
    return kept, {name: dict(values) for name, values in sorted(by_source.items())}

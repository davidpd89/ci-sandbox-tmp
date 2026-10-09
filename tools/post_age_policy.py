"""Politica comun anti-necroposting (09/10/2026): nunca actuar sobre un post ajeno antiguo, en ninguna red.

Un solo criterio para los nueve ejecutores: `conversation_turn_policy.check_execution` (que todos llaman antes de cada accion) delega aqui.
La edad sale, por orden, de (1) una fecha inequívoca del destino (`post_created_at`, `target_created_at` o un post anidado) o (2) el instante embebido en el
ID del post cuando la red lo codifica (X: snowflake; Bluesky: TID del rkey). En Mastodon
los IDs son opacos: no se interpreta como fecha el ID local de un estado federado.
Las respuestas, comentarios y citas sin fecha de destino verificable se omiten antes de
la escritura; otras acciones conservan la compatibilidad y se cuentan como edad_desconocida.
"""
from __future__ import annotations

import datetime as dt
import re

# dias maximos de antiguedad del post destino por tipo de accion
MAX_AGE_DAYS = {"reply": 3, "comment": 3, "comment_external": 3, "quote": 3, "like": 21, "like_external": 21, "favourite": 21, "like_latest": 21, "react": 21, "vote": 21, "boost": 7, "repost": 7}   # likes: como growth_policy (21 d a lector nuevo); boost/repost y texto, mas estrictos
TEXT_KINDS = frozenset({"reply", "comment", "comment_external", "quote"})
FOLLOWUP_MAX_AGE_DAYS = 7           # contestar a quien nos escribio: el comentario puede tardar mas en recibir respuesta, pero no semanas
_DATE_FIELDS = ("target_created_at", "post_created_at", "created_at", "createdAt", "created_utc", "create_time", "created_time", "published_at")
_TWITTER_EPOCH_MS = 1288834974657
_B32 = "234567abcdefghijklmnopqrstuvwxyz"


def _aware(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value


def _parse(value):
    if isinstance(value, dt.datetime):
        return value if value.tzinfo is not None and value.utcoffset() is not None else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value <= 1e9:
            return None
        try:
            return dt.datetime.fromtimestamp(value / (1000 if value > 1e11 else 1), dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and re.fullmatch(r"[0-9]{10}(?:[0-9]{3})?", value.strip()):
        return _parse(int(value.strip()))
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        # Una hora local sin huso no es una fecha UTC verificable.
        return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None
    except (ValueError, TypeError):
        return None


def _snowflake_x(sid):
    sid = str(sid or "")
    if sid.isdigit() and len(sid) >= 17:
        try:
            return dt.datetime.fromtimestamp(((int(sid) >> 22) + _TWITTER_EPOCH_MS) / 1000, dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _tid_bluesky(rkey):
    rkey = str(rkey or "")
    if len(rkey) != 13 or rkey[0] not in "234567abcdefghij" or any(ch not in _B32 for ch in rkey):
        return None
    value = 0
    for ch in rkey:
        value = (value << 5) | _B32.index(ch)
    micros = (value >> 10) & ((1 << 53) - 1)
    try:
        return dt.datetime.fromtimestamp(micros / 1_000_000, dt.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


_URLSAFE_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_META_EPOCH_MS = 1314220021721      # esquema de ID de Instagram/Threads: (id >> 23) + epoch en ms


def _threads_shortcode(code):
    """Instante embebido en el shortcode de /post/<code> (ID de servidor, el autor no lo elige).

    Comprobado empiricamente el 09/10/2026 con 253 permalinks reales (251 caen en la ventana del escaneo, 2 en enero): NO hay doc oficial.
    Fuera de 2020..ahora se trata como desconocido, nunca como fecha valida.
    """
    code = str(code or "")
    if not 8 <= len(code) <= 14 or any(ch not in _URLSAFE_B64 for ch in code):
        return None
    value = 0
    for ch in code:
        value = value * 64 + _URLSAFE_B64.index(ch)
    try:
        when = dt.datetime.fromtimestamp(((value >> 23) + _META_EPOCH_MS) / 1000, dt.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return when if dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc) <= when else None


def _target_ref(item, network=None):
    # Priorizar el destino de la acción por encima de IDs auxiliares de
    # notificación/conversación. No convertir la fecha de otro objeto en la
    # fecha del post que se va a comentar.
    if network == "x":
        keys = ("url", "post_url", "permalink", "target_post_id", "status_id", "_target_uri", "post_uri")
    elif network == "bluesky":
        keys = ("_target_uri", "post_uri", "url", "post_url", "permalink", "target_post_id", "status_id")
    elif network == "threads":
        keys = ("url", "post_url", "permalink", "target_post_id", "status_id")
    else:
        keys = ("status_id", "_target_uri", "post_uri", "target_post_id", "url", "post_url", "permalink")
    for key in keys:
        if item.get(key):
            yield str(item[key])


def _explicit_post_datetime(item):
    """No confundir created_at del trabajo/cola con fecha del objetivo de texto."""
    # created_at / createdAt en la raíz del plan pueden indicar la fecha de
    # ENCOLADO, no la fecha del destino. Nunca certifican antigüedad para
    # ninguna acción: los timestamps del post deben viajar como target_/post_
    # o dentro del objeto post/record obtenido del proveedor.
    fields = tuple(field for field in _DATE_FIELDS if field not in ("created_at", "createdAt"))
    for field in fields:
        if item.get(field):
            when = _parse(item[field])
            if when is not None:
                return when
    # Contratos reales: BlueSky app.bsky.feed.post.record.createdAt;
    # APIs que exponen objeto post/media con fecha de origen.
    post = item.get("post")
    nested_records = (
        post,
        item.get("record"),
        post.get("record") if isinstance(post, dict) else None,
    )
    for nested in nested_records:
        if not isinstance(nested, dict):
            continue
        for field in _DATE_FIELDS:
            if nested.get(field):
                when = _parse(nested[field])
                if when is not None:
                    return when
    return None


def post_datetime(network, item):
    """Fecha declarada por el post o estimación del identificador si no existe."""
    declared = _explicit_post_datetime(item)
    if declared is not None:
        return declared
    # Un identificador auxiliar puede no contener fecha; probar las restantes
    # referencias al destino antes de declarar edad desconocida.
    for ref in _target_ref(item, network):
        when = None
        if network == "x":
            match = re.search(r"/status/(\d+)", ref) or re.fullmatch(r"(\d+)", ref)
            when = _snowflake_x(match.group(1)) if match else None
        elif network == "bluesky":
            when = _tid_bluesky(ref.rstrip("/").rsplit("/", 1)[-1])
        elif network == "threads":
            match = re.search(r"/post/([A-Za-z0-9_-]{8,14})", ref)
            when = _threads_shortcode(match.group(1)) if match else None
        if when is not None:
            return when
    return None


def _plausible(when, now):
    # No imponer un inicio arbitrario: Reddit tiene posts anteriores a 2016.
    # La antigüedad enorme se bloquea, no se reinterpreta como desconocida.
    return when is not None and when <= now + dt.timedelta(minutes=5)


def _is_followup(item):
    reason = str(item.get("motivo") or "").casefold()
    return item.get("reply_to_us") is True or any(
        token in reason for token in ("followup", "contestar_a_su_comentario", "respuesta_a_su_comentario"))


def age_days(network, item, *, now=None):
    now = _aware(now) if now else dt.datetime.now(dt.timezone.utc)
    if (network == "bluesky" and isinstance(item, dict)
            and item.get("kind") in TEXT_KINDS
            and _explicit_post_datetime(item) is None):
        return None  # TID reciente no autentica la edad de una respuesta
    when = post_datetime(network, item)
    return (now - when).total_seconds() / 86400 if _plausible(when, now) else None


def check(network, item, *, now=None):
    """(permitido, motivo). Fecha desconocida impide texto, no tumba la ronda."""
    kind = item.get("kind") if isinstance(item, dict) else None
    text_action = isinstance(kind, str) and kind in TEXT_KINDS
    try:
        limit = MAX_AGE_DAYS.get(kind)
        if limit is None:
            return True, "accion_sin_tope_de_edad"
        if kind in ("reply", "comment", "comment_external") and _is_followup(item):
            limit = FOLLOWUP_MAX_AGE_DAYS
        now = _aware(now) if now else dt.datetime.now(dt.timezone.utc)
        when = post_datetime(network, item)
        # Un timestamp explícito de futuro lejano no da un pase fail-open.
        if when is not None and when > now + dt.timedelta(minutes=5):
            return False, "fecha_futura_inverosimil"
        age = (now - when).total_seconds() / 86400 if when is not None else None
        if age is None:
            return not text_action, "edad_desconocida"
        if age > limit:
            return False, "post_antiguo"
        # ATProto: un TID puede ser elegido por el autor; no autoriza texto.
        # Una fecha explícita del post sigue siendo necesaria para respuesta.
        if network == "bluesky" and text_action and _explicit_post_datetime(item) is None:
            return False, "edad_desconocida"
        return True, "edad_ok"
    except Exception:       # noqa: BLE001 - las acciones de texto fallan cerradas ante datos invalidos
        return not text_action, "edad_desconocida"

def audit_plan(network, plan, *, now=None):
    """Resumen read-only sin objetivos ni textos privados, para instrumentar el embudo."""
    summary = {"red": network, "total": 0, "edad_desconocida": 0,
               "antiguas": 0, "fechas_inverosimiles": 0,
               "admisibles": 0, "desconocidas_respuesta": 0}
    for item in plan:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        if kind not in MAX_AGE_DAYS:
            continue
        summary["total"] += 1
        accepted, reason = check(network, item, now=now)
        if reason == "edad_desconocida":
            summary["edad_desconocida"] += 1
            if kind in ("reply", "comment", "comment_external", "quote"):
                summary["desconocidas_respuesta"] += 1
        elif reason == "fecha_futura_inverosimil":
            summary["fechas_inverosimiles"] += 1
        elif not accepted:
            summary["antiguas"] += 1
        else:
            summary["admisibles"] += 1
    return summary


# Rutas de planes de mechanical_round.py comprobadas en integración (09/10/2026).
# Reddit no tiene una ruta única verificada dentro de ese orquestador.
PLAN_SNAPSHOTS = {
    "bluesky": "bluesky_mech_plan.json",
    "mastodon": "mastodon_mech_plan.json",
    "x": "SISTEMA_DIARIO_X/x_plan.json",
    "threads": "SISTEMA_DIARIO_THREADS/threads_plan.json",
    "facebook": "SISTEMA_DIARIO_FACEBOOK/facebook_plan.json",
    "pinterest": "SISTEMA_DIARIO_PINTEREST/pinterest_plan.json",
    "tiktok": "tiktok_plan.json",
    "instagram": "SISTEMA_DIARIO_INSTAGRAM/instagram_plan.json",
    "reddit": None,
}


def audit_recent_plans(root, *, now=None, max_age_hours=36):
    """Lectura offline de planes; sólo agrega contadores, nunca textos/URLs."""
    import json
    import os
    now = _aware(now) if now else dt.datetime.now(dt.timezone.utc)
    if max_age_hours <= 0:
        raise ValueError("max_age_hours debe ser positivo")
    summaries = {}
    for network, relative in PLAN_SNAPSHOTS.items():
        if relative is None:
            summaries[network] = {"estado": "sin_ruta_verificada"}
            continue
        path = os.path.join(root, relative)
        try:
            info = os.stat(path)
            age_h = (now.timestamp() - info.st_mtime) / 3600
            if age_h < -1 or age_h > max_age_hours:
                summaries[network] = {"estado": "plan_no_reciente"}
                continue
            if info.st_size > 4_000_000:
                summaries[network] = {"estado": "plan_demasiado_grande"}
                continue
            with open(path, encoding="utf-8") as stream:
                items = json.load(stream)
            if not isinstance(items, list):
                raise ValueError("plan no es lista")
            summaries[network] = {"estado": "ok", **audit_plan(network, items, now=now)}
        except FileNotFoundError:
            summaries[network] = {"estado": "sin_plan"}
        except (OSError, ValueError, TypeError, UnicodeError, OverflowError):
            summaries[network] = {"estado": "plan_invalido"}
    return summaries


def main(argv=None):
    """Auditoría SOLO LECTURA de snapshots o plan concreto, sin PII en salida."""
    import argparse
    import json
    import os
    parser = argparse.ArgumentParser()
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument("--network", choices=(
        "x", "threads", "facebook", "pinterest", "reddit", "bluesky",
        "mastodon", "tiktok", "instagram"))
    commands.add_argument("--audit-recent", action="store_true",
                          help="resumen por red de snapshots recientes; sin URLs, textos ni IDs")
    parser.add_argument("--plan", help="ruta JSON del plan que se audita")
    parser.add_argument("--root", help="raíz del checkout para --audit-recent")
    args = parser.parse_args(argv)
    if args.audit_recent:
        if args.plan:
            parser.error("--plan no se combina con --audit-recent")
        root = args.root or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        result = audit_recent_plans(root)
        # NO transformar una ruta desconocida/ausente en '0 respuestas'.
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if not args.plan or args.root:
        parser.error("--network requiere --plan, sin --root")
    with open(args.plan, encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, list):
        parser.error("--plan debe ser una lista de acciones")
    print(json.dumps(audit_plan(args.network, payload), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Análisis offline de respuestas Graph de posts de una Página de Facebook.

NO consulta Meta, no comprueba permisos efectivos, no guarda IDs de terceros
y nunca alimenta premios, follows, respuestas ni acciones. Un JSON aportado
por un tercero no acredita procedencia, acceso o titularidad.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import stat

_ID = re.compile(r"[0-9]{1,40}\Z")
_COMMENT_ID = re.compile(r"[0-9]+(?:_[0-9]+)*\Z")
MAX_BYTES = 256_000
MAX_POSTS = 100
MAX_COMMENTS_PER_POST = 500
WINDOW_DAYS = 14


def _time(value):
    if not isinstance(value, str) or len(value) > 45:
        return None
    try:
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp if stamp.tzinfo and stamp.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _paging_complete(obj):
    if not isinstance(obj, dict):
        return False
    paging = obj.get("paging")
    return paging is None or (isinstance(paging, dict) and "next" not in paging)


def _empty(status):
    return {"network": "facebook", "surface": "own_page_posts",
            "status": status, "permission_verified": False,
            "comments_observed_14d": None, "reactions_aggregate": None,
            "page_posts_observed": None, "can_reward_or_reply": False,
            "coverage": "no_live_access_proven"}


def assess(payload, page_id, *, now=None):
    """Solo observa comentarios directos y totales agregados de posts propios.

    Requiere una captura estructurada ya recibida con la autorización adecuada
    por un operador externo. El análisis no puede autenticar esa captura.
    Ninguna ausencia de permisos, campos o páginas paginadas significa cero.
    """
    if not isinstance(page_id, str) or not _ID.fullmatch(page_id):
        raise ValueError("identidad de Página inválida")
    now = dt.datetime.now(dt.timezone.utc) if now is None else now
    if not isinstance(now, dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("reloj debe llevar zona horaria")
    if not isinstance(payload, dict):
        return _empty("invalid_payload")
    if isinstance(payload.get("error"), dict):
        code = payload["error"].get("code")
        return _empty({200: "permission_denied", 10: "permission_denied",
                       283: "permission_denied", 190: "invalid_token",
                       4: "rate_limited", 17: "rate_limited",
                       32: "rate_limited", 429: "rate_limited",
                       613: "rate_limited",
                       80001: "rate_limited", 368: "platform_block"}.get(code, "api_error")
                      if type(code) is int else "api_error")
    if (payload.get("surface") != "page_posts"
            or payload.get("page_id") != page_id
            or "group_id" in payload
            or not isinstance(payload.get("posts"), dict)):
        return _empty("out_of_scope")
    posts = payload["posts"]
    rows = posts.get("data")
    if (not isinstance(rows, list) or len(rows) > MAX_POSTS
            or "group_id" in posts or not _paging_complete(posts)):
        return _empty("incomplete")
    if not rows:
        # La API/cliente podría devolver lista vacía sin visibilidad:
        # sin posts observados no hay denominador fiable.
        return _empty("empty_unverified")
    comments_total, reaction_total = 0, 0
    reactions_complete = True
    seen_posts, seen_comments = set(), set()
    for post in rows:
        if not isinstance(post, dict) or "group_id" in post:
            return _empty("out_of_scope")
        post_id = post.get("id")
        owner = post.get("from")
        if (not isinstance(post_id, str)
                or not post_id.startswith(page_id + "_")
                or not _COMMENT_ID.fullmatch(post_id)
                or post_id in seen_posts
                or not isinstance(owner, dict)
                or owner.get("id") != page_id):
            return _empty("invalid_post_identity")
        seen_posts.add(post_id)
        comments = post.get("comments")
        if (not isinstance(comments, dict) or not _paging_complete(comments)
                or comments.get("filter") != "toplevel"):
            return _empty("incomplete")
        entries = comments.get("data")
        if not isinstance(entries, list) or len(entries) > MAX_COMMENTS_PER_POST:
            return _empty("incomplete")
        summary = comments.get("summary")
        if (not isinstance(summary, dict) or
                type(summary.get("total_count")) is not int or
                summary["total_count"] != len(entries)):
            return _empty("incomplete")
        for item in entries:
            if not isinstance(item, dict) or "group_id" in item:
                return _empty("invalid_comment")
            comment_id, author, parent = item.get("id"), item.get("from"), item.get("parent")
            if (not isinstance(comment_id, str) or not _COMMENT_ID.fullmatch(comment_id)
                    or comment_id in seen_comments or not isinstance(author, dict)
                    or not isinstance(author.get("id"), str)
                    or not _ID.fullmatch(author["id"])):
                return _empty("invalid_comment")
            seen_comments.add(comment_id)
            if any(key in item and type(item[key]) is not bool
                   for key in ("is_private", "is_hidden")):
                return _empty("invalid_comment")
            if item.get("is_private") is True or item.get("is_hidden") is True:
                return _empty("incomplete")  # no atribuir privados/ocultos
            if parent is not None:
                # En Meta Comment.parent describe una RESPUESTA A UN
                # comentario; no es el post propietario. Solo toplevel.
                if not isinstance(parent, dict):
                    return _empty("invalid_comment")
                continue
            stamp = _time(item.get("created_time"))
            if stamp is None or stamp > now:
                return _empty("invalid_comment")
            if author["id"] != page_id and now - stamp <= dt.timedelta(days=WINDOW_DAYS):
                comments_total += 1
        reaction = post.get("reactions")
        if not isinstance(reaction, dict) or not isinstance(reaction.get("summary"), dict):
            reactions_complete = False
        else:
            count = reaction["summary"].get("total_count")
            if type(count) is not int or not 0 <= count <= 1_000_000_000:
                return _empty("invalid_reactions")
            reaction_total += count
    return {**_empty("observed_unverified"),
            "comments_observed_14d": comments_total,
            "reactions_aggregate": reaction_total if reactions_complete else None,
            "page_posts_observed": len(seen_posts)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Facebook Página: lectura offline sin permisos asumidos")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--now", help="fecha/hora ISO con zona, para pruebas")
    args = parser.parse_args(argv)
    try:
        if args.input.is_symlink() or not args.input.is_file() or args.input.stat().st_size > MAX_BYTES:
            raise ValueError("archivo inválido o demasiado grande")
        if not stat.S_ISREG(args.input.stat().st_mode):
            raise ValueError("se requiere fichero regular")
        with args.input.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("entrada demasiado grande")
        def no_constant(value):
            raise ValueError("constante JSON inválida")
        def no_duplicate_keys(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("clave JSON duplicada")
                result[key] = value
            return result
        payload = json.loads(raw.decode("utf-8"), parse_constant=no_constant,
                             object_pairs_hook=no_duplicate_keys)
        now = _time(args.now) if args.now is not None else None
        if args.now is not None and now is None:
            raise ValueError("fecha inválida")
        report = assess(payload, args.page_id, now=now)
    except (OSError, UnicodeError, ValueError, RecursionError, OverflowError):
        print("CAPTURA_NO_VALIDA")
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Entradas verificables X/Threads: medición local, SIN ejecutar premios.

Solo se aceptan IDs de eventos y origen estructurado de API. Los dumps de
notificaciones web no prueban si un like/reply es nuestro ni aportan IDs fiables.
El registro histórico por (día, cuenta, tipo) permanece para lectura; no se
migra ni se usa como prueba de identidad de un evento individual.
"""
from __future__ import annotations

import datetime as dt
from contextlib import closing
import os
from pathlib import Path
import sqlite3

DEFAULT_DB = Path(__file__).resolve().parents[1] / "00_OPERATIVO" / "inbound_eventos_verificados.sqlite"


def _valid_id(value):
    return (isinstance(value, str) and value.isascii() and value.isdecimal()
            and 0 < len(value) <= 40)


def _day(value):
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def x_mentions(payload, own_user_id):
    """Convierte SOLO respuesta estructurada de GET /2/users/{id}/mentions.

    El llamador debe acreditar que la API se consultó para `own_user_id`.
    Una mención no se considera reply sin `in_reply_to_user_id` coincidente.
    Ningún texto o avatar del navegador crea eventos.
    """
    if not _valid_id(own_user_id) or not isinstance(payload, dict):
        return []
    users = (payload.get("includes") or {}).get("users", [])
    if not isinstance(users, list) or not isinstance(payload.get("data"), list):
        return []
    actors = {u["id"]: u["username"] for u in users
              if isinstance(u, dict) and _valid_id(u.get("id"))
              and isinstance(u.get("username"), str) and u["username"].strip()}
    result = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        event_id, author = item.get("id"), item.get("author_id")
        if not _valid_id(event_id) or not _valid_id(author) or author == own_user_id or author not in actors:
            continue
        day = _day(item.get("created_at"))
        if not day:
            continue
        kind = "comment" if item.get("in_reply_to_user_id") == own_user_id else "mention"
        result.append({"network": "x", "event_id": event_id, "author_id": author,
                       "handle": actors[author], "kind": kind, "day": day,
                       "source": "api:users_mentions", "target_id": own_user_id})
    return result


def threads_replies(rows, own_username, root_post_id):
    """Solo respuestas de GET /{post_id}/replies del post propio verificado."""
    if not _valid_id(root_post_id) or not isinstance(own_username, str) or not own_username.strip():
        return []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        event_id, who = row.get("id"), row.get("username")
        if not _valid_id(event_id) or not isinstance(who, str) or not who.strip():
            continue
        if who.casefold().lstrip("@") == own_username.casefold().lstrip("@"):
            continue
        root, parent = row.get("root_post"), row.get("replied_to")
        if not isinstance(root, (dict, type(None))) or not isinstance(parent, (dict, type(None))):
            continue
        # `root_post` en una respuesta ANIDADA puede señalar nuestro post
        # aunque el destinatario real sea OTRO usuario. Solo contar replies
        # directamente dirigidas al post propio.
        target = (parent or {}).get("id")
        day = _day(row.get("timestamp"))
        if target != root_post_id or (root and root.get("id") != root_post_id) or not day:
            continue
        out.append({"network": "threads", "event_id": event_id, "author_id": "",
                    "handle": who.lstrip("@"), "kind": "comment", "day": day,
                    "source": "api:own_post_replies", "target_id": root_post_id})
    return out


def record(events, *, path=None):
    """INSERT OR IGNORE atómico; conserva eventos separados del mismo autor/día.

    No actualiza relationship_policy.INBOUND ni desencadena publicación, follow,
    like o respuesta. La migración de política necesita reconciliar legados.
    """
    path = Path(path or os.environ.get("RRSS_VERIFIED_INBOUND_DB") or DEFAULT_DB)
    valid = []
    for item in events:
        if (not isinstance(item, dict) or item.get("network") not in ("x", "threads")
                or item.get("source") not in ("api:users_mentions", "api:own_post_replies")
                or not _valid_id(item.get("event_id"))
                or not isinstance(item.get("handle"), str) or not item["handle"].strip()
                or any(ch.isspace() for ch in item["handle"].strip())
                or item.get("kind") not in ("mention", "comment")
                or not isinstance(item.get("day"), str)
                or not _valid_id(item.get("target_id"))
                or not _day(item.get("day")) == item.get("day")
                or (item["network"] == "x"
                    and (item["source"] != "api:users_mentions"
                         or not _valid_id(item.get("author_id"))))
                or (item["network"] == "threads"
                    and (item["source"] != "api:own_post_replies"
                         or item["kind"] != "comment"))):
            raise ValueError("evento entrante sin identidad/procedencia verificable")
        valid.append(item)
    if not valid:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    # sqlite3.Connection.__exit__ NO cierra la conexión en Windows.
    # closing evita candados y fuga de handles tras commits/errores.
    with closing(sqlite3.connect(path, timeout=10)) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS verified_inbound (
            network TEXT NOT NULL, event_id TEXT NOT NULL, author_id TEXT,
            handle TEXT NOT NULL, kind TEXT NOT NULL, day TEXT NOT NULL,
            source TEXT NOT NULL, target_id TEXT NOT NULL,
            PRIMARY KEY (network, event_id))""")
        before = db.total_changes
        for item in valid:
            db.execute("""INSERT OR IGNORE INTO verified_inbound
                (network,event_id,author_id,handle,kind,day,source,target_id)
                VALUES (:network,:event_id,:author_id,:handle,:kind,:day,:source,:target_id)""", item)
            stored = db.execute("""SELECT author_id,handle,kind,day,source,target_id
                FROM verified_inbound WHERE network=? AND event_id=?""",
                (item["network"], item["event_id"])).fetchone()
            expected = tuple(item.get(field) or "" for field in
                             ("author_id", "handle", "kind", "day", "source", "target_id"))
            if stored != expected:
                raise ValueError("colision: mismo ID de evento con autor o procedencia distinta")
        return db.total_changes - before


def read_threads_api(api_get, token, own_username, *, max_posts=25, max_pages=3):
    """Lee respuestas de posts propios; no escribe, no asume paginación total.

    `api_get(path, token, **params)` se inyecta para pruebas herméticas.
    Un fallo de permisos, paginado o respuesta incompleta provoca excepción:
    ninguna fila se guarda automáticamente.
    """
    if (not isinstance(max_posts, int) or isinstance(max_posts, bool)
            or not 1 <= max_posts <= 100
            or not isinstance(max_pages, int) or isinstance(max_pages, bool)
            or not 1 <= max_pages <= 100):
        raise ValueError("Threads: límites de lectura inválidos")
    mine = api_get("me/threads", token, fields="id,is_reply,has_replies", limit=max_posts)
    if not isinstance(mine, dict) or not isinstance(mine.get("data"), list):
        raise ValueError("Threads: listado de posts incompleto")
    # La paginación también existe en me/threads, no solo en /replies.
    # Nunca guardar un snapshot parcial como una cosecha íntegra.
    paging = mine.get("paging") or {}
    if (not isinstance(paging, dict) or paging.get("next")
            or len(mine["data"]) > max_posts):
        raise ValueError("Threads: hay más posts propios o paginación inválida")
    out = []
    for post in mine["data"]:
        if not isinstance(post, dict) or not _valid_id(post.get("id")):
            raise ValueError("Threads: post sin ID")
        if (type(post.get("is_reply")) is not bool
                or type(post.get("has_replies")) is not bool):
            raise ValueError("Threads: is_reply/has_replies no verificables")
        # Si falta is_reply no se puede acreditar que sea un post propio
        # inicial y no una respuesta nuestra dentro de un hilo ajeno.
        if post["is_reply"] or not post["has_replies"]:
            continue
        cursor = None
        seen_cursors = set()
        for _ in range(max_pages):
            params = {"fields": "id,username,timestamp,root_post,replied_to", "limit": 50}
            if cursor:
                params["after"] = cursor
            page = api_get(f"{post['id']}/replies", token, **params)
            if not isinstance(page, dict) or not isinstance(page.get("data"), list):
                raise ValueError("Threads: replies ilegibles")
            out.extend(threads_replies(page["data"], own_username, post["id"]))
            paging = page.get("paging") or {}
            if not isinstance(paging, dict):
                raise ValueError("Threads: paginación inválida")
            if not paging.get("next"):
                break
            cursor = (paging.get("cursors") or {}).get("after")
            if not cursor:
                raise ValueError("Threads: siguiente página sin cursor")
            if not isinstance(cursor, str) or cursor in seen_cursors:
                raise ValueError("Threads: cursor inválido/repetido")
            seen_cursors.add(cursor)
        else:
            if cursor:
                raise ValueError("Threads: paginación parcial; no certificar captura completa")
    return out

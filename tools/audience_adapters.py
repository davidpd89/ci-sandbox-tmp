"""Adaptadores puros de exportaciones/API ya recuperadas al contrato común.

Ninguna petición HTTP, sesión ni acción social. Importar, no recolectar en vivo.
`adapt_page` produce el objeto esperado por audience_discovery.collect_pages;
la procedencia y la antigüedad se aportan desde el escáner/hidratador existente.
"""
from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Mapping
from typing import Any

import audience_discovery as core

FIELDS = {
    "bluesky": {"like": "likes", "repost": "repostedBy", "comment": "replies", "reply": "replies"},
    "mastodon": {"like": "items", "repost": "items", "comment": "items", "reply": "items"},
    "reddit": {"comment": "comments", "reply": "comments"},
    "x": {"like": "users", "repost": "users", "comment": "tweets", "reply": "tweets"},
    "threads": {"comment": "data", "reply": "data"},
    "facebook": {"like": "data", "repost": "data", "comment": "data", "reply": "data"},
    "pinterest": {"comment": "comments", "reply": "comments"},
    "instagram": {"like": "likers", "comment": "comments", "reply": "comments"},
    "tiktok": {"comment": "comments", "reply": "comments"},
}


def _utc(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    return core.timestamp(value)


def _actor(raw: Mapping) -> Mapping | None:
    for key in ("actor", "account", "user", "from"):
        if isinstance(raw.get(key), Mapping):
            return raw[key]
    # Los rosters de Mastodon / X devuelven directamente una cuenta.
    if any(raw.get(k) for k in ("did", "acct", "username", "screen_name", "sec_uid", "pk")):
        return raw
    if isinstance(raw.get("author"), Mapping):
        return raw["author"]
    if isinstance(raw.get("author"), str) and raw["author"].strip():
        return {"handle": raw["author"], "author_fullname": raw.get("author_fullname")}
    if raw.get("handle"):
        return {"handle": raw["handle"], "id": raw.get("author_id")}
    return None


def adapt_page(network: str, kind: str, payload: Mapping, *, post_key: str,
               post_created_at: str | None = None, source_instance: str | None = None) -> dict:
    """Contrato de importación explícito. No se convierte un count agregado a usuarios.

    Se exigen IDs de comentario/reply; los likers sin edge ID admiten derivación
    estable (red + post + actor). Los registros incompletos fallan, no se omiten
    silenciosamente (para no falsear denominadores de discovery).
    """
    if kind not in FIELDS.get(network, {}):
        raise core.ObservationError("fuente_no_observable")
    if not isinstance(payload, Mapping):
        raise core.ObservationError("export_invalido")
    field = FIELDS[network][kind]
    if field not in payload or not isinstance(payload[field], (list, tuple)):
        raise core.ObservationError("export_sin_lista_de_actores")
    items = []
    for entry in payload[field]:
        if not isinstance(entry, Mapping):
            raise core.ObservationError("fila_no_es_mapa")
        actor = _actor(entry)
        if actor is None:
            raise core.ObservationError("actor_ausente_en_export")
        event_id = (entry.get("event_id") or entry.get("comment_id") or
                    (entry.get("id") if kind in ("comment", "reply") else None) or
                    (entry.get("uri") if kind in ("comment", "reply") else None))
        if kind in ("comment", "reply") and not event_id:
            raise core.ObservationError("comentario_sin_id")
        row = {
            "actor": actor,
            "event_id": str(event_id) if event_id else None,
            "text": str(next((entry[k] for k in ("text", "body", "message",
                        "comment_text", "content") if entry.get(k)), "")),
            "occurred_at": _utc(next((entry[k] for k in ("occurred_at",
                        "createdAt", "created_at", "created_utc", "create_time")
                        if entry.get(k) is not None), None)),
            "deleted": entry.get("deleted") is True,
        }
        if network == "mastodon":
            row["instance"] = source_instance or entry.get("instance")
        items.append(row)
    cursors = payload.get("paging", {}).get("cursors", {}) if isinstance(payload.get("paging"), Mapping) else {}
    cursor = payload.get("next_cursor")
    # Respuesta nativa de app.bsky.feed.getLikes/getRepostedBy: `cursor`.
    if cursor is None and network == "bluesky":
        cursor = payload.get("cursor")
    if cursor is None and isinstance(cursors, Mapping):
        cursor = cursors.get("after")
    if cursor is None:
        cursor = payload.get("bookmark")
    if cursor is not None:
        if isinstance(cursor, bool) or not isinstance(cursor, (str, int)):
            raise core.ObservationError("cursor_tipo_invalido")
        cursor = str(cursor)
        if not cursor.strip():
            cursor = None
    # Evitar persistir URLs de paging.next con query strings o tokens.
    return {"items": items, "kind": kind, "post_key": str(post_key),
            "post_created_at": post_created_at, "next_cursor": cursor}

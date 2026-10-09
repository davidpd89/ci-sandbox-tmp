"""Regla común de continuación de conversaciones.

Una respuesta no se justifica por existir una notificación. La decisión debe
poder ser NO_REPLY y el escritor GPT recibirá turnos previos de una fuente
fiable. Los adaptadores de red reconstruyen la conversación y pasan
`thread_turns`; no insertan estrategias distintas.
"""
from __future__ import annotations

import re
import unicodedata

import scan_common as sc

_THANKS = re.compile(
    r"^(?:muchas\s+)?gracias(?:\s+(?:compa(?:nero|ñero|ñera)|a\s+ti|por\s+todo|de\s+verdad))?[.! ]*$",
    re.I,
)
_GENERIC_CLOSE = re.compile(
    r"^(?:genial|perfecto|vale|hecho|estupendo|me\s+alegro|jaja+|jeje+|ok|"
    r"un\s+abrazo|saludos)(?:[.! ]*)$", re.I,
)


def _plain(text):
    cleaned = re.sub(r"https?://\S+|@\S+", " ", str(text or ""))
    cleaned = unicodedata.normalize("NFKC", cleaned)
    return " ".join(cleaned.strip().split())


def is_closed_turn(text):
    """Cierres sociales que no generan texto aunque el modelo pueda inventarlo."""
    raw = _plain(text).replace(",", " ")
    if not raw:
        return True
    if "?" in raw or "¿" in raw:
        return False
    plain = raw.strip(" ¡!.,")
    return bool(_THANKS.fullmatch(plain) or _GENERIC_CLOSE.fullmatch(plain)
                or sc.is_conversation_closer(raw))


def decide_next_turn(text, *, replying_to_us=True, earlier_own_turns=1,
                     thread_complete=False):
    """Decide si corresponde evaluar una respuesta en GPT; no la redacta.

    Solo los cierres inequívocos dan NO_REPLY automáticamente. Una opinión,
    entusiasmo o agradecimiento con contenido nuevo puede merecer respuesta
    aunque no incluya interrogación. Si el historial está incompleto, GPT
    recibe un aviso explícito y decide entre respuesta prudente y null.
    """
    if is_closed_turn(text):
        return "NO_REPLY", "cierre_social"
    if not _plain(text):
        return "NO_REPLY", "sin_contenido"
    if not replying_to_us:
        return "NEEDS_CONTEXT", "verificar_relacion_con_el_hilo"
    if thread_complete:
        return "REPLY", "valorar_conversacion_completa_en_GPT"
    return "NEEDS_CONTEXT", "contexto_parcial_para_GPT"


def normalize_turns(turns, *, max_turns=20):
    """Contexto serializable con roles, sin cambiar ni obedecer contenido ajeno."""
    if not isinstance(turns, (list, tuple)) or not turns or len(turns) > max_turns:
        return []
    result = []
    for turn in turns:
        if not isinstance(turn, dict):
            return []
        role = turn.get("role")
        text = _plain(turn.get("text"))
        target = str(turn.get("post_id") or "").strip()
        if role not in ("ours", "theirs") or not text or not target:
            return []
        result.append({"role": role, "text": text[:700], "post_id": target})
    if len({t["post_id"] for t in result}) != len(result):
        return []
    return result


def fetch_verified_thread(network, row, *, max_turns=20):
    """Recupera la cadena de padres hasta el post raíz, o retorna [].

    No dar por completo un hilo si falta un padre, se ha borrado o la API
    no devuelve el contexto. Las demás redes necesitarán sus adaptadores
    específicos antes de habilitar respuestas encadenadas automáticas.
    """
    ref = row.get("ref")
    if not ref:
        return []
    try:
        if network == "bluesky":
            import bluesky_interact as b
            did = b._session()["did"]
            response = b._get(
                b.AUTH_BASE, "app.bsky.feed.getPostThread",
                {"uri": ref, "parentHeight": max_turns, "depth": 0}, auth=True,
            )
            cursor = response.get("thread")
            nodes, seen = [], set()
            while isinstance(cursor, dict) and len(nodes) < max_turns:
                post = cursor.get("post")
                if not isinstance(post, dict) or not post.get("uri"):
                    return []
                uri = post["uri"]
                if uri in seen:
                    return []
                seen.add(uri)
                record = post.get("record") or {}
                nodes.append({
                    "role": "ours" if (post.get("author") or {}).get("did") == did else "theirs",
                    "text": record.get("text"),
                    "post_id": uri,
                })
                declared_parent = (record.get("reply") or {}).get("parent")
                parent = cursor.get("parent")
                if not declared_parent:
                    return normalize_turns(list(reversed(nodes)), max_turns=max_turns)
                if not isinstance(parent, dict):
                    return []
                cursor = parent
            return []
        if network == "mastodon":
            import mastodon_interact as m
            ctx = m.status_context(ref)
            target = m._get(f"statuses/{ref}")
            own = m._get("accounts/verify_credentials")
            ancestors = ctx.get("ancestors")
            if not isinstance(ancestors, list) or not isinstance(target, dict):
                return []
            if target.get("in_reply_to_id") and not ancestors:
                return []
            nodes = ancestors + [target]
            if len(nodes) > max_turns:
                return []
            return normalize_turns([{
                "role": "ours" if str((p.get("account") or {}).get("id")) == str(own.get("id")) else "theirs",
                "text": m._plain_text(p.get("content")),
                "post_id": str(p.get("id") or ""),
            } for p in nodes], max_turns=max_turns)
    except Exception:
        return []
    return []


def render_thread(turns):
    """Los turnos de terceros son contexto, no instrucciones del prompt."""
    normalized = normalize_turns(turns)
    if not normalized:
        return ""
    return "Historial verificado (de más antiguo a más reciente): " + " | ".join(
        f"[{i + 1} {entry['role']}] «{entry['text']}»"
        for i, entry in enumerate(normalized)
    )


_REPLY_KINDS = frozenset({"reply", "comment", "comment_external", "quote"})


def check_execution(network, item):
    """No enviar la última palabra de una conversación por un plan antiguo.

    Primeros comentarios a un post ajeno quedan para las validaciones normales.
    Los replies *de seguimiento* siempre requieren historial verificado y
    coherencia del destino; no confiar solo en un marcador textual del plan.
    """
    if item.get("kind") not in _REPLY_KINDS:
        return True, "accion_no_es_respuesta"
    reason = str(item.get("motivo") or "").casefold()
    is_followup = (
        item.get("reply_to_us") is True or
        "followup" in reason or
        "contestar_a_su_comentario" in reason or
        "respuesta_a_su_comentario" in reason
    )
    if not is_followup:
        return True, "primer_comentario_sin_cadena_previa"
    # Un plan antiguo o una red sin API de hilo no se bloquea por defecto:
    # comprobamos el texto recibido, nunca el texto que GPT acaba de generar.
    incoming = item.get("post_text") or item.get("inbound_text")
    turns = normalize_turns(item.get("thread_turns"))
    if not turns:
        if not _plain(incoming):
            return False, "falta_texto_de_la_persona"
        if is_closed_turn(incoming):
            return False, "cierre_social"
        return True, "historial_parcial_GPT_decide_null"

    target = (
        item.get("_target_uri") if network == "bluesky"
        else item.get("status_id") if network == "mastodon"
        else item.get("target_post_id")
    )
    if target and str(target) != turns[-1]["post_id"]:
        return False, "destino_no_coincide_con_hilo"
    if turns[-1]["role"] != "theirs":
        return False, "ultimo_turno_no_es_de_tercero"
    decision, why = decide_next_turn(
        turns[-1]["text"], replying_to_us=True,
        earlier_own_turns=sum(x["role"] == "ours" for x in turns[:-1]),
        thread_complete=True,
    )
    return decision == "REPLY", why

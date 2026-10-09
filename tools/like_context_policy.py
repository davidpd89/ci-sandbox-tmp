"""Regla editorial común de likes (8 redes). Sin interpretación visual -> abstenerse.

Un ALT o caption no equivale a haber inspeccionado la imagen. Para que una
fuente autorice un like debe aportar texto propio del post, informar si lleva
adjuntos visuales y no contener las señales de contenido ajeno al nicho.
Los adaptadores normalizan datos, pero NO redefinen esta decisión.
"""
from __future__ import annotations

import re
import unicodedata

import scan_common as sc
import adult_filter

_VISUAL = frozenset({"image", "images", "video", "gif", "animated_gif", "media", "recordwithmedia"})


def _words_without_metadata(text):
    text = re.sub(r"https?://\S+|@\S+|#\S+", " ", str(text or ""), flags=re.I)
    text = unicodedata.normalize("NFKC", text)
    return re.findall(r"[a-záéíóúüñ]+", text.casefold())


_NICHE = re.compile(
    r"\b(?:libro(?:s)?|novela(?:s)?|lectura(?:s)?|fantas[ií]a|"
    r"romantasy|escrit(?:or|ora|ura|ores|oras)|autor(?:a|es|as)?|"
    r"personaje(?:s)?|reseña(?:s)?|biblioteca|editorial|"
    r"portada(?:s)?|cap[ií]tulo(?:s)?|saga(?:s)?)\b", re.I,
)
_SENSITIVE_LABELS = frozenset({
    "porn", "sexual", "graphic-media", "nudity", "nsfw",
    "gore", "violence", "self-harm",
})


def can_like(text, *, media_present=None, sensitive=False):
    """Decisión editorial gradual a partir del texto ORIGINAL verificable.

    Una imagen sola (o con ALT) nunca basta. Cuando el POST contiene texto
    sustantivo de lectura/escritura, su adjunto no lo invalida por sí mismo,
    siempre que no haya etiquetas sensibles ni texto problemático.
    """
    if sensitive:
        return False, "contenido_sensible"
    if media_present is None:
        return False, "medios_no_verificados"
    words = _words_without_metadata(text)
    if len(words) < 2:
        return False, "sin_texto_interpretable"
    if sc.is_political(text) or sc.looks_activist(text) or adult_filter.is_adult_or_dating(text):
        return False, "tema_no_apropiado_para_like_automatico"
    if media_present:
        if len(words) < 5 or not _NICHE.search(str(text or "")):
            return False, "adjunto_sin_contexto_literario_suficiente"
        return True, "texto_literario_sustantivo_con_adjunto"
    return True, "post_textual_verificado"


def bluesky_sensitive(post):
    post = post if isinstance(post, dict) else {}
    author = post.get("author") if isinstance(post.get("author"), dict) else {}
    record = post.get("record") if isinstance(post.get("record"), dict) else {}
    own = record.get("labels")
    if isinstance(own, dict):
        own = own.get("values")
    labels = []
    for values in (post.get("labels"), author.get("labels"), own):
        if isinstance(values, list):
            labels.extend(values)
    return any(str(label.get("val") if isinstance(label, dict) else label).casefold()
               in _SENSITIVE_LABELS for label in labels)


def bluesky_has_visual(post):
    """Lexicons ATProto: una cita o tarjeta externa no es una imagen propia."""
    if not isinstance(post, dict):
        return None
    record = post.get("record") if isinstance(post.get("record"), dict) else {}
    embeds = [e for e in (record.get("embed"), post.get("embed")) if e is not None]
    if not embeds:
        return False
    observed_unknown = False
    for embed in embeds:
        if not isinstance(embed, dict):
            observed_unknown = True
            continue
        kind = str(embed.get("$type") or "").casefold()
        if kind.startswith(("app.bsky.embed.images", "app.bsky.embed.video",
                            "app.bsky.embed.recordwithmedia")):
            return True
        if kind.startswith(("app.bsky.embed.record", "app.bsky.embed.external")):
            continue
        observed_unknown = True
    return None if observed_unknown else False


def mastodon_has_visual(status):
    """Status.media_attachments contiene adjuntos visibles (o None desconocido)."""
    attachments = status.get("media_attachments") if isinstance(status, dict) else None
    if not isinstance(attachments, list):
        return None
    return bool(attachments)


LIKE_KINDS = frozenset({"like", "like_external", "like_latest", "favourite", "vote", "react"})


def _fallback(network, item):
    """No confundir text_fragment o texto saliente con contenido del post."""
    if any(item.get(k) is True for k in ("sensitive", "possibly_sensitive", "over_18", "nsfw")):
        return False, "contenido_sensible"
    text = item.get("target_text") or item.get("post_text") or item.get("target_caption")
    if network == "facebook" and item.get("kind") == "like_external":
        return can_like(text, media_present=True)
    if item.get("media_present") is True:
        return can_like(text, media_present=True)
    if isinstance(text, str) and text.strip():
        return can_like(text, media_present=False)
    if network == "pinterest":
        return False, "pin_sin_titulo_o_descripcion_literaria"
    return True, f"sin_adaptador_{network}_candidato_filtrado_en_escaneo"


def check_execution(network, item, *, bluesky_client=None, mastodon_client=None):
    """Barrera en ejecutor; media_checked del plan no certifica la imagen."""
    if item.get("kind") not in LIKE_KINDS:
        return True, "accion_no_es_like"
    if any(item.get(k) is True for k in ("sensitive", "possibly_sensitive", "over_18", "nsfw")):
        return False, "contenido_sensible"
    if network not in ("bluesky", "mastodon"):
        return _fallback(network, item)
    try:
        if network == "bluesky":
            if bluesky_client is None:
                import bluesky_interact as bluesky_client
            uri = item.get("_target_uri") or bluesky_client._url_to_uri(item.get("url"))
            if not uri:
                return _fallback(network, item)
            response = bluesky_client._get(
                bluesky_client.AUTH_BASE, "app.bsky.feed.getPosts",
                {"uris": [uri]}, auth=True,
            )
            if not isinstance(response, dict) or not isinstance(response.get("posts"), list):
                return False, "bluesky_respuesta_malformada"
            posts = [p for p in (response or {}).get("posts", [])
                     if isinstance(p, dict) and p.get("uri") == uri]
            if len(posts) != 1 or not isinstance(posts[0].get("record"), dict):
                return False, "bluesky_objetivo_no_verificable"
            post = posts[0]
            return can_like(post["record"].get("text"),
                            media_present=bluesky_has_visual(post),
                            sensitive=bluesky_sensitive(post))
        if mastodon_client is None:
            import mastodon_interact as mastodon_client
        ident = str(item.get("status_id") or "").strip()
        if not ident.isdigit():
            return _fallback(network, item)
        status = mastodon_client._get(f"statuses/{ident}")
        if not isinstance(status, dict) or str(status.get("id")) != ident:
            return False, "mastodon_objetivo_no_verificable"
        if status.get("reblog") or status.get("quote"):
            return False, "mastodon_embebido_no_inspeccionado"
        return can_like(mastodon_client._plain_text(status.get("content") or ""),
                        media_present=mastodon_has_visual(status),
                        sensitive=status.get("sensitive") is True or bool(status.get("spoiler_text")))
    except Exception as exc:
        if re.search(r"\b4[0-9]{2}\b", str(exc)):
            return False, f"verificacion_denegada_{type(exc).__name__}"
        if isinstance(exc, (ValueError, KeyError)):
            return False, f"respuesta_no_interpretable_{type(exc).__name__}"
        return _fallback(network, item)

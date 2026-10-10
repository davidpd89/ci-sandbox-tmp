"""
Adaptadores nativos de evidencia contextual para nueve redes sociales.

Norma global y adaptadores por red para la extracción y normalización
de observaciones desde tres colas independientes: WEB, API y MOBILE.

Proporciona el paquete unificado ContextPacket preservando:
- Identificación remota y permalinks estables.
- Trazabilidad de fecha/timestamp verificable (#62).
- Texto de la publicación y cuerpo extendido si existe.
- Hilos de padres ordenados con IDs estables.
- Metadata del autor (handle/nombre).
- Evidencia multimedia con origin/provenance sin inventar descripciones no vistas.
- Ausencia explícita identificada en missing_fields (sin fabricar datos).
"""

from dataclasses import dataclass, field, asdict
import hashlib
import html
from html.parser import HTMLParser
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SUPPORTED_NETWORKS = {
    "bluesky", "mastodon", "x", "threads", "facebook",
    "pinterest", "reddit", "tiktok", "instagram"
}

SUPPORTED_QUEUES = {"web", "api", "mobile"}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []

    def handle_data(self, data):
        self.result.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "br", "div", "li"):
            self.result.append(" ")

    def get_text(self):
        raw = "".join(self.result)
        return re.sub(r"\s+", " ", raw).strip()


def strip_html_tags(raw_html: str) -> str:
    if not raw_html or not isinstance(raw_html, str):
        return ""
    parser = _HTMLTextExtractor()
    try:
        parser.feed(raw_html)
        text = parser.get_text()
    except Exception:
        text = re.sub(r"<[^>]+>", "", raw_html)
    return html.unescape(text).strip()


def _normalize_iso_timestamp(ts_val: Optional[Any]) -> Optional[str]:
    if ts_val is None or ts_val == "":
        return None

    if isinstance(ts_val, (int, float)):
        try:
            val = float(ts_val)
            if val > 1e11 or val < -1e11:  # millis
                val /= 1000.0
            dt = datetime.fromtimestamp(val, tz=timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        except (ValueError, OverflowError, OSError):
            return None

    if not isinstance(ts_val, str):
        return None

    ts_str = ts_val.strip()
    if not ts_str:
        return None

    # Try email/Twitter header format: Fri Oct 09 16:00:00 +0000 2026
    try:
        dt = datetime.strptime(ts_str, "%a %b %d %H:%M:%S %z %Y")
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        pass

    # Standard formats
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(ts_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        except ValueError:
            pass

    # Try ISO fromisoformat if available
    try:
        clean_ts = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


@dataclass
class ContextPacket:
    network: str
    queue: str
    remote_id: str
    permalink: Optional[str] = None
    author_handle: Optional[str] = None
    author_name: Optional[str] = None
    published_at_iso: Optional[str] = None
    text: Optional[str] = None
    body: Optional[str] = None
    parents: List[Dict[str, Any]] = field(default_factory=list)
    media: List[Dict[str, Any]] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    raw_payload_hash: Optional[str] = None
    completeness_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_completeness(
    remote_id: Optional[str],
    published_at_iso: Optional[str],
    author_handle: Optional[str],
    text: Optional[str],
    missing_fields: List[str]
) -> float:
    weights = {
        "remote_id": 0.25,
        "published_at_iso": 0.25,
        "author_handle": 0.20,
        "text": 0.20,
        "no_critical_missing": 0.10
    }
    score = 0.0
    if remote_id and str(remote_id).strip():
        score += weights["remote_id"]
    if published_at_iso:
        score += weights["published_at_iso"]
    if author_handle and str(author_handle).strip():
        score += weights["author_handle"]
    if text and str(text).strip():
        score += weights["text"]
    if "published_at_iso" not in missing_fields and "remote_id" not in missing_fields:
        score += weights["no_critical_missing"]
    return round(score, 4)


def adapt_native_observation(network: str, queue: str, raw_payload: Any) -> ContextPacket:
    if not isinstance(network, str) or not network.strip():
        raise ValueError("Network name must be a non-empty string")
    if not isinstance(queue, str) or not queue.strip():
        raise ValueError("Queue name must be a non-empty string")

    net = network.lower().strip()
    q = queue.lower().strip()

    if net not in SUPPORTED_NETWORKS:
        raise ValueError(f"Red no soportada: {network}")
    if q not in SUPPORTED_QUEUES:
        raise ValueError(f"Cola no soportada: {queue}")

    if raw_payload is None or not isinstance(raw_payload, dict):
        raise TypeError(f"raw_payload must be a non-null dictionary, got {type(raw_payload).__name__}")

    raw_str = json.dumps(raw_payload, sort_keys=True, default=str)
    raw_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:16]

    adapter_func = _ADAPTER_REGISTRY.get(net)
    if not adapter_func:
        raise NotImplementedError(f"Adaptador no implementado para {net}")

    packet = adapter_func(q, raw_payload, raw_hash)
    return packet


# --- Adaptadores específicos por red ---

def _adapt_bluesky(queue: str, payload: Dict[str, Any], raw_hash: str) -> ContextPacket:
    missing = []
    remote_id = payload.get("uri") or payload.get("cid") or payload.get("id") or payload.get("post_id") or ""
    if not remote_id:
        missing.append("remote_id")

    author = payload.get("author") or {}
    author_handle = author.get("handle") or payload.get("author_handle") or ""
    author_name = author.get("displayName") or payload.get("author_name") or author_handle
    if not author_handle:
        missing.append("author_handle")

    record = payload.get("record") or payload.get("value") or payload
    text = record.get("text") or payload.get("text") or ""
    if not text or not str(text).strip():
        missing.append("text")

    raw_date = record.get("createdAt") or payload.get("createdAt") or payload.get("indexedAt")
    pub_date = _normalize_iso_timestamp(raw_date)
    if not pub_date:
        missing.append("published_at_iso")

    permalink = payload.get("permalink")
    if not permalink and author_handle and remote_id:
        if "app.bsky.feed.post" in str(remote_id):
            rkey = str(remote_id).split("/")[-1]
            permalink = f"https://bsky.app/profile/{author_handle}/post/{rkey}"
        elif str(remote_id).startswith("http"):
            permalink = str(remote_id)

    parents = []
    reply_parent = payload.get("reply") or payload.get("parent")
    if reply_parent and isinstance(reply_parent, dict):
        parent_item = reply_parent.get("parent") or reply_parent
        if isinstance(parent_item, dict):
            parent_uri = parent_item.get("uri") or parent_item.get("cid") or parent_item.get("id") or ""
            p_author = parent_item.get("author")
            parent_author = p_author.get("handle") if isinstance(p_author, dict) else (str(p_author) if p_author else "")
            p_record = parent_item.get("record")
            parent_text = p_record.get("text") if isinstance(p_record, dict) else (parent_item.get("text") or "")
            if parent_uri:
                parents.append({"remote_id": str(parent_uri), "author": parent_author or "", "text": parent_text or ""})

    media = []
    embed = record.get("embed") or payload.get("embed") or {}
    if isinstance(embed, dict):
        images = embed.get("images") or []
        for img in images:
            if isinstance(img, dict):
                alt = img.get("alt") or ""
                thumb = img.get("thumb") or img.get("fullsize") or ""
                media.append({
                    "type": "image",
                    "origin": "bluesky_embed",
                    "provenance": thumb or "embed_image",
                    "alt": alt or None
                })
        ext = embed.get("external")
        if isinstance(ext, dict):
            media.append({
                "type": "external",
                "origin": "bluesky_external_embed",
                "provenance": ext.get("uri") or "external_embed",
                "alt": ext.get("title") or None
            })

    completeness = calculate_completeness(remote_id, pub_date, author_handle, text, missing)

    return ContextPacket(
        network="bluesky",
        queue=queue,
        remote_id=str(remote_id),
        permalink=permalink,
        author_handle=author_handle or None,
        author_name=author_name or None,
        published_at_iso=pub_date,
        text=text or None,
        body=None,
        parents=parents,
        media=media,
        missing_fields=missing,
        raw_payload_hash=raw_hash,
        completeness_score=completeness
    )


def _adapt_mastodon(queue: str, payload: Dict[str, Any], raw_hash: str) -> ContextPacket:
    missing = []
    remote_id = payload.get("id") or payload.get("uri") or ""
    if not remote_id:
        missing.append("remote_id")

    account = payload.get("account") or {}
    author_handle = account.get("acct") or account.get("username") or payload.get("author_handle") or ""
    author_name = account.get("display_name") or author_handle
    if not author_handle:
        missing.append("author_handle")

    raw_content = payload.get("content") or payload.get("text") or ""
    clean_text = strip_html_tags(raw_content) if raw_content else ""
    if not clean_text or not clean_text.strip():
        missing.append("text")

    raw_date = payload.get("created_at") or payload.get("createdAt")
    pub_date = _normalize_iso_timestamp(raw_date)
    if not pub_date:
        missing.append("published_at_iso")

    permalink = payload.get("url") or payload.get("uri")

    parents = []
    in_reply_to_id = payload.get("in_reply_to_id")
    if in_reply_to_id:
        parent_author = payload.get("in_reply_to_account_id") or ""
        parents.append({"remote_id": str(in_reply_to_id), "author": str(parent_author), "text": ""})

    media = []
    attachments = payload.get("media_attachments") or []
    for att in attachments:
        if isinstance(att, dict):
            media.append({
                "type": att.get("type", "image"),
                "origin": "mastodon_attachment",
                "provenance": att.get("url") or att.get("preview_url") or "attachment",
                "alt": att.get("description") or None
            })

    completeness = calculate_completeness(remote_id, pub_date, author_handle, clean_text, missing)

    return ContextPacket(
        network="mastodon",
        queue=queue,
        remote_id=str(remote_id),
        permalink=permalink,
        author_handle=author_handle or None,
        author_name=author_name or None,
        published_at_iso=pub_date,
        text=clean_text or None,
        body=raw_content if ("<" in raw_content or "&" in raw_content) else None,
        parents=parents,
        media=media,
        missing_fields=missing,
        raw_payload_hash=raw_hash,
        completeness_score=completeness
    )


def _adapt_x(queue: str, payload: Dict[str, Any], raw_hash: str) -> ContextPacket:
    missing = []
    remote_id = payload.get("id") or payload.get("id_str") or payload.get("rest_id") or ""
    if not remote_id:
        missing.append("remote_id")

    user = payload.get("user") or payload.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {}) or {}
    author_handle = user.get("screen_name") or payload.get("author_handle") or payload.get("username") or ""
    author_name = user.get("name") or payload.get("author_name") or author_handle
    if not author_handle:
        missing.append("author_handle")

    text = payload.get("full_text") or payload.get("text") or payload.get("note_tweet", {}).get("note_tweet_results", {}).get("result", {}).get("text") or ""
    if not text or not str(text).strip():
        missing.append("text")

    raw_date = payload.get("created_at") or payload.get("createdAt")
    pub_date = _normalize_iso_timestamp(raw_date)
    if not pub_date:
        missing.append("published_at_iso")

    permalink = payload.get("permalink")
    if not permalink and author_handle and remote_id:
        permalink = f"https://x.com/{author_handle}/status/{remote_id}"

    parents = []
    in_reply_to_status_id = payload.get("in_reply_to_status_id_str") or payload.get("in_reply_to_status_id")
    if in_reply_to_status_id:
        in_reply_user = payload.get("in_reply_to_screen_name") or ""
        parents.append({"remote_id": str(in_reply_to_status_id), "author": str(in_reply_user), "text": ""})

    media = []
    entities_media = payload.get("extended_entities", {}).get("media") or payload.get("entities", {}).get("media") or []
    for m in entities_media:
        if isinstance(m, dict):
            media.append({
                "type": m.get("type", "photo"),
                "origin": "x_media_entity",
                "provenance": m.get("media_url_https") or m.get("media_url") or "media_entity",
                "alt": m.get("alt_text") or None
            })

    completeness = calculate_completeness(remote_id, pub_date, author_handle, text, missing)

    return ContextPacket(
        network="x",
        queue=queue,
        remote_id=str(remote_id),
        permalink=permalink,
        author_handle=author_handle or None,
        author_name=author_name or None,
        published_at_iso=pub_date,
        text=text or None,
        body=None,
        parents=parents,
        media=media,
        missing_fields=missing,
        raw_payload_hash=raw_hash,
        completeness_score=completeness
    )


def _adapt_threads(queue: str, payload: Dict[str, Any], raw_hash: str) -> ContextPacket:
    missing = []
    remote_id = payload.get("id") or payload.get("pk") or ""
    if not remote_id:
        missing.append("remote_id")

    user = payload.get("user") or payload.get("username") or {}
    if isinstance(user, dict):
        author_handle = user.get("username") or ""
        author_name = user.get("full_name") or author_handle
    else:
        author_handle = str(user)
        author_name = author_handle
    if not author_handle:
        missing.append("author_handle")

    caption = payload.get("caption") or {}
    text = caption.get("text") if isinstance(caption, dict) else (payload.get("text") or payload.get("caption") or "")
    if not text or not str(text).strip():
        missing.append("text")

    raw_date = payload.get("taken_at") or payload.get("created_at") or payload.get("timestamp")
    pub_date = _normalize_iso_timestamp(raw_date)
    if not pub_date:
        missing.append("published_at_iso")

    code = payload.get("code") or payload.get("shortcode")
    permalink = payload.get("permalink") or (f"https://www.threads.net/@{author_handle}/post/{code}" if code and author_handle else None)

    parents = []
    reply_to = payload.get("reply_to") or payload.get("text_post_app_info", {}).get("reply_to", {}).get("target_post_id") or payload.get("parent_post_id")
    if reply_to:
        parents.append({"remote_id": str(reply_to), "author": "", "text": ""})

    media = []
    images = payload.get("image_versions2", {}).get("candidates") or []
    if images and isinstance(images, list):
        first_img = images[0].get("url") if isinstance(images[0], dict) else ""
        media.append({
            "type": "image",
            "origin": "threads_image",
            "provenance": first_img or "candidate_image",
            "alt": None
        })

    completeness = calculate_completeness(remote_id, pub_date, author_handle, text, missing)

    return ContextPacket(
        network="threads",
        queue=queue,
        remote_id=str(remote_id),
        permalink=permalink,
        author_handle=author_handle or None,
        author_name=author_name or None,
        published_at_iso=pub_date,
        text=text or None,
        body=None,
        parents=parents,
        media=media,
        missing_fields=missing,
        raw_payload_hash=raw_hash,
        completeness_score=completeness
    )


def _adapt_facebook(queue: str, payload: Dict[str, Any], raw_hash: str) -> ContextPacket:
    missing = []
    remote_id = payload.get("id") or payload.get("post_id") or ""
    if not remote_id:
        missing.append("remote_id")

    from_user = payload.get("from") or payload.get("author") or {}
    if isinstance(from_user, dict):
        author_handle = from_user.get("id") or from_user.get("username") or ""
        author_name = from_user.get("name") or author_handle
    else:
        author_handle = str(from_user)
        author_name = author_handle
    if not author_handle:
        missing.append("author_handle")

    message = payload.get("message") or payload.get("story") or payload.get("text") or ""
    if not message or not str(message).strip():
        missing.append("text")

    raw_date = payload.get("created_time") or payload.get("created_at") or payload.get("timestamp")
    pub_date = _normalize_iso_timestamp(raw_date)
    if not pub_date:
        missing.append("published_at_iso")

    permalink = payload.get("permalink_url") or payload.get("url")

    parents = []
    parent_id = payload.get("parent_id")
    if parent_id:
        parents.append({"remote_id": str(parent_id), "author": "", "text": ""})

    media = []
    attachments = payload.get("attachments", {}).get("data") or []
    for att in attachments:
        if isinstance(att, dict):
            media.append({
                "type": att.get("type", "photo"),
                "origin": "facebook_attachment",
                "provenance": att.get("url") or att.get("target", {}).get("url") or "attachment",
                "alt": None
            })

    completeness = calculate_completeness(remote_id, pub_date, author_handle, message, missing)

    return ContextPacket(
        network="facebook",
        queue=queue,
        remote_id=str(remote_id),
        permalink=permalink,
        author_handle=author_handle or None,
        author_name=author_name or None,
        published_at_iso=pub_date,
        text=message or None,
        body=None,
        parents=parents,
        media=media,
        missing_fields=missing,
        raw_payload_hash=raw_hash,
        completeness_score=completeness
    )


def _adapt_pinterest(queue: str, payload: Dict[str, Any], raw_hash: str) -> ContextPacket:
    missing = []
    remote_id = payload.get("id") or payload.get("pin_id") or ""
    if not remote_id:
        missing.append("remote_id")

    creator = payload.get("pinner") or payload.get("creator") or payload.get("board", {}).get("owner") or {}
    if isinstance(creator, dict):
        author_handle = creator.get("username") or creator.get("id") or ""
        author_name = creator.get("full_name") or author_handle
    else:
        author_handle = str(creator)
        author_name = author_handle
    if not author_handle:
        missing.append("author_handle")

    title = payload.get("title") or ""
    description = payload.get("description") or payload.get("note") or ""
    combined_text = title if not description else f"{title}\n{description}".strip()
    if not combined_text or not combined_text.strip():
        missing.append("text")

    raw_date = payload.get("created_at") or payload.get("createdAt")
    pub_date = _normalize_iso_timestamp(raw_date)
    if not pub_date:
        missing.append("published_at_iso")

    permalink = payload.get("link") or payload.get("url") or (f"https://pinterest.com/pin/{remote_id}/" if remote_id else None)

    media = []
    media_images = payload.get("media", {}).get("images") or payload.get("images") or {}
    if isinstance(media_images, dict) and media_images:
        orig = media_images.get("originals") or media_images.get("600x") or media_images.get("original") or {}
        img_url = orig.get("url") if isinstance(orig, dict) else ""
        if img_url:
            media.append({
                "type": "image",
                "origin": "pinterest_pin_media",
                "provenance": img_url,
                "alt": payload.get("alt_text") or None
            })

    completeness = calculate_completeness(remote_id, pub_date, author_handle, combined_text, missing)

    return ContextPacket(
        network="pinterest",
        queue=queue,
        remote_id=str(remote_id),
        permalink=permalink,
        author_handle=author_handle or None,
        author_name=author_name or None,
        published_at_iso=pub_date,
        text=title or None,
        body=description or None,
        parents=[],
        media=media,
        missing_fields=missing,
        raw_payload_hash=raw_hash,
        completeness_score=completeness
    )


def _adapt_reddit(queue: str, payload: Dict[str, Any], raw_hash: str) -> ContextPacket:
    missing = []
    remote_id = payload.get("name") or payload.get("id") or ""
    if not remote_id:
        missing.append("remote_id")

    author_handle = payload.get("author") or payload.get("author_fullname") or ""
    if not author_handle:
        missing.append("author_handle")

    title = payload.get("title") or ""
    selftext = payload.get("selftext") or payload.get("body") or ""
    combined_text = title or selftext
    if not combined_text or not str(combined_text).strip():
        missing.append("text")

    raw_date = payload.get("created_utc") or payload.get("created")
    pub_date = _normalize_iso_timestamp(raw_date)
    if not pub_date:
        missing.append("published_at_iso")

    permalink = payload.get("permalink")
    if permalink and not str(permalink).startswith("http"):
        permalink = f"https://www.reddit.com{permalink}"

    parents = []
    parent_id = payload.get("parent_id")
    if parent_id and parent_id != remote_id:
        parents.append({"remote_id": str(parent_id), "author": "", "text": ""})

    media = []
    if payload.get("is_video"):
        media.append({
            "type": "video",
            "origin": "reddit_post_video",
            "provenance": payload.get("media", {}).get("reddit_video", {}).get("fallback_url") or "reddit_video",
            "alt": None
        })
    elif payload.get("url") and any(str(payload.get("url")).endswith(ext) for ext in (".jpg", ".png", ".gif", ".webp")):
        media.append({
            "type": "image",
            "origin": "reddit_post_image",
            "provenance": payload.get("url"),
            "alt": None
        })

    completeness = calculate_completeness(remote_id, pub_date, author_handle, combined_text, missing)

    return ContextPacket(
        network="reddit",
        queue=queue,
        remote_id=str(remote_id),
        permalink=permalink,
        author_handle=author_handle or None,
        author_name=author_handle or None,
        published_at_iso=pub_date,
        text=title or selftext or None,
        body=selftext if (title and selftext) else None,
        parents=parents,
        media=media,
        missing_fields=missing,
        raw_payload_hash=raw_hash,
        completeness_score=completeness
    )


def _adapt_tiktok(queue: str, payload: Dict[str, Any], raw_hash: str) -> ContextPacket:
    missing = []
    remote_id = payload.get("id") or payload.get("aweme_id") or payload.get("video_id") or ""
    if not remote_id:
        missing.append("remote_id")

    author = payload.get("author") or {}
    if isinstance(author, dict):
        author_handle = author.get("unique_id") or author.get("uniqueId") or author.get("nickname") or ""
        author_name = author.get("nickname") or author_handle
    else:
        author_handle = str(author)
        author_name = author_handle
    if not author_handle:
        missing.append("author_handle")

    desc = payload.get("desc") or payload.get("title") or payload.get("text") or ""
    if not desc or not str(desc).strip():
        missing.append("text")

    raw_date = payload.get("create_time") or payload.get("createTime") or payload.get("created_at")
    pub_date = _normalize_iso_timestamp(raw_date)
    if not pub_date:
        missing.append("published_at_iso")

    permalink = payload.get("share_url") or (f"https://www.tiktok.com/@{author_handle}/video/{remote_id}" if author_handle and remote_id else None)

    media = []
    video = payload.get("video") or {}
    cover_url = video.get("cover") or video.get("dynamic_cover") or ""
    if cover_url or remote_id:
        media.append({
            "type": "video",
            "origin": "tiktok_video",
            "provenance": cover_url if isinstance(cover_url, str) else "video_cover",
            "alt": None
        })

    completeness = calculate_completeness(remote_id, pub_date, author_handle, desc, missing)

    return ContextPacket(
        network="tiktok",
        queue=queue,
        remote_id=str(remote_id),
        permalink=permalink,
        author_handle=author_handle or None,
        author_name=author_name or None,
        published_at_iso=pub_date,
        text=desc or None,
        body=None,
        parents=[],
        media=media,
        missing_fields=missing,
        raw_payload_hash=raw_hash,
        completeness_score=completeness
    )


def _adapt_instagram(queue: str, payload: Dict[str, Any], raw_hash: str) -> ContextPacket:
    missing = []
    remote_id = payload.get("id") or payload.get("pk") or ""
    if not remote_id:
        missing.append("remote_id")

    user = payload.get("user") or payload.get("owner") or {}
    if isinstance(user, dict):
        author_handle = user.get("username") or ""
        author_name = user.get("full_name") or author_handle
    else:
        author_handle = str(user)
        author_name = author_handle
    if not author_handle:
        missing.append("author_handle")

    caption = payload.get("caption") or {}
    text = caption.get("text") if isinstance(caption, dict) else (payload.get("text") or payload.get("caption") or "")
    if not text or not str(text).strip():
        missing.append("text")

    raw_date = payload.get("taken_at") or payload.get("timestamp") or payload.get("created_at")
    pub_date = _normalize_iso_timestamp(raw_date)
    if not pub_date:
        missing.append("published_at_iso")

    code = payload.get("code") or payload.get("shortcode")
    permalink = payload.get("permalink") or (f"https://www.instagram.com/p/{code}/" if code else None)

    parents = []
    parent_comment_id = payload.get("parent_comment_id")
    if parent_comment_id:
        parents.append({"remote_id": str(parent_comment_id), "author": "", "text": ""})

    media = []
    carousel = payload.get("carousel_media")
    if carousel and isinstance(carousel, list):
        for item in carousel:
            if isinstance(item, dict):
                m_type = "video" if item.get("media_type") in (2, "video") or item.get("is_video") else "image"
                media.append({
                    "type": m_type,
                    "origin": "instagram_carousel_media",
                    "provenance": item.get("display_url") or item.get("image_url") or "carousel_item",
                    "alt": item.get("accessibility_caption") or None
                })
    else:
        media_type = payload.get("media_type") or ("video" if payload.get("is_video") else "image")
        media.append({
            "type": "video" if str(media_type) in ("2", "video") else "image",
            "origin": "instagram_media",
            "provenance": payload.get("display_url") or payload.get("image_url") or "media_url",
            "alt": payload.get("accessibility_caption") or None
        })

    completeness = calculate_completeness(remote_id, pub_date, author_handle, text, missing)

    return ContextPacket(
        network="instagram",
        queue=queue,
        remote_id=str(remote_id),
        permalink=permalink,
        author_handle=author_handle or None,
        author_name=author_name or None,
        published_at_iso=pub_date,
        text=text or None,
        body=None,
        parents=parents,
        media=media,
        missing_fields=missing,
        raw_payload_hash=raw_hash,
        completeness_score=completeness
    )


_ADAPTER_REGISTRY = {
    "bluesky": _adapt_bluesky,
    "mastodon": _adapt_mastodon,
    "x": _adapt_x,
    "threads": _adapt_threads,
    "facebook": _adapt_facebook,
    "pinterest": _adapt_pinterest,
    "reddit": _adapt_reddit,
    "tiktok": _adapt_tiktok,
    "instagram": _adapt_instagram,
}

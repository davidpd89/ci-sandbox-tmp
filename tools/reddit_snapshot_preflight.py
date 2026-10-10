"""Control offline de contexto Reddit: nunca publica ni realiza peticiones de red.

Entrada: dos Listings JSON de /comments/<id>.json, estado HTTP y revisión
humana de normas/contexto. No sustituye el preflight ejecutado inmediatamente
antes de una escritura real ni acredita permisos de API.
"""
from __future__ import annotations

import argparse
import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
from urllib.parse import urlsplit

MAX_SNAPSHOT_AGE = timedelta(minutes=5)
MAX_RULE_AGE = timedelta(days=7)
MAX_THREAD_AGE = timedelta(days=3)  # Comentario raíz externo: política común de edad (3 días); follow-up separado.
THREAD_PATH = re.compile(r"/r/([A-Za-z0-9_]+)/comments/([a-z0-9]+)(?:/[^/]+)?/?", re.I)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def _instant(value):
    if isinstance(value, bool):
        raise ValueError("fecha inválida")
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("fecha no finita")
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("fecha sin zona horaria")
        return dt.astimezone(timezone.utc)
    raise ValueError("fecha ausente")


def _identity(url):
    if not isinstance(url, str):
        raise ValueError("URL ausente")
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in ("reddit.com", "www.reddit.com")
            or parts.port is not None or parts.username or parts.password
            or parts.query or parts.fragment):
        raise ValueError("URL no oficial o con parámetros")
    match = THREAD_PATH.fullmatch(parts.path)
    if not match:
        raise ValueError("URL no es un hilo raíz")
    return match.group(1).casefold(), match.group(2).casefold()


def _comment_nodes(listing, post_id):
    """Recorre el árbol sin recursión y verifica pertenencia y estructura.

    Cada hijo debe señalar a su padre y al t3 del hilo; sin esa unión,
    una cita o un autor de otro hilo podría autorizarse por accidente.
    """
    stack = [(listing, f"t3_{post_id}", 0)]
    seen = set()
    count = 0
    while stack:
        node, parent_id, depth = stack.pop()
        if depth > 64:
            raise ValueError("árbol de comentarios excesivamente profundo")
        if not isinstance(node, dict) or node.get("kind") != "Listing":
            raise ValueError("Listing de comentarios inválido")
        data = node.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("children"), list):
            raise ValueError("children no es una lista")
        for entry in data["children"]:
            if not isinstance(entry, dict):
                raise ValueError("comentario mal formado")
            if entry.get("kind") == "more":
                raise ValueError("comentarios plegados sin leer")
            if entry.get("kind") != "t1":
                raise ValueError("tipo de comentario no reconocido")
            comment = entry.get("data")
            if not isinstance(comment, dict):
                raise ValueError("datos de comentario inválidos")
            comment_id = comment.get("id")
            if (not isinstance(comment_id, str)
                    or not re.fullmatch(r"[a-z0-9]+", comment_id, re.I)):
                raise ValueError("ID de comentario inválido")
            thing_id = f"t1_{comment_id.casefold()}"
            if thing_id in seen:
                raise ValueError("comentario duplicado en Listing")
            seen.add(thing_id)
            count += 1
            if count > 10000:
                raise ValueError("demasiados comentarios para revisión completa")
            if (str(comment.get("parent_id", "")).casefold() != parent_id
                    or str(comment.get("link_id", "")).casefold() != f"t3_{post_id}"
                    or not isinstance(comment.get("author"), str)
                    or not isinstance(comment.get("body"), str)):
                raise ValueError("comentario ajeno, huérfano o incompleto")
            replies = comment.get("replies", object())
            if replies != "":
                if not isinstance(replies, dict):
                    raise ValueError("replies desconocidas")
                stack.append((replies, thing_id, depth + 1))
            yield comment

def evaluate(plan, snapshot, review, *, now=None):
    """Fail-closed ante campos ausentes, incoherentes o datos caducados."""
    now = now or datetime.now(timezone.utc)
    try:
        now = _instant(now.isoformat())
        if not isinstance(plan, dict) or plan.get("kind") != "comment":
            return Decision(False, "solo se admite comentario raíz")
        sub, post_id = _identity(plan["url"])
        text = plan.get("text")
        if not isinstance(text, str) or not text.strip():
            return Decision(False, "texto ausente")
        if "reply_to" in plan:
            return Decision(False, "respuesta anidada no admitida por este contrato")
        if not isinstance(snapshot, dict) or snapshot.get("http_status") != 200:
            return Decision(False, "HTTP no confirmado (incluye 429): no reintentar")
        checked = _instant(snapshot["retrieved_at"])
        if checked > now or now - checked > MAX_SNAPSHOT_AGE:
            return Decision(False, "snapshot caducado o futuro")
        body = snapshot["body"]
        if not isinstance(body, list) or len(body) != 2:
            return Decision(False, "se esperan dos Listings de /comments/<id>.json")
        post_listing, comments_listing = body
        if post_listing.get("kind") != "Listing":
            return Decision(False, "Listing del hilo inválido")
        posts = post_listing["data"]["children"]
        if len(posts) != 1 or posts[0].get("kind") != "t3":
            return Decision(False, "hilo t3 no identificado")
        post = posts[0]["data"]
        if (str(post["id"]).casefold() != post_id
                or str(post["subreddit"]).casefold() != sub):
            return Decision(False, "identidad de hilo/subreddit no coincide")
        if type(post["locked"]) is not bool or type(post["archived"]) is not bool:
            return Decision(False, "estado de cierre no confiable")
        if post["locked"] or post["archived"]:
            return Decision(False, "hilo cerrado o archivado")
        if post["removed_by_category"] is not None or post["author"] in ("[deleted]", "[removed]"):
            return Decision(False, "hilo eliminado o moderado")
        if post.get("selftext") in ("[removed]", "[deleted]"):
            return Decision(False, "contenido retirado")
        created = _instant(post["created_utc"])
        if created > now or now - created > MAX_THREAD_AGE:
            return Decision(False, "hilo fuera de ventana editorial (7 días)")
        if (not isinstance(review, dict) or review.get("subreddit", "").casefold() != sub
                or review.get("rules_url") != f"https://www.reddit.com/r/{sub}/about/rules/"
                or review.get("approved_by_human") is not True
                or review.get("full_context_read") is not True
                or review.get("rules_allow_comment") is not True
                or review.get("history_state") != "none"):
            return Decision(False, "revisión humana, reglas o historial insuficientes")
        # La revisión debe identificar tanto el hilo como el borrador exacto.
        # El hash documenta la vinculación, pero NO autentica al revisor.
        expected_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if (review.get("post_id") != post_id
                or review.get("plan_sha256") != expected_digest):
            return Decision(False, "revisión no vinculada a este hilo y texto")
        context_checked = _instant(review["context_checked_at"])
        if context_checked < checked or context_checked > now or now - context_checked > MAX_SNAPSHOT_AGE:
            return Decision(False, "lectura humana desactualizada respecto al snapshot")
        rules_checked = _instant(review["rules_checked_at"])
        if rules_checked > now or now - rules_checked > MAX_RULE_AGE:
            return Decision(False, "revisión de normas caducada")
        if review.get("subreddit_type") not in ("public", "restricted", "private"):
            return Decision(False, "tipo de subreddit desconocido")
        if review["subreddit_type"] != "public" and review.get("account_approved") is not True:
            return Decision(False, "comunidad restringida sin autorización acreditada")
        comments = list(_comment_nodes(comments_listing, post_id))
        # num_comments puede ser aproximado; si supera lo leído, fallar cerrado.
        count = post.get("num_comments")
        if isinstance(count, bool) or not isinstance(count, int) or count > len(comments) or count < 0:
            return Decision(False, "lectura de comentarios incompleta o no verificable")
        removal_notices = (
            "your post has been removed",
            "your submission has been removed",
            "se ha eliminado tu publicación",
            "tu publicación ha sido eliminada",
        )
        if any(c.get("author", "").casefold() == "automoderator"
               and any(marker in str(c.get("body", "")).casefold() for marker in removal_notices)
               for c in comments):
            return Decision(False, "AutoModerator comunica retirada del hilo")
        if not isinstance(review.get("account_name"), str) or not review["account_name"].strip():
            return Decision(False, "cuenta activa no identificada")
        if any(c.get("author", "").casefold() == review["account_name"].casefold() for c in comments):
            return Decision(False, "respuesta propia previa, no duplicar")
        quote_id = plan.get("quoted_comment_id")
        if quote_id is None and re.search(r"(?m)^\s*>", text):
            return Decision(False, "cita sin identificador verificable")
        if quote_id is not None:
            if not isinstance(quote_id, str) or not re.fullmatch(r"t1_[a-z0-9]+", quote_id, re.I):
                return Decision(False, "ID de comentario citado inválido")
            matches = [c for c in comments if f"t1_{str(c.get('id', '')).casefold()}" == quote_id.casefold()]
            if len(matches) != 1 or matches[0].get("body") in (None, "", "[deleted]", "[removed]"):
                return Decision(False, "comentario citado ausente o eliminado")
        return Decision(True, "apto solo para revisión manual; no autoriza publicar")
    except (KeyError, ValueError, TypeError, OverflowError, OSError, AttributeError) as exc:
        return Decision(False, f"contrato incompleto/no fiable: {type(exc).__name__}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--review", required=True)
    args = parser.parse_args(argv)
    try:
        with open(args.plan, encoding="utf-8") as f:
            plan = json.load(f)
        with open(args.snapshot, encoding="utf-8") as f:
            snapshot = json.load(f)
        with open(args.review, encoding="utf-8") as f:
            review = json.load(f)
        outcome = evaluate(plan, snapshot, review)
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        # Un JSON malformado nunca debe dar salida que parezca aprobación;
        # tampoco se imprimen rutas, cuerpos de usuario ni excepciones sensibles.
        outcome = Decision(False, f"entrada ilegible: {type(exc).__name__}")
    print(json.dumps({"allowed": outcome.allowed, "reason": outcome.reason}, ensure_ascii=False))
    return 0 if outcome.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())

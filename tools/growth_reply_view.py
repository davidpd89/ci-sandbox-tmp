"""Vista compacta de candidatos a reply para Bluesky/Mastodon (02/10).

Lee un growth_state*.json y saca, sin leer el estado completo, los posts donde
tiene sentido responder: en español, con texto propio suficiente, un post por
cuenta, sin cuentas puente/bot y sin gente a la que ya respondimos hace poco.
Orden: comunidad (relacion previa) antes que adquisicion, luego por score.

Uso:
    python tools/growth_reply_view.py growth_state.json SISTEMA_DIARIO_BLUESKY/registro_interacciones.csv [N] [reply|repost|quote|boost]
"""
import csv
import datetime
import json
import re
import sys

from scan_common import asks_for_opinion, is_feed_bridge

SPANISH_WORDS = {
    "de", "la", "el", "que", "y", "en", "un", "una", "los", "las", "por",
    "con", "para", "es", "se", "del", "lo", "mi", "muy", "pero", "como",
}
URL_OR_TAG = re.compile(r"(https?://\S+|#\w+|@\S+)")


def own_text(text):
    return " ".join(URL_OR_TAG.sub(" ", text or "").split())


def looks_spanish(text):
    words = re.findall(r"[a-záéíóúñü]+", (text or "").lower())
    hits = sum(1 for w in words if w in SPANISH_WORDS)
    return hits >= 3 or any(ch in (text or "") for ch in "¿¡ñ")


def recent_reply_targets(registro_path, days=3, today=None):
    today = today or datetime.date.today()
    cutoff = today - datetime.timedelta(days=days)
    out = set()
    try:
        with open(registro_path, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("tipo") != "reply":
                    continue
                try:
                    when = datetime.date.fromisoformat((row.get("fecha") or "")[:10])
                except ValueError:
                    continue
                if when >= cutoff:
                    handle = (row.get("cuenta") or "").lstrip("@").casefold()
                    out.add(handle)
                    out.add(handle.split("@")[0])
    except OSError:
        pass
    return out


def age_hours(created_at, now=None):
    """Horas desde la publicacion, o None si no hay fecha valida."""
    if not created_at:
        return None
    try:
        when = datetime.datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return max(0.0, (now - when).total_seconds() / 3600)


def freshness_bucket(age):
    """0 = menos de 3 h (la ventana donde una reply se ve de verdad: la velocidad de las
    primeras reacciones pesa mas que el total), 1 = menos de 24 h, 2 = antiguo o sin fecha."""
    if age is None:
        return 2
    return 0 if age <= 3 else 1 if age <= 24 else 2


def view(state, skip=frozenset(), limit=40, min_chars=60, action="reply", include_opinion=False, now=None):
    rows = []
    seen = set()
    for cand in state.get("shortlist") or []:
        handle = (cand.get("handle") or cand.get("acct") or "")
        key = handle.casefold()
        if not key or key in seen or key in skip or key.split("@")[0] in skip:
            continue
        if is_feed_bridge(key):
            continue
        for post in cand.get("posts") or []:
            if action not in (post.get("actions") or []):
                continue
            text = post.get("text") or ""
            plain = own_text(text)
            if len(plain) < min_chars or not looks_spanish(plain):
                continue
            # "lee mi texto" / "que os parece mi relato": se ignora (03/10)
            if action == "reply" and not include_opinion and asks_for_opinion(text):
                continue
            stats = post.get("stats") or {}
            rows.append({
                "post": post["id"], "handle": handle, "lane": cand.get("lane"),
                "score": cand.get("score") or 0, "text": plain,
                "likes": stats.get("likes") or stats.get("favourites") or 0,
                "replies": stats.get("replies") or 0,
                "age_h": age_hours(post.get("created_at"), now),
            })
            seen.add(key)
            break
    # comunidad primero; luego lo MAS RECIENTE (<3 h: contestar pronto es lo que mas rinde
    # en X/Threads/Bluesky), despues lo mas visible (likes) y el score como desempate
    rows.sort(key=lambda r: (r["lane"] != "community", freshness_bucket(r["age_h"]), -r["likes"], -r["score"]))
    return rows[:limit]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    state_path = argv[0]
    registro = argv[1] if len(argv) > 1 else ""
    limit = int(argv[2]) if len(argv) > 2 else 40
    action = argv[3] if len(argv) > 3 else "reply"
    with open(state_path, encoding="utf-8") as stream:
        state = json.load(stream)
    skip = recent_reply_targets(registro) if registro and action == "reply" else set()
    for row in view(state, skip, limit, action=action):
        lane = "C" if row["lane"] == "community" else "A"
        age = "" if row["age_h"] is None else f" {row['age_h']:.0f}h"
        print(f"{row['post']} [{lane}] ♥{row['likes']} ↩{row['replies']}{age} @{row['handle']}: {row['text'][:230]}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())

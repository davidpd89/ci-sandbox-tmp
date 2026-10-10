"""TikTok: comentarios escritos por ChatGPT para el plan de la ronda (07/10/2026, David: «TikTok lleva todo el dia y apenas hay follows, comentarios ni retorno»).

Hasta hoy los comentarios de TikTok los escribia una IA a mano en `tiktok_decisions.json` y, sin IA, la ronda no comentaba NADA (0 comentarios hoy). Tras `prepare`, este paso toma los posts que el
scan propone para comentar (`actions` con `comment`), le pasa a ChatGPT el pie de cada video y la bio del creador, y escribe `tiktok_decisions.json` con los comentarios validos; el `build` los
fusiona con el auto_plan. Un fallo nunca tumba la ronda (decisions queda vacio y la ronda sigue con follows y likes).

    python tools/tiktok_comment_writer.py [--max 25]
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import reply_queue as rq

ROOT = os.path.join(os.path.dirname(__file__), "..")
STATE = os.path.join(ROOT, "tiktok_state.json")
DECISIONS = os.path.join(ROOT, "tiktok_decisions.json")


def pick_posts(state, limit=25):
    """Posts con propuesta de comentario, de los candidatos mejor puntuados y con pie de video con contenido; uno por creador."""
    out, seen = [], set()
    for candidate in sorted(state.get("shortlist") or [], key=lambda c: -float(c.get("score") or 0)):
        handle = str(candidate.get("handle") or "").casefold()
        if handle in seen:
            continue
        for post in candidate.get("posts") or []:
            caption = " ".join(str(post.get("caption") or "").split())
            if "comment" in (post.get("actions") or []) and len(caption) >= 25:
                out.append({"id": post["id"], "author": candidate.get("handle"),
                            "url": post.get("url"), "text": caption,
                            "context": f"bio del creador: {(candidate.get('bio') or '')[:120]}"})
                seen.add(handle)
                break
        if len(out) >= limit:
            break
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    limit = int(argv[argv.index("--max") + 1]) if "--max" in argv else 25
    actions = []
    import reply_hold
    if reply_hold.held():
        print("[tiktok_comment_writer] respuestas EN REVISION: la ronda sigue sin comentarios")
        with open(DECISIONS, "w", encoding="utf-8") as stream:
            json.dump({"actions": []}, stream)
        return 0
    try:
        state = json.load(open(STATE, encoding="utf-8"))
        items = pick_posts(state, limit)
        written = rq.get_or_enqueue(items, "tiktok", wait_min=4) if items else {}
        import reply_provenance as proof
        actions = [a for item in items if item["id"] in written
                   for a in [proof.attach({"kind": "comment", "post": item["id"],
                                           "url": item.get("url"), "handle": item.get("author"),
                                           "text": written[item["id"]]}, item, "tiktok")]
                   if a is not None]
        print(f"[tiktok_comment_writer] {len(actions)} comentarios escritos de {len(items)} videos propuestos")
    except Exception as exc:                       # nunca tumba la ronda
        print(f"[tiktok_comment_writer] error ({type(exc).__name__}: {str(exc)[:100]}); la ronda sigue sin comentarios")
    with open(DECISIONS, "w", encoding="utf-8") as stream:
        json.dump({"actions": actions}, stream, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

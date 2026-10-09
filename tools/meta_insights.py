"""Que contenido rinde en nuestras cuentas de Meta (Instagram, Threads, Facebook), solo lectura y gratis.

Las tres APIs dan metricas por publicacion de nuestras propias cuentas sin App Review. Esta herramienta las
junta en un ranking comun (interacciones = likes + comentarios/respuestas + guardados + compartidos +
reposts) para decidir que formatos y temas repetir. No imprime nunca respuestas crudas (la paginacion
de la API lleva el token dentro de la URL).

    python tools/meta_insights.py [--limit 12]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import facebook_api
import instagram_api
import meta_common as mc
import threads_api

FB_FIELDS = "id,created_time,message,reactions.summary(true).limit(0),comments.summary(true).limit(0),shares"


def engagement(row):
    return sum(row.get(k) or 0 for k in ("likes", "comments", "saved", "shares", "reposts", "quotes"))


def rank(rows):
    """Mayor interaccion primero; a igualdad, mas alcance."""
    return sorted(rows, key=lambda r: (engagement(r), r.get("reach") or 0), reverse=True)


def _metrics(data):
    return {d["name"]: (d.get("values") or [{}])[0].get("value", 0) for d in data.get("data", [])}


def instagram_rows(token, user_id, limit):
    media = mc.graph_get(instagram_api.BASE, f"{user_id}/media", token, limit=limit,
                         fields="id,caption,media_type,like_count,comments_count,timestamp")
    rows = []
    for item in media.get("data", []):
        row = {"red": "instagram", "fecha": item["timestamp"][:10], "tipo": item.get("media_type"),
               "texto": (item.get("caption") or "")[:50].replace(chr(10), " "),
               "likes": item.get("like_count"), "comments": item.get("comments_count")}
        try:
            row.update(_metrics(mc.graph_get(instagram_api.BASE, f"{item['id']}/insights", token,
                                             metric="reach,saved,shares")))
        except RuntimeError:  # algunos formatos antiguos no admiten insights
            pass
        rows.append(row)
    return rows


def threads_rows(token, limit):
    posts = threads_api.api_get("me/threads", token, fields="id,text,timestamp,is_reply", limit=limit)
    rows = []
    for item in posts.get("data", []):
        if item.get("is_reply"):
            continue
        data = _metrics(threads_api.api_get(f"{item['id']}/insights", token,
                                            metric="views,likes,replies,reposts,quotes,shares"))
        rows.append({"red": "threads", "fecha": item["timestamp"][:10], "tipo": "POST",
                     "texto": (item.get("text") or "")[:50].replace(chr(10), " "),
                     "likes": data.get("likes"), "comments": data.get("replies"), "reposts": data.get("reposts"),
                     "quotes": data.get("quotes"), "shares": data.get("shares"), "reach": data.get("views")})
    return rows


def facebook_rows(token, page_id, limit):
    posts = mc.graph_get(facebook_api.BASE, f"{page_id}/posts", token, fields=FB_FIELDS, limit=limit)
    return [{"red": "facebook", "fecha": item["created_time"][:10], "tipo": "POST",
             "texto": (item.get("message") or "")[:50].replace(chr(10), " "),
             "likes": item["reactions"]["summary"]["total_count"],
             "comments": item["comments"]["summary"]["total_count"],
             "shares": (item.get("shares") or {}).get("count", 0)}
            for item in posts.get("data", [])]


def collect(env, limit=12):
    jobs = (("instagram", "IG_ACCESS_TOKEN", lambda: instagram_rows(env["IG_ACCESS_TOKEN"], env["IG_USER_ID"], limit)),
            ("threads", "THREADS_ACCESS_TOKEN", lambda: threads_rows(env["THREADS_ACCESS_TOKEN"], limit)),
            ("facebook", "FB_PAGE_TOKEN", lambda: facebook_rows(env["FB_PAGE_TOKEN"], env["FB_PAGE_ID"], limit)))
    rows, warnings = [], []
    for name, key, job in jobs:
        if not env.get(key):
            warnings.append(f"{name}: falta {key}")
            continue
        try:
            rows += job()
        except Exception as exc:
            warnings.append(f"{name}: {str(exc)[:120]}")
    return rank(rows), warnings


def render(rows, warnings):
    lines = [f"{'red':9} {'fecha':10} {'inter':>5} {'alcance':>7}  texto"]
    for row in rows:
        reach = row.get("reach")
        lines.append(f"{row['red']:9} {row['fecha']} {engagement(row):>5} {reach if reach is not None else '-':>7}  "
                     f"{row['tipo'][:4]:4} {row['texto']}")
    by_net, by_format = {}, {}
    for row in rows:
        by_net.setdefault(row["red"], []).append(engagement(row))
        by_format.setdefault((row["red"], row["tipo"]), []).append((engagement(row), row.get("reach")))
    lines.append("")
    for net, values in by_net.items():
        lines.append(f"{net}: {len(values)} posts, media {sum(values) / len(values):.1f} interacciones")
    if any(len([k for k in by_format if k[0] == net]) > 1 for net in by_net):
        lines.append("por formato:")
        for (net, kind), values in sorted(by_format.items()):
            reach = [r for _, r in values if r is not None]
            lines.append(f"  {net} {kind}: {len(values)} posts, {sum(v for v, _ in values) / len(values):.1f} interacciones"
                         + (f", alcance medio {sum(reach) / len(reach):.0f}" if reach else ""))
    lines += [f"AVISO {w}" for w in warnings]
    return chr(10).join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 12
    rows, warnings = collect(mc.read_env(), limit)
    print(render(rows, warnings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Bandeja unica de las APIs de Meta (Threads, Instagram, Facebook Pages), solo lectura.

Una orden, tres redes: lista los comentarios/respuestas con pregunta que aun no hemos contestado
(politica de David: una conversacion se contesta una vez y solo si preguntan). No publica nada.
Una red que falla (token caducado, sin permiso) no tumba a las demas: se cuenta como aviso.

    python tools/meta_inbox.py            # informe legible
    python tools/meta_inbox.py --json     # lo mismo en JSON (para otras herramientas)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import facebook_api
import instagram_api
import meta_common as mc
import threads_api


def _threads(env):
    token = env["THREADS_ACCESS_TOKEN"]
    me = threads_api.api_get("me", token, fields="username")["username"]
    return threads_api.followups(token, me)


def _instagram(env):
    token = env["IG_ACCESS_TOKEN"]
    me = mc.graph_get(instagram_api.BASE, "me", token, fields="username")["username"]
    return instagram_api.comments_pending(token, env["IG_USER_ID"], me)


def _facebook(env):
    return facebook_api.comments_pending(env["FB_PAGE_TOKEN"], env["FB_PAGE_ID"])


SOURCES = (("threads", "THREADS_ACCESS_TOKEN", _threads),
           ("instagram", "IG_ACCESS_TOKEN", _instagram),
           ("facebook", "FB_PAGE_TOKEN", _facebook))


def collect(env, sources=SOURCES):
    """{red: {"pending": [...], "error": str|None}}; la red sin token se omite con aviso."""
    report = {}
    for name, key, fetch in sources:
        if not env.get(key):
            report[name] = {"pending": [], "error": f"falta {key} en .env"}
            continue
        try:
            report[name] = {"pending": fetch(env), "error": None}
        except Exception as exc:  # una red caida no debe ocultar las otras
            report[name] = {"pending": [], "error": str(exc)[:160]}
    return report


def render(report):
    lines = []
    for name, data in report.items():
        if data["error"]:
            lines.append(f"[{name}] AVISO: {data['error']}")
            continue
        pending = data["pending"]
        lines.append(f"[{name}] {len(pending)} pregunta(s) sin contestar")
        for item in pending:
            who = item.get("username") or "?"
            lines.append(f"  {item.get('id')} @{who}: {(item.get('text') or '')[:160]}")
    return chr(10).join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    report = collect(mc.read_env())
    print(json.dumps(report, ensure_ascii=False, indent=1) if "--json" in argv else render(report))
    return 1 if any(d["error"] for d in report.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())

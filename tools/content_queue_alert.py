"""Revision de publicaciones pendientes o olvidadas, comun a todas las redes (06/10/2026, David: «que en cada ronda se revise si hay alguna publicacion pendiente de hoy o de un dia
anterior que se nos olvido»).

Lee las carpetas `publicaciones <Red> GPT/` (`content_queue`) y para cada red:
  * VENCIDAS: fichas con fecha/hora ya pasada que no estan marcadas como publicadas. Antes de avisar se COMPRUEBA en la propia red si el texto ya esta publicado (Bluesky, Mastodon y
    Threads por su API; David publica a mano y a menudo no actualiza el Estado de la ficha): si esta, la ficha se marca sola como «publicada (verificada)» y no molesta mas.
  * HOY: fichas que salen hoy mas tarde.
No publica ni programa nada (decision de David del 28/09: publicacion propia manual/nativa); su trabajo es que no se olvide. Escribe `00_OPERATIVO/PENDIENTES_PUBLICACION.md`
(todas las redes) y imprime un resumen corto de la red pedida, que cada ronda deja en su log.

    python tools/content_queue_alert.py [red|todas] [--no-verify]
"""
import datetime
import os
import re
import sys
import unicodedata
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
import content_queue as cq

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT_MD = os.path.join(ROOT, "00_OPERATIVO", "PENDIENTES_PUBLICACION.md")
VERIFIABLE = ("bluesky", "mastodon", "threads", "facebook", "instagram")
BROWSER_VERIFIABLE = ("x", "pinterest")          # solo se comprueban con el navegador cuando quien llama tiene el turno del Edge (content_publisher)
SNIPPET = 45


def fold(text):
    value = unicodedata.normalize("NFKD", str(text or "").casefold())
    value = re.sub(r"https?://\S+", " ", "".join(ch for ch in value if not unicodedata.combining(ch)))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def snippet(text):
    return fold(text)[:SNIPPET]


def own_recent_texts(red, allow_browser=False):
    """Textos de nuestras publicaciones recientes en `red` (o None si no se pueden leer): por API, y por navegador solo si `allow_browser` (quien llama debe tener el turno del Edge)."""
    try:
        if red == "pinterest":
            if not allow_browser:
                return None
            import pinterest_publish as pp
            return [fold(text) for text in pp.own_recent_texts()]
        if red == "x":
            if not allow_browser:
                return None
            import x_interact as x
            return [fold(text) for text in x.own_recent_texts()]
        if red == "bluesky":
            import bluesky_interact as b
            did = b._session()["did"]
            data = b._get(b.AUTH_BASE, "app.bsky.feed.getAuthorFeed", {"actor": did, "limit": 100, "filter": "posts_no_replies"})
            return [fold((item["post"]["record"] or {}).get("text")) for item in data.get("feed", [])]
        if red == "mastodon":
            import mastodon_interact as m
            me = m._get("accounts/verify_credentials")
            rows = m._get(f"accounts/{me['id']}/statuses", {"limit": 40, "exclude_replies": "true", "exclude_reblogs": "true"})
            texts = [fold(m._plain_text(row.get("content"))) for row in rows]
            for scheduled in m._get("scheduled_statuses", {"limit": 40}):          # lo que David dejo PROGRAMADO en la propia Mastodon tambien cuenta como ya gestionado
                texts.append(fold((scheduled.get("params") or {}).get("text")))
            return texts
        if red in ("facebook", "instagram"):
            import meta_common as mc
            import meta_publish as mp
            env = mc.read_env()
            if red == "facebook":
                return [fold(t) for t in mp.facebook_recent_texts(env["FB_PAGE_TOKEN"], env["FB_PAGE_ID"])]
            return [fold(t) for t in mp.instagram_recent_texts(env["IG_ACCESS_TOKEN"], env["IG_USER_ID"])]
        if red == "threads":
            import threads_api as api
            env = api._env()
            data = api.api_get("me/threads", env["THREADS_ACCESS_TOKEN"], fields="id,text", limit=50)
            return [fold(row.get("text")) for row in data.get("data", [])]
    except Exception:
        return None
    return None


def verify_values(item):
    """Textos de la ficha que identifican su publicacion en la red: el cuerpo, y en Pinterest/Reddit tambien el titulo (y el ALT del Pin)."""
    values = [item.get("texto")]
    if item.get("red") in ("pinterest", "reddit"):
        values += [item.get("titulo"), item.get("alt")]
    return [v for v in values if v]


def classify(red, now=None, verify=True, allow_browser=False):
    """{'due': [...], 'today': [...], 'verified': [...], 'unverifiable': bool} para una red."""
    now = now or datetime.datetime.now(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
    due = cq.due_items(red, now)
    verified = []
    unverifiable = red not in VERIFIABLE and not (allow_browser and red in BROWSER_VERIFIABLE)
    if due and verify and not unverifiable:
        texts = own_recent_texts(red, allow_browser)
        if texts is None:
            unverifiable = True
        else:
            still = []
            for item in due:
                keys = [k for k in (snippet(value) for value in verify_values(item)) if k]
                if keys and any(key in text for key in keys for text in texts):
                    try:
                        cq.mark_done(item["md_path"], "publicada (verificada en la red)")
                    except Exception:
                        pass
                    verified.append(item)
                else:
                    still.append(item)
            due = still
    today = [item for item in cq.future_items(red, now) if item["fecha_hora"].date() == now.date()]
    return {"due": due, "today": today, "verified": verified, "unverifiable": unverifiable}


def describe(item, now):
    days = (now.date() - item["fecha_hora"].date()).days
    when = "hoy" if days == 0 else "ayer" if days == 1 else f"hace {days} dias"
    first = " ".join((item["texto"] or "").split())[:80]
    return f"{item['fecha_hora']:%d/%m %H:%M} ({when}) · {os.path.basename(os.path.dirname(item['md_path']))} · «{first}»"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    target = next((a for a in argv if not a.startswith("--")), "todas")
    verify = "--no-verify" not in argv
    now = datetime.datetime.now(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
    results = {red: classify(red, now, verify) for red in cq.RED_FOLDERS}
    # Revisión editorial de fichas manuales: cola desconocida, sin publicación.
    import voice_output_finalization as voice
    for red, res in results.items():
        for item in res["due"] + res["today"]:
            fields = {"texto": item.get("texto") or ""}
            if red in ("reddit", "pinterest"):
                fields["titulo"] = item.get("titulo") or ""
            if item.get("alt"):
                fields["alt"] = item["alt"]
            try:
                voice.inspect_fields(fields, network=red, queue=None)
            except voice.VoicePreflightUnavailable:
                # No bloquear el recordatorio si falta el QA; no hay envío remoto.
                print(f"[{red}] auditor_es_no_disponible; se conserva el informe manual")
                break
    lines = [f"# Publicaciones pendientes ({now:%d/%m/%Y %H:%M})", "",
             "Generado por `tools/content_queue_alert.py` en cada ronda. No publica nada: avisa de lo vencido y de lo de hoy. Las de Bluesky, Mastodon y Threads se comprueban en la red y las "
             "ya publicadas se marcan solas; en el resto, «sin verificar» significa que hay que mirar a mano si ya salio.", ""]
    for red, res in results.items():
        if not (res["due"] or res["today"] or res["verified"]):
            continue
        suffix = " (sin verificar en la red)" if res["unverifiable"] and res["due"] else ""
        lines.append(f"## {red.capitalize()}{suffix}")
        for item in sorted(res["due"], key=lambda i: i["fecha_hora"]):
            lines.append(f"- **VENCIDA** {describe(item, now)}")
        for item in sorted(res["today"], key=lambda i: i["fecha_hora"]):
            lines.append(f"- hoy {describe(item, now)}")
        for item in res["verified"]:
            lines.append(f"- ya publicada, ficha marcada: {describe(item, now)}")
        lines.append("")
    if len(lines) == 4:
        lines.append("Nada pendiente.")
    with open(OUT_MD, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    names = list(cq.RED_FOLDERS) if target == "todas" else [target]
    for red in names:
        res = results.get(red)
        if res is None:
            print(f"[{red}] sin carpeta de publicaciones")
            continue
        if res["verified"]:
            print(f"[{red}] {len(res['verified'])} ficha(s) ya publicadas en la red: marcadas")
        if res["due"]:
            flag = " (sin verificar en la red)" if res["unverifiable"] else ""
            print(f"[{red}] PENDIENTE: {len(res['due'])} publicacion(es) VENCIDA(S) sin publicar{flag}:")
            for item in sorted(res["due"], key=lambda i: i["fecha_hora"])[:6]:
                print(f"   - {describe(item, now)}")
        if res["today"]:
            print(f"[{red}] hoy: " + "; ".join(f"{i['fecha_hora']:%H:%M}" for i in sorted(res["today"], key=lambda i: i["fecha_hora"])))
        if not (res["due"] or res["today"] or res["verified"]):
            print(f"[{red}] nada pendiente")
    print(f"informe completo: {os.path.relpath(OUT_MD, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Publicacion automatica de las fichas `publicaciones <Red> GPT/` (06/10/2026, autorizada por David: «cada dia un script revise esas carpetas de cada red y publique lo que corresponda»).

Una sola logica para todas las redes (que ficha toca, comprobaciones, registro, marcado) y un adaptador por red (como se publica y como se confirma). Redes con adaptador:
bluesky y mastodon (API), threads y x (navegador, con el turno del Edge). El resto de redes (Facebook, Instagram, Pinterest, Reddit, TikTok) siguen en `content_queue_alert.py`
(solo avisa) hasta que tengan un flujo de publicacion validado.

Una ficha se publica si, a la vez:
  * su estado es «lista» (no «requiere verificar…», no «borrador»), no tiene bloqueos editoriales ni datos incompletos (texto, fecha/hora, imagen con ALT);
  * su fecha/hora ya paso, pero hace NO MAS de `max_overdue_days` (3): una ficha mas vieja puede estar caducada (evento, fecha) y solo se avisa;
  * el texto NO esta ya publicado en la red (se comprueba antes: si esta, la ficha se marca y no se repite);
  * la red esta activada en `00_OPERATIVO/auto_publicacion.json`.
Como mucho UNA ficha por red y ejecucion (varias vencidas salen en ejecuciones sucesivas, separadas), con la pausa de un paso de ronda o de la tarea horaria. Cada publicacion queda en
`00_OPERATIVO/publicaciones_automaticas.csv` y en la propia ficha (`Estado: publicada por la ronda …`). Sin `--apply` solo informa de lo que publicaria.

    python tools/content_publisher.py [red|todas] [--apply]
"""
import csv
import datetime
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
import content_queue as cq
import content_queue_alert as cqa
from time_utils import to_utc_instant

ROOT = os.path.join(os.path.dirname(__file__), "..")
CONFIG = os.path.join(ROOT, "00_OPERATIVO", "auto_publicacion.json")
LOG = os.path.join(ROOT, "00_OPERATIVO", "publicaciones_automaticas.csv")
# X (06/10, David: «si hay algo en la carpeta que no se publico, publicalo y listo»): se activa. Una ficha vencida cuyo texto no esta en el perfil NO esta programada de forma nativa (habria salido
# a su hora), asi que verificar el perfil basta para no duplicar. `max_overdue_days` 14 (antes 3): David quiere que se publique lo atrasado; lo dependiente de la fecha («hoy», «manana»…) se descarta.
DEFAULT_CONFIG = {"enabled": {"bluesky": True, "mastodon": True, "threads": True, "x": True, "facebook": False, "instagram": False, "pinterest": True}, "max_overdue_days": 14}
BROWSER = {"threads", "x", "pinterest", "reddit"}          # facebook e instagram salen por la API oficial (meta_publish.py), sin navegador


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        data = {}
    return {"enabled": {**DEFAULT_CONFIG["enabled"], **(data.get("enabled") or {})}, "max_overdue_days": int(data.get("max_overdue_days", DEFAULT_CONFIG["max_overdue_days"]))}


PROFILE_LINKS = os.path.join(ROOT, "00_OPERATIVO", "enlaces_perfil.json")      # {"instagram": ["Auditor de página", ...]}: etiquetas de enlace ya puestas en el perfil


def profile_link_ready(red, label, path=None):
    """Instagram (y otras redes con «enlace en el perfil») no admiten el enlace en el post: la ficha dice «En el perfil: «X»» y publicarla antes de que X este en el perfil deja al lector sin destino."""
    try:
        with open(path or PROFILE_LINKS, encoding="utf-8") as stream:
            labels = json.load(stream).get(red) or []
    except (OSError, ValueError):
        labels = []
    return label.casefold() in {str(l).casefold() for l in labels}


DATE_BOUND = re.compile(r"\b(hoy|mañana|esta noche|esta tarde|esta mañana|este (?:lunes|martes|miércoles|jueves|viernes|sábado|domingo)|ayer|dentro de \d+ días)\b", re.IGNORECASE)


def _to_utc_instant(dt_or_now, tz_name="Europe/Madrid"):
    return to_utc_instant(dt_or_now, tz_name=tz_name)


def blockers_of(item, issues_by_path, now=None):
    """Motivos por los que una ficha NO se publica sola (lista vacia = se puede)."""
    reasons = []
    if DATE_BOUND.search(item.get("texto") or ""):
        now_utc = _to_utc_instant(now or datetime.datetime.now(ZoneInfo("Europe/Madrid")))
        item_utc = item.get("fecha_hora_utc") or _to_utc_instant(item.get("fecha_hora"))
        late = (now_utc - item_utc).days if (now_utc and item_utc) else 0
        if late >= 1:
            reasons.append("el texto depende de la fecha («hoy», «mañana»…) y ya esta vencido")
    estado = (item.get("estado") or "").casefold()
    # «requiere verificar si se publico o programo»: la verificacion previa en la red (run -> verify) ya descarto que este publicada; lo vencido y no encontrado sale.
    if not (estado.startswith("lista") and "manual" not in estado) and "verificar si se public" not in estado:
        reasons.append(f"estado «{item.get('estado')}»")
    label = (item.get("meta") or {}).get("etiqueta del enlace de perfil")
    if label and not profile_link_ready(item.get("red"), label):
        reasons.append(f"el texto remite al enlace de perfil «{label}» y aun no consta en el perfil (anadirlo y apuntarlo en enlaces_perfil.json)")
    if item.get("blockers"):
        reasons.append("bloqueo editorial: " + ", ".join(item["blockers"]))
    if issues_by_path.get(item["md_path"]):
        reasons.append("datos incompletos: " + ", ".join(issues_by_path[item["md_path"]]))
    for media in item.get("media") or []:
        if not media.get("exists"):
            reasons.append(f"falta el archivo {media.get('filename')}")
    return reasons


def eligible(red, now, config, issues_by_path):
    """(publicable, descartadas): ficha vencida mas antigua primero entre las que pasan todas las comprobaciones."""
    ok, skipped = [], []
    now_utc = _to_utc_instant(now or datetime.datetime.now(ZoneInfo("Europe/Madrid")))
    for item in sorted(cq.due_items(red, now), key=lambda i: i.get("fecha_hora_utc") or _to_utc_instant(i["fecha_hora"])):
        reasons = blockers_of(item, issues_by_path, now)
        item_utc = item.get("fecha_hora_utc") or _to_utc_instant(item["fecha_hora"])
        late = (now_utc - item_utc).days if (now_utc and item_utc) else 0
        if late > config["max_overdue_days"]:
            reasons.append(f"vencida hace {late} dias (limite {config['max_overdue_days']}): decide David si sigue vigente")
        (skipped if reasons else ok).append((item, reasons))
    return [i for i, _ in ok], skipped


# ------------------------------------------------------------------------------------------------------ adaptadores
def publish_bluesky(item):
    import bluesky_interact as b
    sess = b._session()
    text = item["texto"]
    b._check_length(text)
    b._check_spanish_orthography(text)
    record = b._add_richtext({"$type": "app.bsky.feed.post", "text": text, "createdAt": b._now(), "langs": ["es"]})
    if item.get("imagen"):
        record["embed"] = b._upload_image(item["imagen"], item["alt"])
    created = b._require_created_record(b._post_xrpc("com.atproto.repo.createRecord", {"repo": sess["did"], "collection": "app.bsky.feed.post", "record": record}), "app.bsky.feed.post")
    handle = sess.get("handle") or "autorademoescritor.bsky.social"
    return f"https://bsky.app/profile/{handle}/post/{created['uri'].rsplit('/', 1)[-1]}"


def publish_mastodon(item):
    import mastodon_interact as m
    result = m.patient(lambda: m.publish_own(item["texto"], item.get("imagen"), item.get("alt") or ""))
    return result.get("url") or result["id"]


def publish_threads(item):
    import threads_interact as t
    return t.post(item["texto"], item.get("imagen"))


def publish_x(item):
    import x_interact as x
    return x.post(item["texto"], item.get("imagen"))          # devuelve el permalink localizado en el perfil


def _media(item):
    existing = [m for m in item.get("media") or [] if m.get("exists")]
    return [m["path"] for m in existing], [m.get("alt") or "" for m in existing]


def publish_facebook(item):
    import meta_common as mc
    import meta_publish as mp
    env = mc.read_env()
    images, alts = _media(item)
    post_id = mp.publish_facebook(env["FB_PAGE_TOKEN"], env["FB_PAGE_ID"], item["texto"], images, alts)
    return mp.facebook_permalink(env["FB_PAGE_TOKEN"], post_id)


def publish_instagram(item):
    import meta_common as mc
    import meta_publish as mp
    env = mc.read_env()
    images, alts = _media(item)
    urls = [mp.public_image_url(env["FB_PAGE_TOKEN"], env["FB_PAGE_ID"], path) for path in images]
    media_id = mp.publish_instagram(env["IG_ACCESS_TOKEN"], env["IG_USER_ID"], item["texto"], urls, alts)
    return mp.instagram_permalink(env["IG_ACCESS_TOKEN"], media_id)


def publish_pinterest(item):
    import pinterest_publish as pp
    meta = item.get("meta") or {}
    missing = [name for name, value in (("titulo", item.get("titulo")), ("descripcion", item.get("texto")), ("enlace", meta.get("enlace")), ("tablero", meta.get("tablero")),
                                        ("imagen", item.get("imagen"))) if not value]
    if missing:
        raise RuntimeError("ficha de Pinterest incompleta: falta " + ", ".join(missing))
    return pp.publish_pin(item["imagen"], item["titulo"], item["texto"], meta["enlace"], item.get("alt") or meta.get("alt", ""), meta["tablero"], apply=True)


PUBLISHERS = {"bluesky": publish_bluesky, "mastodon": publish_mastodon, "threads": publish_threads, "x": publish_x,
              "facebook": publish_facebook, "instagram": publish_instagram, "pinterest": publish_pinterest}


def _log(red, item, url):
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        if new:
            writer.writerow(["fecha_hora", "red", "ficha", "programada", "url"])
        stamp = (datetime.datetime.now(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
                 if red == "x" else datetime.datetime.now())
        writer.writerow([stamp.isoformat(timespec="minutes"), red, os.path.basename(item["carpeta"]), f"{item['fecha_hora']:%Y-%m-%d %H:%M}", url])


MIN_GAP_HOURS = 3        # entre dos publicaciones automaticas de la misma red (evita soltar de golpe varias fichas atrasadas)


def last_auto_publication(red, log_path=None, *, strict=False, not_after=None, notify=None):
    """Ultima ficha; en preflight X, un CSV inválido no equivale a historial vacío."""
    last = None
    path = log_path or LOG
    try:
        with open(path, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=strict)
            required = {"fecha_hora", "red", "ficha", "programada", "url"}
            if strict and (not reader.fieldnames or
                           not required.issubset(reader.fieldnames) or
                           len(reader.fieldnames) != len(set(reader.fieldnames))):
                raise ValueError("cabecera de publicaciones automáticas inválida")
            for row in reader:
                if strict and (None in row or not row.get("red")):
                    raise ValueError("fila incompleta del historial de fichas")
                if row.get("red") != red:
                    continue
                if strict and any(not (row.get(key) or "").strip() for key in required):
                    raise ValueError("fila incompleta del historial de fichas")
                try:
                    when = datetime.datetime.fromisoformat(row["fecha_hora"])
                except (ValueError, KeyError, TypeError):
                    if strict:
                        raise ValueError("fecha inválida del historial de fichas") from None
                    continue
                if red == "x" and when.tzinfo is not None:
                    when = when.astimezone(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
                if red == "x" and not_after is not None:
                    check_not_after = not_after.replace(tzinfo=None) if not_after.tzinfo is not None else not_after
                    if when > check_not_after:
                        if notify is not None:
                            notify("[x] AVISO: ficha con fecha en el futuro; no cuenta para cadencia")
                        continue
                last = when if last is None or when > last else last
    except FileNotFoundError:
        if strict and not os.path.isdir(os.path.dirname(os.path.abspath(path))):
            raise
    except (csv.Error, UnicodeError):
        if strict:
            raise ValueError("CSV o codificación inválida del historial de fichas") from None
    except OSError:
        if strict:
            raise
    return last


def _verify(red, now):
    return cqa.classify(red, now, allow_browser=True)


def run(red, *, apply=False, now=None, out=print, publishers=None, verify=_verify, log_path=None):
    """Publica como mucho una ficha de `red`. Devuelve la URL o None."""
    now = now or datetime.datetime.now(ZoneInfo("Europe/Madrid"))
    if red == "x":
        if now.tzinfo is not None and now.utcoffset() is not None:
            now = now.astimezone(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
        elif now.tzinfo is not None:
            now = now.replace(tzinfo=None)
    else:
        if now.tzinfo is None:
            now = now.replace(tzinfo=ZoneInfo("Europe/Madrid"))
        else:
            now = now.astimezone(ZoneInfo("Europe/Madrid"))
    config = load_config()
    publishers = publishers or PUBLISHERS
    if red not in publishers or not config["enabled"].get(red):
        return None
    issues = {path: missing for path, missing in cq.pending_parse_issues(red, auto_only=False)}
    verify(red, now)                      # marca solas las fichas que ya estan publicadas en la red (David publica a mano y a veces no actualiza la ficha)
    ready, skipped = eligible(red, now, config, issues)
    for item, reasons in skipped:
        out(f"[{red}] NO se publica {os.path.basename(item['carpeta'])} ({item['fecha_hora']:%d/%m %H:%M}): " + "; ".join(reasons))
    if not ready:
        return None
    x_gap_hours = MIN_GAP_HOURS
    try:
        if apply and red == "x":
            # Mantener 3 h ENTRE FICHAS de X como antes de esta PR.
            # Las 6 h del banco solo limitan el cruce BANCO -> FICHA;
            # no cambiar la periodicidad interna sin evidencias de impacto.
            import x_bank_publish as xb
            last = last_auto_publication(
                red, log_path, strict=True,
                not_after=now + datetime.timedelta(minutes=5), notify=out)
        else:
            # Conservar la firma histórica de las demás redes y sus adaptadores.
            last = last_auto_publication(red, log_path)
    except (OSError, ValueError) as exc:
        out(f"[x] ERROR integridad: NO se publica; historial de fichas no verificable ({type(exc).__name__})")
        return None
    if apply and last is not None:
        if red == "x":
            elapsed = xb.conservative_elapsed_seconds(now, last)
        else:
            now_dt = now.replace(tzinfo=None) if hasattr(now, "tzinfo") and now.tzinfo is not None else now
            last_dt = last.replace(tzinfo=None) if hasattr(last, "tzinfo") and last.tzinfo is not None else last
            elapsed = (now_dt - last_dt).total_seconds()
        if elapsed < x_gap_hours * 3600:
            out(f"[{red}] hay {len(ready)} ficha(s) lista(s) pero la ultima publicacion automatica fue a las {last:%H:%M}: se espera (minimo {x_gap_hours} h entre dos)")
            return None
    if apply and red == "x":
        # #114 revalida banco -> fichas; el camino inverso también debe
        # respetar el historial del banco tras conseguir el turno Edge.
        # main() sostiene browser_session durante run(), por lo que esta
        # lectura y la publicación se realizan bajo el mismo candado.
        # xb se ha importado dentro del preflight de X, evitando importar
        # x_bank_publish globalmente (dependencia circular con su main).
        # Una fila muy futura puede indicar reloj o CSV editado a mano:
        # no paralizar durante días todas las fichas por ese dato anómalo.
        recent_bound = now + datetime.timedelta(minutes=5)
        bank_times = []
        try:
            bank_rows = xb.read_log(strict=True)
        except (OSError, ValueError) as exc:
            out(f"[x] ERROR integridad: NO se publica; registro del banco no verificable ({type(exc).__name__})")
            return None
        for row in bank_rows:
            when = row.get("when")
            if not isinstance(when, datetime.datetime) or (
                    when.tzinfo is not None and when.utcoffset() is not None):
                out("[x] ERROR integridad: NO se publica; fecha del banco no verificable")
                return None
            if when > recent_bound:
                out("[x] AVISO: registro del banco con fecha en el futuro; "
                    "se ignora para el enfriamiento de fichas")
                continue
            bank_times.append(when)
        if bank_times:
            last_bank = max(bank_times)
            if xb.conservative_elapsed_seconds(now, last_bank) < xb.MIN_GAP_HOURS * 3600:
                out(f"[x] hay {len(ready)} ficha(s) lista(s) pero el último post del banco "
                    f"fue a las {last_bank:%H:%M}: se espera "
                    f"(mínimo {xb.MIN_GAP_HOURS} h entre banco y ficha)")
                return None
    item = ready[0]
    label = f"{os.path.basename(item['carpeta'])} ({item['fecha_hora']:%d/%m %H:%M}) «{' '.join(item['texto'].split())[:60]}»"
    if not apply:
        out(f"[{red}] publicaria: {label}")
        return None
    try:
        url = publishers[red](item)
    except Exception:
        # el envio pudo salir aunque no se confirmara (Threads: «no hay un unico permalink nuevo verificable»): se comprueba en la red ANTES de dar la ficha por no publicada
        verify(red, now)
        if item["md_path"] not in {i["md_path"] for i in cq.due_items(red, now)}:
            out(f"[{red}] PUBLICADA (confirmada en la red tras un aviso del cliente): {label}")
            _log(red, item, "confirmada por API")
            return "confirmada por API"
        raise
    cq.mark_done(item["md_path"], f"publicada por la ronda: {url}")
    _log(red, item, url)
    out(f"[{red}] PUBLICADA: {label} -> {url}")
    return url


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    target = next((a for a in argv if not a.startswith("--")), "todas")
    apply = "--apply" in argv
    names = list(PUBLISHERS) if target == "todas" else [target]
    import contextlib
    import action_ledger
    for red in names:
        if red not in PUBLISHERS:
            print(f"[{red}] sin adaptador de publicacion automatica (solo aviso: content_queue_alert.py)")
            continue
        try:
            guard = action_ledger.browser_session(wait_minutes=40) if red in BROWSER else contextlib.nullcontext()          # tambien sin --apply: la verificacion en la red usa el navegador
            with guard:
                run(red, apply=apply)
        except Exception as exc:
            print(f"[{red}] ERROR al publicar: {type(exc).__name__}: {str(exc)[:200]} (no se marca la ficha; la siguiente ejecucion lo reintenta tras comprobar si salio)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

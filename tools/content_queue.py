"""
Cola de autopromocion (24/09) - lee las carpetas `publicaciones <Red> GPT/`
(contenido ya redactado por David/GPT: texto final, imagen, ALT, fecha/hora
propuesta) y decide que esta LISTO para salir ahora mismo, sin depender de
que ninguna sesion siga despierta a la hora exacta.

Por que existe: ni Bluesky ni Threads tienen programacion nativa real (AT
Protocol no programa - confirmado en vivo el 24/09 via busqueda web, no es
una limitacion de este cliente; Threads no expone attach de topic/comunidad
todavia desde el compositor). En vez de intentar disparar la publicacion en
el segundo exacto (fragil, depende de que Claude siga activo ese momento),
este modulo implementa lo que David pidio explicitamente: "si cuando
ejecutamos bluesky ve que hay una publicacion pendiente ya la pone al
momento. Y si ayer no se publico, que la publique y listo" - es decir,
"debido o vencido" (due), no "a las X en punto".

X y Mastodon SI tienen programacion real del lado del servidor (el boton
Schedule de X, el parametro scheduled_at de la API de Mastodon) - para esas
dos NO hace falta esperar a que este "debido": se programa en cuanto se
detecta, sea cual sea la fecha futura, y el propio X/Mastodon se encarga de
publicarlo a su hora exacta sin que dependa de esta sesion.

Formato esperado de cada `publicaciones <Red> GPT/AAAA-MM-DD/publicacion.md`
(ya establecido por las carpetas existentes, no inventado aqui): un campo
`**Estado:**` en las primeras lineas, fecha/hora en uno de dos formatos
("Fecha y hora: <dia> DD/MM/YYYY, HH:MM" o "Fecha:"/"Hora:" separados con
fecha en letra), imagen en "Imagen:"/"Archivo:", ALT en "ALT:" o bajo
"### Texto alternativo", y el texto final bajo "## Texto final" (a veces en
un bloque ```text```, a veces en parrafo simple).

Uso:
    from content_queue import due_items, scan_items, mark_done
"""
import datetime
import glob
import os
import re
from zoneinfo import ZoneInfo

ROOT = os.path.join(os.path.dirname(__file__), "..")

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}

RED_FOLDERS = {
    "x": "publicaciones X GPT",
    "threads": "publicaciones Threads GPT",
    "bluesky": "publicaciones Bluesky GPT",
    "mastodon": "publicaciones Mastodon GPT",
    "facebook": "publicaciones Facebook GPT",
    "instagram": "publicaciones Instagram GPT",
    "reddit": "publicaciones Reddit GPT",
    "pinterest": "publicaciones Pinterest GPT",
    "tiktok": "publicaciones TikTok GPT",
}


def classify_local_datetime(dt_naive, tz_name="Europe/Madrid"):
    """Clasifica una fecha/hora local naive en su zona horaria:
    - 'unambiguous': hora normal sin salto ni solapamiento.
    - 'non_existent': salto de primavera (spring-forward gap), hora imposible.
    - 'ambiguous': solapamiento de otoño (fall-back overlap), dos instantes UTC.
    """
    if dt_naive is None:
        return "missing"
    tz = ZoneInfo(tz_name)
    dt0 = dt_naive.replace(tzinfo=tz, fold=0)
    dt1 = dt_naive.replace(tzinfo=tz, fold=1)

    utc0 = dt0.astimezone(datetime.timezone.utc)
    back0 = utc0.astimezone(tz)
    if (back0.hour, back0.minute) != (dt_naive.hour, dt_naive.minute):
        return "non_existent"

    if dt0.utcoffset() != dt1.utcoffset():
        return "ambiguous"

    return "unambiguous"


def resolve_dst_datetime(dt_naive, meta=None, tz_name="Europe/Madrid"):
    """Resuelve el instante UTC exacto para una fecha/hora local, aplicando
    desambiguación explícita (fold, offset o instante UTC) si la hora es ambigua.
    Devuelve (classification, dt_utc, error_msg).
    """
    if dt_naive is None:
        return ("missing", None, None)

    status = classify_local_datetime(dt_naive, tz_name=tz_name)
    if status == "non_existent":
        return ("non_existent", None, "fecha/hora imposible (salto DST / spring-forward gap)")

    tz = ZoneInfo(tz_name)
    if status == "unambiguous":
        dt_tz = dt_naive.replace(tzinfo=tz)
        return ("unambiguous", dt_tz.astimezone(datetime.timezone.utc), None)

    meta = meta or {}
    # Buscar claves de desambiguación explícita
    fold_str = meta.get("fold")
    offset_str = meta.get("offset") or meta.get("offset utc") or meta.get("utc offset")
    utc_str = meta.get("utc") or meta.get("instante utc") or meta.get("utc instant")

    if utc_str:
        try:
            iso_str = utc_str.rstrip("Z").rstrip(".")
            if "T" not in iso_str and " " in iso_str:
                iso_str = iso_str.replace(" ", "T")
            dt_utc = datetime.datetime.fromisoformat(iso_str)
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=datetime.timezone.utc)
            else:
                dt_utc = dt_utc.astimezone(datetime.timezone.utc)
            return ("ambiguous", dt_utc, None)
        except (ValueError, TypeError):
            pass

    if fold_str in ("0", "1"):
        fold_val = int(fold_str)
        dt_tz = dt_naive.replace(tzinfo=tz, fold=fold_val)
        return ("ambiguous", dt_tz.astimezone(datetime.timezone.utc), None)

    if offset_str:
        m = re.search(r"([+-])?0?(\d{1,2}):?(\d{2})?", str(offset_str))
        if m:
            sign = -1 if m.group(1) == "-" else 1
            hrs = int(m.group(2))
            mins = int(m.group(3) or 0)
            target_seconds = sign * (hrs * 3600 + mins * 60)
            dt0 = dt_naive.replace(tzinfo=tz, fold=0)
            dt1 = dt_naive.replace(tzinfo=tz, fold=1)
            if int(dt0.utcoffset().total_seconds()) == target_seconds:
                return ("ambiguous", dt0.astimezone(datetime.timezone.utc), None)
            if int(dt1.utcoffset().total_seconds()) == target_seconds:
                return ("ambiguous", dt1.astimezone(datetime.timezone.utc), None)

    return ("ambiguous", None, "fecha/hora ambigua en cambio de hora (fall-back overlap); se requiere offset o fold explícito")


def _parse_fecha_hora(content):
    # Formato combinado: "Fecha y hora:** jueves 24/09/2026, 17:30"
    m = re.search(r"Fecha y hora:\*\*\s*\w+\s+(\d{1,2})/(\d{1,2})/(\d{4}),\s*(\d{1,2}):(\d{2})", content)
    if m:
        day, month, year, hour, minute = map(int, m.groups())
        return datetime.datetime(year, month, day, hour, minute)
    # Formato ISO ya usado por varias fichas: "2026-09-28, 09:30" (con "Fecha y hora:" o solo "Fecha:").
    m_iso = re.search(
        r"Fecha(?: y hora)?:\*\*\s*(\d{4})-(\d{2})-(\d{2}),\s*(\d{1,2}):(\d{2})",
        content,
    )
    if m_iso:
        year, month, day, hour, minute = map(int, m_iso.groups())
        return datetime.datetime(year, month, day, hour, minute)
    # Formato separado: "Fecha( propuesta)?:** ..., 24 de septiembre de 2026" +
    # "Hora( propuesta)?:** 19:30"
    m_fecha = re.search(
        r"Fecha(?: propuesta)?:\*\*\s*[^,]*,?\s*(\d{1,2}) de (\w+) de (\d{4})", content
    )
    m_hora = re.search(r"Hora(?: propuesta)?:\*\*\s*(\d{1,2}):(\d{2})", content)
    if m_fecha and m_hora:
        day, mes_txt, year = m_fecha.groups()
        mes = MESES.get(mes_txt.lower())
        if mes:
            hour, minute = map(int, m_hora.groups())
            return datetime.datetime(int(year), mes, int(day), hour, minute)
    return None



def _safe_media_path(carpeta, filename):
    """Resuelve media solo dentro de la carpeta de la ficha."""
    if not isinstance(filename, str) or not filename.strip():
        return None
    original = filename.strip()
    if re.match(r"^[A-Za-z]:[\\/]", original):
        return None
    raw = original.replace("\\", os.sep)
    if os.path.isabs(raw):
        return None
    base = os.path.realpath(carpeta)
    candidate = os.path.realpath(os.path.join(base, raw))
    try:
        if os.path.commonpath([base, candidate]) != base:
            return None
    except ValueError:
        return None
    return candidate


def _parse_media_entries(content, carpeta):
    """Detecta media declarada tanto en metadatos como en 'Medios y ALT'."""
    entries = []

    direct = re.search(
        r"(?:Imagen|Archivo):\*\*\s*\x60([^\x60]+)\x60",
        content,
        re.I,
    )
    if direct:
        filename = direct.group(1).strip()
        path = _safe_media_path(carpeta, filename)
        entries.append({
            "filename": filename,
            "path": path,
            "exists": bool(path and os.path.isfile(path)),
            "alt": _parse_alt(content),
        })

    section = re.search(
        r"^## Medios y ALT\s*\n+(.*?)(?=^## |\Z)",
        content,
        re.S | re.M | re.I,
    )
    if section:
        for match in re.finditer(
            r"^\s*\d+\.\s*\x60([^\x60]+)\x60\s*:\s*(.+?)\s*$",
            section.group(1),
            re.M,
        ):
            filename = match.group(1).strip()
            if any(item["filename"] == filename for item in entries):
                continue
            path = _safe_media_path(carpeta, filename)
            entries.append({
                "filename": filename,
                "path": path,
                "exists": bool(path and os.path.isfile(path)),
                "alt": match.group(2).strip(),
            })
    return entries

def _parse_imagen(content, carpeta):
    """Compatibilidad: devuelve una sola imagen solo si la ficha declara una."""
    entries = _parse_media_entries(content, carpeta)
    if len(entries) != 1:
        return None
    return entries[0]["path"] if entries[0]["exists"] else None

def _parse_alt(content):
    m = re.search(r"ALT:\*\*\s*(.+)", content)
    if m:
        return m.group(1).strip()
    m = re.search(
        r"### Texto alternativo\s*\n+(.+?)(?=\n#|\n\n##|\Z)",
        content,
        re.S,
    )
    return m.group(1).strip() if m else ""

def _parse_texto(content):
    """Extrae el cuerpo editorial en los encabezados reales de las 9 redes."""
    headings = (
        r"Texto final[^\n]*",
        r"Caption final[^\n]*",
        r"Texto",
        r"Descripción",
    )
    for heading in headings:
        match = re.search(
            rf"^## {heading}\s*\n+(.*?)(?=^## |\Z)",
            content,
            re.S | re.M | re.I,
        )
        if not match:
            continue
        block = match.group(1).strip()
        fence = re.search(r"\x60\x60\x60text\s*\n(.*?)\n\x60\x60\x60", block, re.S | re.I)
        return fence.group(1).strip() if fence else block
    return None

def _parse_meta(content):
    """Datos de la ficha en sus lineas `- **Clave:** valor` (tablero, subreddit, flair, enlace, ALT...), con la clave en minusculas."""
    meta = {}
    for key, value in re.findall(r"^\s*(?:-\s*)?\*\*([^*:\n]+):\*\*\s*(.+?)\s*$", content, re.M):
        meta.setdefault(key.strip().casefold(), value.strip().rstrip(".").strip("`").strip())
    return meta


def _parse_titulo(content):
    """Seccion `## Titulo` (Pinterest, Reddit): una sola linea."""
    m = re.search(r"^## T[ií]tulo\s*\n+(.*?)(?=^## |\Z)", content, re.S | re.M | re.I)
    return " ".join(m.group(1).split()) if m else None


def _parse_primera_respuesta(content):
    """Primera respuesta propia opcional; también funciona como última sección."""
    m = re.search(
        r"^## Primera respuesta propia\s*\n+(.*?)(?=^## |\Z)",
        content,
        re.S | re.M | re.I,
    )
    if not m:
        return None
    return m.group(1).strip().split("\n\n")[0].strip()

def _parse_estado(content):
    m = re.search(r"\*\*Estado:\*\*([^\n]*)", content)
    return m.group(1).strip() if m else ""



def _parse_auto_ok(content):
    """Opt-in inequívoco, únicamente en el bloque de metadatos inicial."""
    metadata = re.split(r"^##\s+", content, maxsplit=1, flags=re.M)[0]
    return bool(re.search(
        r"^\s*(?:-\s*)?\*\*Auto:\*\*\s*(?:sí|si|yes|true)\s*\.?\s*$",
        metadata,
        flags=re.I | re.M,
    ))

def _explicit_blockers(content):
    folded = content.casefold()
    blockers = []
    for phrase in (
        "no usarlo todavía",
        "no usarlo todavia",
        "pendiente de verificar",
    ):
        if phrase in folded:
            blockers.append(phrase)
    return blockers



def scan_items(red):
    """Devuelve todas las fichas de esa red (publicadas/programadas o no),
    parseadas, ordenadas por fecha."""
    folder = RED_FOLDERS[red]
    base = os.path.join(ROOT, folder)
    items = []
    for md_path in sorted(glob.glob(os.path.join(base, "*", "publicacion.md"))):
        carpeta = os.path.dirname(md_path)
        with open(md_path, encoding="utf-8") as f:
            content = f.read()
        fecha_hora = _parse_fecha_hora(content)
        meta = _parse_meta(content)
        dst_status, fecha_hora_utc, dst_err = resolve_dst_datetime(fecha_hora, meta)
        media = _parse_media_entries(content, carpeta)
        single_media = media[0] if len(media) == 1 else None
        items.append({
            "red": red,
            "md_path": md_path,
            "carpeta": carpeta,
            "fecha_hora": fecha_hora,
            "fecha_hora_utc": fecha_hora_utc,
            "dst_status": dst_status,
            "dst_err": dst_err,
            "estado": _parse_estado(content),
            "auto_ok": _parse_auto_ok(content),
            "blockers": _explicit_blockers(content),
            "texto": _parse_texto(content),
            "media": media,
            "media_count": len(media),
            "imagen": (
                single_media["path"]
                if single_media and single_media["exists"]
                else None
            ),
            "imagen_declarada": bool(media),
            "alt": (
                single_media["alt"]
                if single_media
                else _parse_alt(content)
            ),
            "primera_respuesta": _parse_primera_respuesta(content),
            "meta": meta,
            "titulo": _parse_titulo(content),
        })
    return items



def pending_parse_issues(red, auto_only=False):
    """Fichas no resueltas que la cola no puede ejecutar de forma fiable."""
    issues = []
    for item in scan_items(red):
        if auto_only and not item.get("auto_ok"):
            continue
        state = item["estado"]
        if state and _ya_resuelto(state):
            continue
        missing = []
        if not state:
            missing.append("Estado")
        if not item["fecha_hora"]:
            missing.append("fecha/hora")
        elif item.get("dst_err"):
            missing.append(item["dst_err"])
        if not item["texto"]:
            missing.append("Texto final")
        missing_media = [
            entry["filename"] for entry in item.get("media", [])
            if not entry.get("exists")
        ]
        if missing_media:
            missing.append(
                "archivo(s) de media inexistente(s): " + ", ".join(missing_media)
            )
        if item.get("auto_ok") and item.get("media_count", 0) > 1:
            missing.append(
                "varios archivos de media: la cola automática actual solo "
                "admite uno"
            )
        if item["imagen"] and not item["alt"]:
            missing.append("ALT de imagen")
        if item.get("auto_ok") and item.get("blockers"):
            missing.append("bloqueo editorial explícito: " + ", ".join(item["blockers"]))
        if missing:
            issues.append((item["md_path"], missing))
    return issues



def _ya_resuelto(estado):
    """BUG REAL evitado antes de usarlo: un chequeo ingenuo de "publicad" in e
    habria marcado como resuelto el estado INICIAL "no programada ni
    publicada" (contiene literalmente "publicada" como subcadena, aunque
    negado por el "ni" que la precede). Se comprueba primero la negacion
    explicita."""
    e = estado.lower()
    if re.search(r"no\s+(programad|publicad)", e):
        return False
    # Estado de cuarentena: una escritura pudo haberse realizado pero no
    # quedó confirmada. No reintentar automáticamente y arriesgar duplicado.
    if "revisar manualmente" in e or "estado incierto" in e:
        return True
    return "publicad" in e or "programad" in e


def _to_utc_instant(dt_or_now, tz_name="Europe/Madrid"):
    if dt_or_now is None:
        return None
    if isinstance(dt_or_now, datetime.datetime):
        if dt_or_now.tzinfo is None:
            tz = ZoneInfo(tz_name)
            return dt_or_now.replace(tzinfo=tz).astimezone(datetime.timezone.utc)
        return dt_or_now.astimezone(datetime.timezone.utc)
    return None


def due_items(red, now=None):
    """Fichas con fecha/hora ya vencida (<= ahora) y todavia no marcadas
    como publicadas/programadas - las "debidas" que David pidio poder
    recuperar aunque se ejecute tarde (ayer, hoy, la semana pasada)."""
    now_utc = _to_utc_instant(now if now is not None else datetime.datetime.now(ZoneInfo("Europe/Madrid")))
    out = []
    for item in scan_items(red):
        if not item["fecha_hora"] or not item.get("fecha_hora_utc") or not item["texto"] or not item["estado"]:
            continue
        if item.get("dst_err"):
            continue
        if _ya_resuelto(item["estado"]):
            continue
        if item["fecha_hora_utc"] <= now_utc:
            out.append(item)
    return out


def future_items(red, now=None):
    """Fichas con fecha/hora futura y sin resolver - para X/Mastodon, que SI
    programan de verdad, no hace falta esperar a que esten "debidas"."""
    now_utc = _to_utc_instant(now if now is not None else datetime.datetime.now(ZoneInfo("Europe/Madrid")))
    out = []
    for item in scan_items(red):
        if not item["fecha_hora"] or not item.get("fecha_hora_utc") or not item["texto"] or not item["estado"]:
            continue
        if item.get("dst_err"):
            continue
        if _ya_resuelto(item["estado"]):
            continue
        if item["fecha_hora_utc"] > now_utc:
            out.append(item)
    return out



def read_state(md_path):
    with open(md_path, encoding="utf-8") as stream:
        return _parse_estado(stream.read())

def mark_done(md_path, nota):
    with open(md_path, encoding="utf-8") as f:
        content = f.read()
    fecha = datetime.datetime.now(ZoneInfo("Europe/Madrid")).isoformat(timespec="minutes")
    content, changed = re.subn(
        r"\*\*Estado:\*\*[^\n]*",
        lambda match: f"**Estado:** {nota} ({fecha})",
        content, count=1,
    )
    if changed != 1:
        raise RuntimeError("La ficha no tiene campo **Estado:**; no se puede registrar resultado")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)

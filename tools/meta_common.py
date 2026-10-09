"""Piezas comunes de las APIs de Meta (Threads, Instagram, Facebook Pages) - 03/10/2026.

Las tres hablan con una Graph API casi identica (GET/POST con access_token, errores JSON, tokens en
.env, "responder una vez y solo si preguntan"). Lo comun vive aqui; cada red solo define su base,
sus endpoints y su politica. Las funciones puras no tocan la red (testeables).
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
CRLF = chr(13) + chr(10)


def read_env(root=None):
    values = {}
    with open(os.path.join(root or ROOT, ".env"), encoding="utf-8") as stream:
        for line in stream:
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.rstrip(CRLF).split("=", 1)
                values[key.strip()] = value.strip()
    return values


def write_env(updates, root=None):
    """Sustituye o anade claves en .env conservando el resto y el tipo de salto de linea."""
    path = os.path.join(root or ROOT, ".env")
    with open(path, "rb") as stream:
        raw = stream.read().decode("utf-8")
    newline = CRLF if CRLF in raw else chr(10)
    lines, seen = [], set()
    for line in raw.splitlines():
        key = line.split("=", 1)[0]
        if key in updates and "=" in line:
            line = f"{key}={updates[key]}"
            seen.add(key)
        lines.append(line)
    lines += [f"{k}={v}" for k, v in updates.items() if k not in seen]
    with open(path, "wb") as stream:
        stream.write((newline.join(lines) + newline).encode("utf-8"))


def _error_message(exc):
    body = exc.read().decode("utf-8", "replace")
    try:
        return json.loads(body)["error"]["message"][:200]
    except (ValueError, KeyError):
        return body[:200]


def graph_get(base, path, token, **params):
    params["access_token"] = token
    url = base + path + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"API {exc.code}: {_error_message(exc)}") from None


def graph_post(base, path, token, **params):
    params["access_token"] = token
    request = urllib.request.Request(base + path, data=urllib.parse.urlencode(params).encode())
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"API {exc.code}: {_error_message(exc)}") from None


def unanswered(items, my_names, answered_ids=(), text_key="text", user_key="username", id_key="id",
               time_key="timestamp"):
    """Mensajes ajenos con pregunta y sin respuesta nuestra, mas recientes primero.
    Politica de David (03/10): una conversacion se contesta una vez; despues solo si nos preguntan."""
    mine = {str(n).casefold() for n in my_names}
    out = []
    for item in items:
        if str(item.get(user_key) or "").casefold() in mine:
            continue
        if item.get(id_key) in answered_ids or "?" not in (item.get(text_key) or ""):
            continue
        out.append(item)
    return sorted(out, key=lambda r: r.get(time_key) or "", reverse=True)


def check_text(text, limit):
    text = (text or "").strip()
    if not text:
        raise ValueError("texto vacio")
    if len(text) > limit:
        raise ValueError(f"{len(text)} caracteres (max {limit})")
    return text


def reject_returned_question(text, allow=False):
    if "?" in text and not allow:
        raise ValueError("un seguimiento no termina con pregunta (se alargaria el hilo)")
    return text

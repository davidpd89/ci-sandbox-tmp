"""Audita el Edge compartido (CDP 9223). Nunca inicia procesos de navegador.

Uso:
    python tools/cdp_health.py
    python tools/cdp_health.py --close-target TARGET_ID --confirm

El cierre es explícito por ID exacto de una pestaña del contexto CDP. Antes
de cerrar se vuelve a leer /json/list y se exige que ID y URL sigan siendo
exactamente los aprobados.
"""
import argparse
import json
import urllib.request
from urllib.parse import quote, urlsplit

CDP_URL = "http://127.0.0.1:9223"
SOCIAL_DOMAINS = {
    "x.com", "www.x.com", "twitter.com", "www.twitter.com",
    "threads.com", "www.threads.com", "threads.net", "www.threads.net",
    "instagram.com", "www.instagram.com", "facebook.com", "www.facebook.com",
    "bsky.app", "www.bsky.app", "mastodon.social", "www.mastodon.social",
    "reddit.com", "www.reddit.com", "pinterest.com", "www.pinterest.com",
    "tiktok.com", "www.tiktok.com",
}


def _cdp_json(path):
    with urllib.request.urlopen(CDP_URL + path, timeout=5) as response:
        return json.load(response)


def _cdp_text(path):
    with urllib.request.urlopen(CDP_URL + path, timeout=5) as response:
        return response.read().decode("utf-8", errors="replace")


def _split_url_safe(value):
    try:
        return urlsplit(value or "")
    except (TypeError, ValueError):
        return urlsplit("about:blank")


def _page_targets():
    data = _cdp_json("/json/list")
    if not isinstance(data, list):
        raise RuntimeError("CDP /json/list no devolvió una lista; no continuar")
    return [item for item in data if isinstance(item, dict) and item.get("type") == "page"]


def _safe_target_label(target):
    """Etiqueta de inventario sin path, query, fragment, usuario ni contraseña."""
    original = target.get("url", "")
    if original == "about:blank":
        return "about:blank"
    parsed = _split_url_safe(original)
    if parsed.hostname:
        scheme = parsed.scheme if parsed.scheme in {"http", "https"} else "[esquema]"
        return f"{scheme}://{parsed.hostname}/ [ruta oculta]"
    return "[URL no confiable] [ruta oculta]"


def _approved_close_url(value):
    """Solo about:blank o HTTPS de un host social exacto, sin credenciales/puerto."""
    if value == "about:blank":
        return True
    parsed = _split_url_safe(value)
    try:
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in SOCIAL_DOMAINS
        and parsed.username is None
        and parsed.password is None
        and port is None
    )


def _unique_target(targets, target_id):
    matches = [item for item in targets if item.get("id") == target_id]
    if len(matches) != 1:
        raise RuntimeError(
            "Target ID no encontrado o ambiguo: lista caducada; repetir diagnóstico"
        )
    return matches[0]


def _close_target_explicit(target_id, approved_url):
    """Revalida el target y usa el endpoint CDP de cierre por ID exacto."""
    current = _unique_target(_page_targets(), target_id)
    current_url = current.get("url", "")
    if current_url != approved_url:
        raise RuntimeError(
            "La pestaña ha navegado desde el diagnóstico; no cerrar"
        )
    if not _approved_close_url(current_url):
        raise RuntimeError(
            "El target ya no cumple la política de cierre; no cerrar"
        )
    encoded_id = quote(str(target_id), safe="")
    response = _cdp_text(f"/json/close/{encoded_id}")
    if "Target is closing" not in response:
        raise RuntimeError(
            f"CDP no confirmó el cierre del target {target_id!r}: {response[:120]!r}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-tabs", type=int, default=20)
    parser.add_argument("--close-target", metavar="TARGET_ID")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if args.max_tabs < 1:
        parser.error("--max-tabs debe ser >= 1")
    if bool(args.close_target) != bool(args.confirm):
        parser.error(
            "Para cerrar una pestaña indicar --close-target ID Y --confirm"
        )

    _cdp_json("/json/version")  # exige una sesión existente; nunca arranca Edge
    targets = _page_targets()

    print(f"Edge CDP 9223: {len(targets)} pestaña(s); umbral {args.max_tabs}")
    for target in targets:
        print(f"{target.get('id', '?')} | {_safe_target_label(target)[:170]}")

    if len(targets) >= args.max_tabs:
        print(
            "AVISO: revisar pestañas duplicadas antes de cambiar de red; "
            "NO cerrar a ciegas"
        )

    if not args.close_target:
        print(
            "Diagnóstico de pestañas terminado. Procesos zombie: "
            "inspección manual en Administrador de tareas."
        )
        return 2 if len(targets) >= args.max_tabs else 0

    target = _unique_target(targets, args.close_target)
    approved_url = target.get("url", "")
    if not _approved_close_url(approved_url):
        parsed = _split_url_safe(approved_url)
        domain = parsed.hostname or "[sin-host]"
        raise RuntimeError(
            f"No se permite cerrar target fuera de HTTPS/redes aprobadas: {domain}"
        )

    _close_target_explicit(args.close_target, approved_url)
    print(f"TARGET CERRADO por solicitud explícita: {args.close_target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

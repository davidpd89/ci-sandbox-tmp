"""Auditoría OPCIONAL y de solo lectura de pines ya publicados vía Pinterest API v5.

No forma parte del flujo diario de publicación. La publicación/programación sigue
siendo manual/nativa en Pinterest.

python tools/pinterest_api_audit.py --demo  # prueba local sin red
python tools/pinterest_api_audit.py         # requiere PINTEREST_ACCESS_TOKEN

Scopes mínimos de esta utilidad:
    user_accounts:read boards:read pins:read

No crea, modifica ni publica pines; no imprime tokens.
"""
import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request


API_ORIGIN = "https://api.pinterest.com"
PINS_URL = API_ORIGIN + "/v5/pins"
USER_ACCOUNT_URL = API_ORIGIN + "/v5/user_account"
EXPECTED_USERNAME = "autorademodiaz"

INTERNAL_ID = re.compile(r"\b(?:IG|TT|FB|DP)-[A-Z0-9-]+\b", re.I)
HOME_HOSTS = {"autorademodiaz.com", "www.autorademodiaz.com"}


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Nunca reenviar Authorization a una ubicación distinta."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            req.full_url,
            code,
            "Redirección rechazada por seguridad",
            headers,
            fp,
        )


def _open_request(request):
    opener = urllib.request.build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=20)


def _request_json(url, token):
    """GET a la API oficial sin incluir secretos en mensajes de error."""
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Configurar PINTEREST_ACCESS_TOKEN en el entorno")

    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise RuntimeError("URL interna de Pinterest API inválida") from exc

    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.pinterest.com"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
    ):
        raise RuntimeError("La auditoría solo puede llamar a https://api.pinterest.com")

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + token.strip(),
            "Accept": "application/json",
        },
    )
    try:
        with _open_request(request) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Pinterest API devolvió HTTP {exc.code}; revisar permisos/estado del token"
        ) from None
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"No se pudo conectar con Pinterest API: {exc.reason}"
        ) from None
    except (ValueError, TypeError, UnicodeError) as exc:
        raise RuntimeError("Pinterest API devolvió JSON inválido") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Pinterest API devolvió una respuesta no estructurada")
    return payload


def verify_account(token, expected_username=EXPECTED_USERNAME):
    """Confirma que el token pertenece exactamente a la cuenta esperada."""
    payload = _request_json(USER_ACCOUNT_URL, token)
    username = payload.get("username")
    if not isinstance(username, str) or not username.strip():
        raise RuntimeError(
            "Pinterest API no devolvió username; no se puede confirmar identidad"
        )
    active = username.strip().lstrip("@").casefold()
    expected = expected_username.strip().lstrip("@").casefold()
    if active != expected:
        raise RuntimeError(
            f"Cuenta Pinterest activa @{active}; se esperaba @{expected}. "
            "Auditoría cancelada."
        )
    return payload


def audit_pin(pin):
    """Incidencias editoriales comprobables, sin inferir formato del pin."""
    issues = []
    title = pin.get("title")
    link = pin.get("link")
    board_id = pin.get("board_id")
    alt_text = pin.get("alt_text")

    if not isinstance(title, str) or not title.strip():
        issues.append("título ausente o inválido")
    elif INTERNAL_ID.search(title):
        issues.append("ID interno visible en título")

    if not isinstance(link, str) or not link.strip():
        issues.append(
            "sin enlace de destino: revisar si este pin necesita CTA editorial"
        )
    else:
        try:
            parsed = urllib.parse.urlsplit(link.strip())
            port = parsed.port
            valid = (
                parsed.scheme == "https"
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
                and port is None
            )
        except (TypeError, ValueError):
            valid = False
            parsed = None
        if not valid:
            issues.append("enlace de destino no es HTTPS válido")
        elif (
            parsed.hostname.casefold() in HOME_HOSTS
            and parsed.path in ("", "/")
        ):
            issues.append("destino genérico a la home")

    board_value = (
        str(board_id).strip()
        if isinstance(board_id, (str, int)) and not isinstance(board_id, bool)
        else ""
    )
    if (
        not board_value
        or not board_value.isdecimal()
        or int(board_value) == 0
    ):
        issues.append("sin board_id válido en la respuesta API: verificar tablero")

    if not isinstance(alt_text, str) or not alt_text.strip():
        issues.append("ALT ausente o vacío: revisar accesibilidad del pin")
    return issues


def list_pins(
    token,
    max_pages=5,
    page_size=100,
    include_metrics=False,
    expected_username=EXPECTED_USERNAME,
):
    """Verifica identidad y lee todas las páginas hasta agotar bookmark."""
    if not 1 <= max_pages <= 30 or not 1 <= page_size <= 250:
        raise ValueError(
            "max_pages debe estar entre 1 y 30; page_size entre 1 y 250"
        )

    verify_account(token, expected_username=expected_username)

    cursor = None
    seen_cursors = set()
    seen_ids = set()

    for _page in range(max_pages):
        params = {
            "page_size": page_size,
            "include_protected_pins": "false",
        }
        if include_metrics:
            params["pin_metrics"] = "true"
        if cursor:
            params["bookmark"] = cursor
        url = PINS_URL + "?" + urllib.parse.urlencode(params)
        payload = _request_json(url, token)

        if not isinstance(payload.get("items"), list):
            raise RuntimeError(
                "La respuesta API no contiene lista 'items' válida"
            )

        for pin in payload["items"]:
            if not isinstance(pin, dict):
                raise RuntimeError(
                    "Pinterest API devolvió un pin no estructurado"
                )
            pin_id = pin.get("id")
            if (
                isinstance(pin_id, bool)
                or not isinstance(pin_id, (str, int))
                or not str(pin_id).strip()
            ):
                raise RuntimeError(
                    "Pinterest devolvió un pin sin identificador válido; "
                    "auditoría incompleta (no se puede deduplicar)"
                )
            pin_id = str(pin_id).strip()
            if pin_id in seen_ids:
                continue
            seen_ids.add(pin_id)
            yield pin

        next_cursor = payload.get("bookmark")
        if next_cursor in (None, ""):
            return
        if (
            not isinstance(next_cursor, str)
            or not next_cursor.strip()
            or next_cursor in seen_cursors
        ):
            raise RuntimeError(
                "Bookmark inválido o repetido; se detiene paginación"
            )
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    raise RuntimeError(
        f"Se alcanzó el tope de {max_pages} páginas con un bookmark pendiente: "
        "auditoría INCOMPLETA; ampliar --max-pages para cubrir todos los pines"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="auditar pines de ejemplo sin red",
    )
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="incluir métricas orgánicas disponibles por pin",
    )
    args = parser.parse_args()

    if args.demo:
        pins = [
            {
                "id": "123",
                "title": "IG-02-08 — Un libro",
                "link": "https://autorademodiaz.com/",
                "board_id": "9",
                "alt_text": "Portada y lectura del libro.",
            },
            {
                "id": "456",
                "title": "Una escena de lectura",
                "link": "https://autorademodiaz.com/cuaderno/",
                "board_id": "9",
                "alt_text": "Escena de lectura vinculada al cuaderno.",
            },
        ]
    else:
        # Reunir TODA la lectura antes de imprimir evita presentar una página
        # parcial como auditoría completa si falla una página posterior.
        pins = list(
            list_pins(
                os.environ.get("PINTEREST_ACCESS_TOKEN"),
                max_pages=args.max_pages,
                include_metrics=args.metrics,
            )
        )

    total, flagged = 0, 0
    for pin in pins:
        total += 1
        issues = audit_pin(pin)
        if args.metrics and not args.demo:
            metrics = pin.get("pin_metrics")
            if metrics is not None:
                print(
                    "   métricas API:",
                    json.dumps(metrics, ensure_ascii=False)[:500],
                )
        if issues:
            flagged += 1
            print(
                f"[REVISAR] pin={pin.get('id')} | "
                + "; ".join(issues)
            )
        else:
            print(f"[OK] pin={pin.get('id')}")

    print(
        f"Auditados {total} pines publicados; "
        f"{flagged} con incidencias."
    )


if __name__ == "__main__":
    main()

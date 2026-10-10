"""Preflight OFFLINE para preparar pines que después se publican manualmente.

No abre Pinterest, no usa Metricool, no programa ni publica nada.

Formato:
[
  {
    "kind": "manual_pin",
    "text": "descripción del pin",
    "media": ["ruta-o-referencia-de-la-imagen"],
    "media_alt_text": ["descripción accesible"],
    "board_name": "Nombre visible del tablero",
    "pin_title": "Título editorial",
    "pin_link": "https://davidportodiaz.com/ruta-especifica/",
    "motivo": "opcional"
  }
]

Uso:
    python tools/pinterest_execute.py plan.json

El nombre histórico del archivo se conserva por compatibilidad, pero su función
actual es SOLO validar/preparar. El usuario publica o programa manualmente en
Pinterest después de revisar el resultado.
"""
import json
import os
import re
import sys
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")

import check_duplicate_phrase as dup
from x_interact import _check_spanish_orthography


def _valid_https_destination(value):
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and port is None
    )


def _validate(item):
    if not isinstance(item, dict):
        return ["cada elemento del plan debe ser un objeto JSON"]

    errors = []
    kind = item.get("kind")
    if kind == "schedule_pin":
        errors.append(
            "kind 'schedule_pin' está retirado: Metricool ya no se usa. "
            "Cambiar a 'manual_pin' y publicar/programar manualmente."
        )
    elif kind != "manual_pin":
        errors.append("kind debe ser 'manual_pin'")

    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        errors.append("text debe ser una descripción no vacía")
    else:
        try:
            _check_spanish_orthography(text)
        except ValueError as exc:
            errors.append(str(exc))
        hits = dup.check(text)
        if hits:
            errors.append(f"solape de texto detectado: {hits[0]}")

    media = item.get("media")
    if not isinstance(media, list) or not media:
        errors.append("media debe ser una lista no vacía")
    elif any(not isinstance(m, str) or not m.strip() for m in media):
        errors.append("cada elemento de media debe ser una referencia no vacía")

    alt = item.get("media_alt_text")
    if not isinstance(alt, list) or not alt:
        errors.append(
            "media_alt_text debe ser una lista no vacía de descripciones"
        )
    elif any(not isinstance(a, str) or not a.strip() for a in alt):
        errors.append(
            "cada media_alt_text debe ser una descripción no vacía"
        )
    elif isinstance(media, list) and len(alt) != len(media):
        errors.append(
            "media_alt_text debe tener tantas entradas como media"
        )

    board = item.get("board_name")
    if not isinstance(board, str) or not board.strip():
        errors.append(
            "board_name debe ser el nombre visible del tablero elegido manualmente"
        )

    title = item.get("pin_title")
    if not isinstance(title, str) or not title.strip():
        errors.append("pin_title debe ser un título editorial no vacío")
    elif re.search(r"\b[A-Z]{2,4}-\d{2}-\d{2}\b", title):
        errors.append(f"pin_title contiene un ID interno: {title!r}")

    link = item.get("pin_link")
    link = link.strip() if isinstance(link, str) else ""
    if not _valid_https_destination(link):
        errors.append(
            "pin_link debe ser una URL HTTPS válida, sin credenciales ni puerto"
        )
    else:
        parsed = urlsplit(link)
        if (
            parsed.hostname.casefold()
            in {"davidportodiaz.com", "www.davidportodiaz.com"}
            and parsed.path in ("", "/")
        ):
            errors.append(
                "pin_link genérico a la home, incluso con parámetros"
            )

    # Limites reales de Pinterest (API v5 / interfaz): titulo 100, descripcion 800, ALT 500.
    if isinstance(title, str) and len(title.strip()) > PIN_TITLE_MAX:
        errors.append(f"pin_title de {len(title.strip())} caracteres (max {PIN_TITLE_MAX})")
    if isinstance(text, str) and len(text.strip()) > PIN_DESCRIPTION_MAX:
        errors.append(f"text de {len(text.strip())} caracteres (max {PIN_DESCRIPTION_MAX})")
    if isinstance(alt, list) and any(isinstance(a, str) and len(a.strip()) > PIN_ALT_MAX for a in alt):
        errors.append(f"media_alt_text supera {PIN_ALT_MAX} caracteres")

    return errors


# Pinterest es un buscador visual, no una red social de conversacion (03/10): el
# alcance viene de que titulo, descripcion y tablero coincidan con lo que la gente
# busca, no de comentar/seguir (la API v5 ni siquiera ofrece comentarios). Estos
# avisos no bloquean; guian la redaccion.
PIN_TITLE_MAX = 100
PIN_DESCRIPTION_MAX = 800
PIN_ALT_MAX = 500
SEO_TERMS = ("libro", "libros", "lectura", "leer", "novela", "fantasía", "fantasia", "escribir",
             "escritura", "escritor", "literatura", "relato", "poesía", "poesia", "guía", "guia",
             "club de lectura", "clásico", "clasico", "biblioteca", "librería", "libreria")


def _seo_warnings(item):
    """Avisos de SEO de Pinterest para un pin ya valido (lista de strings)."""
    title = (item.get("pin_title") or "").strip()
    text = (item.get("text") or "").strip()
    board = (item.get("board_name") or "").strip()
    warnings = []
    folded = f"{title} {text}".casefold()
    if not any(term in folded for term in SEO_TERMS):
        warnings.append("ni el titulo ni la descripcion incluyen un termino de busqueda del nicho (libro, lectura, fantasia...)")
    if not any(term in title.casefold() for term in SEO_TERMS):
        warnings.append("el titulo no lleva la palabra clave: es lo que mas pesa en la busqueda")
    if len(text) < 100:
        warnings.append(f"descripcion de {len(text)} caracteres: 150-400 con la frase de busqueda en la primera linea rinde mas")
    if text.count("#") > 3:
        warnings.append("mas de 3 hashtags: Pinterest los trata como relleno")
    if title and title == title.upper() and len(title) > 8:
        warnings.append("titulo en mayusculas")
    if len(board.split()) < 2:
        warnings.append("el nombre del tablero deberia ser una frase buscable (p. ej. 'Libros de fantasia en espanol'), no una palabra")
    return warnings


def run_plan(plan):
    """Valida localmente. Nunca ejecuta una acción remota."""
    if not isinstance(plan, list):
        raise ValueError("El plan Pinterest debe ser una lista JSON")

    results = []
    for item in plan:
        if not isinstance(item, dict):
            results.append(
                {
                    "kind": "desconocido",
                    "resultado": "invalido:cada elemento debe ser objeto JSON",
                }
            )
            continue

        errors = _validate(item)
        if errors:
            results.append(
                {
                    **item,
                    "resultado": f"invalido:{'; '.join(errors)}",
                }
            )
        else:
            results.append(
                {
                    **item,
                    "resultado": "listo_para_publicacion_manual",
                    "avisos_seo": _seo_warnings(item),
                }
            )
    return results


def _print_manual_checklist(item):
    print(f"- Título: {item.get('pin_title', '')}")
    print(f"- Tablero: {item.get('board_name', '')}")
    print(f"- Destino: {item.get('pin_link', '')}")
    print(f"- Media: {len(item.get('media', []))}")
    print("- Revisar visual y ALT en la interfaz antes de publicar/programar.")
    print("- Confirmar fecha/hora directamente en Pinterest si se programa.")
    for warning in item.get("avisos_seo", []):
        print(f"- AVISO SEO: {warning}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)

    with open(sys.argv[1], encoding="utf-8") as stream:
        plan = json.load(stream)

    results = run_plan(plan)
    invalid = False
    print("\n=== PREFLIGHT PINTEREST — SIN PUBLICAR ===")
    for result in results:
        print(f"\n{result['resultado']}")
        if result["resultado"] == "listo_para_publicacion_manual":
            _print_manual_checklist(result)
        else:
            invalid = True

    print(
        "\nNo se ha abierto Pinterest, no se ha programado ni publicado nada."
    )
    raise SystemExit(2 if invalid else 0)

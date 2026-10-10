"""Bloqueo de imagen, multimedia y fuentes solo en la página propia (PR #58).

No registrar rutas en BrowserContext de una sesión CDP compartida: interferiría
con pestañas de terceros. El modo ligero se desactiva con RRSS_LEAN_BROWSER=0.
Pinterest conserva su navegación con imágenes, fuera de esta utilidad.
"""
from __future__ import annotations

import os
import weakref

BLOCKED = ("image", "media", "font")
_DONE = weakref.WeakSet()


def enabled():
    return os.environ.get("RRSS_LEAN_BROWSER", "1") != "0"


def apply(page):
    """Instala interceptación exclusivamente por Page; ignora BrowserContext."""
    if not enabled() or page is None or not hasattr(page, "url"):
        return False
    try:
        if page in _DONE:
            return True
    except TypeError:
        pass  # No cachear objetos fake no weakrefables.

    def handler(route):
        try:
            if route.request.resource_type in BLOCKED:
                route.abort()
            else:
                route.continue_()
        except Exception:
            pass

    try:
        page.route("**/*", handler)
    except Exception:
        return False
    try:
        _DONE.add(page)
    except TypeError:
        pass
    return True

<<<<<<< HEAD
"""Navegador «ligero» (07/10/2026): sin imagenes, videos ni fuentes.

El PC tiene la RAM casi llena y las paginas de X/Threads/Facebook tardaban 20-50 s en cargar (videos que se reproducen solos, miles de imagenes): rondas enteras perdidas por timeouts. Las
automatizaciones leen TEXTO y pulsan botones; no necesitan ver imagenes ni reproducir video. `apply(contexto)` aborta esas peticiones en el contexto CDP de ESTA conexion de Playwright (no
cambia el Edge de David ni su perfil). Se desactiva con RRSS_LEAN_BROWSER=0. No se usa en Pinterest (sus rejillas dependen de las imagenes).
=======
"""Bloqueo de imagen, multimedia y fuentes solo en la página propia (PR #58).

No registrar rutas en BrowserContext de una sesión CDP compartida: interferiría
con pestañas de terceros. El modo ligero se desactiva con RRSS_LEAN_BROWSER=0.
Pinterest conserva su navegación con imágenes, fuera de esta utilidad.
>>>>>>> origin/research/public-reuse-parent
"""
from __future__ import annotations

import os
<<<<<<< HEAD

BLOCKED = ("image", "media", "font")
_DONE = set()
=======
import weakref

BLOCKED = ("image", "media", "font")
_DONE = weakref.WeakSet()
>>>>>>> origin/research/public-reuse-parent


def enabled():
    return os.environ.get("RRSS_LEAN_BROWSER", "1") != "0"


<<<<<<< HEAD
def apply(context):
    """Instala el bloqueo en `context` una sola vez por conexion. Devuelve True si queda activo."""
    if not enabled() or context is None:
        return False
    key = id(context)
    if key in _DONE:
        return True
=======
def apply(page):
    """Instala interceptación exclusivamente por Page; ignora BrowserContext."""
    if not enabled() or page is None or not hasattr(page, "url"):
        return False
    try:
        if page in _DONE:
            return True
    except TypeError:
        pass  # No cachear objetos fake no weakrefables.
>>>>>>> origin/research/public-reuse-parent

    def handler(route):
        try:
            if route.request.resource_type in BLOCKED:
                route.abort()
            else:
                route.continue_()
        except Exception:
            pass

    try:
<<<<<<< HEAD
        context.route("**/*", handler)
    except Exception:
        return False
    _DONE.add(key)
=======
        page.route("**/*", handler)
    except Exception:
        return False
    try:
        _DONE.add(page)
    except TypeError:
        pass
>>>>>>> origin/research/public-reuse-parent
    return True

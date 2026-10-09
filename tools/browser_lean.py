"""Navegador «ligero» (07/10/2026): sin imagenes, videos ni fuentes.

El PC tiene la RAM casi llena y las paginas de X/Threads/Facebook tardaban 20-50 s en cargar (videos que se reproducen solos, miles de imagenes): rondas enteras perdidas por timeouts. Las
automatizaciones leen TEXTO y pulsan botones; no necesitan ver imagenes ni reproducir video. `apply(contexto)` aborta esas peticiones en el contexto CDP de ESTA conexion de Playwright (no
cambia el Edge de David ni su perfil). Se desactiva con RRSS_LEAN_BROWSER=0. No se usa en Pinterest (sus rejillas dependen de las imagenes).
"""
from __future__ import annotations

import os

BLOCKED = ("image", "media", "font")
_DONE = set()


def enabled():
    return os.environ.get("RRSS_LEAN_BROWSER", "1") != "0"


def apply(context):
    """Instala el bloqueo en `context` una sola vez por conexion. Devuelve True si queda activo."""
    if not enabled() or context is None:
        return False
    key = id(context)
    if key in _DONE:
        return True

    def handler(route):
        try:
            if route.request.resource_type in BLOCKED:
                route.abort()
            else:
                route.continue_()
        except Exception:
            pass

    try:
        context.route("**/*", handler)
    except Exception:
        return False
    _DONE.add(key)
    return True

<<<<<<< HEAD
"""Libera memoria del Edge 9223 entre rondas (07/10/2026): con la RAM casi llena (577 MB libres de 16 GB: Chrome 3 GB, VS Code 2 GB, Edge 3,4 GB) las cargas pasaban de 20-30 s y
rondas enteras de X, Threads y Pinterest caian por timeout. Cada herramienta abre su pestana; aqui las pestanas de paginas ya usadas vuelven a `about:blank` (el login vive en las
cookies del perfil, no en la pestana) y se cierran las sobrantes, dejando una sola.

    python tools/edge_trim.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def trim(log=print):
    import action_ledger
    from playwright.sync_api import sync_playwright
    with action_ledger.browser_session(wait_minutes=10):
        p = sync_playwright().start()
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9223", timeout=30000)
            pages = [pg for ctx in browser.contexts for pg in ctx.pages]
            for index, pg in enumerate(pages):
                try:
                    if index == 0:
                        pg.goto("about:blank", timeout=10000)
                    else:
                        pg.close()
                except Exception:
                    pass
            log(f"[edge] {len(pages)} pestanas -> 1 en blanco")
        finally:
            p.stop()
=======
"""Mantenimiento CDP conservador (PR #58).

Antes cerraba todas las pestañas del navegador salvo la primera, que navegaba
a about:blank. La URL o posición no acredita propiedad. No se cierra ninguna
pestaña sin un token de propiedad verificable entre procesos.
"""


def trim(log=print):
    """No destructivo: sin CDP, sin Edge, sin modificación de URLs."""
    log("[edge] trim conservador: 0 pestañas modificadas; propiedad desconocida")
    return 0
>>>>>>> origin/research/public-reuse-parent


if __name__ == "__main__":
    trim()

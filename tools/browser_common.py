"""Piezas comunes de las redes que se manejan por NAVEGADOR (Edge con CDP 9223): vigilante de cuelgues y conexion compartida (06/10/2026).

Antes `threads_interact.py` tenia su propia copia (vigilante + sesion compartida) y X abria un Playwright y una conexion CDP nuevos en CADA like/follow. Aqui vive una sola:

  * `Watchdog`: si no hay actividad (`beat()`) en `limit` segundos el proceso termina (`os._exit(6)`), porque un `evaluate` de Playwright sobre un Edge colgado no tiene tiempo limite
    y dejaba el turno del navegador (y a las otras redes) parado minutos. El registro es accion a accion, asi que no se pierde nada.
  * `Browser`: `session()` abre UNA conexion CDP para todas las acciones de un plan y `connect()` devuelve esa misma pagina (o abre una suelta fuera de una sesion).
"""
import contextlib
import os
import threading
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


class Watchdog:
    def __init__(self, name):
        self.name = name
        self.last = time.time()
        self.started = False

    def beat(self):
        self.last = time.time()

    def start(self, limit=300, interval=15):
        if self.started or not limit:
            return
        self.started = True

        def loop():
            while True:
                time.sleep(interval)
                idle = time.time() - self.last
                if idle > limit:
                    print(f"VIGILANTE: {int(idle)} s sin actividad en el navegador (Edge colgado); se aborta el proceso para liberar el turno. "
                          "Receta: tools/cdp_resume_workers.py", flush=True)
                    os._exit(6)

        self.beat()
        threading.Thread(target=loop, daemon=True, name=f"{self.name}-watchdog").start()


class KeepOpen:
    """`p.stop()` de las funciones sueltas no hace nada cuando hay una sesion compartida abierta."""

    def stop(self):
        pass


class Browser:
    def __init__(self, name, cdp_url, hosts, watchdog=None):
        self.name, self.cdp_url, self.hosts = name, cdp_url, set(hosts)
        self.watchdog = watchdog or Watchdog(name)
        self.shared = None

    def _page(self, browser):
        ctx = browser.contexts[0]
        try:
            import browser_lean
            browser_lean.apply(ctx)         # 07/10: sin imagenes/video/fuentes (RAM casi llena: cargas de 20-50 s)
        except Exception:
            pass
        pages = [pg for pg in ctx.pages if urlsplit(pg.url).hostname in self.hosts]
        return pages[-1] if pages else ctx.new_page()

    def session(self):
        """`with browser.session() as pg:`: una sola conexion CDP; dentro, `connect()` devuelve esa pagina. Tiempos por defecto de 15 s (30 s navegando): ninguna llamada espera 30 s por defecto."""
        @contextlib.contextmanager
        def manager():
            p = sync_playwright().start()
            try:
                browser = p.chromium.connect_over_cdp(self.cdp_url)
                pg = self._page(browser)
                pg.set_default_timeout(15000)
                pg.set_default_navigation_timeout(30000)
                self.shared = pg
                self.watchdog.start()
                yield pg
            finally:
                self.shared = None
                p.stop()
        return manager()

    def connect(self):
        if self.shared is not None:
            return KeepOpen(), self.shared
        p = sync_playwright().start()
        browser = p.chromium.connect_over_cdp(self.cdp_url)
        return p, self._page(browser)

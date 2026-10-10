"""Piezas comunes de las redes que se manejan por NAVEGADOR (Edge con CDP 9223): vigilante de cuelgues y conexion compartida (06/10/2026).

Antes `threads_interact.py` tenia su propia copia (vigilante + sesion compartida) y X abria un Playwright y una conexion CDP nuevos en CADA like/follow. Aqui vive una sola:

  * `Watchdog`: si no hay actividad (`beat()`) en `limit` segundos el proceso termina (`os._exit(6)`), porque un `evaluate` de Playwright sobre un Edge colgado no tiene tiempo limite
    y dejaba el turno del navegador (y a las otras redes) parado minutos. El registro es accion a accion, asi que no se pierde nada.
  * `Browser`: `session()` abre UNA conexion CDP para todas las acciones de un plan y `connect()` devuelve esa misma pagina (o abre una suelta fuera de una sesion).
"""
import contextlib
<<<<<<< HEAD
import os
import threading
import time
from urllib.parse import urlsplit
=======
import inspect
import os
import threading
import time
>>>>>>> origin/research/public-reuse-parent

from playwright.sync_api import sync_playwright


class Watchdog:
    def __init__(self, name):
        self.name = name
<<<<<<< HEAD
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
=======
        self.last = time.monotonic()
        self.started = False
        self._cancel = None

    def beat(self):
        self.last = time.monotonic()

    def start(self, limit=300, interval=15):
        if not limit:
            return
        self.beat()
        if self.started:
            return
        stop = threading.Event()
        self._cancel = stop
        self.started = True

        def loop():
            while not stop.wait(interval):
                idle = time.monotonic() - self.last
                if idle > limit and not stop.is_set():
>>>>>>> origin/research/public-reuse-parent
                    print(f"VIGILANTE: {int(idle)} s sin actividad en el navegador (Edge colgado); se aborta el proceso para liberar el turno. "
                          "Receta: tools/cdp_resume_workers.py", flush=True)
                    os._exit(6)

<<<<<<< HEAD
        self.beat()
        threading.Thread(target=loop, daemon=True, name=f"{self.name}-watchdog").start()

=======
        threading.Thread(target=loop, daemon=True, name=f"{self.name}-watchdog").start()

    def stop(self):
        """No abortar el proceso cuando ya se liberó el turno CDP."""
        stop = self._cancel
        self._cancel = None
        self.started = False
        if stop is not None:
            stop.set()

>>>>>>> origin/research/public-reuse-parent

class KeepOpen:
    """`p.stop()` de las funciones sueltas no hace nada cuando hay una sesion compartida abierta."""

    def stop(self):
        pass


<<<<<<< HEAD
=======
def connect_cdp(chromium, endpoint, *, timeout=20000):
    """Evitar mutar el contexto CDP compartido en Playwright >=1.60.

    Se usa detección de firma, no un retry de conexión después de TypeError:
    una conexión CDP fallida puede haber tenido efectos y reintentar es inseguro.
    """
    kwargs = {"timeout": timeout}
    try:
        if "no_defaults" in inspect.signature(chromium.connect_over_cdp).parameters:
            kwargs["no_defaults"] = True
    except (TypeError, ValueError):
        pass
    return chromium.connect_over_cdp(endpoint, **kwargs)


class OwnedPlaywright:
    """Solo cerrar la página creada por esta conexión, nunca Browser ni BrowserContext."""

    def __init__(self, driver, page):
        self.driver, self.page, self.stopped = driver, page, False

    def stop(self):
        if self.stopped:
            return
        self.stopped = True
        try:
            try:
                self.page.close()
            except Exception:
                pass  # La pestaña pudo cerrarse o desconectarse antes.
        finally:
            self.driver.stop()


def new_owned_page(browser, *, lean=True):
    """El dominio/URL no demuestra propiedad. No reutilizar pestañas ajenas."""
    if not browser.contexts:
        raise RuntimeError("CDP sin contexto predeterminado: no cambiar de perfil")
    pg = browser.contexts[0].new_page()
    if lean:
        try:
            import browser_lean
            browser_lean.apply(pg)  # Ruta por página, no por contexto compartido.
        except Exception:
            pass
    return pg


>>>>>>> origin/research/public-reuse-parent
class Browser:
    def __init__(self, name, cdp_url, hosts, watchdog=None):
        self.name, self.cdp_url, self.hosts = name, cdp_url, set(hosts)
        self.watchdog = watchdog or Watchdog(name)
        self.shared = None

    def _page(self, browser):
<<<<<<< HEAD
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
=======
        return new_owned_page(browser)

    def session(self):
        """Una pestaña propia por sesión: 15 s acciones, 30 s navegación."""
        @contextlib.contextmanager
        def manager():
            if self.shared is not None:
                raise RuntimeError("sesión CDP ya abierta en este adaptador")
            p = sync_playwright().start()
            pg = None
            try:
                browser = connect_cdp(p.chromium, self.cdp_url)
>>>>>>> origin/research/public-reuse-parent
                pg = self._page(browser)
                pg.set_default_timeout(15000)
                pg.set_default_navigation_timeout(30000)
                self.shared = pg
                self.watchdog.start()
                yield pg
            finally:
                self.shared = None
<<<<<<< HEAD
                p.stop()
=======
                try:
                    if pg is not None:
                        pg.close()
                except Exception:
                    pass
                finally:
                    try:
                        self.watchdog.stop()
                    finally:
                        p.stop()
>>>>>>> origin/research/public-reuse-parent
        return manager()

    def connect(self):
        if self.shared is not None:
<<<<<<< HEAD
            return KeepOpen(), self.shared
        p = sync_playwright().start()
        browser = p.chromium.connect_over_cdp(self.cdp_url)
        return p, self._page(browser)
=======
            if getattr(self.shared, "is_closed", lambda: False)():
                raise RuntimeError("pestaña CDP cerrada: no reintentar acciones")
            return KeepOpen(), self.shared
        p = sync_playwright().start()
        try:
            browser = connect_cdp(p.chromium, self.cdp_url)
            pg = self._page(browser)
            return OwnedPlaywright(p, pg), pg
        except Exception:
            p.stop()
            raise
>>>>>>> origin/research/public-reuse-parent

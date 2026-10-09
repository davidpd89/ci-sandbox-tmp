"""Autoauditoria de Threads (05/10/2026). Desde el 06/10 la logica vive en `browser_self_audit.py` (comun a las redes por navegador: Threads y X); aqui solo la configuracion de Threads.

    python tools/threads_self_audit.py [--decide]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import browser_self_audit as bsa

NETWORK = "threads"
ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_THREADS")
CONFIG = bsa.Config(NETWORK, "Threads", ROOT, "threads_pool",
                    supply_hint="ampliar fuentes del scan (busquedas, comunidad Book Threads, temas) o revisar los filtros de idioma/nicho en threads_pool.pick",
                    reply_hint="Meta indica que las replies son casi la mitad de las visualizaciones: pase editorial diario de 10-25 replies (cola de replies de Threads)")


def gaps(m):
    return bsa.gaps(m, CONFIG)


def collect(today=None):
    return bsa.collect(CONFIG, today)


def main(argv=None):
    return bsa.main(CONFIG, argv)


if __name__ == "__main__":
    raise SystemExit(main())

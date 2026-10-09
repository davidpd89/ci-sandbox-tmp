"""Autoauditoria de X (06/10/2026): gemela de la de Threads (`browser_self_audit.py`). Vigila oferta (reserva de posts y cuentas), fiabilidad (likes no confirmados, objetivos que
ya no existen), avisos de la interfaz (cortacircuitos) y crecimiento; `--decide` mueve la rampa de X (`volume_ramp.X_STAGES`) por salud: sube tras un dia sano, baja ante cualquier aviso.

    python tools/x_self_audit.py [--decide]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import browser_self_audit as bsa

NETWORK = "x"
ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_X")
CONFIG = bsa.Config(NETWORK, "X", ROOT, "x_pool",
                    supply_hint="ampliar fuentes del scan (busquedas Recientes/Destacados, pestana Personas, seguidores de semillas) o revisar los filtros de idioma/nicho en x_pool.pick",
                    reply_hint="replies editoriales a quien ya conversa con nosotros (notificaciones) y a posts que piden recomendacion; X premia la conversacion")


def gaps(m):
    return bsa.gaps(m, CONFIG)


def collect(today=None):
    return bsa.collect(CONFIG, today)


def main(argv=None):
    return bsa.main(CONFIG, argv)


if __name__ == "__main__":
    raise SystemExit(main())

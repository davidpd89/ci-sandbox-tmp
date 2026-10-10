"""Mantenimiento CDP conservador (PR #58).

Antes cerraba todas las pestañas del navegador salvo la primera, que navegaba
a about:blank. La URL o posición no acredita propiedad. No se cierra ninguna
pestaña sin un token de propiedad verificable entre procesos.
"""


def trim(log=print):
    """No destructivo: sin CDP, sin Edge, sin modificación de URLs."""
    log("[edge] trim conservador: 0 pestañas modificadas; propiedad desconocida")
    return 0


if __name__ == "__main__":
    trim()

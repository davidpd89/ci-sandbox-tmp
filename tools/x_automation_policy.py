"""Regla transversal de X: no crear likes mediante automatización.

Reglas oficiales X (consulta 09/10/2026):
https://help.x.com/en/rules-and-policies/x-automation
https://docs.x.com/developer-guidelines

No hay override de entorno: cambiar la política requiere revisar permisos y
los términos, no basta con modificar un valor en Scheduler.
"""
x_likes_automaticos = False
AUTOMATIC_LIKE_KINDS = frozenset(("like", "like_latest"))


def is_automatic_like(item):
    return isinstance(item, dict) and item.get("kind") in AUTOMATIC_LIKE_KINDS


def without_automatic_likes(plan):
    """No modificar la entrada; permitir el resto de acciones intactas."""
    return [item for item in plan if not is_automatic_like(item)]

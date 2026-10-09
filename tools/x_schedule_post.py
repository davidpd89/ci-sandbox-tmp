"""Programador automático de X retirado.

Desde el 28/09/2026 la publicación/programación propia en X es manual/nativa.
El nombre del módulo se conserva por compatibilidad histórica, pero no abre CDP,
no escribe en el compositor y no programa posts.
"""

_MESSAGE = (
    "Publicación propia automatizada en X desactivada. "
    "Usar publicación/programación manual y nativa."
)


class OwnPublicationDisabled(RuntimeError):
    pass


def schedule_post(text, media_path, year, month, day, hour, minute):
    raise OwnPublicationDisabled(_MESSAGE)


if __name__ == "__main__":
    raise OwnPublicationDisabled(_MESSAGE)

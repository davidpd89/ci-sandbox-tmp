"""Lote histórico de programación X retirado.

El antiguo lote de julio dependía de tools/x_schedule_post.py. La publicación propia
automatizada ya no es una vía operativa y este archivo falla antes de leer media,
re-encodar vídeos, abrir navegador o programar nada.
"""

_MESSAGE = (
    "Lote automático de X retirado. "
    "Usar publicación/programación manual y nativa."
)


class OwnPublicationDisabled(RuntimeError):
    pass


def main():
    raise OwnPublicationDisabled(_MESSAGE)


if __name__ == "__main__":
    main()

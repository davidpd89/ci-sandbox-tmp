"""Interruptor de RESPUESTAS automaticas (07/10/2026, David): mientras exista `00_OPERATIVO/respuestas_en_revision.flag` no se publica ningun comentario/respuesta automatico en ninguna red
(X, Threads, Facebook, TikTok, Reddit): los comentarios del plan pasan a «me gusta» y las demas acciones (follows, likes, guardados) siguen igual. Se quita el fichero cuando David aprueba la
calidad de las respuestas (ver `00_OPERATIVO/_pruebas_respuestas/`)."""
import os

FLAG = os.path.join(os.path.dirname(__file__), "..", "00_OPERATIVO", "respuestas_en_revision.flag")


def held():
    return os.path.exists(FLAG)

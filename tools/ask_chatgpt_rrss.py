"""Interfaz legacy: delega en chatgpt_consult, sin tocar pestañas ajenas.

Mantiene `ask(query, timeout_s)` para los consumidores antiguos. La consulta
nueva se efectúa en pestaña propia y turno CDP dedicado si está disponible.
"""
import math
import sys


def ask(query, timeout_s=240):
    from chatgpt_consult import consult
    if not isinstance(timeout_s, (int, float)) or not math.isfinite(timeout_s):
        raise ValueError("timeout_s debe ser un número finito")
    if timeout_s <= 0:
        raise ValueError("timeout_s debe ser positivo")
    answer, _url = consult(query, wait_min=max(1, math.ceil(timeout_s / 60)))
    return answer


if __name__ == "__main__":
    print(ask(sys.argv[1] if len(sys.argv) > 1 else "hola"))

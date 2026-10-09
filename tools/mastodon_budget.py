"""Cupo de peticiones de Mastodon compartido entre procesos (06/10/2026, David: «el 429 hay que organizarlo para que no pase»).

mastodon.social da 300 peticiones por 5 minutos POR CUENTA: lo gastan a la vez los scans, los ejecutores, el minero de la reserva y las herramientas sueltas (perfil, bloqueos,
limpiezas), cada uno en su propio proceso. Antes cada proceso solo conocia su ultima respuesta, y los scans bajaban hasta 5 peticiones restantes: el siguiente proceso en pedir recibia un 429.

Ahora cada respuesta publica la cuota REAL (cabeceras X-RateLimit-*) en un fichero comun y, antes de cada peticion, el proceso consulta ese fichero y espera al reinicio de la ventana si el
margen que le toca ya no esta disponible. El margen depende de la prioridad:

    scan      90   las lecturas masivas dejan siempre 90 peticiones para quien escribe
    normal    25   por defecto (ejecutores, consultas sueltas)
    priority   3   herramientas que no pueden fallar (perfil, bloqueos, limpiezas): usan lo que quede

Asi un scan nunca deja sin cupo a un ejecutor ni a una herramienta, y un 429 solo aparece si algo ajeno a nuestros procesos gasta el cupo.
"""
import datetime as dt
import json
import os
import time

PATH = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_MASTODON", "cache", "ratelimit.json")
RESERVES = {"scan": 90, "normal": 25, "priority": 3}
MAX_WAIT_SECONDS = 310


def _now():
    return dt.datetime.now(dt.timezone.utc)


def publish(remaining, limit, reset, path=None):
    """Guarda la cuota real de la ultima respuesta (si es de la misma ventana, conserva el menor `remaining`)."""
    if remaining is None or reset is None:
        return
    path = path or PATH
    try:
        current = read(path)
        if current and current["reset"] == reset and current["remaining"] is not None and current["remaining"] < remaining:
            remaining = current["remaining"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as stream:
            json.dump({"remaining": int(remaining), "limit": limit, "reset": reset.isoformat()}, stream)
        os.replace(tmp, path)
    except OSError:
        pass                      # el fichero compartido es una ayuda: sin el, cada proceso se rige por su propia ultima respuesta


def read(path=None):
    """{'remaining', 'limit', 'reset'} de la ventana compartida o None si no hay datos validos."""
    try:
        with open(path or PATH, encoding="utf-8") as stream:
            data = json.load(stream)
        return {"remaining": data.get("remaining"), "limit": data.get("limit"), "reset": dt.datetime.fromisoformat(data["reset"])}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def seconds_to_wait(priority, own=None, shared=None, now=None):
    """Segundos que hay que esperar antes de pedir (0 si hay margen). Se usa el estado mas pesimista de la ventana vigente (el propio o el compartido)."""
    now = now or _now()
    reserve = RESERVES.get(priority, RESERVES["normal"])
    waits = []
    for state in (own, shared):
        if not state or state.get("remaining") is None or state.get("reset") is None:
            continue
        left = (state["reset"] - now).total_seconds()
        if left > 0 and state["remaining"] <= reserve:
            waits.append(left)
    return min(max(waits), MAX_WAIT_SECONDS) + 2 if waits else 0.0


def wait_for_budget(priority, own=None, sleep=time.sleep, log=print, path=None, now=None):
    """Espera (si hace falta) a que la ventana se renueve. Devuelve los segundos esperados."""
    wait = seconds_to_wait(priority, own, read(path), now)
    if wait > 0:
        log(f"  [cupo Mastodon] margen de «{priority}» agotado: espero {wait:.0f} s a que se renueve la ventana")
        sleep(wait)
    return wait

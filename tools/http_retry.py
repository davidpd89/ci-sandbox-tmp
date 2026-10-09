"""Reintentos de GET ante fallos transitorios (03/10).

Una ronda programada sin supervision no puede morir por un 500 puntual de la API (visto el
03/10: `listRecords` devolvio un Internal Server Error y el `prepare` entero cayo en 5 s).
Solo se reintentan LECTURAS (idempotentes): 5xx, timeouts y cortes de conexion, con espera
creciente y algo de azar. Los 429 NO se reintentan aqui (los gestiona cada cliente con su
logica de cuota) y las escrituras nunca (podrian duplicar una accion).
"""
import random
import time

import requests

TRANSIENT_STATUS = {500, 502, 503, 504}
DEFAULT_DELAYS = (1.5, 4.0, 9.0)


def get_with_retry(url, *, get=None, delays=DEFAULT_DELAYS, sleeper=time.sleep, rng=random, **kwargs):
    """requests.get con hasta len(delays) reintentos. Devuelve la ultima respuesta; si hubo
    excepcion en todos los intentos, relanza la ultima."""
    get = get or requests.get
    last_exc = None
    for attempt in range(len(delays) + 1):
        try:
            response = get(url, **kwargs)
            if response.status_code not in TRANSIENT_STATUS or attempt == len(delays):
                return response
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt == len(delays):
                raise
        sleeper(delays[attempt] * rng.uniform(0.8, 1.3))
    raise last_exc  # inalcanzable salvo bucle vacio

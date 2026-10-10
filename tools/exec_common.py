"""Piezas COMUNES de los ejecutores de Bluesky, Mastodon y Threads (06/10/2026).

Cada ejecutor llevaba su copia de lo mismo (`_Results`, la pausa por etapa de la rampa) y las correcciones aparecian en una red y no en otra (el reintento ante un 5xx se
hizo primero en Mastodon). Aqui vive lo que no depende de la API de cada red; lo propio de una red (prefetch, interaccion, registro de columnas) sigue en su ejecutor.

* `ResultList`: lista que avisa a `on_result` en cada `append` (cada accion queda registrada al momento; un corte del proceso solo pierde la accion en curso).
* `network_pause`: pausa humana entre escrituras con el rango y las dudas de la etapa vigente de la rampa (`volume_ramp`).
* `follow_vet`: motivo de rechazo de un perfil de una red por navegador ANTES de seguirlo o darle like (cuenta enorme, politica/activismo/ligue, otro idioma). Threads y X.
* `with_retries`: ejecuta una accion y, ante un fallo TRANSITORIO (5xx, red), reintenta con espera creciente; los demas errores se propagan tal cual.
"""
import re
import time

import growth_policy as gp
import scan_common as sc
import text_common as tc



<<<<<<< HEAD
=======
class WriteOutcomeUnknown(RuntimeError):
    """El intento de escritura alcanzó la frontera POST sin ACK fiable.

    status_code solo se conoce si el servidor devolvió una respuesta HTTP;
    errores de red sin respuesta conservan status_code=None.
    """

    def __init__(self, message, *, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def uncertain_transport_error(exc):
    """Posible POST enviado sin ACK; SOLO usar desde la frontera de escritura.

    Requests documenta ConnectTimeout como seguro para reintentar: no es un
    ReadTimeout. Para el resto, una llamada sin respuesta puede haber escrito.
    """
    import requests
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return False
    return isinstance(exc, (
        TimeoutError, ConnectionError,
        requests.exceptions.Timeout, requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
        requests.exceptions.ContentDecodingError,
    ))


>>>>>>> origin/research/public-reuse-parent
def omit_previously_published_reply(text, check, *, network, index, log=print):
    """Política común: una reply ya publicada se omite, NO invalida el lote.

    `check` es el comparador de historial existente en el adaptador.
    No se capturan sus excepciones, ni se relajan errores de identidad, esquema,
    ortografía o límites. El log deliberadamente no expone textos de terceros.
    """
    if check(text):
        log(f"[{network}] OMITIDO_PREFLIGHT_DUPLICADO elemento={index}: "
            "texto ya publicado; continuar con las acciones validas")
        return True
    return False

<<<<<<< HEAD
=======
# Motivos cerrados, sin autores, textos, URLs ni identificadores de cuentas.
SAFE_PREFLIGHT_SKIP_REASONS = frozenset({
    "texto_publicado", "texto_repetido_lote", "objetivo_repetido_lote",
    "relacion_repetida_lote", "microtexto_publicado", "post_antiguo",
})
SAFE_PREFLIGHT_SKIP_OUTCOMES = {
    "texto_publicado": "saltado_preflight_texto_publicado",
    "texto_repetido_lote": "saltado_preflight_texto_repetido_lote",
    "objetivo_repetido_lote": "saltado_preflight_objetivo_repetido_lote",
    "relacion_repetida_lote": "saltado_preflight_relacion_repetida_lote",
    "microtexto_publicado": "saltado_preflight_microtexto_publicado",
    "post_antiguo": "saltado_preflight_post_antiguo",
}


# 09/10/2026: el tope de antigüedad vive en `post_age_policy` (comun a todas las redes); estos envoltorios sirven al preflight de Mastodon.
def post_too_old(kind, status_id, created_at=None, *, now=None):
    import post_age_policy
    allowed, _ = post_age_policy.check("mastodon", {"kind": kind, "status_id": status_id, "post_created_at": created_at}, now=now)
    return not allowed


def mastodon_post_age_days(status_id, created_at=None, *, now=None):
    import post_age_policy
    return post_age_policy.age_days("mastodon", {"status_id": status_id, "post_created_at": created_at}, now=now)


def is_safe_preflight_omit(result):
    """La lista cerrada evita aceptar otro resultado bajo un prefijo genérico."""
    return result in SAFE_PREFLIGHT_SKIP_OUTCOMES.values()


def record_preflight_skip(skipped, *, network, index, kind, reason, log=print):
    """Registra una omisión segura sin exponer contenido y sin confirmar acciones.

    `skipped` es opcional para preservar llamadas que solo quieren la lista
    de acciones válidas. Nunca omitir identidad o política.
    """
    if reason not in SAFE_PREFLIGHT_SKIP_REASONS:
        raise ValueError("motivo de omision preflight no permitido")
    if skipped is not None:
        skipped.append({"kind": kind, "resultado": SAFE_PREFLIGHT_SKIP_OUTCOMES[reason]})
    log(f"[{network}] OMITIDO_PREFLIGHT_DUPLICADO elemento={index} motivo={reason}")



class PreflightSkipBuffer:
    """Acumula omisiones sin emitir eventos antes de validar el lote entero.

    Si otra acción falla la validación, el buffer se descarta sin modificar
    `skipped` ni contaminar el informe de omisiones efectivas.
    """
    def __init__(self, network, skipped=None, log=print):
        self.network = network
        self.skipped = skipped
        self.log = log
        self.pending = []

    def add(self, index, kind, reason):
        if reason not in SAFE_PREFLIGHT_SKIP_REASONS:
            raise ValueError("motivo de omision preflight no permitido")
        self.pending.append((index, kind, reason))

    def commit(self):
        for index, kind, reason in self.pending:
            record_preflight_skip(self.skipped, network=self.network, index=index,
                                  kind=kind, reason=reason, log=self.log)
        self.pending.clear()


>>>>>>> origin/research/public-reuse-parent
TRANSIENT_HTTP = frozenset({500, 502, 503, 504})
DEFAULT_BACKOFF = (6, 20)


def follow_vet(info):
    """Motivo de rechazo de un perfil ANTES de seguirlo / darle like (None si vale). `info`: {followers, bio, name} del perfil abierto. Solo espanol (David 06/10)."""
    followers, bio = info.get("followers"), f"{info.get('name') or ''} {info.get('bio') or ''}".strip()
    if info.get("handle") and info.get("network"):          # 07/10: contadores observados para el ciclo de hubs de reciprocidad (reciprocity.py)
        try:
            import reciprocity
            reciprocity.observe(info["network"], info["handle"], followers, info.get("following"), bio)
        except Exception:
            pass
    if followers is not None and followers > gp.FOLLOW_MAX_FOLLOWERS:
        return f"cuenta enorme ({followers} seguidores)"
    if sc.is_political(bio) or sc.looks_activist(bio):
        return "biografia politica/activista/de ligue"
    if tc.looks_english(bio) and not tc.looks_spanish(bio):
        return "biografia en ingles"
    if tc.other_language(bio):
        return "biografia en otro idioma"
    return None


class ResultList(list):
    """Lista de resultados que llama a `on_result(item)` en cada `append`."""

    def __init__(self, on_result=None):
        super().__init__()
        self._on_result = on_result

    def append(self, item):
        super().append(item)
        if self._on_result:
            self._on_result(item)


def network_pause(network, a=None, b=None, default=None):
    """Pausa entre acciones. Sin `a`/`b` (o con el valor por defecto de la red, `default`) manda la etapa de la rampa de `network`; con un rango explicito, ese rango."""
    doubt, stall = 0.12, 0.03
    if a is None or b is None or (default is not None and (a, b) == tuple(default)):
        try:
            import volume_ramp
            a, b = volume_ramp.pause_range(network=network)
            doubt, stall = volume_ramp.pause_doubts(network=network)
        except Exception:
            a, b = (a, b) if a is not None and b is not None else (default or (1.5, 5.0))
    sc.human_pause(a, b, doubt=doubt, stall=stall)


def status_code_of(exc):
    """Codigo HTTP de una excepcion de cualquier red (`status_code`, `status` o `response.status_code`); None si no lo trae."""
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    if isinstance(value, int):
        return value
    match = re.search(r"fall[oó]\s*\((\d{3})\)", str(exc))       # los clientes de Bluesky lanzan RuntimeError("POST ... fallo (502): ...")
    return int(match.group(1)) if match else None


def with_retries(call, *, transient=TRANSIENT_HTTP, backoff=DEFAULT_BACKOFF, retry_on=(), sleep=time.sleep, log=print):
    """`call()` con reintentos ante 5xx (codigos de `transient`) o excepciones de `retry_on`. Devuelve el resultado o relanza el ultimo error."""
    for wait in (*backoff, None):
        try:
            return call()
        except Exception as exc:                      # noqa: BLE001 - se reclasifica: solo lo transitorio se reintenta
            retriable = status_code_of(exc) in transient or (retry_on and isinstance(exc, tuple(retry_on)))
            if wait is None or not retriable:
                raise
            log(f"  fallo transitorio ({type(exc).__name__}: {str(exc)[:80]}): reintento en {wait} s")
            sleep(wait)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# Metricas y ESTADO.md de cada ronda (06/10): las tres redes tenian su copia de las mismas dos funciones, que solo diferian en las etiquetas.
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
import csv
import datetime
import os


def _counts(results):
    counts = {}
    for r in results:
        if r.get("resultado") == "confirmado":
            counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    return counts


def append_metricas(path, results, metrics, *, keys=("followers", "following", "posts")):
    """Una fila en `metricas.csv`: fecha, las metricas de `keys` (lo que la red no mide se escribe «?»), y el resumen de la sesion."""
    resumen = ", ".join(f"{v} {k}" for k, v in _counts(results).items())
    with open(path, "a", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerow([datetime.date.today().isoformat(), *[metrics.get(key, "?") for key in keys],
                                     f"Sesion via pipeline scan->plan->execute: {resumen}."])


def update_estado(path, results, metrics, *, fields=(("Seguidores", "followers"), ("Siguiendo", "following"), ("Posts", "posts"))):
    """Reescribe en `ESTADO.md` las secciones «Última sesión» y «Métricas actuales»; `fields` = [(etiqueta, clave)] de las metricas que muestra la red."""
    import re
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as stream:
        content = stream.read()
    resumen = ", ".join(f"{v} {k}" for k, v in _counts(results).items()) or "sin acciones confirmadas"
    shown = " ".join(f"{label}: {metrics[key]}." for label, key in fields if key in metrics)
    content = re.sub(r"## Última sesión.*?(?=\n## |\Z)",
                     f"## Última sesión\n\n{datetime.date.today().isoformat()}. {resumen}. Detalle: `registro_interacciones.csv`.\n\n", content, count=1, flags=re.S)
    content = re.sub(r"## Métricas actuales.*?(?=\n## |\Z)", f"## Métricas actuales (de `metricas.csv`, última fila)\n\n{shown}\n\n", content, count=1, flags=re.S)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(content)

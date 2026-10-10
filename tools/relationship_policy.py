"""Regulador de RELACIONES, generico para todas las redes (07/10/2026, David).

Idea: mantener el numero de seguidos parecido al de seguidores y dar a cada cuenta lo que ella da. Una sola logica (aqui) y cada red solo pone sus botones:

  1. SEGUIR → ESPERAR → DEJAR DE SEGUIR. Quien no devuelve el follow en `GRACE_DAYS` (7) dias deja de ser seguido (`unfollow_cleanup.py`).
  2. SEGUNDA OPORTUNIDAD. Pasado `RETRY_COOLDOWN_DAYS` (21) la cuenta puede volver a salir en un scan y se le da otra oportunidad. Tras `MAX_ATTEMPTS` (3) intentos sin que nos siga
     de vuelta, la cuenta queda en LISTA NEGRA y los scans la ignoran para siempre. (Un unfollow por otra causa —idioma, bot, spam, bloqueo— es permanente desde el primer momento.)
  3. PROPORCION. SIN tope (decision de David 07/10): puede haber 3x seguidos en la semana de espera; a los 7 dias la limpieza vuelve a dejarlo en lo que devuelve. El tope existe (`ratio_cap` en
     `00_OPERATIVO/reciprocidad_politica.json`) pero esta desactivado.
  4. RECIPROCIDAD DE ACCIONES. Primer paso nuestro: hasta `FIRST_STEP_COMMENTS` (2) comentarios a una cuenta sin que ella haya hecho nada. Despues, un comentario nuestro por cada
     comentario suyo (`inbound_interacciones.csv`). Si nos sigue y nunca comenta, no se le comenta mas.

Todo se calcula del REGISTRO de cada red (`registro_interacciones.csv`) y del registro de entradas (`00_OPERATIVO/inbound_interacciones.csv`); nada se guarda aparte.

    python tools/relationship_policy.py report bluesky|mastodon|x|threads|reddit
"""
from __future__ import annotations

import csv
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import growth_policy as gp

ROOT = os.path.join(os.path.dirname(__file__), "..")
INBOUND = os.environ.get("RRSS_INBOUND_PATH") or os.path.join(ROOT, "00_OPERATIVO", "inbound_interacciones.csv")
GRACE_DAYS = gp.NONRECIPROCAL_DAYS  # fuente compartida con unfollow_cleanup
RETRY_COOLDOWN_DAYS = 21
MAX_ATTEMPTS = 3
RATIO_CAP = None          # 07/10 (David): SIN tope de proporcion; la limpieza de 7 dias purga el exceso cada dia. Se puede activar en reciprocidad_politica.json
FOLLOWING_FLOOR = 300
FIRST_STEP_COMMENTS = 2
COMMENT_KINDS = ("reply", "comment", "comentario", "comment_external", "respuesta")
OK_RESULTS = ("confirmado", "publicado")


def norm(handle):
    return str(handle or "").strip().lstrip("@").casefold()


def reason_is_reciprocity(notes):
    """True si el unfollow fue por no devolver el follow (recuperable); cualquier otra causa es permanente."""
    return "no devuelve" in (notes or "").casefold()


def _rows(registro):
    try:
        with open(registro, encoding="utf-8", newline="") as stream:
            yield from csv.DictReader(stream)
    except OSError:
        return


def _nonreciprocity_decisions(registro, today=None):
    """Unica proyección para discovery y ranking; no escribe SQLite ni CSV."""
    import json
    import pathlib
    import relationship_memory as rm

    # El CSV por red es la fuente del estado actual. Los registros sintéticos
    # sin carpeta de red usan una red neutral para el cálculo puro.
    parent = pathlib.Path(registro).parent.name.upper()
    network = parent.removeprefix("SISTEMA_DIARIO_").casefold()
    if network not in rm.NETWORKS:
        network = "x"

    options = {}
    try:
        with open(SETTINGS, encoding="utf-8") as stream:
            config = json.load(stream)
        options.update(config.get("memoria_reciprocidad") or {})
        network_settings = (config.get("redes") or {}).get(network) or {}
        options.update(network_settings.get("memoria_reciprocidad") or {})
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    # Nombres reconocidos; un fichero antiguo no cambia nada.
    allowed = rm.Policy.__dataclass_fields__
    options = {key: val for key, val in options.items() if key in allowed}
    policy = rm.Policy(initial_days=RETRY_COOLDOWN_DAYS,
                       max_failures=MAX_ATTEMPTS, **{
                           key: value for key, value in options.items()
                           if key not in {"initial_days", "max_failures"}})
    if "initial_days" in options or "max_failures" in options:
        policy = rm.Policy(**{**policy.__dict__,
                              **{k: v for k, v in options.items()
                                 if k in {"initial_days", "max_failures"}}})
    return rm.decisions_from_rows(_rows(registro), network,
                                  today=today, policy=policy)


def blocked_accounts(registro, today=None):
    """Cuentas excluidas de nuevos follows; se consulta en todos los scans."""
    return {account for account, state
            in _nonreciprocity_decisions(registro, today).items()
            if not state["allowed"]}


def blacklist(registro):
    """Cuentas con ciclos fallidos hasta agotar oportunidades configuradas."""
    return {account: state["failures"]
            for account, state in _nonreciprocity_decisions(registro).items()
            if state["status"] == "exhausted"}


def follow_memory_ranking(registro, today=None):
    """Deltas de prioridad para nuevos follows, incluso cuando ya vence el cooldown."""
    return {account: state["rank_delta"]
            for account, state in _nonreciprocity_decisions(registro, today).items()
            if state["allowed"] and state["rank_delta"] != 0}


SETTINGS = os.path.join(ROOT, "00_OPERATIVO", "reciprocidad_politica.json")


def settings(network=None):
    """Ajustes (ratio_cap, following_floor) con la excepcion por red de `00_OPERATIVO/reciprocidad_politica.json`; sin fichero, los valores por defecto."""
    import json
    cfg = {"ratio_cap": RATIO_CAP, "following_floor": FOLLOWING_FLOOR}
    try:
        data = json.load(open(SETTINGS, encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    cfg.update({k: v for k, v in data.items() if k in cfg})
    cfg.update({k: v for k, v in (data.get("redes", {}).get(network) or {}).items() if k in cfg})
    return cfg


def follow_allowance(followers, following, *, network=None, ratio_cap=None, floor=None):
    """Cuantos seguidos NUEVOS caben ahora: max(suelo, cap x seguidores) - seguidos. Sin contadores, sin tope (None)."""
    if followers is None or following is None:
        return None
    cfg = settings(network)
    ratio_cap = cfg["ratio_cap"] if ratio_cap is None else ratio_cap
    if not ratio_cap:
        return None
    floor = cfg["following_floor"] if floor is None else floor
    return max(0, int(max(floor, ratio_cap * followers)) - int(following))


def latest_counts(network):
    """(seguidores, siguiendo) de la ultima fila numerica de `metricas.csv` de la red, o (None, None)."""
    path = os.path.join(ROOT, f"SISTEMA_DIARIO_{network.upper()}", "metricas.csv")
    result = (None, None)
    for row in _rows(path):
        try:
            result = (int(row["seguidores"]), int(row["siguiendo"]))
        except (KeyError, ValueError, TypeError):
            continue
    return result


# ---- reciprocidad de acciones (comentarios) ----
def log_inbound(network, handle, kind, today=None, path=None):
    """Anota que `handle` hizo algo por nosotros (comment|like|repost|follow). Una fila por cuenta, tipo y dia."""
    path = path or INBOUND
    handle = norm(handle)
    if not handle or kind not in ("comment", "like", "repost", "follow"):
        return False
    today = (today or datetime.date.today()).isoformat()
    key = (today, network, handle, kind)
    cache = log_inbound.__dict__.setdefault("_seen", {})
    seen = cache.get(path)
    if seen is None:          # claves ya escritas en el fichero (no se duplican entre rondas ni procesos)
        seen = cache[path] = {(r.get("fecha"), r.get("red"), norm(r.get("handle")), r.get("tipo")) for r in _rows(path)}
    if key in seen:
        return False
    seen.add(key)
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as stream:
        w = csv.writer(stream)
        if new:
            w.writerow(["fecha", "red", "handle", "tipo"])
        w.writerow([today, network, handle, kind])
    return True


def inbound_counts(network, handle, path=None):
    out = {}
    for row in _rows(path or INBOUND):
        if row.get("red") == network and norm(row.get("handle")) == norm(handle):
            out[row["tipo"]] = out.get(row["tipo"], 0) + 1
    return out


def outbound_comments(registro, handle):
    n = 0
    for row in _rows(registro):
        if (row.get("tipo") or "").strip().casefold() in COMMENT_KINDS and row.get("resultado") in OK_RESULTS and norm(row.get("cuenta")) == norm(handle):
            n += 1
    return n


def _comment_allowed_counts(outbound, inbound_comments):
    """Norma única: dos primeros pasos y después uno por comentario recibido."""
    return outbound < FIRST_STEP_COMMENTS + inbound_comments


def comment_allowed(network, handle, registro, *, inbound_path=None):
    """Consulta directa de la política de comentarios para una cuenta."""
    out = outbound_comments(registro, handle)
    if out < FIRST_STEP_COMMENTS:
        return True  # no leer inbound cuando quedan comentarios iniciales
    return _comment_allowed_counts(
        out, inbound_counts(network, handle, inbound_path).get("comment", 0)
    )


def comment_filter(network, registro):
    """Cierra una funcion handle -> bool para los constructores de plan (cachea el registro entero una vez)."""
    outs = {}
    for row in _rows(registro):
        if (row.get("tipo") or "").strip().casefold() in COMMENT_KINDS and row.get("resultado") in OK_RESULTS:
            outs[norm(row.get("cuenta"))] = outs.get(norm(row.get("cuenta")), 0) + 1
    inbound = {}
    for row in _rows(INBOUND):
        if row.get("red") == network and row.get("tipo") == "comment":
            inbound[norm(row.get("handle"))] = inbound.get(norm(row.get("handle")), 0) + 1

    def allowed(handle):
        h = norm(handle)
        out = outs.get(h, 0)
        return _comment_allowed_counts(out, inbound.get(h, 0))
    return allowed


def report(network):
    folder = f"SISTEMA_DIARIO_{network.upper()}"
    registro = os.path.join(ROOT, folder, "registro_interacciones.csv")
    followers, following = latest_counts(network)
    today = datetime.date.today()
    black = blacklist(registro)
    print(f"[{network}] seguidores={followers} siguiendo={following} cupo de seguidos nuevos={follow_allowance(followers, following, network=network)}")
    print(f"[{network}] lista negra (>= {MAX_ATTEMPTS} intentos sin devolver): {len(black)}; bloqueadas por espera/permanentes: {len(blocked_accounts(registro, today))}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) == 2 and argv[0] == "report":
        report(argv[1])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

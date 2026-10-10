"""Cohortes D+1/D+3/D+7: observaciones confirmadas, no fechas inferidas.

Núcleo puro, sin I/O ni credenciales. D+N es el día natural de Europe/Madrid.
Una ausencia solo es negativa si el adaptador suministra una observación
explícita, completa y del propio día D+N. Una importación tardía no retrodata
la observación. Las exportaciones de eventos con fecha fiable pueden adaptarse
antes de llamar a este módulo; no convertir una primera captura en evento.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
NETWORKS = ("bluesky", "mastodon", "x", "threads", "facebook", "pinterest", "reddit", "tiktok")
DEADLINES = (1, 3, 7)
COVERAGE = ("complete", "partial", "unavailable")
BASELINE = ("not_follower", "preexisting", "unknown", "legacy_unverified")


def local_day(value):
    """Conserva fechas de calendario; normaliza datetimes conscientes a Madrid."""
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError("datetime sin zona horaria")
        return value.astimezone(TZ).date()
    if type(value) is date:
        return value
    raise TypeError("fecha debe ser date o datetime con zona")


def _not_after(left, right):
    """Orden por instante real cuando ambos valores conocen la hora."""
    if isinstance(left, datetime) and isinstance(right, datetime):
        local_day(left)
        local_day(right)
        return left.astimezone(timezone.utc) <= right.astimezone(timezone.utc)
    return local_day(left) <= local_day(right)


def _order_key(value, index):
    # En el cambio horario de otoño, 02:30 fold=1 es posterior a 02:45 fold=0.
    # Ordenar por hora de pared invertiría follow y unfollow.
    if isinstance(value, datetime):
        local_day(value)
        return (local_day(value), value.astimezone(timezone.utc), index)
    return (local_day(value), datetime.min.replace(tzinfo=timezone.utc), index)


@dataclass(frozen=True)
class FollowEvent:
    network: str
    subject_id: str                  # opaco y estable SI la red lo proporciona
    occurred_at: date | datetime
    source: str = "otros"
    kind: str = "follow"            # follow / unfollow
    confirmed: bool = True
    baseline: str = "unknown"       # no asumir que no era seguidor
    identity: str = "handle"        # conservador: stable solo con prueba de ID persistente
    event_id: Optional[str] = None


@dataclass(frozen=True)
class FollowerObservation:
    network: str
    subject_id: str
    captured_at: date | datetime    # fecha real de la foto, NO de descarga
    follows_back: Optional[bool]   # None = no observable
    coverage: str = "unavailable"
    received_at: date | datetime | None = None
    capability: str = "unavailable" # capacidad declarada por adaptador, no asumida
    permission: str = "unknown"     # origen/autorización verificados por adaptador
    method: str = "unknown"         # API/snapshot/export/etc.
    identity: str = "handle"


def _validate_event(event):
    if event.network not in NETWORKS or not isinstance(event.subject_id, str) or not event.subject_id.strip():
        raise ValueError("red o sujeto inválido")
    if event.kind not in ("follow", "unfollow") or event.baseline not in BASELINE:
        raise ValueError("tipo de evento o baseline inválidos")
    if event.identity not in ("stable", "handle"):
        raise ValueError("identidad inválida")
    if not isinstance(event.confirmed, bool) or not isinstance(event.source, str):
        raise TypeError("confirmed o source inválidos")
    return local_day(event.occurred_at)


def _validate_observation(obs):
    if obs.network not in NETWORKS or not isinstance(obs.subject_id, str) or not obs.subject_id.strip():
        raise ValueError("red o sujeto inválido")
    if obs.coverage not in COVERAGE or obs.identity not in ("stable", "handle"):
        raise ValueError("cobertura o identidad inválidas")
    if obs.follows_back is not None and type(obs.follows_back) is not bool:
        raise TypeError("follows_back debe ser bool o None")
    if obs.follows_back is not None and obs.capability == "unavailable":
        raise ValueError("evidencia presente con capacidad no disponible")
    captured = local_day(obs.captured_at)
    received = local_day(obs.received_at) if obs.received_at is not None else captured
    if not _not_after(obs.captured_at, obs.received_at or obs.captured_at):
        raise ValueError("recepción anterior a captura")
    return captured, received


def _empty():
    return {"eligible": 0, "converted": 0, "not_converted": 0,
            "unknown": 0, "censored": 0, "pending": 0,
            "legacy_unverified": 0, "weak_identity": 0, "rate": None,
            "lower_bound": None, "coverage": "unavailable"}


def _finalize(row):
    observed = row["converted"] + row["not_converted"]
    row["rate"] = (round(row["converted"] / observed, 3)
                   if observed and row["unknown"] == 0 and row["censored"] == 0
                   and not row["legacy_unverified"]
                   and not row["weak_identity"]
                   else None)
    row["lower_bound"] = (round(row["converted"] / (row["eligible"] + row["censored"]), 3)
                          if row["eligible"] and not row["legacy_unverified"]
                          and not row["weak_identity"] else None)
    row["coverage"] = ("unavailable" if row["eligible"] == 0 else
                       "complete" if row["unknown"] == 0 and row["censored"] == 0
                       and row["weak_identity"] == 0
                       and row["legacy_unverified"] == 0 else "partial")
    return row


def evaluate(events, observations, *, as_of, deadlines=DEADLINES):
    """Devuelve matriz de cohortes por red/hito/fuente, con desconocidos explícitos.

    Cada follow confirmado abre episodio. Duplicados sin unfollow no lo reabren;
    unfollow cierra y refollow inicia un episodio nuevo. Sin ID persistente no se
    fusionan dos handles distintos. not_converted significa sin positivo
    observado hasta el checkpoint completo, no ausencia histórica de follow.
    """
    end = local_day(as_of)
    if not deadlines or any(type(n) is not int or n <= 0 for n in deadlines):
        raise ValueError("deadlines inválidos")
    windows = tuple(dict.fromkeys(deadlines))
    ordered = []
    used_ids = {}
    for index, ev in enumerate(events):
        day = _validate_event(ev)
        if not _not_after(ev.occurred_at, as_of) or not ev.confirmed:
            continue
        key = (ev.network, ev.event_id) if ev.event_id else None
        if key is not None:
            signature = (ev.network, ev.subject_id, ev.occurred_at, ev.kind, ev.confirmed,
                         ev.source, ev.baseline, ev.identity)
            if key in used_ids:
                if used_ids[key] != signature:
                    raise ValueError("event_id reutilizado para eventos incompatibles")
                continue
            used_ids[key] = signature
        ordered.append((_order_key(ev.occurred_at, index), index, ev))
    ordered.sort(key=lambda x: x[0])

    episodes = []
    active = {}
    for _, _, ev in ordered:
        day = local_day(ev.occurred_at)
        key = ev.network, ev.subject_id, ev.identity
        if ev.kind == "unfollow":
            if key in active:
                old = active.pop(key)
                old["closed"] = day
                old["closed_at"] = ev.occurred_at
        elif key not in active:
            ep = {"event": ev, "day": day, "closed": None, "closed_at": None}
            episodes.append(ep)
            active[key] = ep

    obs_by_subject = {}
    for obs in observations:
        captured, received = _validate_observation(obs)
        if not _not_after(obs.received_at or obs.captured_at, as_of) or not _not_after(obs.captured_at, as_of):
            continue
        key = obs.network, obs.subject_id, obs.identity
        obs_by_subject.setdefault(key, []).append((captured, obs))
    for items in obs_by_subject.values():
        items.sort(key=lambda item: item[0])

    result = {network: {f"D+{n}": {} for n in windows} for network in NETWORKS}
    for ep in episodes:
        ev, start, closed = ep["event"], ep["day"], ep["closed"]
        if ev.baseline == "preexisting":
            continue
        observations_for = obs_by_subject.get((ev.network, ev.subject_id, ev.identity), ())
        for n in windows:
            row = result[ev.network][f"D+{n}"].setdefault(ev.source, _empty())
            deadline = start + timedelta(days=n)
            if deadline > end:
                row["pending"] += 1
                continue
            if ev.baseline == "unknown":
                row["unknown"] += 1  # baseline desconocida: nunca al denominador
                continue
            snapshots = [item for item in observations_for
                         if start <= item[0] <= deadline
                         and _not_after(ev.occurred_at, item[1].captured_at)
                         and (closed is None or _not_after(item[1].captured_at, ep["closed_at"]))]
            positive = any(o.follows_back is True and o.coverage != "unavailable" and o.permission != "denied"
                           for _, o in snapshots)
            # El primer positivo observado no desaparece al hacer unfollow después.
            # Si no hubo positivo y cerramos antes de D+N, el caso sí se censura.
            if not positive and closed is not None and closed < deadline:
                row["censored"] += 1
                continue
            row["eligible"] += 1
            row["legacy_unverified"] += int(ev.baseline == "legacy_unverified")
            row["weak_identity"] += int(ev.identity == "handle")
            if positive:
                row["converted"] += 1
            elif any(day == deadline and o.follows_back is False
                     and o.coverage == "complete" and o.permission != "denied"
                     for day, o in snapshots):
                row["not_converted"] += 1
            else:
                row["unknown"] += 1

    return {"schema_version": 2, "timezone": "Europe/Madrid",
            "definition": "first_observed_positive_by_local_D+N",
            "networks": {net: {window: {source: _finalize(row)
                                          for source, row in sources.items()}
                               for window, sources in periods.items()}
                         for net, periods in result.items()}}


def legacy_projection(result, network):
    """Salida antigua de #33. Los desconocidos figuran como cero SOLO en este legado."""
    output = {}
    for window, sources in result["networks"][network].items():
        items = {}
        for source, entry in sources.items():
            count = entry["eligible"]
            if count:
                back = entry["converted"]
                items[source] = {"followed": count, "back": back,
                                 "rate": round(back / count, 3)}
        output[window] = dict(sorted(items.items(),
                                     key=lambda pair: (-pair[1]["rate"],
                                                       -pair[1]["followed"], pair[0])))
    return output

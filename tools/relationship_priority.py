"""Priorizador diario de relaciones, puramente offline y sin acciones sociales.

Entrada: snapshots JSON canonicos, con elegibilidad comprobada por los adaptadores.
Salida: recomendaciones explicables, separadas en WEB/API/MOBILE. No abre redes,
ni consulta estado, ni genera respuestas o planes ejecutables.
Python 3.11+, solo biblioteca estandar.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
from collections import Counter
from pathlib import Path

NETWORKS = frozenset(("x", "threads", "facebook", "pinterest", "reddit",
                      "bluesky", "mastodon", "tiktok", "instagram"))
LANES = ("WEB", "API", "MOBILE")
ACTIONS = ("reply", "follow", "reactivate", "visit")
KINDS = ("comment", "repost", "follow", "like")
HANDLE_RE = re.compile(r"^[\w@.:-]{1,120}$", re.UNICODE)
VERSION = "relationship-priority/v1"


def _number(value, field, *, minimum=0.0, maximum=1.0):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{field}: numero obligatorio")
    # Comprobar el rango ANTES de convertir: int de JSON arbitrariamente grande
    # puede lanzar OverflowError en float(...) y abortar todas las candidaturas.
    if not minimum <= value <= maximum:
        raise ValueError(f"{field}: fuera de rango")
    n = float(value)
    if not math.isfinite(n):
        raise ValueError(f"{field}: fuera de rango")
    return n


def _count(value, field):
    return int(_number(value, field, minimum=0, maximum=1_000_000)) if (
        not isinstance(value, float) or value.is_integer()
    ) else (_ for _ in ()).throw(ValueError(f"{field}: entero obligatorio"))


def _date(value, field, today, *, required=False):
    if value is None or value == "":
        if required:
            raise ValueError(f"{field}: fecha requerida")
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError(f"{field}: fecha ISO YYYY-MM-DD requerida")
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field}: fecha ISO YYYY-MM-DD") from exc
    if parsed > today:
        raise ValueError(f"{field}: fecha futura")
    return parsed


def _flag(row, name):
    value = row.get(name, False)
    if not isinstance(value, bool):
        raise ValueError(f"{name}: booleano obligatorio")
    return value


def _normalize(row, today):
    if not isinstance(row, dict):
        raise ValueError("candidato debe ser objeto")
    network = row.get("network")
    lane = row.get("lane")
    handle = row.get("handle")
    if (not isinstance(network, str) or network not in NETWORKS
            or not isinstance(lane, str) or lane not in LANES):
        raise ValueError("network o lane no reconocida")
    if not isinstance(handle, str) or not HANDLE_RE.fullmatch(handle):
        raise ValueError("handle invalido")
    actor_id = row.get("actor_id")
    if actor_id is not None and (not isinstance(actor_id, str) or not actor_id.strip()
                                 or len(actor_id) > 200):
        raise ValueError("actor_id invalido")
    incoming = row.get("inbound", {})
    if not isinstance(incoming, dict) or set(incoming) - set(KINDS):
        raise ValueError("inbound: tipos desconocidos")
    incoming = {kind: _count(incoming.get(kind, 0), f"inbound.{kind}") for kind in KINDS}
    affinity = _number(row.get("affinity", 0), "affinity")
    reciprocal = row.get("reciprocity")
    reciprocal = None if reciprocal is None else _number(reciprocal, "reciprocity")
    last_in = _date(row.get("last_inbound_at"), "last_inbound_at", today)
    last_out = _date(row.get("last_outbound_at"), "last_outbound_at", today)
    latest = _date(row.get("latest_post_at"), "latest_post_at", today)
    reply_date = _date(row.get("reply_target_at"), "reply_target_at", today)
    outbound = _count(row.get("outbound_30d", 0), "outbound_30d")
    flags = {name: _flag(row, name) for name in (
        "reply_eligible", "thread_verified", "follow_eligible", "already_following",
        "reactivation_eligible", "visit_eligible", "blocked", "self_account")}
    # Si hay actividad entrante registrada, se exige fecha: evita premios eternos.
    if any(incoming.values()) and last_in is None:
        raise ValueError("last_inbound_at requerido si inbound no esta vacio")
    identity = (network, actor_id.strip().casefold() if actor_id else handle.lstrip("@").casefold())
    return dict(network=network, lane=lane, handle=handle, identity=identity,
                actor_id=actor_id, inbound=incoming, affinity=affinity,
                reciprocity=reciprocal, last_in=last_in, last_out=last_out,
                latest=latest, reply_date=reply_date, outbound=outbound, **flags)


def _eligible(record, today, max_target_age):
    if record["blocked"] or record["self_account"]:
        return (), ("bloqueado" if record["blocked"] else "cuenta propia",)
    allowed = []
    reasons = []
    if record["reply_eligible"] and record["thread_verified"] and record["reply_date"]:
        if (today - record["reply_date"]).days <= max_target_age:
            allowed.append("reply")
        else:
            reasons.append("reply: destino antiguo")
    elif record["reply_eligible"]:
        reasons.append("reply: falta contexto verificado o fecha")
    if record["follow_eligible"] and not record["already_following"]:
        allowed.append("follow")
    if record["reactivation_eligible"] and record["last_out"]:
        idle = (today - record["last_out"]).days
        if 14 <= idle <= 90 and record["latest"] and (today - record["latest"]).days <= max_target_age:
            allowed.append("reactivate")
        else:
            reasons.append("reactivate: requiere post reciente y 14-90 dias sin contacto")
    if record["visit_eligible"]:
        allowed.append("visit")
    return tuple(allowed), tuple(reasons)


def _score(record, action, today):
    inc = record["inbound"]
    inbound_points = (min(inc["comment"], 5) * 3.6
                      + min(inc["follow"], 1) * 6.0
                      + min(inc["repost"], 4) * 2.0
                      + min(inc["like"], 6) * 1.0)
    inbound_points = min(inbound_points, 32.0)
    days = (today - record["last_in"]).days if record["last_in"] else None
    # Los agregados son del periodo observado: sin una ventana fiable, el
    # volumen historico y la variedad deben decaer con la misma recencia.
    decay = 2 ** (-days / 14) if days is not None else 0.0
    inbound_points *= decay
    recency = round(15 * decay, 3)
    depth = min(8.0, sum(v > 0 for v in inc.values()) * 2.0) * decay
    reciprocal = 0 if record["reciprocity"] is None else 8 * record["reciprocity"]
    inactivity = (today - record["last_out"]).days if record["last_out"] else None
    fresh = min(6, max(0, inactivity) / 5) if inactivity is not None else 0.0
    fatigue = -min(15, record["outbound"] * 3)
    action_bonus = {"reply": 16.0, "follow": 7.0, "reactivate": 5.0, "visit": 1.0}[action]
    parts = dict(niche=round(12 * record["affinity"], 3),
                 inbound=round(inbound_points, 3), recency=recency, depth=depth,
                 reciprocity=round(reciprocal, 3), time_since_contact=round(fresh, 3),
                 fatigue=fatigue, action=action_bonus)
    return round(sum(parts.values()), 3), parts


def _candidate(row, today, max_target_age):
    record = _normalize(row, today)
    actions, reasons = _eligible(record, today, max_target_age)
    if not actions:
        return None, dict(network=record["network"], handle=record["handle"],
                          reason="; ".join(reasons) if reasons else "sin accion autorizada")
    options = [(_score(record, action, today), action) for action in actions]
    (score, features), action = min(options, key=lambda x: (-x[0][0], ACTIONS.index(x[1])))
    return dict(network=record["network"], lane=record["lane"], handle=record["handle"],
                actor_id=record["actor_id"], identity=record["identity"],
                action=action, eligible_actions=list(actions),
                score=score, features=features, notes=list(reasons)), None


def rank_daily(snapshot, *, today, limits=None, max_target_age=7, diversity_weight=3.0):
    """Puro y determinista. Nunca une colas ni convierte elegibilidad en orden.

    Un actor por red; duplicados reconciliados por mejor evidencia/prioridad.
    Diversidad = penalizacion blanda, nunca un cupo que cierre el volumen.
    """
    if not isinstance(today, dt.date) or isinstance(today, dt.datetime):
        raise ValueError("today debe ser date")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("candidates"), list):
        raise ValueError("snapshot.candidates: lista requerida")
    if (isinstance(max_target_age, bool) or not isinstance(max_target_age, int)
            or not 0 <= max_target_age <= 30):
        raise ValueError("max_target_age fuera de rango")
    diversity_weight = _number(diversity_weight, "diversity_weight", maximum=50)
    if limits is None:
        limits = {lane: 25 for lane in LANES}
    if set(limits) != set(LANES):
        raise ValueError("limits: declarar WEB, API y MOBILE por separado")
    limits = {lane: _count(limits[lane], f"limits.{lane}") for lane in LANES}
    # Primero normalizar TODAS las observaciones, tambien las vetadas. De
    # otro modo la segunda fuente podria volver elegible a una cuenta bloqueada.
    normalized, excluded = [], []
    ids_by_handle = {}
    for index, row in enumerate(snapshot["candidates"]):
        try:
            record = _normalize(row, today)
        except ValueError as exc:
            excluded.append(dict(index=index, reason=str(exc)))
            continue
        normalized.append((index, record))
        if record["actor_id"]:
            alias = (record["network"], record["handle"].lstrip("@").casefold())
            ids_by_handle.setdefault(alias, set()).add(record["identity"])

    vetoes = set()
    records = []
    for index, record in normalized:
        alias = (record["network"], record["handle"].lstrip("@").casefold())
        ids = ids_by_handle.get(alias, set())
        if not record["actor_id"] and len(ids) == 1:
            record["identity"] = next(iter(ids))
        elif not record["actor_id"] and len(ids) > 1:
            # Un handle con varios IDs no autoriza asignarlo a ninguno.
            # Un veto ambiguo impide recomendar cualquiera de los alias.
            if record["blocked"] or record["self_account"]:
                vetoes.update(ids)
            excluded.append(dict(index=index, network=record["network"],
                                 handle=record["handle"], reason="identidad ambigua"))
            continue
        if record["blocked"] or record["self_account"]:
            vetoes.add(record["identity"])
        records.append((index, record))

    # Conservar la mejor observacion de cada actor EN CADA COLA. La deduplicacion
    # global prematura pierde plazas libres cuando la primera cola se satura.
    winners = {}
    def tie(item):
        return (-item["score"], ACTIONS.index(item["action"]), LANES.index(item["lane"]),
                item["handle"].casefold(), item["handle"], item["actor_id"] or "",
                tuple(item["eligible_actions"]), tuple(item["notes"]),
                json.dumps(item["features"], sort_keys=True))

    for index, record in records:
        if record["identity"] in vetoes:
            excluded.append(dict(index=index, network=record["network"],
                                 handle=record["handle"], reason="veto de identidad: bloqueado o cuenta propia"))
            continue
        candidate, error = _candidate(snapshot["candidates"][index], today, max_target_age)
        if error:
            excluded.append(dict(index=index, **error))
            continue
        candidate["identity"] = record["identity"]
        if "inbound" not in snapshot["candidates"][index]:
            candidate["notes"].append("inbound: observacion desconocida")
        actor = winners.setdefault(candidate["identity"], {})
        lane = candidate["lane"]
        previous = actor.get(lane)
        if previous is None or tie(candidate) < tie(previous):
            if previous is not None:
                excluded.append(dict(index=index, network=candidate["network"],
                                     handle=candidate["handle"], reason="duplicado reemplazado en cola"))
            actor[lane] = candidate
        else:
            excluded.append(dict(index=index, network=candidate["network"],
                                 handle=candidate["handle"], reason="duplicado descartado en cola"))

    # Matching con caminos aumentantes: maximiza cobertura con cupos por cola
    # sin recomendar dos veces a un mismo actor. Procesa mayor puntuacion antes
    # y reubica candidatos si asi se libera una plaza para otro actor.
    assignments = {}
    occupants = {lane: [] for lane in LANES}

    def option_order(actor):
        return sorted(winners[actor], key=lambda lane: (
            -winners[actor][lane]["score"], LANES.index(lane)))

    def place(actor, lane):
        previous_lane = assignments.get(actor)
        if previous_lane is not None:
            occupants[previous_lane].remove(actor)
        assignments[actor] = lane
        occupants[lane].append(actor)

    def augment(actor, visited):
        for lane in option_order(actor):
            if lane in visited:
                continue
            visited.add(lane)
            if len(occupants[lane]) < limits[lane]:
                place(actor, lane)
                return True
            # Desplazar antes al ocupante con menor coste de reubicacion.
            for incumbent in sorted(occupants[lane], key=lambda other: (
                    winners[other][lane]["score"], other)):
                if augment(incumbent, visited):
                    place(actor, lane)
                    return True
        return False

    # Intercalar redes con penalizacion blanda ANTES de ocupar plazas: hacerlo
    # solo al ordenar los ganadores no corrige un cupo ya monopolizado.
    unassigned = set(winners)
    while unassigned:
        network_counts = {lane: Counter(winners[a][lane]["network"] for a in occupants[lane])
                          for lane in LANES}
        actor = min(unassigned, key=lambda a: (
            -max(v["score"] - diversity_weight * network_counts[lane][v["network"]]
                 for lane, v in winners[a].items()), a))
        unassigned.remove(actor)
        augment(actor, set())

    grouped = {lane: [winners[actor][lane] for actor in occupants[lane]]
               for lane in LANES}
    output = {}
    for lane in LANES:
        remaining = grouped[lane]
        counts = Counter()
        chosen = []
        while remaining:
            pick = min(remaining, key=lambda r: (
                -(r["score"] - diversity_weight * counts[r["network"]]),
                -r["score"], r["network"], r["identity"][1], r["action"]))
            remaining.remove(pick)
            shown = {k: v for k, v in pick.items() if k != "identity"}
            shown["rank"] = len(chosen) + 1
            shown["selection_score"] = round(pick["score"] - diversity_weight * counts[pick["network"]], 3)
            chosen.append(shown)
            counts[pick["network"]] += 1
        output[lane] = chosen
    return dict(version=VERSION, date=today.isoformat(), queues=output,
                summary={"candidates": len(snapshot["candidates"]), "unique_eligible": len(winners),
                         "selected": sum(map(len, output.values())),
                         "selected_by_network": dict(sorted(Counter(
                             item["network"] for lane in LANES for item in output[lane]).items()))},
                excluded=excluded)


def evaluate_synthetic(snapshot, output, *, k=10):
    """Contraste descriptivo de etiquetas de fixtures. PROHIBIDO usar en score.

    Las etiquetas no se asumen observaciones reales; precisan ventana madura.
    """
    labels = {}
    for row in snapshot["candidates"]:
        if not isinstance(row, dict) or "converted" not in row:
            continue
        if not isinstance(row["converted"], bool):
            raise ValueError("converted requiere booleano")
        key = (row.get("network"), (str(row.get("actor_id") or "").strip().casefold() if row.get("actor_id") else str(row.get("handle", "")).lstrip("@").casefold()))
        if key in labels and labels[key] != row["converted"]:
            raise ValueError("etiquetas contradictorias para misma identidad")
        labels[key] = row["converted"]
    if not isinstance(k, int) or k < 1:
        raise ValueError("k debe ser positivo")
    result = {}
    for lane, items in output["queues"].items():
        first = items[:k]
        known = []
        for row in first:
            actor_id = row["actor_id"]
            identifier = actor_id.strip().casefold() if actor_id else row["handle"].lstrip("@").casefold()
            key = (row["network"], identifier)
            if key in labels:
                known.append(labels[key])
        result[lane] = dict(k=min(k, len(first)), observed=len(known),
                            precision=(round(sum(known) / len(known), 3) if known else None))
    return result


def markdown(output):
    lines = [f"# Prioridades {output['date']} (solo lectura)", "",
             "Recomendaciones, no acciones ejecutadas ni contenido generado.", ""]
    for lane in LANES:
        lines += [f"## {lane}", "", "| # | Red | Cuenta | Acción | Score | Motivos |",
                  "| --- | --- | --- | --- | ---: | --- |"]
        for row in output["queues"][lane]:
            explanation = ", ".join(f"{key}:{value:+g}" for key, value in row["features"].items() if value)
            lines.append(f"| {row['rank']} | {row['network']} | {row['handle']} | {row['action']} | {row['score']:.3f} | {explanation} |")
        if not output["queues"][lane]:
            lines.append("| — | — | — | — | — | sin candidaturas elegibles |")
        lines.append("")
    lines += [f"Evaluados: {output['summary']['candidates']}; elegibles únicos: {output['summary']['unique_eligible']}; seleccionados: {output['summary']['selected']}.",
              f"Descartados o duplicados: {len(output['excluded'])} (detalle en JSON)."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSON explicitamente suministrado, solo lectura")
    parser.add_argument("--today", required=True, help="YYYY-MM-DD; hace el replay reproducible")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--limit-web", type=int, default=25)
    parser.add_argument("--limit-api", type=int, default=25)
    parser.add_argument("--limit-mobile", type=int, default=25)
    parser.add_argument("--evaluate-synthetic", action="store_true")
    args = parser.parse_args(argv)
    date = dt.date.fromisoformat(args.today)
    snapshot = json.loads(Path(args.input).read_text(encoding="utf-8"))
    output = rank_daily(snapshot, today=date,
                        limits={"WEB": args.limit_web, "API": args.limit_api,
                                "MOBILE": args.limit_mobile})
    if args.evaluate_synthetic:
        output["synthetic_evaluation"] = evaluate_synthetic(snapshot, output)
    print(json.dumps(output, ensure_ascii=False, indent=2) if args.format == "json" else markdown(output), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Proyección OFFLINE multired de fidelización entrante (PR 69).

No llama a APIs, no usa cuentas ni escribe estados. Sus propuestas son solo
revisiones editoriales: no son planes de ejecución de ninguna plataforma.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
import json
import re
from pathlib import Path

NETWORKS = ("x", "threads", "facebook", "pinterest", "reddit", "bluesky",
            "mastodon", "tiktok", "instagram")
LANES = {"x": "WEB", "threads": "WEB", "facebook": "WEB",
         "pinterest": "WEB", "instagram": "WEB", "bluesky": "API",
         "mastodon": "API", "tiktok": "MOBILE"}
ALIASES = {"like": "like", "favourite": "like", "favorite": "like",
           "repost": "repost", "reblog": "repost", "boost": "repost",
           "share": "repost", "follow": "follow", "comment": "comment",
           "reply": "reply", "mention": "mention", "save": "save",
           "bookmark": "save"}
WEIGHTS = {"like": 1, "save": 2, "repost": 3, "follow": 3,
           "comment": 4, "mention": 4, "reply": 5}


def _day(raw, label):
    if not isinstance(raw, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw) is None:
        raise ValueError(f"{label}: fecha ISO YYYY-MM-DD requerida")
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{label}: fecha inválida") from exc


def _name(raw):
    if not isinstance(raw, str):
        raise ValueError("handle no es texto")
    value = raw.strip().lstrip("@").casefold()
    if not value or len(value) > 180 or any(ch.isspace() for ch in value):
        raise ValueError("handle ausente/inválido")
    return value


def read_legacy_csv(path):
    """Export de relationship_policy: una presencia por red/cuenta/tipo/día."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream)
        if not {"fecha", "red", "handle", "tipo"}.issubset(rows.fieldnames or []):
            raise ValueError("CSV legacy sin cabeceras requeridas")
        result = []
        for row in rows:
            if None in row:
                raise ValueError("CSV legacy con columnas inesperadas")
            result.append({"network": row["red"], "handle": row["handle"],
                           "kind": row["tipo"], "day": row["fecha"],
                           "granularity": "daily_aggregate"})
    return result


def _identity(actor_id, handle=None):
    """ID estable primero; sin ID solo alias (nunca unir los dos)."""
    if actor_id is not None:
        if (not isinstance(actor_id, str) or not actor_id.strip()
                or len(actor_id) > 240):
            raise ValueError("actor_id inválido")
        return "id:" + actor_id.strip()
    if handle is None:
        raise ValueError("identidad de outbound/post ausente")
    return "handle:" + _name(handle)


def _normalize(raw, today, history_days):
    if not isinstance(raw, dict):
        raise ValueError("observación no es un objeto")
    net = str(raw.get("network", "")).casefold().strip()
    if net not in NETWORKS:
        raise ValueError("red desconocida")
    handle = _name(raw.get("handle"))
    kind = ALIASES.get(str(raw.get("kind", "")).casefold().strip())
    if kind is None:
        raise ValueError("tipo de interacción desconocido")
    day = _day(raw.get("day"), "evento")
    if day > today or day < today - timedelta(days=history_days - 1):
        return None
    granularity = raw.get("granularity", "event")
    if granularity not in ("event", "daily_aggregate"):
        raise ValueError("granularidad desconocida")
    event_id = raw.get("event_id")
    if granularity == "event":
        if (not isinstance(event_id, str) or not event_id.strip()
                or len(event_id) > 240):
            raise ValueError("evento individual sin ID estable")
    elif event_id is not None:
        raise ValueError("agregado diario no lleva event_id")
    actor_id = raw.get("actor_id")
    target_ref = raw.get("target_ref")
    context = raw.get("context_quality")
    source = raw.get("source")
    if source is not None:
        # Puente explícito de lectura de X/Threads: el target_id NATIVO
        # apunta a la cuenta/post propio, NO al comentario entrante.
        allowed = {("x", "api:users_mentions"), ("threads", "api:own_post_replies")}
        if ((net, source) not in allowed or granularity != "event"
                or kind not in (("comment", "mention") if net == "x" else ("comment",))):
            raise ValueError("origen nativo incompatible")
        native_target = raw.get("target_id")
        if (not isinstance(native_target, str) or not native_target.strip()
                or len(native_target) > 240):
            raise ValueError("origen nativo sin target_id acreditado")
        if actor_id is not None or target_ref not in (None, event_id):
            raise ValueError("origen nativo con identidad/destino contradictorios")
        native_author = raw.get("author_id")
        if net == "x":
            if (not isinstance(native_author, str) or not native_author.strip()
                    or len(native_author) > 240):
                raise ValueError("autor X no acreditado")
            actor_id = native_author
        elif native_author not in ("", None):
            raise ValueError("identidad Threads no acreditada")
        target_ref = event_id  # ID del evento entrante, nunca post propio
        context = context or "partial"
    person = _identity(actor_id, handle)
    if target_ref is not None and (not isinstance(target_ref, str)
                                   or not target_ref.strip() or len(target_ref) > 500):
        raise ValueError("destino inválido")
    answered = raw.get("answered")
    if answered is not None and type(answered) is not bool:
        raise ValueError("answered debe ser booleano verificado")
    if context is not None and context not in ("complete", "partial"):
        raise ValueError("context_quality desconocida")
    return {"network": net, "handle": handle, "kind": kind, "day": day,
            "granularity": granularity, "event_id": event_id,
            "actor_id": actor_id, "target_ref": target_ref,
            "answered": answered, "context_quality": context, "source": source,
            "person": person}

def _canonical_events(rows, today, history_days):
    normalized = [item for raw in rows if (item := _normalize(raw, today, history_days))]
    # Vincular el legado por handle con actor_id únicamente cuando hay ID único.
    ids = {}
    for item in normalized:
        if item["actor_id"]:
            ids.setdefault((item["network"], item["handle"]), set()).add(item["actor_id"])
    for item in normalized:
        possible = ids.get((item["network"], item["handle"]), set())
        item["person"] = ("id:" + item["actor_id"] if item["actor_id"] else
                          "id:" + next(iter(possible)) if len(possible) == 1 else
                          "handle:" + item["handle"])
    unique = {}
    for item in normalized:
        key = ((item["network"], item["event_id"]) if item["granularity"] == "event"
               else (item["network"], item["person"], item["kind"], item["day"]))
        old = unique.get(key)
        if old:
            fields = ("network", "person", "kind", "day", "granularity", "actor_id",
                      "target_ref", "answered", "source")
            if any(old[field] != item[field] for field in fields):
                raise ValueError("colisión de identidad o contenido de evento")
            if old["context_quality"] != item["context_quality"]:
                if {old["context_quality"], item["context_quality"]} <= {None, "partial", "complete"}:
                    if item["context_quality"] == "complete":
                        unique[key] = item
                else:
                    raise ValueError("contexto contradictorio")
        else:
            unique[key] = item
    # El CSV legado no acredita el número de eventos; si existe un evento con
    # ID individual del mismo día/tipo/persona, no sumar también el agregado.
    individual = {(v["network"], v["person"], v["kind"], v["day"])
                  for v in unique.values() if v["granularity"] == "event"}
    return [item for item in unique.values()
            if item["granularity"] == "event" or
            (item["network"], item["person"], item["kind"], item["day"]) not in individual]


def _outbound_lookup(rows, today):
    done = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("network") not in NETWORKS:
            raise ValueError("outbound: red inválida")
        if type(row.get("confirmed")) is not bool:
            raise ValueError("outbound: confirmación explícita requerida")
        if row["confirmed"] is not True:
            continue
        action = row.get("action")
        if action not in ("reply", "thank", "visit"):
            raise ValueError("outbound: acción desconocida")
        when = _day(row.get("day"), "outbound")
        if when > today:
            continue
        # Jamás atribuir una acción por el handle de un actor identificado:
        # puede haberse renombrado o el alias haber pasado a otra persona.
        person = _identity(row.get("actor_id"), row.get("handle"))
        target = row.get("target_ref") if action == "reply" else None
        if action == "reply" and (not isinstance(target, str) or not target.strip()):
            continue  # no cerrar un hilo sin destino exacto confirmado
        key = (row["network"], person, action, target)
        done[key] = max(when, done.get(key, when))
    return done

def _posts(rows, today, max_age):
    posts = {}
    for item in rows:
        if not isinstance(item, dict) or item.get("network") not in NETWORKS:
            raise ValueError("post: red inválida")
        person = _identity(item.get("actor_id"), item.get("handle"))
        day = _day(item.get("day"), "post")
        ref = item.get("ref")
        if (type(item.get("verified")) is not bool or
                type(item.get("original")) is not bool or
                type(item.get("niche_es")) is not bool):
            raise ValueError("post: procedencia, originalidad y nicho explícitos")
        if (not item["verified"] or not item["original"] or not item["niche_es"]
                or not isinstance(ref, str) or not ref.strip()
                or day > today or (today - day).days > max_age):
            continue
        key = (item["network"], person)
        value = {"ref": ref, "day": day}
        if key not in posts or (day, ref) > (posts[key]["day"], posts[key]["ref"]):
            posts[key] = value
    return posts

def build(observations, *, as_of, legacy=(), outbound=(), posts=(),
          history_days=90, recent_days=14, post_max_age_days=7,
          per_lane=12, per_contact_threads=4, coverage=None):
    """Proyecta señales, score explicable, recurrencia y revisión por cola.

    API puramente funcional: jamás llama a red ni lee estados predeterminados.
    """
    if type(as_of) is not date:
        raise ValueError("as_of debe ser date")
    if (not all(type(n) is int and n > 0 for n in
                (history_days, recent_days, post_max_age_days, per_lane, per_contact_threads))
            or recent_days > history_days):
        raise ValueError("ventanas o límite inválidos")
    if coverage is None:
        coverage = {}
    if (not isinstance(coverage, dict) or
            any(k not in NETWORKS or v not in ("complete", "partial", "unknown")
                for k, v in coverage.items())):
        raise ValueError("cobertura no válida")
    events = _canonical_events([*legacy, *observations], as_of, history_days)
    confirmed = _outbound_lookup(outbound, as_of)
    recent_posts = _posts(posts, as_of, post_max_age_days)
    people = {}
    for e in events:
        key = (e["network"], e["person"])
        people.setdefault(key, []).append(e)
    ranked = []
    for (net, person), own in people.items():
        own.sort(key=lambda e: (e["day"], e["event_id"] or "", e["handle"]))
        last = own[-1]["day"]
        days = {e["day"] for e in own}
        recent = [e for e in own if (as_of - e["day"]).days < recent_days]
        if not recent:
            continue
        kinds = {e["kind"] for e in recent}
        handle = own[-1]["handle"]
        components = {
            "recency": max(0, 6 - (as_of - last).days // 2),
            "frequency": min(10, 2 * len(recent)),
            "depth": min(12, sum(WEIGHTS[e["kind"]] for e in recent)),
            "diversity": min(8, 2 * len(kinds)),
            "recurrence": min(8, 4 * (len({e["day"] for e in recent}) - 1)),
        }
        score = sum(components.values())
        proposals = []
        # Una cuenta ocupa un cupo, pero puede tener varios hilos abiertos.
        # latest por ref, incluso answered=True para no resucitar un hilo cerrado.
        by_ref = {}
        for e in reversed(recent):
            if e["kind"] in ("reply", "comment", "mention") and e["target_ref"]:
                by_ref.setdefault(e["target_ref"], e)
        for ref, e in list(by_ref.items()):
            if len([p for p in proposals if p["kind"] in ("reply_review", "context_review")]) >= per_contact_threads:
                break
            if e["answered"] is True or (e["answered"] is None and not e["source"]):
                continue
            last_reply = confirmed.get((net, person, "reply", ref))
            if last_reply is not None and last_reply >= e["day"]:
                continue
            # La mención y el estado de respuesta desconocido solo autorizan
            # investigar contexto; jamás presentar una respuesta como pendiente.
            verified_pending = e["answered"] is False and e["kind"] != "mention"
            proposals.append({"kind": ("reply_review" if verified_pending and
                                      e["context_quality"] == "complete"
                                      else "context_review"), "target_ref": ref})
        for action, label in (("thank", "thank_review"), ("visit", "visit_recent_review")):
            prev = confirmed.get((net, person, action, None))
            if prev is not None and (as_of - prev).days < 7:
                continue
            if action == "thank":
                if len(days) >= 2 or len(kinds) >= 2 or "follow" in kinds:
                    proposals.append({"kind": label})
            else:
                post = recent_posts.get((net, person))
                if post:
                    proposals.append({"kind": label, "target_ref": post["ref"],
                                      "post_day": post["day"].isoformat()})
        if proposals:
            ranked.append({"network": net, "handle": handle,
                           "identity": person, "lane": LANES.get(net, "UNASSIGNED"),
                           "score": score, "components": components,
                           "distinct_days": len(days),
                           "events_recent": len(recent),
                           "last_inbound": last.isoformat(),
                           "proposals": proposals})
    ranked.sort(key=lambda r: (-r["score"], -r["distinct_days"],
                               r["network"], r["identity"]))
    # Repartir turnos dentro de cada cola: un volumen alto en X no oculta
    # señales de Facebook/Threads, sin mezclar locks o ejecutores de cola.
    queues = {lane: [] for lane in ("WEB", "API", "MOBILE", "UNASSIGNED")}
    buckets = {lane: {} for lane in queues}
    for item in ranked:
        buckets[item["lane"]].setdefault(item["network"], []).append(item)
    for lane, by_network in buckets.items():
        while len(queues[lane]) < per_lane and any(by_network.values()):
            order = sorted((net for net, items in by_network.items() if items),
                           key=lambda net: (-by_network[net][0]["score"], net))
            for net in order:
                if len(queues[lane]) >= per_lane:
                    break
                queues[lane].append(by_network[net].pop(0))
    by_network = {}
    for net in NETWORKS:
        group = [events for (n, _), events in people.items() if n == net]
        eligible = sum(min(x["day"] for x in seq) <= as_of - timedelta(days=1)
                       for seq in group)
        repeat = sum(min(x["day"] for x in seq) <= as_of - timedelta(days=1)
                     and len({x["day"] for x in seq}) >= 2 for seq in group)
        by_network[net] = {"contacts": len(group), "eligible_for_repeat": eligible,
                           "repeated_contacts": repeat,
                           "repeat_rate": round(repeat / eligible, 4) if eligible else None,
                           "coverage": coverage.get(net, "unknown")}
    return {"as_of": as_of.isoformat(), "mode": "review_only",
            "queues": queues, "metrics": by_network,
            "observations_unique": len(events),
            "queued_contacts": sum(len(q) for q in queues.values())}


def _load(path, default):
    if path is None:
        return default
    with Path(path).open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, type(default)):
        raise ValueError("JSON de entrada con tipo incorrecto")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--observations", help="lista JSON de eventos con IDs")
    parser.add_argument("--legacy-csv", help="CSV diario del registro inbound")
    parser.add_argument("--outbound", help="JSON de acciones confirmadas")
    parser.add_argument("--posts", help="JSON de posts recientes verificados")
    parser.add_argument("--coverage", help="JSON de cobertura por red")
    args = parser.parse_args(argv)
    if not args.observations and not args.legacy_csv:
        parser.error("requiere --observations o --legacy-csv explícito")
    result = build(_load(args.observations, []), as_of=_day(args.as_of, "as_of"),
                   legacy=read_legacy_csv(args.legacy_csv) if args.legacy_csv else (),
                   outbound=_load(args.outbound, []),
                   posts=_load(args.posts, []),
                   coverage=_load(args.coverage, {}))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

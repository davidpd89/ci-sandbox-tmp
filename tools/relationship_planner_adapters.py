"""Puente read-only de productores nativos a relationship_priority (#71).

No ejecuta planes ni acciones. Entradas explícitas (manifiesto con rutas sintéticas
o rutas revisadas por el operador), sin estado propio ni escrituras.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
import json
from pathlib import Path
import re
import sqlite3
from contextlib import closing

NETWORKS = ("x", "threads", "facebook", "pinterest", "reddit",
            "bluesky", "mastodon", "tiktok", "instagram")
LANES = ("WEB", "API", "MOBILE")
CONFIRMED = frozenset(("confirmado", "publicado"))
COMMENTS = frozenset(("reply", "comment", "comentario", "comment_external", "respuesta"))
INBOUND_KINDS = frozenset(("comment", "repost", "follow", "like"))
VERSION = "relationship-planner-adapters/v1"


def _day(value):
    """Fecha real, estricta y sin asumir que timestamps locales son UTC."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and re.fullmatch(r"\d{10}(?:\d{3})?", value)):
        try:
            number = float(value)
            if number > 1e11:
                number /= 1000
            if 946684800 <= number < 4102444800:
                return dt.datetime.fromtimestamp(number, tz=dt.timezone.utc).date().isoformat()
        except (OverflowError, ValueError, TypeError):
            return None
        return None
    if not isinstance(value, str):
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return dt.date.fromisoformat(value).isoformat()
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is not None and stamp.utcoffset() is not None:
            return stamp.astimezone(dt.timezone.utc).date().isoformat()
    except (ValueError, OverflowError):
        pass
    return None


def _handle(value):
    if not isinstance(value, str):
        return ""
    value = value.strip().lstrip("@")
    return value if value and len(value) <= 120 and not any(ch.isspace() for ch in value) else ""


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    import math
    return float(value) if 0 <= value <= 1 and math.isfinite(value) else None


def _items(data, network):
    """Formas reales: lista, {'candidates'}, Pinterest authors/pins, TikTok posts."""
    if isinstance(data, list):
        return list(data)
    if not isinstance(data, dict):
        raise ValueError("productor: se esperaba lista u objeto")
    if network == "pinterest":
        # El tipo de contenedor no prueba que una acción esté permitida.
        # Solo trasladar acciones que haya declarado explícitamente el productor.
        authors = [dict(a) for a in data.get("authors", []) if isinstance(a, dict)]
        pins = [{**p, "handle": p.get("handle") or p.get("author")} for p in data.get("pins", [])
                if isinstance(p, dict)]
        return authors + pins
    rows = data.get("candidates", data.get("actors", []))
    if not isinstance(rows, list):
        raise ValueError("productor.candidates debe ser lista")
    if network == "tiktok":
        out = []
        for actor in rows:
            if not isinstance(actor, dict):
                out.append(actor)
                continue
            out.append(actor)
            for post in actor.get("posts", []):
                if isinstance(post, dict):
                    out.append({**actor, **post, "kind": post.get("kind"),
                                "actions": post.get("actions", [post.get("kind")]),
                                "target_created_at": post.get("target_created_at") or post.get("created_at") or post.get("create_time"),
                                "preflight": post.get("preflight", {})})
        return out
    return rows


def _confirmed_outbound(rows, network, today):
    """Agregación de historial confirmado; jamás acciones intentadas."""
    per = defaultdict(lambda: {"comments": 0, "out30": 0, "last": None,
                               "blocked": False, "following": None})
    for row in rows:
        if not isinstance(row, dict) or (row.get("resultado") or "").casefold() not in CONFIRMED:
            continue
        if row.get("red") not in (None, "", network):
            continue
        handle = _handle(row.get("cuenta") or row.get("handle"))
        kind = str(row.get("tipo") or "").casefold()
        when = _day(row.get("fecha"))
        if not handle or not when or when > today.isoformat():
            continue
        state = per[handle.casefold()]
        if kind in COMMENTS:
            state["comments"] += 1
        if 0 <= (today - dt.date.fromisoformat(when)).days < 30:
            state["out30"] += 1
        if state["last"] is None or when > state["last"]:
            state["last"] = when
        if kind == "block":
            state["blocked"] = True
        # Sólo los cambios de follow con fecha válida y resultado confirmado.
        if kind in ("follow", "unfollow"):
            prev = state.get("follow_at")
            if prev is None or when > prev or (when == prev and kind == "unfollow"):
                state["follow_at"] = when
                state["following"] = (kind == "follow")
    return per


def _verified_inbound(events, today):
    """Eventos #69 por ID estable; identidad y fecha verificables."""
    seen, counts, last, ids, conflicts = {}, defaultdict(Counter), {}, {}, set()
    for row in events:
        if not isinstance(row, dict):
            continue
        net, event_id = row.get("network"), row.get("event_id")
        handle = _handle(row.get("handle"))
        kind, day = row.get("kind"), _day(row.get("day"))
        if (net not in NETWORKS or not isinstance(event_id, str) or not event_id
                or not handle or kind not in INBOUND_KINDS or day is None or day > today.isoformat()):
            continue
        key = (net, event_id)
        payload = (handle.casefold(), kind, day, str(row.get("author_id") or ""))
        if key in seen:
            if seen[key] != payload:
                conflicts.add(key)
            continue
        seen[key] = payload
    # Ventana móvil de 30 días, ambos extremos incluidos (hoy y hoy-29).
    # Preservar señales de identidad antiguas, pero no volver a premiar
    # actividad histórica cuando aparece una interacción nueva.
    cutoff = (today - dt.timedelta(days=29)).isoformat()
    for (net, event_id), (handle, kind, day, author_id) in seen.items():
        if (net, event_id) in conflicts:
            continue
        key = (net, handle)
        if author_id:
            ids.setdefault(key, set()).add(author_id)
        if day < cutoff:
            continue
        counts[key][kind] += 1
        last[key] = max(last.get(key, day), day)
    return counts, last, ids, len(conflicts)


def _target_day(row):
    # Nunca usar created_at de la raíz de una tarea: puede ser la fecha de la cola.
    for key in ("target_created_at", "post_created_at", "reply_target_at",
                "target_created_utc", "post_created_utc"):
        if _day(row.get(key)):
            return _day(row[key])
    post = row.get("post")
    if isinstance(post, dict):
        for key in ("created_at", "createdAt", "create_time", "created_time", "created_utc"):
            if _day(post.get(key)):
                return _day(post[key])
    return None


def _coverage_complete(proof, rows, today):
    """Prueba positiva DECLARADA de cobertura integral del registro de salidas.

    La ventana completa es necesaria para la regla de reciprocidad histórica:
    dos comentarios iniciales + uno por cada respuesta inbound. Una exportación
    truncada nunca equivale a un contador cero.
    """
    if not isinstance(proof, dict) or not isinstance(rows, list):
        return False
    if proof.get("status") != "complete":
        return False
    start = _day(proof.get("from"))
    account = _day(proof.get("account_since"))
    end = _day(proof.get("through"))
    current = today.isoformat()
    return bool(start and account and end and start <= account <= current <= end)


def build_snapshot(sources, outbound, inbound, *, today, outbound_coverage=None):
    """Devuelve (snapshot #71, diagnóstico). Aísla errores por fuente y fila."""
    if not isinstance(today, dt.date) or isinstance(today, dt.datetime):
        raise ValueError("today requiere datetime.date")
    if not isinstance(sources, list):
        raise ValueError("sources debe ser lista")
    if not isinstance(outbound, dict) or not isinstance(inbound, list):
        raise ValueError("outbound debe ser objeto e inbound lista")
    inc, last_in, event_ids, conflicts = _verified_inbound(inbound, today)
    if outbound_coverage is not None and not isinstance(outbound_coverage, dict):
        raise ValueError("outbound_coverage requiere objeto")
    # read_manifest adjunta los certificados declarados de cada exportación;
    # callers programáticos también pueden suministrarlos explícitamente.
    proofs = {src["network"]: src["_outbound_coverage"] for src in sources
              if isinstance(src, dict) and src.get("network") in NETWORKS
              and "_outbound_coverage" in src}
    proofs.update(outbound_coverage or {})
    coverage_ok = {net: net in outbound and _coverage_complete(
        proofs.get(net), outbound.get(net), today) for net in NETWORKS}
    history = {network: _confirmed_outbound(outbound.get(network, []), network, today)
               for network in NETWORKS}
    candidates, excluded = [], []
    # Resolver aliases antes de escoger cola; conflictos = no planificar.
    aliases = defaultdict(set)
    vetoes, already_followed = set(), set()
    for source in sources:
        if not isinstance(source, dict) or source.get("network") not in NETWORKS:
            continue
        try:
            rows = _items(source.get("data"), source["network"])
        except (ValueError, TypeError):
            continue
        for item in rows:
            if isinstance(item, dict):
                h = _handle(item.get("handle") or item.get("username") or item.get("author"))
                actor = item.get("actor_id") or item.get("author_id")
                net = source["network"]
                actor_id = actor.strip().casefold() if isinstance(actor, str) and actor.strip() else None
                if h and actor_id:
                    aliases[(net, h.casefold())].add(actor_id)
                pre = item.get("preflight")
                if not isinstance(pre, dict):
                    continue
                identities = ([(net, "handle", h.casefold())] if h else [])
                if actor_id:
                    identities.append((net, "id", actor_id))
                # Un veto en un colector nunca puede ser borrado por el
                # preflight optimista de otra cola con el mismo actor.
                if pre.get("blocked") is True or pre.get("self_account") is True:
                    vetoes.update(identities)
                if pre.get("follow_state_verified") is True and pre.get("already_following") is True:
                    already_followed.update(identities)
    for key, values in event_ids.items():
        aliases[key].update(x.casefold() for x in values)
    for source_index, source in enumerate(sources):
        if not isinstance(source, dict):
            excluded.append({"source": source_index, "reason": "fuente no objeto"})
            continue
        net, lane = source.get("network"), source.get("lane")
        if net not in NETWORKS or lane not in LANES:
            excluded.append({"source": source_index, "reason": "red o cola desconocida"})
            continue
        if source.get("_read_error"):
            excluded.append({**{"source": source_index, "network": net},
                             "reason": source["_read_error"]})
            continue
        try:
            rows = _items(source.get("data"), net)
        except (ValueError, TypeError) as exc:
            excluded.append({"source": source_index, "network": net, "reason": str(exc)})
            continue
        for index, item in enumerate(rows):
            place = {"source": source_index, "index": index, "network": net}
            if not isinstance(item, dict):
                excluded.append({**place, "reason": "candidato no objeto"})
                continue
            handle = _handle(item.get("handle") or item.get("username") or item.get("author"))
            if not handle:
                excluded.append({**place, "reason": "handle ausente"})
                continue
            key = (net, handle.casefold())
            alias = aliases[key]
            actor_id = next(iter(alias)) if len(alias) == 1 else None
            identities = [(net, "handle", handle.casefold())]
            if actor_id:
                identities.append((net, "id", actor_id))
            if any(identity in vetoes for identity in identities):
                excluded.append({**place, "reason": "veto de identidad entre colas"})
                continue
            if len(alias) > 1:
                excluded.append({**place, "reason": "identidad contradictoria"})
                continue
            pre = item.get("preflight")
            if not isinstance(pre, dict) or pre.get("checked_at") != today.isoformat():
                excluded.append({**place, "reason": "preflight ausente o caducado"})
                continue
            own, blocked = pre.get("self_account"), pre.get("blocked")
            if not isinstance(own, bool) or not isinstance(blocked, bool):
                excluded.append({**place, "reason": "bloqueo/cuenta propia sin verificar"})
                continue
            if own or blocked or history[net][handle.casefold()]["blocked"]:
                excluded.append({**place, "reason": "bloqueo o cuenta propia"})
                continue
            actions = item.get("actions")
            if actions is None:
                actions = [item.get("kind")]
            if not isinstance(actions, list):
                excluded.append({**place, "reason": "acciones inválidas"})
                continue
            follow = "follow" in actions and pre.get("follow_eligible") is True
            state = history[net][handle.casefold()]
            following = pre.get("already_following")
            if not isinstance(following, bool) or pre.get("follow_state_verified") is not True:
                follow = False  # ausencia de observación no equivale a no seguir
                following = True
            if state["following"] is True or any(identity in already_followed for identity in identities):
                following = True  # otra cola o el registro confirmado prevalecen
            target_day = _target_day(item)
            comment = any(a in actions for a in ("reply", "comment", "comment_external"))
            eligible_comment = (coverage_ok[net] and comment and pre.get("thread_verified") is True
                                and pre.get("comment_allowed") is True
                                and state["comments"] < 2 + inc[key]["comment"]
                                and target_day is not None
                                and 0 <= (today - dt.date.fromisoformat(target_day)).days <= 3)
            if not (follow and not following or eligible_comment
                    or pre.get("visit_eligible") is True or pre.get("reactivation_eligible") is True):
                excluded.append({**place, "reason": "sin acción con evidencia suficiente"})
                continue
            affinity = _number(item.get("affinity"))
            reciprocity = _number(item.get("reciprocity"))
            latest = _day(item.get("latest_post_at"))
            row = dict(network=net, lane=lane, handle=handle, actor_id=actor_id,
                       affinity=affinity if affinity is not None else 0.0,
                       reciprocity=reciprocity, inbound=dict(inc[key]),
                       last_inbound_at=last_in.get(key), last_outbound_at=state["last"],
                       outbound_30d=state["out30"], latest_post_at=latest,
                       reply_target_at=target_day, blocked=False, self_account=False,
                       reply_eligible=bool(eligible_comment), thread_verified=bool(eligible_comment),
                       follow_eligible=bool(follow and not following), already_following=following,
                       reactivation_eligible=pre.get("reactivation_eligible") is True,
                       visit_eligible=pre.get("visit_eligible") is True)
            # Sin certificación de inbound no presentar el cero como conocido.
            # El scorer común ya distingue ausencia de campo de un agregado 0.
            if not inc[key]:
                row.pop("inbound")
            candidates.append(row)
            # No incluir handle/IDs/textos en diagnósticos exportables.
            if affinity is None or reciprocity is None:
                excluded.append({**place, "note": "afinidad o reciprocidad desconocida; no imputada"})
    return {"candidates": candidates}, {"excluded": excluded, "inbound_id_conflicts": conflicts,
                                        "outbound_coverage": {
                                            net: "complete" if coverage_ok[net] else "unknown_or_incomplete"
                                            for net in NETWORKS},
                                        "sources": len(sources), "prepared": len(candidates)}


def plan_dry_run(sources, outbound, inbound, *, today, scorer=None, limits=None,
                 outbound_coverage=None):
    """Consume score #71 sin duplicar la función ni generar planes ejecutables."""
    if scorer is None:
        try:
            from relationship_priority import rank_daily as scorer
        except ImportError as exc:
            raise RuntimeError("Falta tools/relationship_priority.py (#71); integrar dependencia antes de planificar") from exc
    snapshot, diagnostics = build_snapshot(sources, outbound, inbound, today=today,
                                           outbound_coverage=outbound_coverage)
    result = scorer(snapshot, today=today, limits=limits)
    # El ranking es recomendación exclusivamente; jamás devolver kind/text accionable.
    return {"version": VERSION, "mode": "offline_dry_run_not_executable",
            "snapshot": snapshot, "ranking": result, "diagnostics": diagnostics,
            "executor_preflight_required": True}


def read_manifest(path):
    """Solo lectura de rutas EXPLÍCITAS; SQLite 'mode=ro'; sin globs ni red."""
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = []
    coverages = manifest.get("outbound_coverage", {})
    if not isinstance(coverages, dict):
        raise ValueError("outbound_coverage: se esperaba objeto")
    for entry in manifest["sources"]:
        source = {"network": entry["network"], "lane": entry["lane"]}
        if entry["network"] in coverages:
            source["_outbound_coverage"] = coverages[entry["network"]]
        try:
            source["data"] = json.loads(Path(entry["path"]).read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            source["_read_error"] = "archivo de productor ausente, inválido o inaccesible"
        sources.append(source)
    outbound, unavailable = {}, set()
    for net, filename in manifest.get("outbound_csvs", {}).items():
        try:
            with Path(filename).open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if not {"cuenta", "fecha", "tipo", "resultado"} <= set(reader.fieldnames or ()):
                    raise ValueError("cabeceras incompletas")
                outbound[net] = list(reader)
        except (OSError, ValueError, TypeError, csv.Error):
            unavailable.add(net)
    for item in sources:
        if item["network"] in unavailable:
            item["_read_error"] = "registro confirmado ausente o inválido"
    inbound = []
    if manifest.get("verified_inbound_sqlite"):
        # Resolver la ruta local antes de URI: paths Windows y espacios.
        uri = Path(manifest["verified_inbound_sqlite"]).resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as db:
            db.row_factory = sqlite3.Row
            inbound = [dict(row) for row in db.execute(
                "SELECT network, event_id, author_id, handle, kind, day FROM verified_inbound")]
    return sources, outbound, inbound


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Manifiesto explícito JSON; nunca lee cuentas por defecto")
    parser.add_argument("--today", required=True)
    args = parser.parse_args(argv)
    sources, outbound, inbound = read_manifest(args.manifest)
    result = plan_dry_run(sources, outbound, inbound, today=dt.date.fromisoformat(args.today))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

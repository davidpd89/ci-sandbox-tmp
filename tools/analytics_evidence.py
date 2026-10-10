"""Informe reproducible de evidencias seudónimas, siempre offline.

No infiere ventas a partir de clicks ni efectos causales a partir de holdouts.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys

from growth_attribution import wilson

NETWORKS = frozenset("x threads facebook pinterest reddit bluesky mastodon tiktok instagram".split())
QUEUES = frozenset(("WEB", "API", "MOBILE"))
OUTCOMES = ("followback", "web_visit", "sale", "reading")
SOURCES = {"followback": "api_snapshot", "web_visit": "first_party_analytics",
           "sale": "order_system", "reading": "reader_system"}
ACK_SOURCES = frozenset(("action_ledger", "confirmed_api", "confirmed_web", "confirmed_mobile"))
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")


def _id(value, field):
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{field}: identificador seudónimo inválido")
    return value


def _utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("se requiere fecha UTC con Z")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError("fecha inválida") from exc


def _utm(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"source", "medium", "campaign"}:
        raise ValueError("UTM incompleta")
    return {k: _id(v, "utm_" + k) for k, v in value.items()}


def _dedupe(rows, label):
    if not isinstance(rows, list) or len(rows) > 100000:
        raise ValueError(f"{label}: lista inválida")
    result, duplicates = {}, 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{label}: fila inválida")
        key = _id(row.get("id"), "id")
        if key in result:
            if result[key] != row:
                raise ValueError(f"{label}: id con datos contradictorios")
            duplicates += 1
        else:
            result[key] = row
    return result, duplicates


def analyze(payload):
    """Agrupa por red/cola/campaña/brazo y distingue inmaduro, desconocido y cero."""
    if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        raise ValueError("schema_version=1 obligatorio")
    now = _utc(payload.get("as_of"))
    days = payload.get("window_days")
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError("window_days fuera de rango")
    exposures, dup_e = _dedupe(payload.get("exposures"), "exposures")
    observations, dup_o = _dedupe(payload.get("observations"), "observations")
    if not exposures:
        raise ValueError("faltan exposiciones")
    units, arms, tokens = {}, defaultdict(set), {}
    unconfirmed = 0
    for row in exposures.values():
        for field in ("network", "queue", "campaign", "subject", "cohort", "action",
                      "status", "source", "source_ref"):
            _id(row.get(field), field)
        net, queue, cohort, status = (row[k] for k in ("network", "queue", "cohort", "status"))
        if net not in NETWORKS or queue not in QUEUES or cohort not in ("treated", "control"):
            raise ValueError("red, cola o brazo inválido")
        if status not in ("confirmed", "holdout", "failed", "uncertain"):
            raise ValueError("estado no reconocido")
        if (cohort == "control") != (status == "holdout"):
            raise ValueError("el control exige holdout")
        if (cohort == "control" and row["source"] != "holdout_ledger") or (
                cohort == "treated" and row["source"] not in ACK_SOURCES):
            raise ValueError("fuente de ACK inválida")
        when = _utc(row.get("occurred_at"))
        if when > now:
            raise ValueError("exposición futura")
        utm = _utm(row.get("utm"))
        tracking_marker = row.get("tracking_id")
        if tracking_marker is not None:
            _id(tracking_marker, "tracking_id")
        if utm and (not tracking_marker or utm["source"] != net or utm["campaign"] != row["campaign"]):
            raise ValueError("UTM no verificable")
        if cohort == "control" and (utm or tracking_marker):
            raise ValueError("control contaminado por tracking")
        unit_key = (net, row["campaign"], row["subject"])
        arms[unit_key].add(cohort)
        if tracking_marker:
            if tracking_marker in tokens and tokens[tracking_marker] != unit_key:
                raise ValueError("tracking_id reutilizado")
            tokens[tracking_marker] = unit_key
        if status in ("failed", "uncertain"):
            unconfirmed += 1
            continue
        candidate = {**row, "_when": when}
        if unit_key not in units or (when, row["id"]) < (
                units[unit_key]["_when"], units[unit_key]["id"]):
            units[unit_key] = candidate
    if any(len(v) > 1 for v in arms.values()):
        raise ValueError("sujeto en tratamiento y control")
    chosen = {row["id"]: row for row in units.values()}
    observed = defaultdict(list)
    credited, outside = {}, 0
    for row in observations.values():
        _id(row.get("exposure_id"), "exposure_id")
        _id(row.get("source_ref"), "source_ref")
        exposure = exposures.get(row["exposure_id"])
        if exposure is None:
            raise ValueError("observación sin exposición")
        metric = row.get("outcome")
        if metric not in OUTCOMES or row.get("source") != SOURCES[metric]:
            raise ValueError("fuente de resultado no acreditada")
        if type(row.get("positive")) is not bool or type(row.get("complete")) is not bool:
            raise ValueError("positive y complete requieren booleanos")
        if row.get("basis") != ("identity" if metric == "followback" else "tracked"):
            raise ValueError("base de enlace no verificada")
        if metric != "followback":
            if not exposure.get("tracking_id") or row.get("tracking_id") != exposure["tracking_id"]:
                raise ValueError("enlace de resultado sin tracking_id exacto")
            if metric == "web_visit" and (not exposure.get("utm") or
                                           _utm(row.get("utm")) != _utm(exposure["utm"])):
                raise ValueError("tráfico web sin UTM exacta")
            if row["positive"]:
                ref = (row["source"], row["source_ref"])
                if ref in credited and credited[ref] != row["exposure_id"]:
                    raise ValueError("conversión atribuida dos veces")
                credited[ref] = row["exposure_id"]
        when = _utc(row.get("observed_at"))
        if when > now:
            raise ValueError("observación futura")
        selected = chosen.get(row["exposure_id"])
        if not selected:
            continue
        if not selected["_when"] <= when <= selected["_when"] + timedelta(days=days):
            outside += 1
            continue
        observed[(row["exposure_id"], metric)].append((row["positive"], row["complete"], when))
    grouped = defaultdict(lambda: {"eligible": 0, "immature": 0, "positive": 0,
                                   "negative": 0, "unknown": 0})
    for exposure in chosen.values():
        mature = now >= exposure["_when"] + timedelta(days=days)
        for metric in OUTCOMES:
            key = (exposure["network"], exposure["queue"], exposure["campaign"],
                   exposure["cohort"], metric)
            entry = grouped[key]
            entry["eligible"] += 1
            if not mature:
                entry["immature"] += 1
                continue
            proofs = observed[(exposure["id"], metric)]
            positive = any(p for p, _, _ in proofs)
            negative = any(not p and complete and t >= exposure["_when"] + timedelta(days=days)
                           for p, complete, t in proofs)
            if positive and negative:
                raise ValueError("evidencias contradictorias para una ventana")
            entry["positive" if positive else "negative" if negative else "unknown"] += 1
    rows = []
    for key, counts in sorted(grouped.items()):
        mature = counts["eligible"] - counts["immature"]
        readiness = ("immature" if not mature else "partial" if counts["unknown"] or
                     counts["immature"] else "complete")
        rate = counts["positive"] / mature if readiness == "complete" else None
        low_high = (list(wilson(counts["positive"], mature, z=1.6448536269514722))
                    if readiness == "complete" else None)
        rows.append(dict(zip(("network", "queue", "campaign", "cohort", "outcome"), key)) |
                    counts | {"readiness": readiness, "rate": rate, "wilson90": low_high})
    return {"schema_version": 1, "as_of": payload["as_of"], "window_days": days,
            "interpretation": "descriptive_only_not_causal", "groups": rows,
            "quality": {"duplicate_exposures": dup_e, "duplicate_observations": dup_o,
                        "unconfirmed_actions": unconfirmed,
                        "repeated_subject_exposures": sum(
                            e["status"] in ("confirmed", "holdout") for e in exposures.values()) - len(chosen),
                        "ignored_out_of_window": outside,
                        "networks_without_exposure": sorted(NETWORKS - {
                            e["network"] for e in chosen.values()})}}


def _unique_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("clave JSON duplicada")
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError("NaN/Infinity no admitidos")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analítica descriptiva y auditada, offline")
    parser.add_argument("input_json", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input_json.open("rb") as file:
            raw = file.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("entrada superior a 2 MB")
        payload = json.loads(raw, object_pairs_hook=_unique_keys,
                             parse_constant=_reject_constant)
        print(json.dumps(analyze(payload), ensure_ascii=False, sort_keys=True))
    except (OSError, TypeError, KeyError, ValueError, RecursionError, OverflowError) as exc:
        print(f"Entrada inválida: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

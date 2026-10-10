"""Puente SOLO LECTURA del ledger de #84 a trayectorias Retentioneering.

Sin conexiones sociales, escrituras en el ledger ni decisiones de ejecución.
Contrato de entrada: tools/relationship_event_ledger.py (#84, esquema v1).
Retentioneering es OPCIONAL: solo se importa en to_eventstream().
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone, timedelta
import json
from pathlib import Path
import sqlite3

NETWORKS = frozenset(("x", "threads", "facebook", "pinterest", "reddit",
                      "bluesky", "mastodon", "tiktok", "instagram"))
KINDS = frozenset(("follow", "unfollow", "like", "comment", "reply",
                   "repost", "visit", "followback"))
COLUMNS = frozenset(("seq", "event_id", "network", "queue", "subject", "kind",
                     "outcome", "occurred_at", "precision"))
CSV_COLUMNS = ("user_id", "event", "timestamp", "network", "queue", "event_id")


def _instant(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp no es texto")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp ISO-8601 invalido") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("timestamp sin zona: no inferir horario/DST")
    return moment.astimezone(timezone.utc)


def read_ledger(path: str | Path):
    """Lee exactamente el esquema del ledger #84, sin crear ni migrar DB.

    Omite eventos inciertos, fallidos o no verificados; una observacion
    negativa no acredita una nueva accion. No ordena eventos de precision dia.
    """
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    omitted = Counter()
    records = []
    try:
        with sqlite3.connect(uri, uri=True, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            cols = {r[1] for r in conn.execute("PRAGMA table_info(relationship_events)")}
            if not COLUMNS.issubset(cols):
                raise ValueError("no es un ledger relacional #84 v1")
            for row in conn.execute(
                "SELECT seq,event_id,network,queue,subject,kind,outcome,"
                "occurred_at,precision FROM relationship_events ORDER BY occurred_at,seq"
            ):
                net, queue, kind = row["network"], row["queue"], row["kind"]
                if (net not in NETWORKS or queue not in ("WEB", "API", "MOBILE")
                        or kind not in KINDS or not isinstance(row["subject"], str)
                        or not row["subject"].strip()):
                    raise ValueError("fila incompatible con el contrato #84")
                if row["precision"] == "day":
                    omitted["day_precision"] += 1
                    continue
                if row["precision"] != "instant":
                    raise ValueError("precision desconocida")
                event_name = (
                    "followback.present" if kind == "followback" and row["outcome"] == "present"
                    else kind + ".confirmed" if kind != "followback" and row["outcome"] == "confirmed"
                    else None
                )
                if event_name is None:
                    omitted["not_positive_evidence"] += 1
                    continue
                moment = _instant(row["occurred_at"])
                records.append({
                    "user_id": json.dumps([net, row["subject"]], ensure_ascii=False,
                                          separators=(",", ":")),
                    "event": event_name, "timestamp": moment.isoformat(),
                    "network": net, "queue": queue, "event_id": str(row["event_id"]),
                    "_sort": (moment, row["seq"]),
                })
    except sqlite3.Error as exc:
        raise ValueError(f"ledger inexistente, ilegible o no SQLite: {exc}") from exc

    records.sort(key=lambda r: (r["user_id"], r["_sort"]))
    # Un snapshot reiterado de 'te sigue' no equivale a interacciones nuevas.
    seen_followbacks = set()
    clean = []
    for row in records:
        if row["event"] == "followback.present":
            if row["user_id"] in seen_followbacks:
                omitted["repeated_followback_snapshot"] += 1
                continue
            seen_followbacks.add(row["user_id"])
        clean.append({key: row[key] for key in CSV_COLUMNS})
    return clean, dict(omitted)


def summarize(rows, *, as_of: date):
    """Cuentos verificables, no score de relacion ni conversion atribuida.

    observed_followback_d7/d30 son minimos observados. Los sujetos sin
    evidencia no son no-seguidores: la cobertura de observaciones es parcial.
    """
    by_network = {n: Counter() for n in sorted(NETWORKS)}
    paths = defaultdict(list)
    for row in rows:
        network = row["network"]
        if network not in NETWORKS:
            raise ValueError("network invalida")
        when = _instant(row["timestamp"])
        if when.date() > as_of:
            raise ValueError("evento posterior a as_of")
        by_network[network][row["event"]] += 1
        paths[row["user_id"]].append((when, row["event"], network))
    transitions = Counter()
    cohort = {n: {str(days): {"eligible": 0, "observed_followback": 0}
                  for days in (7, 30)} for n in sorted(NETWORKS)}
    for seq in paths.values():
        # No inferir orden para dos acciones con hora identica.
        seq.sort(key=lambda r: r[0])
        for before, after in zip(seq, seq[1:]):
            if before[0] < after[0]:
                transitions[(before[2], before[1], after[1])] += 1
        follows = [r[0] for r in seq if r[1] == "follow.confirmed"]
        backs = [r[0] for r in seq if r[1] == "followback.present"]
        if not follows:
            continue
        first_follow = min(follows)
        net = seq[0][2]
        for days in (7, 30):
            if (as_of - first_follow.date()).days < days:
                continue  # censura temporal: ventana aun no cerrada
            bucket = cohort[net][str(days)]
            bucket["eligible"] += 1
            if any(first_follow <= back <= first_follow.replace(
                    ) + __import__("datetime").timedelta(days=days) for back in backs):
                bucket["observed_followback"] += 1
    return {
        "as_of": as_of.isoformat(),
        "events": len(rows), "paths": len(paths),
        "network_events": {n: dict(sorted(v.items())) for n, v in by_network.items()},
        "transitions_strict_time": [
            {"network": n, "from": a, "to": b, "count": count}
            for (n, a, b), count in sorted(transitions.items())
        ],
        "followback_observed_lower_bound": cohort,
    }


def write_csv(rows, path: str | Path):
    """Export opt-in; no incluye texto de posts ni credenciales."""
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def to_eventstream(rows):
    """REUTILIZACION REAL opcional de retentioneering (Apache-2.0).

    pip install retentioneering==5.2.4 en entorno analitico separado.
    No se importa en el pipeline de las nueve redes.
    """
    import pandas as pd  # dependencia transitiva de retentioneering
    import retentioneering as rete
    data = pd.DataFrame(
        [{key: row[key] for key in ("user_id", "event", "timestamp")} for row in rows],
        columns=("user_id", "event", "timestamp"),
    )
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)
    return rete.Eventstream(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", help="SQLite del ledger #84 (solo lectura)")
    parser.add_argument("--as-of", required=True, help="Fecha UTC YYYY-MM-DD")
    parser.add_argument("--export-csv", help="Salida CSV local opcional")
    args = parser.parse_args(argv)
    as_of = date.fromisoformat(args.as_of)
    rows, omitted = read_ledger(args.ledger)
    summary = summarize(rows, as_of=as_of)
    summary["omitted"] = omitted
    if args.export_csv:
        write_csv(rows, args.export_csv)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CRM de lectura local para las nueve redes. No ejecuta acciones ni crea estado.
Proyección sobre CSV ya existentes y un índice opcional de hilos verificados.
Los límites y procedencia se describen en docs/research/community-crm-loyalty.md.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import sys

NETWORKS = ("x", "threads", "facebook", "pinterest", "reddit", "bluesky",
            "mastodon", "tiktok", "instagram")
LANES = {"x": "WEB", "threads": "WEB", "facebook": "WEB",
         "pinterest": "WEB", "bluesky": "API", "mastodon": "API",
         "tiktok": "MOBILE", "instagram": "WEB"}
INBOUND_KINDS = {"comment", "like", "repost", "follow"}
OUTBOUND_KINDS = {"reply", "comment", "comentario", "comment_external", "respuesta",
                  "like", "favourite", "repost", "boost", "follow"}
CONFIRMED = {"confirmado", "publicado"}


def _handle(value: object) -> str:
    return str(value or "").strip().lstrip("@").casefold()


def _network(value: object) -> str:
    net = str(value or "").strip().casefold()
    if net not in NETWORKS:
        raise ValueError(f"Red desconocida: {net!r}")
    return net


def _day(value: object, context: str) -> date:
    # Nunca se deduce la fecha actual para un evento sin fecha.
    if not isinstance(value, str) or len(value) < 10:
        raise ValueError(f"Fecha ausente en {context}")
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ValueError(f"Fecha inválida en {context}") from exc


def _csv(path: Path, required: set[str], *, missing_ok: bool = False) -> list[dict[str, str]]:
    if not path.exists():
        if missing_ok:
            return []  # una red aún sin registro
        raise FileNotFoundError(f"CSV de entrada obligatorio inexistente: {path}")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not required.issubset(set(reader.fieldnames or ())):
            raise ValueError(f"Cabeceras incompletas: {path.name}")
        result = list(reader)
    if any(None in row for row in result):
        raise ValueError(f"CSV con columnas adicionales sin cabecera: {path.name}")
    return result


def _json(path: Path | None, default: object) -> object:
    if path is None:
        return default
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _contact(data: dict, net: str, handle: str) -> dict:
    key = f"{net}:{handle}"
    if key not in data:
        data[key] = {"network": net, "handle": handle, "lane": LANES.get(net, "UNASSIGNED"),
                     "tags": [], "last_inbound": None, "last_outbound": None,
                     "inbound": {kind: 0 for kind in sorted(INBOUND_KINDS)},
                     "outbound_confirmed": 0, "history": [], "pending": [],
                     "score": 0, "score_reasons": []}
    return data[key]


def build(inbound: Path, registries_root: Path, *, inbox: Path | None = None,
          labels: Path | None = None, as_of: date | None = None,
          window_days: int = 14, history_days: int = 90) -> dict:
    """Proyección determinista sobre ficheros locales explícitos.

    Los CSV inbound agregan cuenta/tipo/día. Inbox incorpora destinos por ref
    verificada, pero nunca suma de nuevo esos comentarios al contador.
    """
    today = as_of or date.today()
    if not isinstance(today, date) or window_days < 1 or history_days < window_days:
        raise ValueError("Fechas o ventanas inválidas")
    cutoff = today - timedelta(days=window_days - 1)
    historic = today - timedelta(days=history_days - 1)
    people: dict[str, dict] = {}
    daily_seen = set()
    active_days: dict[str, set] = {}
    for number, row in enumerate(_csv(inbound, {"fecha", "red", "handle", "tipo"}), 2):
        net = _network(row["red"])
        handle = _handle(row["handle"])
        kind = (row["tipo"] or "").strip().casefold()
        if not handle or kind not in INBOUND_KINDS:
            continue
        day = _day(row["fecha"], f"inbound:{number}")
        if not historic <= day <= today:
            continue
        dedup = (day, net, handle, kind)
        if dedup in daily_seen:
            continue
        daily_seen.add(dedup)
        c = _contact(people, net, handle)
        c["history"].append({"date": day.isoformat(), "direction": "in", "kind": kind})
        c["last_inbound"] = max(c["last_inbound"] or "", day.isoformat())
        if day >= cutoff:
            c["inbound"][kind] += 1
            active_days.setdefault(f"{net}:{handle}", set()).add(day)

    for net in NETWORKS:
        path = registries_root / f"SISTEMA_DIARIO_{net.upper()}" / "registro_interacciones.csv"
        for number, row in enumerate(_csv(path, {"fecha", "cuenta", "tipo", "resultado"}, missing_ok=True), 2):
            handle = _handle(row["cuenta"])
            kind = (row["tipo"] or "").strip().casefold()
            if not handle or any(part not in OUTBOUND_KINDS for part in kind.split("+")) or (row["resultado"] or "").strip().casefold() not in CONFIRMED:
                continue
            day = _day(row["fecha"], f"outbound:{net}:{number}")
            if not historic <= day <= today:
                continue
            c = _contact(people, net, handle)
            c["history"].append({"date": day.isoformat(), "direction": "out", "kind": kind})
            c["last_outbound"] = max(c["last_outbound"] or "", day.isoformat())
            c["outbound_confirmed"] += 1

    # Inbox es índice de destinos, no otra cosecha que aumente contadores.
    inbox_rows = _json(inbox, [])
    if not isinstance(inbox_rows, list):
        raise ValueError("inbox debe ser una lista JSON")
    refs = {}
    for pos, item in enumerate(inbox_rows):
        if not isinstance(item, dict):
            raise ValueError(f"Evento inbox inválido {pos}")
        net, handle = _network(item.get("network")), _handle(item.get("handle"))
        ref = item.get("ref")
        thread = item.get("thread") or ref
        answered = item.get("answered")
        if not handle or not isinstance(ref, str) or not ref.strip() or not isinstance(thread, str) or not thread.strip() or type(answered) is not bool:
            raise ValueError(f"Inbox incompleto {pos}: requiere ref/thread, handle y answered booleano")
        day = _day(item.get("date"), f"inbox:{pos}")
        if day > today:
            continue
        identity = (net, ref)
        old = refs.get(identity)
        if old and (old["handle"] != handle or old["thread"] != thread):
            raise ValueError(f"Ref con identidad/hilo contradictorios en {net}")
        quality = item.get("context_quality", "partial")
        if quality not in ("complete", "partial"):
            raise ValueError(f"Calidad de contexto inválida en inbox:{pos}")
        # Desempates reproducibles: answered gana, después contexto completo.
        if old is None or (day, answered, quality == "complete") > (old["day"], old["answered"], old["context_quality"] == "complete"):
            refs[identity] = {"network": net, "handle": handle, "ref": ref,
                              "thread": thread, "day": day, "answered": answered,
                              "context_quality": quality}
    # El mismo ref repetido se resuelve arriba (answered gana el empate).
    # Entre refs diferentes solo hay fechas por día: no se puede ordenar
    # dos mensajes del mismo día ni suponer que uno contestado cerró el otro.
    threads: dict[tuple[str, str, str], list[dict]] = {}
    for item in refs.values():
        key = (item["network"], item["handle"], item["thread"])
        threads.setdefault(key, []).append(item)
    for items in threads.values():
        newest_day = max(item["day"] for item in items)
        if newest_day < cutoff:
            continue
        latest = [item for item in items if item["day"] == newest_day]
        unanswered = [item for item in latest if not item["answered"]]
        if not unanswered:
            continue
        # Selección determinista del ref; cualquier empate entre refs exige
        # revisión de contexto, nunca cierre automático ni respuesta directa.
        item = min(unanswered, key=lambda entry: entry["ref"])
        ambiguous = len(latest) > 1
        c = _contact(people, item["network"], item["handle"])
        c["pending"].append({"ref": item["ref"], "thread": item["thread"],
                             "date": item["day"].isoformat(),
                             "context_quality": item["context_quality"],
                             "status": "review_context" if ambiguous or item["context_quality"] != "complete" else "review_reply"})

    tagmap = _json(labels, {})
    if not isinstance(tagmap, dict):
        raise ValueError("labels debe ser un objeto JSON")
    for key, tags in tagmap.items():
        if not isinstance(key, str) or ":" not in key or not isinstance(tags, list) or any(not isinstance(t, str) or not t.strip() or len(t) > 40 for t in tags):
            raise ValueError(f"Etiqueta inválida: {key!r}")
        net, handle = key.split(":", 1)
        canonical = f"{_network(net)}:{_handle(handle)}"
        if canonical in people:
            people[canonical]["tags"] = sorted({t.strip() for t in tags})

    result = []
    for key, c in people.items():
        counts = c["inbound"]
        recent = bool(active_days.get(key))
        # Triage explicable, no sustituye el experimento de scoring #69.
        parts = {"comments": 3 * min(counts["comment"], 3),
                 "reposts": 2 * min(counts["repost"], 2),
                 "follows": 2 * min(counts["follow"], 1),
                 "likes": min(counts["like"], 2),
                 "repeat_days": 2 if len(active_days.get(key, ())) >= 2 else 0,
                 "recency": (3 if (today - max(active_days[key])).days <= 2 else
                             2 if (today - max(active_days[key])).days <= 7 else 1) if recent else 0,
                 "pending": 5 if c["pending"] else 0}
        c["score"] = sum(parts.values())
        c["score_reasons"] = [f"{k}:+{v}" for k, v in parts.items() if v]
        c["history"].sort(key=lambda x: (x["date"], x["direction"], x["kind"]))
        c["pending"].sort(key=lambda x: (x["date"], x["ref"]), reverse=True)
        result.append(c)
    result.sort(key=lambda x: (-bool(x["pending"]), -x["score"], -(date.fromisoformat(x["last_inbound"]).toordinal() if x["last_inbound"] else 0), x["network"], x["handle"]))
    return {"schema": 1, "as_of": today.isoformat(), "window_days": window_days,
            "inbox_coverage": "absent" if inbox is None else "provided_completeness_unknown",
            "contacts": result, "pending_threads": sum(len(c["pending"]) for c in result),
            "by_lane": {lane: sum(len(c["pending"]) for c in result if c["lane"] == lane)
                        for lane in ("WEB", "API", "MOBILE", "UNASSIGNED")}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbound", required=True, type=Path)
    parser.add_argument("--registries-root", required=True, type=Path)
    parser.add_argument("--inbox", type=Path, help="Export offline de respuestas con ref/answered verificados")
    parser.add_argument("--labels", type=Path, help="Etiquetas explícitas JSON, sin notas libres")
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--window-days", type=int, default=14)
    parser.add_argument("--history-days", type=int, default=90)
    args = parser.parse_args(argv)
    try:
        data = build(args.inbound, args.registries_root, inbox=args.inbox,
                     labels=args.labels, as_of=args.as_of,
                     window_days=args.window_days, history_days=args.history_days)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"community_crm: {exc}", file=sys.stderr)
        return 2
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

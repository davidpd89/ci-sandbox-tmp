"""TikTok inbox relationship observations: offline, fail-closed, no account I/O.

This module deliberately does NOT issue follow/like/comment events, write state,
contact TikTok, or call relationship_policy.log_inbound. A new-follower UI row
is not a notification ID or reliable timestamp of a new follow.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any

MAX_INPUT_BYTES = 64 * 1024
MAX_ROWS = 200
_HANDLE = re.compile(r"[A-Za-z0-9._]{2,32}\Z", re.ASCII)
ORIGIN = "inbox:new_follower"
# ISO 8601 calendar timestamp, explicit offset and seconds (not a TikTok event time).
_TIMESTAMP = re.compile(
    r"[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])\Z"
)
MAX_JSON_DEPTH = 8


class InvalidObservation(ValueError):
    """An input cannot be interpreted as a trustworthy UI observation."""


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise InvalidObservation("observed_at debe ser ISO 8601 con zona horaria")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidObservation("observed_at no es una fecha ISO válida") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidObservation("observed_at requiere zona horaria")
    return parsed.isoformat()


def _handle(value: Any) -> str | None:
    if not isinstance(value, str) or value != value.strip():
        return None
    raw = value.removeprefix("@")
    if not _HANDLE.fullmatch(raw):
        return None  # reject Unicode lookalikes before case conversion
    norm = raw.lower()
    return norm if norm != "davidportoescritor" else None


def summarize(snapshot: dict[str, Any], *, include_handles: bool = False) -> dict[str, Any]:
    """Classify explicitly supplied screenshots/rows, never invent inbound events.

    The input is a declaration of an observation, not authenticated TikTok data.
    It needs owner confirmation + a row reached from the inbox + matching relation
    on the destination profile. These are still not proof of a new follow event.
    """
    if not isinstance(snapshot, dict) or type(snapshot.get("schema")) is not int or snapshot["schema"] != 1:
        raise InvalidObservation("schema debe ser 1")
    stamp = _timestamp(snapshot.get("observed_at"))
    if type(snapshot.get("owner_account_checked")) is not bool:
        raise InvalidObservation("owner_account_checked debe ser booleano")
    rows = snapshot.get("rows")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise InvalidObservation("rows debe ser una lista acotada")

    accepted: set[str] = set()
    rejected: Counter[str] = Counter()
    for row in rows:
        if not isinstance(row, dict):
            rejected["fila_invalida"] += 1
            continue
        # Un conteo o un comentario leído en un vídeo ajeno no prueban
        # que esa persona haya interactuado con nuestra cuenta.
        if row.get("source") != ORIGIN:
            rejected["origen_no_acreditado"] += 1
            continue
        if snapshot["owner_account_checked"] is not True:
            rejected["cuenta_no_comprobada"] += 1
            continue
        handle = _handle(row.get("handle"))
        if not handle:
            rejected["identidad_no_acreditada"] += 1
            continue
        if (row.get("inbox_relation") != "follows_me"
                or row.get("profile_relation") != "follows_me"
                or row.get("navigation_provenance") != "profile_opened_from_inbox_row"):
            rejected["relacion_no_corroborrada"] += 1
            continue
        if handle in accepted:
            rejected["duplicada_en_lectura"] += 1
            continue
        accepted.add(handle)

    report = {
        "schema": 1,
        "observed_at": stamp,
        "scope": ORIGIN,
        "coverage": "parcial_declarada_sin_verificacion_remota",
        "relationships_observed": len(accepted),
        "rejected_by_reason": dict(sorted(rejected.items())),
        "new_follow_events": None,
        "inbound_comment_events": None,
        "inbound_like_events": None,
        "event_ids": None,
        "event_time": None,
        "eligible_for_inbound_ledger": False,
        "eligible_for_auto_rewards": False,
    }
    if include_handles is True:
        report["handles"] = sorted(accepted)
    return report


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject contradictory JSON fields instead of trusting the last one."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidObservation("clave JSON duplicada")
        result[key] = value
    return result


def _no_nonfinite(_value: str) -> None:
    raise InvalidObservation("valor JSON no finito")


def _check_json_structure(data: Any) -> Any:
    """Cap nested fields even if they are otherwise ignored by the report."""
    stack = [(data, 0)]
    count = 0
    while stack:
        value, depth = stack.pop()
        count += 1
        if depth > MAX_JSON_DEPTH or count > 10000:
            raise InvalidObservation("JSON supera el límite de profundidad o elementos")
        if isinstance(value, dict):
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)
    return data


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            raise InvalidObservation("archivo supera el límite de 64 KiB")
        return _check_json_structure(json.loads(
            data.decode("utf-8-sig"), object_pairs_hook=_unique_object,
            parse_constant=_no_nonfinite))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InvalidObservation(f"archivo no válido: {type(exc).__name__}") from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Vista offline de relaciones TikTok (sin escrituras)")
    parser.add_argument("--input", type=Path, required=True, help="JSON sintético/normalizado local")
    parser.add_argument("--show-handles", action="store_true", help="mostrar identificadores de terceros en consola")
    args = parser.parse_args(argv)
    try:
        data = summarize(_read_json(args.input), include_handles=args.show_handles)
    except InvalidObservation as exc:
        parser.error(str(exc))
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

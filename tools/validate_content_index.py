from __future__ import annotations

import argparse
import json
from pathlib import Path


VALID_STATES = {
    "idea",
    "borrador",
    "revision",
    "revision_david",
    "lista_para_programar",
    "programada",
    "programado",
    "publicado",
}
VALID_CATEGORIES = {"interes", "autor_proceso", "libro_cta", "70", "20", "10"}
VALID_REDS = {
    "instagram",
    "facebook",
    "tiktok",
    "threads",
    "bluesky",
    "youtube",
    "pinterest",
    "linkedin",
    "gbp",
    "x",
}
VALID_FORMATS = {
    "reel",
    "short",
    "tiktok",
    "carrusel",
    "quote_card",
    "imagen",
    "post",
    "thread",
    "pin",
    "story",
    "video",
    "foto_suelta",
    "reel_simple",
    "carrusel_guardable",
}


def as_list(value: object) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def validate_record(record: dict, line_no: int, seen_ids: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    record_id = record.get("id")
    if not record_id:
        errors.append(f"line {line_no}: missing id")
    elif record_id in seen_ids:
        errors.append(f"line {line_no}: duplicate id {record_id}")
    else:
        seen_ids.add(str(record_id))

    state_raw = record.get("estado")
    state = str(state_raw).strip().lower() if state_raw is not None else ""
    if state not in VALID_STATES:
        errors.append(f"line {line_no}: invalid estado {state_raw!r}")

    category_raw = record.get("categoria_70_20_10")
    category = str(category_raw).strip().lower() if category_raw is not None else ""
    if category not in VALID_CATEGORIES:
        errors.append(f"line {line_no}: invalid categoria_70_20_10 {category_raw!r}")

    red = record.get("red")
    reds = as_list(red)
    if not reds or any(item not in VALID_REDS for item in reds):
        errors.append(f"line {line_no}: invalid red {red!r}")

    formato_raw = record.get("formato")
    formato = str(formato_raw).strip().lower() if formato_raw is not None else ""
    if formato not in VALID_FORMATS:
        errors.append(f"line {line_no}: invalid formato {formato_raw!r}")

    if state in {"lista_para_programar", "programada", "programado"}:
        if not record.get("fuente_real"):
            errors.append(f"line {line_no}: {state} without fuente_real")
        if record.get("qa_status") not in {None, "", "pass"}:
            errors.append(f"line {line_no}: {state} with qa_status not pass")

    if not record.get("hook"):
        warnings.append(f"line {line_no}: missing hook")
    if not record.get("asset_ids"):
        warnings.append(f"line {line_no}: missing asset_ids")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate content_index.jsonl")
    parser.add_argument("path", nargs="?", default="content_index.jsonl")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"[WARN] {path}: missing")
        return 0
    lines = [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    if not lines:
        print(f"[WARN] {path}: exists but has no records")
        return 0

    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    for line_no, line in enumerate(lines, 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: invalid JSON ({exc.msg})")
            continue
        if not isinstance(record, dict):
            errors.append(f"line {line_no}: record must be an object")
            continue
        rec_errors, rec_warnings = validate_record(record, line_no, seen_ids)
        errors.extend(rec_errors)
        warnings.extend(rec_warnings)

    status = "FAIL" if errors else "PASS"
    print(f"[{status}] {path}: {len(lines)} record(s)")
    for err in errors:
        print(f"  error: {err}")
    for warn in warnings:
        print(f"  warn: {warn}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

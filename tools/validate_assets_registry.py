from __future__ import annotations

import argparse
import csv
from pathlib import Path


EXPECTED_HEADER = [
    "asset_id",
    "path",
    "tipo",
    "fuente",
    "licencia_uso",
    "descripcion_visual",
    "personas_detectadas",
    "texto_visible",
    "uso_recomendado",
    "redes_formatos",
    "piezas_usadas",
    "ultima_vez_usado",
    "riesgo_repeticion",
    "requiere_limpieza_fondo",
    "notas_qa",
]

VALID_RISK = {"", "null", "bajo", "medio", "alto"}
VALID_CLEAN = {"", "null", "si", "no"}
LOCAL_SOURCES = {"", "null", "propio", "local", "david", "asset_propio", "repo"}


def is_external(row: dict[str, str]) -> bool:
    fuente = row.get("fuente", "").strip().lower()
    path = row.get("path", "").strip().lower()
    if fuente and fuente not in LOCAL_SOURCES:
        return True
    return any(token in path for token in ["pexels", "pixabay", "unsplash", "stock", "api"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate assets_registry.csv")
    parser.add_argument("path", nargs="?", default="assets_registry.csv")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"[WARN] {path}: missing")
        return 0

    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        if header != EXPECTED_HEADER:
            print(f"[FAIL] {path}: invalid header")
            print(f"  expected: {EXPECTED_HEADER}")
            print(f"  actual:   {header}")
            return 1
        rows = list(reader)

    if not rows:
        print(f"[WARN] {path}: header exists but has no asset rows")
        return 0

    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    for row_no, row in enumerate(rows, 2):
        asset_id = row.get("asset_id", "").strip()
        if not asset_id:
            errors.append(f"row {row_no}: missing asset_id")
        elif asset_id in seen_ids:
            errors.append(f"row {row_no}: duplicate asset_id {asset_id}")
        else:
            seen_ids.add(asset_id)

        if not row.get("path", "").strip():
            errors.append(f"row {row_no}: missing path")
        if is_external(row) and not row.get("licencia_uso", "").strip():
            errors.append(f"row {row_no}: external asset without licencia_uso")

        risk = row.get("riesgo_repeticion", "").strip().lower()
        if risk not in VALID_RISK:
            errors.append(f"row {row_no}: invalid riesgo_repeticion {risk!r}")

        clean = row.get("requiere_limpieza_fondo", "").strip().lower()
        if clean not in VALID_CLEAN:
            errors.append(f"row {row_no}: invalid requiere_limpieza_fondo {clean!r}")

        if not row.get("descripcion_visual", "").strip():
            warnings.append(f"row {row_no}: missing descripcion_visual")

    status = "FAIL" if errors else "PASS"
    print(f"[{status}] {path}: {len(rows)} asset row(s)")
    for err in errors:
        print(f"  error: {err}")
    for warn in warnings:
        print(f"  warn: {warn}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Limpieza de boosts caducados (29/09) - mismo patron que
bluesky_cleanup_ttl.py/x_cleanup_ttl.py: el impacto a corto plazo de un
boost no exige que quede fijado para siempre en el perfil propio. Borra
SOLO los boosts que `mastodon_execute.py` programo el mismo dia que se
crearon (columna `borrar_el` en `boost_ttl.csv`), nunca un favourite ni
una reply propia.

No es parte de la ronda de crecimiento diaria - es mantenimiento de perfil,
se ejecuta aparte:

    python tools/mastodon_cleanup_ttl.py
    python tools/mastodon_cleanup_ttl.py --dry-run

Mismo criterio de seguridad que el resto de limpiezas TTL: un rate limit
real detiene el resto del lote en vez de seguir insistiendo, y cada fila
procesada se marca en el CSV al momento (no se reconstruye el archivo
entero al final), asi un corte a mitad de ejecucion no pierde el registro
de lo que ya se retiro.
"""
import csv
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import mastodon_interact as m
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_MASTODON")
TTL_CSV = os.path.join(ROOT, "boost_ttl.csv")

FIELDS = ["fecha", "acct", "status_id", "url", "borrar_el", "estado"]


def _load_rows(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    with open(path, encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise RuntimeError(
                f"{path}: cabecera inesperada {reader.fieldnames!r}, se esperaba {FIELDS!r}"
            )
        return list(reader)


def _write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def due_rows(rows, today):
    due = []
    for row in rows:
        if row.get("estado") != "pendiente":
            continue
        try:
            borrar_el = datetime.date.fromisoformat(row["borrar_el"])
        except (KeyError, ValueError):
            continue
        if borrar_el <= today:
            due.append(row)
    return due


def run(dry_run=False, today=None):
    today = today or datetime.date.today()
    rows = _load_rows(TTL_CSV)
    pending = due_rows(rows, today)
    print(f"{len(rows)} filas en el registro; {len(pending)} vencidas hoy ({today.isoformat()}).")
    if not pending:
        return rows

    if dry_run:
        for row in pending:
            print(f"  [dry-run] retiraria boost {row['acct']} -> {row['status_id']}")
        return rows

    for index, row in enumerate(pending):
        print(f"=== retirar boost {row['acct']} ({row['status_id']}) ===")
        try:
            m.unboost(row["status_id"])
            row["estado"] = "retirado"
        except m.MastodonRateLimitExceeded as exc:
            print(f"PARADA RATE LIMIT: {exc}")
            _write_rows(TTL_CSV, rows)
            print("Progreso guardado; el resto queda pendiente para la próxima ejecución.")
            return rows
        except Exception as exc:
            print(f"FALLO: {type(exc).__name__}: {exc}")
            row["estado"] = f"fallo:{exc}"
        _write_rows(TTL_CSV, rows)
        if index < len(pending) - 1:
            sc.pause(3, 8)

    retirados = sum(1 for row in pending if row["estado"] == "retirado")
    print(f"\n{retirados}/{len(pending)} boosts retirados correctamente.")
    return rows


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in argv
    run(dry_run=dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

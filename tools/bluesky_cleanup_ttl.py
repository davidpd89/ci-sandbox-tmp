"""
Limpieza de reposts/citas caducados (29/09) - pedido explicito de David: el
impacto a corto plazo de repostear/citar no exige que el registro se quede
fijado para siempre en el perfil propio. Este script borra SOLO los
registros de repost/cita que `bluesky_execute.py` programo el mismo dia que
se crearon (columna `borrar_el` en `repost_quote_ttl.csv`), nunca el post
original de otra cuenta ni una publicacion propia normal.

No es parte de la ronda de crecimiento diaria - es mantenimiento de perfil,
se ejecuta aparte (antes o despues de una ronda, o de forma independiente):

    python tools/bluesky_cleanup_ttl.py
    python tools/bluesky_cleanup_ttl.py --dry-run

Mismo criterio de seguridad que bluesky_execute.py: un 429 detiene el resto
del lote en vez de seguir insistiendo, y cada fila procesada se marca en el
CSV al momento (no se reconstruye el archivo entero al final), asi un corte
a mitad de ejecucion no pierde el registro de lo que ya se borro.
"""
import csv
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import bluesky_interact as b
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY")
TTL_CSV = os.path.join(ROOT, "repost_quote_ttl.csv")

RateLimitExceeded = getattr(
    b,
    "RateLimitExceeded",
    type("_NoRateLimitExceeded", (Exception,), {}),
)

FIELDS = ["fecha", "kind", "handle", "own_uri", "target_url", "borrar_el", "estado"]


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
    """Filas pendientes cuya fecha de borrado ya llegó (o pasó)."""
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
            print(f"  [dry-run] borraria {row['kind']} {row['handle']} -> {row['own_uri']}")
        return rows

    for index, row in enumerate(pending):
        # Los TTL retiran acciones públicas: también son escrituras remotas.
        # Una cuarentena sobrevenida no debe permitir más borrados.
        import circuit_breaker as cb
        allowed, reason = cb.write_preflight("bluesky")
        if not allowed:
            print(f"[bluesky] cortacircuitos ABIERTO: {reason}; TTL pendientes conservados")
            break
        print(f"=== borrar {row['kind']} {row['handle']} ({row['own_uri']}) ===")
        try:
            b.delete_own_record(row["own_uri"])
            row["estado"] = "borrado"
        except RateLimitExceeded as exc:
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

    borrados = sum(1 for row in pending if row["estado"] == "borrado")
    print(f"\n{borrados}/{len(pending)} registros borrados correctamente.")
    return rows


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in argv
    run(dry_run=dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Limpieza de reposts/citas caducados (29/09) - mismo patron que
bluesky_cleanup_ttl.py/mastodon_cleanup_ttl.py: el impacto a corto plazo de
repostear/citar no exige que el registro se quede fijado para siempre en el
perfil propio. Borra SOLO lo que `x_execute.py` programo el mismo dia que se
creo (columna `borrar_el` en `reposts_activos.csv`, ventana de 21 dias ya
establecida en REGLAS.md), nunca el post original de otra cuenta ni una
respuesta normal.

Un repost se deshace sobre la URL original con unrepost(); una cita se borra
como post propio con delete_post() sobre su own_uri (sin own_uri localizado
en su momento, la fila no se llega a crear - ver _append_repost_ttl en
x_execute.py).

No es parte de la ronda diaria - es mantenimiento de perfil, se ejecuta
aparte:

    python tools/x_cleanup_ttl.py
    python tools/x_cleanup_ttl.py --dry-run
"""
import csv
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import x_interact as x
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_X")
TTL_CSV = os.path.join(ROOT, "reposts_activos.csv")

FIELDS = ["fecha", "kind", "handle", "url", "own_uri", "borrar_el", "estado"]


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
            target = row["url"] if row["kind"] == "repost" else row["own_uri"]
            print(f"  [dry-run] borraria {row['kind']} {row['handle']} -> {target}")
        return rows

    for index, row in enumerate(pending):
        # Los TTL retiran acciones públicas: también son escrituras remotas.
        # Una cuarentena sobrevenida no debe permitir más borrados.
        import circuit_breaker as cb
        allowed, reason = cb.write_preflight("x")
        if not allowed:
            print(f"[x] cortacircuitos ABIERTO: {reason}; TTL pendientes conservados")
            break
        target = row["url"] if row["kind"] == "repost" else row["own_uri"]
        print(f"=== borrar {row['kind']} {row['handle']} ({target}) ===")
        try:
            if row["kind"] == "repost":
                x.unrepost(row["url"])
            else:
                x.delete_post(row["own_uri"])
            row["estado"] = "borrado"
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
    if not dry_run:
        x.ensure_browser()
    run(dry_run=dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

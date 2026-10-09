"""Auditar y, opcionalmente, reclasificar descartes editoriales históricos R11.

Solo lectura por defecto. Para aplicar, detener antes TODOS los ejecutores,
indicar --apply --offline-confirmed y crear un backup SQLite exclusivo.
Nunca se modifica created/updated ni se reclasifican acciones remotas reales.
"""
import argparse
import contextlib
import os
import pathlib
import sqlite3

from action_ledger import CONFIRMED, SKIPPED_POLICY, OUTCOME_CLASS, _outcome_key


def _connect_existing(path, *, readonly=False):
    """La auditoría usa mode=ro; solo la fase --apply solicita mode=rw."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    mode = "ro" if readonly else "rw"
    return sqlite3.connect(pathlib.Path(path).resolve().as_uri() + f"?mode={mode}",
                           uri=True, timeout=30, isolation_level=None)


def _eligible(detail):
    classification = OUTCOME_CLASS.get(_outcome_key(detail))
    return classification is not None and classification[0] == SKIPPED_POLICY


def summary(db):
    """Distribución completa status/motivo; equivale al SELECT de auditoría R11."""
    with contextlib.closing(_connect_existing(db, readonly=True)) as conn:
        return conn.execute(
            "SELECT status, substr(COALESCE(detail,''),1,25) AS prefix, count(*) "
            "FROM actions GROUP BY status, prefix ORDER BY status, prefix"
        ).fetchall()


def candidates(db):
    """Filas históricas mal confirmadas; lectura sin modificar la base."""
    with contextlib.closing(_connect_existing(db, readonly=True)) as conn:
        rows = conn.execute(
            "SELECT kind,target,detail,created,updated "
            "FROM actions WHERE status=?", (CONFIRMED,),
        ).fetchall()
    return [row for row in rows if _eligible(row[2])]


def apply(db, backup, *, offline_confirmed=False):
    """Migración reversible SOLO tras parar ejecutores; el backup no se pisa."""
    if not offline_confirmed:
        raise ValueError("Confirma que no hay ejecutores activos: --offline-confirmed")
    if os.path.abspath(db) == os.path.abspath(backup):
        raise ValueError("El backup no puede sobrescribir el ledger")
    if not os.path.isfile(db):
        raise FileNotFoundError(db)
    # O_EXCL evita sobrescribir una copia anterior.
    fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with contextlib.closing(_connect_existing(db)) as src, \
             contextlib.closing(sqlite3.connect(backup)) as dest:
            src.backup(dest)  # snapshot SQLite consistente, también en WAL
            if dest.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise sqlite3.DatabaseError("Backup SQLite no supera PRAGMA quick_check")
    except BaseException:
        os.unlink(backup)
        raise
    with contextlib.closing(_connect_existing(db)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            rows = conn.execute(
                "SELECT kind,target,detail,created,updated "
                "FROM actions WHERE status=?", (CONFIRMED,),
            ).fetchall()
            migrated = 0
            for kind, target, detail, created, updated in rows:
                if not _eligible(detail):
                    continue
                migrated += conn.execute(
                    "UPDATE actions SET status=? WHERE kind=? AND target=? "
                    "AND status=? AND detail=? AND created=? AND updated=?",
                    (SKIPPED_POLICY, kind, target, CONFIRMED,
                     detail, created, updated),
                ).rowcount
            conn.execute("COMMIT")
            return migrated
        except BaseException:
            conn.execute("ROLLBACK")
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--offline-confirmed", action="store_true")
    parser.add_argument("--backup")
    opts = parser.parse_args(argv)
    print(f"Motor SQLite Python: {sqlite3.sqlite_version}")
    print("Estado | prefijo del motivo (25 caracteres) | filas")
    for status, prefix, count in summary(opts.db):
        print(f"  {status} | {prefix} | {count}")
    rows = candidates(opts.db)
    print(f"confirmed históricas elegibles: {len(rows)}")
    for code in sorted({_outcome_key(row[2]) for row in rows}):
        print(f"  {code}: {sum(_outcome_key(row[2]) == code for row in rows)}")
    if opts.apply:
        if not opts.backup:
            parser.error("--apply requiere --backup con ruta nueva")
        migrated = apply(opts.db, opts.backup, offline_confirmed=opts.offline_confirmed)
        print(f"reclasificadas: {migrated}")
    else:
        print("Solo lectura; no se han modificado filas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

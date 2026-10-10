"""X: reserva persistente de posts y cuentas candidatos (06/10/2026).

Misma reserva que Threads (`browser_pool.py`): el scan guarda todo lo que ve —posts de las busquedas Recientes con scroll, cuentas de la pestana Personas y de las listas de
seguidores de las cuentas semilla del nicho— y el constructor del plan elige entre lo acumulado: posts recientes, del nicho, en ESPANOL (X asigna idioma a cada post: `lang`), de cuentas
con las que aun no hemos hecho nada, uno por cuenta. Descubrir (caro: carga paginas) queda desacoplado de ejecutar.

    python tools/x_pool.py stats
    python tools/x_pool.py top [--n 20]
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import browser_pool as bpool
from browser_pool import (add_seeds, due_seeds, estimated_age_hours, first_touch, fragment_key, mark, mark_account, mark_seed, pick, pick_accounts, stats)  # noqa: F401

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_X")
DB_PATH = os.path.join(ROOT, "cache", "pool.sqlite3")
MY_HANDLE = "davidportodiaz"


def connect(path=None):
    """RRSS_X_POOL_PATH aisla los tests de la reserva real."""
    return bpool.connect(path or os.environ.get("RRSS_X_POOL_PATH") or DB_PATH)


def record_posts(db, posts, source, today=None):
    """posts: dicts de `x_interact.extract_posts` (handle, url, text, lang, age_hours, repost, pinned). Los reposts y fijados no se guardan (el autor del permalink si cuenta,
    pero el texto ya lo habria traido su propio post). Devuelve cuantos eran nuevos."""
    rows = [(p["handle"], p["url"], p["text"], source, p.get("age_hours"), p.get("lang")) for p in posts if p["handle"].casefold() != MY_HANDLE and not p.get("pinned")]
    return bpool.record_post_rows(db, rows, today)


def record_accounts(db, rows, today=None):
    return bpool.record_accounts(db, rows, MY_HANDLE, today)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    db = connect()
    try:
        if argv and argv[0] == "top":
            n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 20
            for row in pick(db, n):
                print(f"{row['score']:>5} @{row['handle']:<28} {row['source']:<28} {row['text'][:90]!r}")
        else:
            print(json.dumps(stats(db), ensure_ascii=False))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

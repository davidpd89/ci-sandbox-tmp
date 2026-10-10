"""Facebook: reserva persistente de posts candidatos (06/10/2026).

Hasta hoy `facebook_scan.py` sobrescribia `facebook_candidates.json` cada dia con lo que veia ese dia y la ronda actuaba sobre eso: sin memoria ni atribucion, y el filtro solo
descartaba politica, de ahi religion y famosos. Ahora el scan GUARDA todo lo visto en la reserva comun (`browser_pool.py`, la misma de Threads y X) con su fuente first-touch
(hashtag o busqueda) y el constructor del plan elige entre lo acumulado con un clasificador positivo (senales de libros/lectura/escritura) y uno negativo (religion, famosos...).

El «handle» de Facebook es el nombre visible de la pagina/persona (no hay arroba): vale como clave de cuenta.

    python tools/facebook_pool.py stats
    python tools/facebook_pool.py top [--n 20]
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import browser_pool as bpool
from browser_pool import (add_seeds, due_seeds, estimated_age_hours, first_touch, fragment_key, mark, mark_account, mark_seed, pick, pick_accounts, stats)  # noqa: F401

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_FACEBOOK")
DB_PATH = os.path.join(ROOT, "cache", "pool.sqlite3")
MY_NAME = "David Porto Escritor"


def connect(path=None):
    """RRSS_FACEBOOK_POOL_PATH aisla los tests de la reserva real."""
    return bpool.connect(path or os.environ.get("RRSS_FACEBOOK_POOL_PATH") or DB_PATH)


def record_posts(db, rows, source, today=None):
    """rows: [(autor, permalink, texto)] como los devuelve `facebook_interact.get_hashtag_data/get_search_data`. Devuelve cuantos eran nuevos."""
    out = [(author, permalink, text, source, None, None) for author, permalink, text in rows if author and author.casefold() != MY_NAME.casefold()]
    return bpool.record_post_rows(db, out, today)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    db = connect()
    try:
        if argv and argv[0] == "top":
            n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 20
            for row in pick(db, n):
                print(f"{row['score']:>5} {row['handle'][:28]:<28} {row['source'][:30]:<30} {row['text'][:90]!r}")
        else:
            print(json.dumps(stats(db), ensure_ascii=False))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

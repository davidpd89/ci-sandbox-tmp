"""Ranking de hashtags de Mastodon por alcance real (03/10, solo lectura, 1 llamada por tag).

`GET /api/v1/tags/:name` devuelve `history` (usos y cuentas por dia, ultima semana). Con eso se ve
que etiquetas del growth_config merecen tiempo (muchas cuentas distintas) y cuales estan casi
muertas, y se prueban candidatas nuevas del nicho sin servicio externo.

    python tools/hashtag_report.py                 # tags de growth_config.json
    python tools/hashtag_report.py Fantasia Rol    # etiquetas concretas
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.join(os.path.dirname(__file__), "..")
CANDIDATES = ["Fantasia", "LiteraturaFantastica", "NovelaFantastica", "ScienceFictionBooks", "Poesia",
              "Escritores", "Rol", "Booktok", "SciFiBooks", "Lectores", "AutoPublicacion", "Cuentos"]


def weekly(history):
    """(usos, cuentas-dia, dias con datos) de la semana; `history` viene como cadenas."""
    uses = sum(int(day.get("uses") or 0) for day in history)
    accounts = sum(int(day.get("accounts") or 0) for day in history)
    return uses, accounts, len(history)


def rank(infos):
    """infos: {tag: respuesta de la API} -> filas ordenadas por cuentas distintas (alcance)."""
    rows = []
    for tag, info in infos.items():
        uses, accounts, days = weekly(info.get("history") or [])
        rows.append({"tag": tag, "uses": uses, "accounts": accounts,
                     "uses_per_account": round(uses / accounts, 2) if accounts else None})
    return sorted(rows, key=lambda r: -r["accounts"])


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    import mastodon_interact as m
    if argv:
        tags, source = argv, "pedidas"
    else:
        with open(os.path.join(ROOT, "SISTEMA_DIARIO_MASTODON", "growth_config.json"), encoding="utf-8") as stream:
            configured = json.load(stream).get("hashtags", [])
        tags, source = configured + [t for t in CANDIDATES if t not in configured], "config + candidatas"
    infos = {}
    for tag in tags:
        try:
            infos[tag] = m.tag_info(tag)
        except Exception as exc:
            print(f"  {tag}: sin datos ({str(exc)[:50]})")
    print(f"hashtags ({source}), ultima semana: cuentas distintas/dia acumuladas, usos")
    for row in rank(infos):
        print(f"  #{row['tag']:<22} cuentas {row['accounts']:>5}  usos {row['uses']:>5}  usos/cuenta {row['uses_per_account']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

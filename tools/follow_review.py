"""Revision de follows sin devolver tras N dias (03/10) - SOLO LECTURA.

Regla vigente (Bluesky COMUNIDAD.md, Mastodon REGLAS.md): no hay unfollow en lote y
solo se plantea dejar de seguir pasado un mes completo sin ninguna senal de vuelta.
Este informe lista, sin tocar nada, a quien seguimos desde hace >= N dias y no nos
sigue de vuelta, con lo que se le hizo (like/reply/boost) para que David decida.
Una relacion con reply o conversacion real merece mas paciencia que un follow frio.

    python tools/follow_review.py bluesky [--days 30]
    python tools/follow_review.py mastodon [--days 30]
"""
import datetime
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import growth_attribution as ga

ROOT = ga.ROOT


def review(rows, followers, today, days=30, *, network=None):
    """Devuelve lista de dicts {account, since, age_days, actions} de follows
    confirmados con >= `days` dias que NO estan en `followers`."""
    followed = {}
    actions = defaultdict(set)
    for row in rows:
        kind = row.get("tipo", "")
        outcome = row.get("resultado")
        if outcome not in ("confirmado", "publicado") and not (
                kind == "unfollow" and outcome == "saltado_ya_no_seguido"):
            continue
        account = ga.norm(row.get("cuenta"))
        if not account or account.startswith("https"):
            continue
        parts = set(kind.split("+"))
        if parts & ga.FOLLOW_KINDS:
            try:
                when = datetime.date.fromisoformat((row.get("fecha") or "")[:10])
            except ValueError:
                continue
            if account not in followed or when < followed[account]:
                followed[account] = when
        if kind == "unfollow":
            followed.pop(account, None)
            actions.pop(account, None)  # una nueva relacion no hereda conversaciones antiguas
            continue
        if account in followed:
            actions[account] |= {part for part in parts if part not in ga.FOLLOW_KINDS and part}
    followers = {ga.norm(f) for f in followers}
    out = []
    for account, since in followed.items():
        age = (today - since).days
        if age < days or any((account == f if network == "mastodon" else ga._same(account, f)) for f in followers):
            continue
        out.append({"account": account, "since": since.isoformat(), "age_days": age,
                    "actions": ga.combo(actions[account])})
    return sorted(out, key=lambda r: (r["actions"] != "solo_follow", -r["age_days"]))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("bluesky", "mastodon"):
        print(__doc__)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 30
    net = argv[0]
    rows = ga.load_registro(os.path.join(ROOT, f"SISTEMA_DIARIO_{net.upper()}", "registro_interacciones.csv"))
    followers = ga.bluesky_followers() if net == "bluesky" else ga.mastodon_followers()
    result = review(rows, followers, datetime.date.today(), days, network=net)
    print(f"{net}: {len(result)} follows de >= {days} dias sin devolver ({len(followers)} seguidores reales)")
    for item in result[:40]:
        print(f"  {item['since']} ({item['age_days']}d) {item['account']:<40} {item['actions']}")
    if len(result) > 40:
        print(f"  ... y {len(result) - 40} mas")
    print("Solo informe: no se ha dejado de seguir a nadie.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

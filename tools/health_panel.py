"""Panel de salud de la automatizacion (03/10): las señales que importan con volumen alto.

No hay umbrales publicos de moderacion, asi que se miden las señales que suelen delatar
automatizacion o que indican que el volumen ya no rinde (propuesta de ChatGPT, 03/10):

* acciones por dia y mezcla (like/follow/reply...);
* objetivos unicos / acciones y % de acciones sobre cuentas ya tocadas en los ultimos 7 dias;
* follow-back real de los follows con >= 7 dias (curva marginal: si baja al subir el volumen,
  se ha encontrado el techo economico aunque la API permita mas);
* 429 / errores en los logs de las rondas;
* relacion seguidos/seguidores.

    python tools/health_panel.py bluesky [--days 7]
    python tools/health_panel.py mastodon [--days 7]
"""
import datetime
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import growth_attribution as ga

ROOT = ga.ROOT


def window_stats(rows, today, days=7):
    """Metricas de acciones confirmadas en los ultimos `days` dias."""
    cutoff = today - datetime.timedelta(days=days)
    actions, per_day, kinds = [], Counter(), Counter()
    touched_before = set()
    for row in rows:
        if row.get("resultado") not in ("confirmado", "publicado"):
            continue
        try:
            when = datetime.date.fromisoformat((row.get("fecha") or "")[:10])
        except ValueError:
            continue
        account = ga.norm(row.get("cuenta"))
        if not account or account.startswith("https"):
            continue
        if when < cutoff:
            touched_before.add(account)
            continue
        actions.append((when, account, row.get("tipo", "")))
        per_day[when] += 1
        for part in (row.get("tipo", "") or "").split("+"):
            kinds[part] += 1
    targets = {a for _, a, _ in actions}
    repeated = sum(1 for _, a, _ in actions if a in touched_before)
    return {"actions": len(actions), "per_day": dict(sorted(per_day.items())), "kinds": dict(kinds),
            "unique_targets": len(targets),
            "unique_ratio": round(len(targets) / len(actions), 2) if actions else None,
            "touched_before_pct": round(100 * repeated / len(actions)) if actions else None}


# "429" a secas casa con contadores (posts_seen 1429, "reply": 429): exigir contexto HTTP/rate limit.
_RATE_LIMIT = re.compile(r"(?:HTTP|status|codigo|error|RateLimit)\D{0,15}429|RATE.?LIMIT|Too Many Requests", re.I)


def log_errors(log_dir, today, days=7):
    """Cuenta 429 y fallos en los logs de rondas de los ultimos dias."""
    cutoff = today - datetime.timedelta(days=days)
    hits = Counter()
    if not os.path.isdir(log_dir):
        return hits
    for name in os.listdir(log_dir):
        match = re.match(r"mech_(\d{4}-\d{2}-\d{2})", name)
        if not match or datetime.date.fromisoformat(match.group(1)) < cutoff:
            continue
        with open(os.path.join(log_dir, name), encoding="utf-8", errors="replace") as stream:
            text = stream.read()
        hits["429"] += sum(1 for line in text.splitlines() if _RATE_LIMIT.search(line))
        hits["fallos"] += len(re.findall(r"^FALLO(?! DE PREFLIGHT)", text, re.MULTILINE))
        hits["preflight"] += len(re.findall(r"FALLO DE PREFLIGHT", text))
        hits["rondas"] += 1
    return hits


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("bluesky", "mastodon"):
        print(__doc__)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    net = argv[0]
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 7
    today = datetime.date.today()
    base = os.path.join(ROOT, f"SISTEMA_DIARIO_{net.upper()}")
    rows = ga.load_registro(os.path.join(base, "registro_interacciones.csv"))
    stats = window_stats(rows, today, days)
    print(f"== {net}: ultimos {days} dias ==")
    print(f"acciones confirmadas: {stats['actions']}  mezcla: {stats['kinds']}")
    print(f"por dia: {stats['per_day']}")
    print(f"objetivos unicos/acciones: {stats['unique_targets']}/{stats['actions']} = {stats['unique_ratio']}  "
          f"| sobre cuentas ya tocadas antes: {stats['touched_before_pct']} %")
    followers = ga.bluesky_followers() if net == "bluesky" else ga.mastodon_followers()
    table = ga.attribute(rows, followers, today, 7)
    seen = sum(v[0] for v in table.values())
    back = sum(v[1] for v in table.values())
    if seen:
        low, high = ga.wilson(back, seen)
        print(f"follow-back de follows con >= 7 dias: {back}/{seen} = {100 * back / seen:.1f} %  (90 %: {100 * low:.0f}-{100 * high:.0f} %)")
    errors = log_errors(os.path.join(base, "cache"), today, days)
    print(f"logs de rondas: {dict(errors)}")
    print("Si el follow-back cae al subir el volumen o aparecen 429/avisos, ese es el techo economico; si no, hay margen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

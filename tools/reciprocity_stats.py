"""Medicion del follow-back por HUB (07/10/2026; ChatGPT, consulta L): el hallazgo de @rober solo vale si cada hub demuestra que devuelve el follow.

Para cada hub registrado (`00_OPERATIVO/hubs_reciprocidad.json`): de las cuentas que SEGUIMOS (registro de la red, con >= `MIN_AGE` dias) y que aparecen en sus listas de seguidores o seguidos
(tabla `edges` de la reserva), cuantas nos siguen ahora. Una cuenta que viene de varios hubs cuenta en todos (all_sources). Se suaviza con un prior bayesiano hacia la tasa global de la red
(posterior = (devueltos + prior*peso) / (seguidos + peso)) para no coronar ni hundir un hub con 5 muestras; con `MIN_N` muestras, un hub cuyo posterior queda por debajo de la mitad de la
tasa global se RETIRA de las semillas (solo los promovidos/anadidos como hub, nunca las semillas del nicho) y uno que supera 1,5 veces la global se marca `bueno`.

    python tools/reciprocity_stats.py mastodon|bluesky [--apply]      # sin --apply solo informa
"""
from __future__ import annotations

import csv
import datetime
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))
import reciprocity as rc

ROOT = os.path.join(os.path.dirname(__file__), "..")
MIN_AGE = 3
MIN_N = 40
PRIOR_WEIGHT = 20
RETIRE_BELOW = 0.5
GOOD_ABOVE = 1.5


def _key(account):
    return str(account or "").strip().lstrip("@").casefold().split("@")[0]


def posterior(back, n, prior_rate, weight=PRIOR_WEIGHT):
    return (back + prior_rate * weight) / (n + weight)


def hub_table(follows, followers, edges, hubs):
    """follows: {cuenta: fecha_iso}; followers: iterable de cuentas que nos siguen; edges: [(cuenta, hub)]; hubs: iterable de hubs.
    Devuelve ({hub: [seguidos, devueltos]}, [seguidos_total, devueltos_total])."""
    mine = {_key(f) for f in followers}
    by_account = {}
    for account, hub in edges:
        by_account.setdefault(_key(account), set()).add(hub)
    table = {hub: [0, 0] for hub in hubs}
    total = [0, 0]
    for account, _when in follows.items():
        key = _key(account)
        total[0] += 1
        total[1] += 1 if key in mine else 0
        for hub in by_account.get(key, ()):
            if hub in table:
                table[hub][0] += 1
                table[hub][1] += 1 if key in mine else 0
    return table, total


def decide(table, total, *, min_n=MIN_N):
    """{hub: {n, back, rate, posterior, decision}} con decision en `retirar` / `bueno` / `seguir` / `pocos_datos`."""
    overall = (total[1] / total[0]) if total[0] else 0.0
    out = {}
    for hub, (n, back) in table.items():
        post = posterior(back, n, overall)
        if n < min_n:
            decision = "pocos_datos"
        elif overall and post < RETIRE_BELOW * overall:
            decision = "retirar"
        elif overall and post > GOOD_ABOVE * overall:
            decision = "bueno"
        else:
            decision = "seguir"
        out[hub] = {"seguidos": n, "devueltos": back, "tasa": round(back / n, 3) if n else None, "posterior": round(post, 3), "decision": decision}
    return out, overall


def _load_follows(registro, today, min_age=MIN_AGE):
    out = {}
    try:
        with open(registro, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("resultado") not in ("confirmado", "publicado") or "follow" not in (row.get("tipo") or "").split("+") or row.get("tipo") == "unfollow":
                    continue
                try:
                    when = datetime.date.fromisoformat((row.get("fecha") or "")[:10])
                except ValueError:
                    continue
                if (today - when).days >= min_age:
                    out.setdefault(row["cuenta"], when.isoformat())
    except OSError:
        pass
    return out


def run(network, apply=False, today=None, followers=None):
    today = today or datetime.date.today()
    registry = rc.load_registry()
    hubs = {h: v for h, v in (registry.get(network) or {}).items() if v.get("estado") != "retirado"}
    if not hubs:
        print(f"[{network}] sin hubs registrados")
        return {}
    folder = {"mastodon": "SISTEMA_DIARIO_MASTODON", "bluesky": "SISTEMA_DIARIO_BLUESKY"}[network]
    follows = _load_follows(os.path.join(ROOT, folder, "registro_interacciones.csv"), today)
    db = sqlite3.connect(os.path.join(ROOT, folder, "cache", "pool.sqlite3"))
    try:
        if network == "mastodon":
            edges = db.execute("SELECT acct, seed FROM edges WHERE kind IN ('followers','following')").fetchall()
        else:
            edges = db.execute("SELECT a.handle, e.seed FROM edges e JOIN accounts a ON a.did = e.did WHERE e.kind IN ('followers','following')").fetchall()
    finally:
        db.close()
    if followers is None:
        import growth_attribution as ga
        followers = ga.mastodon_followers() if network == "mastodon" else ga.bluesky_followers()
    table, total = hub_table(follows, followers, edges, hubs)
    result, overall = decide(table, total)
    print(f"[{network}] follows con >= {MIN_AGE} dias: {total[0]}; devueltos {total[1]} ({100 * overall:.0f} %)")
    for hub, info in sorted(result.items(), key=lambda kv: -kv[1]["seguidos"])[:15]:
        print(f"  {hub:<42} {info['devueltos']}/{info['seguidos']} posterior {info['posterior']:.2f} -> {info['decision']}")
    if apply:
        seeds_path = {"mastodon": os.path.join(ROOT, folder, "mastodon_seeds.json"), "bluesky": os.path.join(ROOT, folder, "bluesky_seeds.json")}[network]
        try:
            seeds = json.load(open(seeds_path, encoding="utf-8"))
        except (OSError, ValueError):
            seeds = {}
        retired = []
        for hub, info in result.items():
            entry = registry[network][hub]
            entry.update({"seguidos": info["seguidos"], "devueltos": info["devueltos"], "posterior": info["posterior"], "decision": info["decision"], "medido": today.isoformat()})
            seed = seeds.get(hub) or {}
            if info["decision"] == "retirar" and (seed.get("origin") == "hub" or seed.get("type") == "hub"):
                entry["estado"] = "retirado"
                seeds.pop(hub, None)
                retired.append(hub)
        with open(rc.REGISTRY, "w", encoding="utf-8") as stream:
            json.dump(registry, stream, ensure_ascii=False, indent=1, sort_keys=True)
        if retired:
            with open(seeds_path, "w", encoding="utf-8") as stream:
                json.dump(seeds, stream, ensure_ascii=False, indent=1, sort_keys=True)
            print(f"[{network}] hubs retirados: {', '.join(retired)}")
    return result


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv or argv[0] not in ("mastodon", "bluesky"):
        print(__doc__)
        return 2
    run(argv[0], apply="--apply" in argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

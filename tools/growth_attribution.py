"""Atribucion de follow-back (02/10): que acciones acompanan a los follows que
SI nos devolvieron el follow. Responde "donde merece la pena gastar tokens":
si las cuentas con reply nos siguen mas que las que solo recibieron follow,
las replies compensan; si no, basta la ronda mecanica.

Lee registro_interacciones.csv (red) y la lista real de seguidores por API.

    python tools/growth_attribution.py bluesky
    python tools/growth_attribution.py mastodon [--min-age 2]

Solo cuenta follows con al menos --min-age dias (los de hoy no han tenido tiempo).
"""
import csv
import datetime
import os
import sys
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..")
FOLLOW_KINDS = {"follow"}
LIKE_KINDS = {"like", "favourite"}
BOOST_KINDS = {"repost", "boost", "quote"}


def norm(handle):
    return (handle or "").strip().lstrip("@").casefold()


def _same(a, b):
    """Coincidencia tolerante: registro guarda a veces solo el nombre local."""
    if a == b:
        return True
    la, lb = a.split("@")[0], b.split("@")[0]
    return la == lb and ("@" not in a or "@" not in b)


def load_registro(path):
    with open(path, encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def combo(kinds):
    """Etiqueta de las acciones recibidas ademas del follow."""
    tags = []
    if kinds & LIKE_KINDS:
        tags.append("like")
    if "reply" in kinds:
        tags.append("reply")
    if kinds & BOOST_KINDS:
        tags.append("boost")
    return "+".join(tags) or "solo_follow"


def attribute(rows, followers, today, min_age=2):
    """Devuelve {combo: [seguidos, devueltos]} y el total."""
    by_account = defaultdict(lambda: {"kinds": set(), "follow_date": None})
    for row in rows:
        if row.get("resultado") not in ("confirmado", "publicado"):
            continue
        account = norm(row.get("cuenta"))
        if not account or account.startswith("https"):
            continue
        entry = by_account[account]
        kind = row.get("tipo", "")
        parts = set(kind.split("+"))  # registro antiguo: "favourite+reply", "like+reply"
        if len(parts) > 1:
            entry["kinds"] |= parts - FOLLOW_KINDS
            kind = "follow" if parts & FOLLOW_KINDS else ""
        if kind in FOLLOW_KINDS:
            try:
                when = datetime.date.fromisoformat((row.get("fecha") or "")[:10])
            except ValueError:
                continue
            if entry["follow_date"] is None or when < entry["follow_date"]:
                entry["follow_date"] = when
        else:
            entry["kinds"].add(kind)
    followers = {norm(f) for f in followers}
    table = defaultdict(lambda: [0, 0])
    for account, entry in by_account.items():
        when = entry["follow_date"]
        if when is None or (today - when).days < min_age:
            continue
        label = combo(entry["kinds"])
        table[label][0] += 1
        if any(_same(account, f) for f in followers):
            table[label][1] += 1
    return dict(table)


AGE_EDGES = (1, 3, 7, 14, 30)


def age_curve(rows, followers, today, edges=AGE_EDGES):
    """[(edad minima, seguidos, devueltos)]: de los follows con al menos N dias, cuantos nos siguen
    HOY. Muestra cuanto tarda en llegar el follow-back (si 14 d >> 3 d, medir a 3 d subestima) y,
    con el tiempo, si se mantiene (propuesta de ChatGPT, 03/10: retencion, no solo follow-back)."""
    curve = []
    for edge in edges:
        table = attribute(rows, followers, today, edge)
        curve.append((edge, sum(v[0] for v in table.values()), sum(v[1] for v in table.values())))
    return curve


MICRO_MAX_WORDS = 8


def reply_arm(text):
    """Brazo del experimento 'microrespuesta vs respuesta elaborada' (propuesta de ChatGPT,
    03/10): micro = hasta 8 palabras. Se deduce del texto: no hace falta etiquetar nada."""
    words = [w for w in (text or "").split() if any(ch.isalnum() for ch in w)]
    return "micro" if len(words) <= MICRO_MAX_WORDS else "elaborada"


def by_reply_style(rows, followers, today, min_age=2):
    """{brazo: [seguidos con reply, devueltos]} para cuentas a las que seguimos Y respondimos.
    Con n pequena solo orienta: hay sesgo de seleccion (se contesta mejor a quien parece mas
    prometedor), asi que mirar conteos con su intervalo, no decidir por un porcentaje."""
    followers = {norm(f) for f in followers}
    follow_date, reply_text = {}, {}
    for row in rows:
        if row.get("resultado") not in ("confirmado", "publicado"):
            continue
        account = norm(row.get("cuenta"))
        kind = row.get("tipo", "")
        if not account or account.startswith("https"):
            continue
        if "follow" in kind.split("+") and kind != "unfollow":
            try:
                when = datetime.date.fromisoformat((row.get("fecha") or "")[:10])
            except ValueError:
                continue
            follow_date[account] = min(when, follow_date.get(account, when))
        if "reply" in kind.split("+") and (row.get("texto_usado") or "").strip():
            reply_text.setdefault(account, row["texto_usado"])
    table = defaultdict(lambda: [0, 0])
    for account, text in reply_text.items():
        when = follow_date.get(account)
        if when is None or (today - when).days < min_age:
            continue
        arm = reply_arm(text)
        table[arm][0] += 1
        if any(_same(account, f) for f in followers):
            table[arm][1] += 1
    return dict(table)


def source_of(notes):
    """Fuente de un follow a partir de la columna `notas` del registro (05/10): `src=<fuente>` de las acciones automaticas del motor de
    crecimiento, o la etiqueta de la oleada de semillas / de follow-back; 'otras' si no hay procedencia (registro antiguo)."""
    notes = notes or ""
    if ":src=" in notes:
        return notes.split(":src=", 1)[1].split(":")[0].split("+")[0].strip() or "otras"   # varias rutas: se atribuye a la primera
    if notes.startswith("seed_wave:commenter:"):
        return "seed_wave/comentarista/" + notes.split(":")[2]
    if notes.startswith("seed_wave:seed"):
        return "seed_wave/semilla"
    if "followback_wave" in notes:
        return "followback_wave"
    return "otras"


def by_source(rows, followers, today, min_age=2):
    """{fuente: [seguidos, devueltos]} solo para follows con edad suficiente: que fuente rinde follow-back."""
    followers = {norm(f) for f in followers}
    table = defaultdict(lambda: [0, 0])
    seen = set()
    for row in rows:
        if row.get("resultado") != "confirmado" or "follow" not in (row.get("tipo") or "").split("+") or (row.get("tipo") == "unfollow"):
            continue
        account = norm(row.get("cuenta"))
        if not account or account in seen:
            continue
        try:
            when = datetime.date.fromisoformat((row.get("fecha") or "")[:10])
        except ValueError:
            continue
        if (today - when).days < min_age:
            continue
        seen.add(account)
        label = source_of(row.get("notas"))
        table[label][0] += 1
        if any(_same(account, f) for f in followers):
            table[label][1] += 1
    return dict(table)


def holdout_view(holdout_rows, followers, today, min_age=14):
    """Seguimiento ORGANICO del grupo de control: candidatos que detectamos y apartamos a
    proposito sin seguir. Devuelve (apartados con edad suficiente, ya nos siguen).
    La diferencia con el follow-back de los que SI seguimos son los seguidores incrementales."""
    followers = {norm(f) for f in followers}
    n = back = 0
    for row in holdout_rows:
        try:
            when = datetime.date.fromisoformat((row.get("fecha") or "")[:10])
        except ValueError:
            continue
        if (today - when).days < min_age:
            continue
        n += 1
        account = norm(row.get("cuenta"))
        if any(_same(account, f) for f in followers):
            back += 1
    return n, back


def wilson(back, n, z=1.64):
    """Intervalo de Wilson (~90 %) para una proporcion; (0, 1) si n = 0."""
    if n == 0:
        return (0.0, 1.0)
    p = back / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def format_table(table):
    lines = []
    total = [0, 0]
    for label, (seen, back) in sorted(table.items(), key=lambda kv: -kv[1][0]):
        total[0] += seen
        total[1] += back
        lines.append(f"  {label:<18} {back:>3}/{seen:<4} {100 * back / seen:5.1f}%")
    if total[0]:
        lines.append(f"  {'TOTAL':<18} {total[1]:>3}/{total[0]:<4} {100 * total[1] / total[0]:5.1f}%")
    return "\n".join(lines) or "  (sin follows con edad suficiente)"


def bluesky_followers():
    sys.path.insert(0, os.path.dirname(__file__))
    import bluesky_interact as b
    out, cursor = [], None
    while True:
        params = {"actor": b.HANDLE, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        data = b._get(b.PUBLIC_BASE, "app.bsky.graph.getFollowers", params, auth=False)
        out += [f["handle"] for f in data.get("followers", [])]
        cursor = data.get("cursor")
        if not cursor:
            return out


def mastodon_followers():
    sys.path.insert(0, os.path.dirname(__file__))
    import mastodon_interact as m
    me = m._get("accounts/verify_credentials")
    rows = m._get_paginated(f"accounts/{me['id']}/followers", {"limit": 80}, max_pages=20)
    return [r["acct"] for r in rows]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("bluesky", "mastodon"):
        print(__doc__)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    min_age = int(argv[argv.index("--min-age") + 1]) if "--min-age" in argv else 2
    net = argv[0]
    rows = load_registro(os.path.join(ROOT, f"SISTEMA_DIARIO_{net.upper()}", "registro_interacciones.csv"))
    followers = bluesky_followers() if net == "bluesky" else mastodon_followers()
    print(f"{net}: {len(followers)} seguidores reales; follows con >= {min_age} dias:")
    print(format_table(attribute(rows, followers, datetime.date.today(), min_age)))
    print("Curva por edad (follows con >= N dias que nos siguen hoy):")
    for edge, seen, back in age_curve(rows, followers, datetime.date.today()):
        if seen:
            low, high = wilson(back, seen)
            print(f"  >= {edge:>2} d  {back:>3}/{seen:<4} {100 * back / seen:5.1f}%  (90%: {100 * low:.0f}-{100 * high:.0f}%)")
    sources = by_source(rows, followers, datetime.date.today(), min_age)
    if sources:
        print("Por fuente (el primer follow de cada cuenta; 'otras' = registro anterior al 05/10 sin procedencia):")
        for label, (n, back) in sorted(sources.items(), key=lambda kv: -kv[1][0])[:20]:
            print(f"  {label:<44} {back:>3}/{n:<4} {100 * back / n:5.1f}%")
    holdout_path = os.path.join(ROOT, f"SISTEMA_DIARIO_{net.upper()}", "holdout.csv")
    if os.path.exists(holdout_path):
        n, back = holdout_view(load_registro(holdout_path), followers, datetime.date.today(), 14)
        if n:
            low, high = wilson(back, n)
            print(f"Grupo de control (follows apartados, >= 14 dias): {back}/{n} nos siguen solos "
                  f"({100 * back / n:.1f} %, 90 %: {100 * low:.0f}-{100 * high:.0f} %). "
                  "Restar a la tasa de follow-back de los seguidos = seguidores incrementales.")
        else:
            print("Grupo de control: aun sin candidatos con 14 dias de edad.")
    style = by_reply_style(rows, followers, datetime.date.today(), min_age)
    if style:
        print("Estilo de reply (micro = hasta 8 palabras; solo orientativo, n pequena):")
        for arm, (n, back) in sorted(style.items()):
            low, high = wilson(back, n)
            print(f"  {arm:<10} {back:>3}/{n:<4} {100 * back / n:5.1f}%  (90%: {100 * low:.0f}-{100 * high:.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

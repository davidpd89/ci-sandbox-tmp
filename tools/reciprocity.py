"""Cuentas RECIPROCAS («hubs de follow-back») para todas las redes (07/10/2026).

Descubrimiento (David, 07/10): un hub ilustrativo (datos orientativos) tiene 33.750 seguidores y sigue a 37.400: crece SIGUIENDO a mucha gente que le sigue de vuelta. Quien tiene
esa conducta (sigue casi tantas cuentas como le siguen) devuelve el follow; y sus listas de seguidores y de seguidos son un caladero de cuentas con la misma cultura de follow-back.
No es una anecdota de Mastodon: el patron vale en Bluesky, X, Threads, Instagram, TikTok y Pinterest.

Este modulo es el nucleo COMUN (sin red ni navegador):
  * `classify(followers, following, statuses)` -> "super" | "reciprocal" | None
  * `affinity_bonus(followers, following)` -> puntos que cada reserva suma a un candidato que probablemente devuelva el follow
  * `select_hubs(rows, exclude, n)` -> las cuentas de la reserva que merecen ser semilla (hub) para minar sus listas: el ciclo se alimenta solo
  * registro `00_OPERATIVO/hubs_reciprocidad.json` (red -> cuenta -> metricas y fecha) para ver el ciclo de todas las redes

Uso en las redes: Mastodon (`mastodon_pool.py`) y Bluesky (`bluesky_pool.py`) ya lo aplican (bonus en `affinity` + promocion de hubs tras cada minado). En las redes por navegador/movil
(X, Threads, Facebook, Pinterest, TikTok, Instagram) la reserva no guarda contadores: ver `00_OPERATIVO/REDES/HUBS_RECIPROCIDAD.md` para el plan por red.
"""
from __future__ import annotations

import datetime
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
REGISTRY = os.path.join(ROOT, "00_OPERATIVO", "hubs_reciprocidad.json")

SUPER_MIN_FOLLOWERS, SUPER_MIN_FOLLOWING = 1500, 1000        # hub: audiencia y salida grandes
SUPER_MAX_FOLLOWERS, SUPER_MAX_FOLLOWING = 150_000, 60_000   # por encima es una granja de follows o una celebridad, no una cuenta que devuelve el follow
BRIDGES = ("threads.net", "brid.gy", "bsky.brid.gy")         # cuentas puente: no devuelven follows reales
SUPER_RATIO = (0.6, 2.5)                                      # seguidos / seguidores
RECIP_MIN_FOLLOWERS, RECIP_MIN_FOLLOWING = 100, 150
RECIP_RATIO = (0.5, 3.0)
MIN_STATUSES = 20


import re
import unicodedata

# bio que DECLARA follow-back: es la senal mas directa (la cuenta dice que devuelve el follow) y vale en todas las redes
FOLLOWBACK_BIO = re.compile(r"(sigo de vuelta|sigo a quien(es)? me sig|sigo a todos|te sigo si me sigues|sigueme y te sigo|siguenos y te seguimos|sdv\b|fb ?100|follow ?back|f4f\b|l4l\b|"
                            r"followback|sigo de regreso|devuelvo (el )?follow|devuelvo (los )?seguidores|sigo a mis seguidores)")
FOLLOWBACK_QUERIES = ["sigo de vuelta", "sigo a quien me sigue", "sigueme y te sigo", "follow back lectores", "sdv libros", "sigo de vuelta escritores", "sigo de vuelta lectores", "sigo a mis seguidores libros"]


def _fold(text):
    return "".join(ch for ch in unicodedata.normalize("NFD", (text or "").lower()) if unicodedata.category(ch) != "Mn")


def declares_followback(bio):
    # Compartido por todos los adaptadores que ya llaman declared_bonus.
    # Una mención explicativa o negativa NO es intención explícita.
    try:
        from reciprocity_signals import classify_text
    except ImportError:
        from tools.reciprocity_signals import classify_text
    return any(s["kind"] == "follow_exchange" and s["intent"] == "explicit"
               for s in classify_text(bio))


def declared_bonus(bio):
    """+2.5 de oferta si la bio declara que devuelve el follow."""
    return 2.5 if declares_followback(bio) else 0.0


def ratio(followers, following):
    if not followers or following is None:
        return None
    return following / followers


def classify(followers, following, statuses=None):
    """'super' (hub grande y reciproco), 'reciprocal' (cuenta normal que sigue casi tanto como le siguen) o None. Sin contadores -> None."""
    if followers is None or following is None:
        return None
    r = ratio(followers, following)
    if r is None or (statuses is not None and statuses < MIN_STATUSES):
        return None
    if (SUPER_MIN_FOLLOWERS <= followers <= SUPER_MAX_FOLLOWERS and SUPER_MIN_FOLLOWING <= following <= SUPER_MAX_FOLLOWING and SUPER_RATIO[0] <= r <= SUPER_RATIO[1]):
        return "super"
    if (RECIP_MIN_FOLLOWERS <= followers <= SUPER_MAX_FOLLOWERS and RECIP_MIN_FOLLOWING <= following <= SUPER_MAX_FOLLOWING and RECIP_RATIO[0] <= r <= RECIP_RATIO[1]):
        return "reciprocal"
    return None


def affinity_bonus(followers, following, statuses=None):
    """Puntos de oferta: la cuenta reciproca normal es la que mas probablemente devuelva el follow; el hub enorme da menos atencion por seguidor."""
    kind = classify(followers, following, statuses)
    return {"reciprocal": 2.0, "super": 1.0}.get(kind, 0.0)


def select_hubs(rows, *, exclude=(), n=10):
    """rows: dicts con handle, followers, following, statuses (opcional) y `ok` (True si es del idioma/nicho). Devuelve hasta `n` cuentas 'super' ordenadas por salida (mas follows dados = mas
    cultura de follow-back), sin las de `exclude`."""
    banned = {str(x).casefold() for x in exclude}
    picks = []
    for row in rows:
        handle = str(row.get("handle") or "")
        if not handle or handle.casefold() in banned or not row.get("ok", True) or handle.casefold().endswith(BRIDGES):
            continue
        if classify(row.get("followers"), row.get("following"), row.get("statuses")) == "super":
            picks.append(row)
    picks.sort(key=lambda row: (-int(row.get("following") or 0), str(row["handle"]).casefold()))
    return picks[:n]


def load_registry(path=None):
    try:
        with open(path or REGISTRY, encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return {}


def register(network, hubs, *, via="pool", path=None, today=None):
    """Anota los hubs promovidos de una red (handle -> metricas); no pisa la fecha de descubrimiento."""
    path = path or REGISTRY
    data = load_registry(path)
    section = data.setdefault(network, {})
    today = (today or datetime.date.today()).isoformat()
    for row in hubs:
        entry = section.setdefault(str(row["handle"]), {"descubierto": today, "via": via})
        entry.update({"seguidores": row.get("followers"), "siguiendo": row.get("following"), "ratio": round(ratio(row.get("followers"), row.get("following")) or 0, 2), "actualizado": today})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=1, sort_keys=True)
    return len(section)


# ---- redes por navegador: contadores observados al verificar perfiles (X muestra seguidores Y seguidos; Threads solo seguidores) ----
OBSERVATIONS = os.path.join(ROOT, "00_OPERATIVO", "perfiles_contadores.csv")


def observe(network, handle, followers, following, bio="", path=None, today=None):
    """Anota los contadores de un perfil que el ejecutor ya tenia abierto (no cuesta ninguna navegacion mas). Una fila por cuenta y dia."""
    import csv
    path = path or OBSERVATIONS
    handle = str(handle or "").lstrip("@")
    if not handle or followers is None:
        return False
    today = (today or datetime.date.today()).isoformat()
    try:
        import text_common as tc
        spanish = bool(tc.looks_spanish(bio or "")) and not tc.other_language(bio or "")
    except Exception:
        spanish = False
    key = (today, network, handle.casefold())
    cache = observe.__dict__.setdefault("_seen", set())
    if key in cache:
        return False
    cache.add(key)
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as stream:
        w = csv.writer(stream)
        if new:
            w.writerow(["fecha", "red", "handle", "seguidores", "siguiendo", "espanol", "declara_followback"])
        w.writerow([today, network, handle, followers, "" if following is None else following, int(spanish), int(declares_followback(bio))])
    return True


def observed_rows(network, path=None):
    """Ultima observacion por cuenta de una red, como filas para `select_hubs`."""
    import csv
    latest = {}
    try:
        with open(path or OBSERVATIONS, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("red") == network:
                    latest[row["handle"].casefold()] = row
    except OSError:
        return []
    out = []
    for row in latest.values():
        try:
            followers = int(row["seguidores"])
            following = int(row["siguiendo"]) if row.get("siguiendo") not in (None, "") else None
        except ValueError:
            continue
        out.append({"handle": row["handle"], "followers": followers, "following": following, "ok": row.get("espanol") == "1"})
    return out


def promote_browser(network, n=10):
    """X y Threads: los perfiles verificados que son `super` recíprocos y en español pasan a SEMILLAS de la reserva (se leen sus seguidores). Devuelve los hubs añadidos."""
    if network == "x":
        import x_pool as pool
    elif network == "threads":
        import threads_pool as pool
    else:
        raise ValueError(f"sin contadores de seguidos observables en {network}")
    db = pool.connect()
    try:
        existing = {row[0] for row in db.execute("SELECT handle FROM seeds")}
        picks = select_hubs(observed_rows(network), exclude=existing, n=n)
        if picks:
            pool.add_seeds(db, [p["handle"] for p in picks], source="hub")
            register(network, picks, via="perfil_verificado")
        return picks
    finally:
        db.close()


def main(argv=None):
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["promote"] and len(argv) > 1:
        picks = promote_browser(argv[1])
        print(f"[{argv[1]}] hubs reciprocos nuevos: " + (", ".join(f"{p['handle']} ({p['followers']}/{p['following']})" for p in picks) or "ninguno"))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

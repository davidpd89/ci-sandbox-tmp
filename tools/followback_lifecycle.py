"""Reconstrucción offline del ciclo de followback, independiente del transporte.

No consulta redes ni efectúa follows/unfollows. La ausencia en una lista parcial
NO es prueba de ausencia de reciprocidad. Las identidades son por red y, en
Mastodon, conservan el dominio (ana@uno != ana@dos).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict

NETWORKS = ("bluesky", "mastodon", "x", "threads", "facebook",
            "instagram", "pinterest", "reddit", "tiktok")
CHANNELS = {"bluesky": "API", "mastodon": "API", "x": "WEB",
            "threads": "WEB", "facebook": "WEB", "instagram": "WEB",
            "pinterest": "WEB", "reddit": "WEB", "tiktok": "MOBILE"}
# Fuentes comprobadas en el mirror de 10/10/2026, no capacidades supuestas.
FOLLOWBACK_SOURCES = {
    "bluesky": "getFollowers + getProfile.viewer.followedBy",
    "mastodon": "followers + accounts/relationships.followed_by",
    "x": "collect_followers + indicador de perfil Te sigue",
    "threads": "collect_followers + profile_info.follows_me",
    "tiktok": "tiktok_reciprocity_audit (parcial/completo)",
}


def account_key(network, value):
    """Clave estricta: no equiparar distintos servidores Mastodon."""
    if network not in NETWORKS:
        raise ValueError(f"red no soportada: {network}")
    value = str(value or "").strip().lstrip("@").casefold()
    return value if value and not value.startswith(("http:", "https:")) else ""


def _date(value):
    try:
        return dt.date.fromisoformat(str(value or "")[:10])
    except (TypeError, ValueError):
        return None


def replay(rows, *, network, today, followers=(), following=None,
           followers_complete=False, following_complete=False,
           grace_days=7):
    """Reconstruye un registro por cuenta con reloj inyectado.

    followers aporta positivos incluso si es una lectura parcial. Ausencias
    solo cuentan si followers_complete=True. Los eventos sintéticos
    followback_observed/followback_lost son observaciones *verificadas*.
    following=None significa estado actual desconocido, no lista vacía.
    La salida eligible indica elegibilidad observada, NO autoriza actuar.
    """
    if network not in NETWORKS:
        raise ValueError(network)
    if not isinstance(today, dt.date) or isinstance(today, dt.datetime):
        raise TypeError("today debe ser datetime.date")
    if grace_days < 0:
        raise ValueError("grace_days negativo")
    positive = {account_key(network, x) for x in followers}
    current_following = None if following is None else {
        account_key(network, x) for x in following
    }
    tracks = defaultdict(list)
    for order, row in enumerate(rows):
        if row.get("red") not in (None, "", network):
            continue
        key = account_key(network, row.get("cuenta") or row.get("handle"))
        when = _date(row.get("fecha"))
        if not key or when is None or when > today:
            continue
        tracks[key].append((when, order, row))

    # Permite observar seguidos manuales aun sin fecha de follow registrada.
    if current_following is not None:
        for key in current_following:
            if key:
                tracks[key]

    output = {}
    for key in sorted(tracks):
        since = None
        pending = False
        observed_back = None
        ever_back = False
        reply_after_follow = False
        cycles = 0
        for when, _, row in sorted(tracks[key], key=lambda item: (item[0], item[1])):
            kind = str(row.get("tipo") or "").strip().casefold()
            outcome = str(row.get("resultado") or "").strip().casefold()
            parts = set(kind.split("+"))
            if kind == "followback_observed" and outcome == "confirmado":
                observed_back, ever_back = True, True
            elif kind == "followback_lost" and outcome == "confirmado":
                observed_back = False
            elif kind == "unfollow" and outcome in ("confirmado", "publicado", "saltado_ya_no_seguido"):
                since, pending, reply_after_follow = None, False, False
                # Una observacion del ciclo anterior no certifica el nuevo follow.
                observed_back, ever_back = None, False
            elif "follow" in parts:
                if outcome in ("confirmado", "publicado"):
                    if since is None:
                        since, cycles = when, cycles + 1
                        reply_after_follow = False
                    pending = False
                elif outcome in ("pendiente_aprobacion", "requested") and since is None:
                    pending = True
            # Un evento combinado (follow+reply) cuenta ambas acciones; el
            # `elif` anterior omitia la conversacion y marcaba eligible.
            if "reply" in parts and outcome in ("confirmado", "publicado") and since is not None:
                reply_after_follow = True

        # Un positivo parcial prevalece; no sustituirlo por ausencia inferida.
        if key in positive:
            observed_back, ever_back = True, True
        elif followers_complete:
            observed_back = False
        if current_following is not None and key in current_following:
            active = True
        elif current_following is not None and following_complete:
            active = False
        else:
            active = None  # no probado por un listado truncado

        age = (today - since).days if since is not None else None
        due = age is not None and age >= grace_days
        if active is False:
            state = "not_following"
        elif since is None:
            # Un follow manual sin antiguedad conocida puede ser reciproco
            # cuando ambas listas confirman la relacion actual.
            state = ("reciprocal" if active is True and observed_back is True
                     else "pending_approval" if pending else "manual_unknown_age")
        elif observed_back is True:
            state = "reciprocal"
        elif not due:
            state = "waiting"
        elif reply_after_follow:
            state = "engaged_review"
        elif observed_back is None:
            state = "due_unverified"
        elif ever_back:
            state = "lost_followback"
        else:
            state = "eligible" if active is True else "due_unverified"
        eligible = (state in ("eligible", "lost_followback") and active is True
                    and observed_back is False and not reply_after_follow)
        output[key] = {
            "network": network, "account": key, "state": state,
            "since": since.isoformat() if since else None,
            "age_days": age, "follow_cycles": cycles,
            "observed_back": observed_back,
            "following_verified": active,
            "has_conversation": reply_after_follow,
            "eligible": eligible,
        }
    return output


def coverage(*, pipelines=None, cleanup_adapters=None):
    """Cobertura REAL de conexión de limpieza; sin importar adaptadores externos."""
    if pipelines is None:
        from mechanical_round import PIPELINES
        pipelines = PIPELINES
    if cleanup_adapters is None:
        from unfollow_cleanup import ADAPTERS
        cleanup_adapters = ADAPTERS
    from network_capabilities import _scheduled
    return {
        net: {
            "channel": CHANNELS[net],
            "lifecycle_replay": True,
            "followback_source": FOLLOWBACK_SOURCES.get(net),
            "live_unfollow_adapter": net in cleanup_adapters,
            "cleanup_scheduled": net in cleanup_adapters and
                _scheduled(pipelines.get(net) or {}, "unfollow_cleanup.py", net),
        }
        for net in NETWORKS
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", help="JSON sintético {network, today, rows, followers, following, ...}")
    parser.add_argument("--matrix", action="store_true")
    args = parser.parse_args(argv)
    if not args.fixture and not args.matrix:
        parser.error("indicar --fixture o --matrix")
    if args.fixture:
        with open(args.fixture, encoding="utf-8") as src:
            item = json.load(src)
        data = replay(item.get("rows", []), network=item["network"],
                      today=dt.date.fromisoformat(item["today"]),
                      followers=item.get("followers", []),
                      following=item.get("following"),
                      followers_complete=item.get("followers_complete", False),
                      following_complete=item.get("following_complete", False),
                      grace_days=item.get("grace_days", 7))
    else:
        data = coverage()
    print(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

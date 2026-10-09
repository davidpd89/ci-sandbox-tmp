"""Calendario editorial read-only. Nunca publica, programa ni cambia estados."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import content_queue as cq

# Transporte del contenido, NO carriles de engagement de round_queue.
LANES = dict(x="WEB", threads="WEB", pinterest="WEB",
             facebook="API", instagram="API", bluesky="API",
             mastodon="API", reddit="API", tiktok="MOBILE")


def resolve_wall_time(wall: datetime, zone: ZoneInfo) -> datetime:
    """Rechaza horas locales inexistentes o ambiguas; nunca elige fold sin permiso."""
    if wall.tzinfo is not None:
        raise ValueError("fecha de ficha ya tiene zona")
    instants = []
    for fold in (0, 1):
        utc = wall.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) == wall and utc not in instants:
            instants.append(utc)
    if not instants:
        raise ValueError("hora_inexistente")
    if len(instants) != 1:
        raise ValueError("hora_ambigua")
    return instants[0]


def _entry(red: str, item: dict, now: datetime, zone: ZoneInfo, max_days: int) -> dict:
    # El mismo identificador después de mover de unidad o checkout.
    folder = Path(str(item.get("md_path", "")).replace("\\", "/")).parent.name
    source = f"{cq.RED_FOLDERS[red]}/{folder}/publicacion.md"
    text = item.get("texto") or ""
    state = item.get("estado") or ""
    when = item.get("fecha_hora")
    issues = []
    instant = None
    if not state:
        issues.append("estado_ausente")
    if not text.strip():
        issues.append("texto_ausente")
    if when is None:
        issues.append("fecha_ausente")
    elif not isinstance(when, datetime):
        issues.append("fecha_invalida")
    else:
        try:
            instant = resolve_wall_time(when, zone)
        except ValueError as exc:
            issues.append(str(exc) if str(exc) in ("hora_ambigua", "hora_inexistente")
                          else "fecha_invalida")
    if item.get("blockers"):
        issues.append("bloqueo_editorial")
    media = item.get("media") or []
    if any(not m.get("exists") for m in media):
        issues.append("medio_ausente")
    if any(not str(m.get("alt") or "").strip() for m in media):
        issues.append("alt_ausente")
    if not media and item.get("imagen_declarada"):
        issues.append("medio_inconsistente")

    if cq._ya_resuelto(state):
        status = "resolved"
    elif issues:
        status = "invalid"
    elif state.casefold().strip().rstrip(".") not in ("lista", "lista para publicar", "lista para publicación", "lista para publicacion", "lista para programar"):
        status = "review"
    elif instant > now:
        status = "future"
    elif now - instant > timedelta(days=max_days):
        status = "stale"
    else:
        status = "due"

    normal = " ".join(text.split()).casefold()
    fp = sha256((red + "\0" + normal).encode("utf-8")).hexdigest()[:24] if normal else None
    return dict(
        id=sha256(source.encode("utf-8")).hexdigest()[:24],
        source=source, network=red, lane=LANES[red],
        time_utc=instant.isoformat().replace("+00:00", "Z") if instant else None,
        time_local=when.isoformat(timespec="minutes") if isinstance(when, datetime) else None,
        status=status, auto_opt_in=item.get("auto_ok") is True,
        media_count=len(media), fingerprint=fp, issues=issues
    )


def build_calendar(*, now: datetime | None = None, zone_name: str = "Europe/Madrid",
                   max_overdue_days: int = 14, networks=None, scanner=None) -> dict:
    """Resumen estable, sin llamadas de red ni escrituras. scanner admite fixtures."""
    if max_overdue_days < 0:
        raise ValueError("max_overdue_days negativo")
    zone = ZoneInfo(zone_name)
    now = datetime.now(timezone.utc) if now is None else now
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now sin zona")
    now = now.astimezone(timezone.utc)
    names = list(cq.RED_FOLDERS) if networks is None else list(networks)
    if len(set(names)) != len(names) or any(n not in cq.RED_FOLDERS or n not in LANES for n in names):
        raise ValueError("red duplicada o desconocida")
    scan = scanner if scanner is not None else cq.scan_items
    items = [_entry(red, item, now, zone, max_overdue_days)
             for red in names for item in scan(red)]
    fingerprints, slots = defaultdict(list), defaultdict(list)
    for entry in items:
        if entry["fingerprint"]:
            fingerprints[(entry["network"], entry["fingerprint"])].append(entry)
        if entry["status"] == "resolved":
            continue
        if entry["time_utc"] and entry["status"] in ("due", "future", "stale"):
            slots[(entry["network"], entry["time_utc"])].append(entry)
    for groups, warning in ((fingerprints, "possible_duplicate"),
                            (slots, "slot_collision")):
        for rows in groups.values():
            if len(rows) > 1:
                for row in rows:
                    row["issues"].append(warning)
    items.sort(key=lambda e: (e["time_utc"] is None, e["time_utc"] or "",
                              e["network"], e["source"]))
    counts = Counter(row["status"] for row in items)
    return dict(schema_version=1, generated_at_utc=now.isoformat().replace("+00:00", "Z"),
                timezone=zone_name, max_overdue_days=max_overdue_days,
                read_only=True, totals={k: counts[k] for k in
                  ("due", "future", "stale", "review", "invalid", "resolved")}, items=items)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Prevalidación editorial sin publicar")
    parser.add_argument("--network", choices=tuple(cq.RED_FOLDERS), action="append",
                        dest="networks")
    parser.add_argument("--timezone", default="Europe/Madrid")
    parser.add_argument("--max-overdue-days", type=int, default=14)
    args = parser.parse_args(argv)
    try:
        result = build_calendar(networks=args.networks, zone_name=args.timezone,
                                max_overdue_days=args.max_overdue_days)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

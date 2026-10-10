"""TikTok: auditoria de reciprocidad y conversion por fuente (08/10/2026).

Lee, en el movil y solo lectura, nuestra lista de Seguidores y la cruza con los follows
confirmados del sistema. Mantiene dos vistas:

* resumen actual por fuente/semilla/consulta, compatible con el selector de semillas;
* cohortes observadas D+1/D+3/D+7. La fecha del primer follow-back se persiste en
  reciprocity_audit.json. Solo se incluyen en esas cohortes follows hechos desde que
  empezo la observacion, para no inventar la fecha de retorno de seguidores antiguos.

El paso post de TikTok la ejecuta cada 6 h, de modo que las cohortes se actualizan sin
acciones de escritura sobre TikTok.

    python tools/tiktok_reciprocity_audit.py [--max-rows 400] [--min-age-days 3]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import tiktok_bulk_follow as bulk
<<<<<<< HEAD
=======
import tiktok_cohort_adapter as cohorts
from cohort_metrics import TZ
>>>>>>> origin/research/public-reuse-parent

ROOT = bulk.ROOT
AUDIT_PATH = os.path.join(ROOT, "reciprocity_audit.json")
OWN_BUTTON_X = (690, 730)
DEADLINE_DAYS = (1, 3, 7)


def adaptive_row_budget(min_rows, follower_count):
    """Escala la lectura con los seguidores declarados en el perfil.

    La UI abrevia cifras (p. ej. 1,2 mil), de ahí el margen para redondeos.
    `min_rows` sigue siendo el mínimo solicitado por --max-rows, no un tope
    permanente que congela la conversión cuando la cuenta crece.
    """
    if follower_count is None:
        return min_rows
    return max(min_rows, int(follower_count * 1.12) + 20)


def profile_follower_count(tree):
    """Contador de nuestro perfil; None si su posición/lectura es ambigua.

    TikTok Android muestra «Seguidores» junto a la cifra, o en TextViews
    adyacentes. El valor es orientativo: sirve para decidir cuánto recorrer,
    nunca para deducir que un handle ausente no nos sigue.
    """
    from tiktok_mobile_nav import _norm, _tiktok_elements, clean, element_texts, parse_count
    elements = _tiktok_elements(tree)
    labels, distinct_labels = [], set()
    for el in elements:
        texts = element_texts(el) or []
        norm = _norm(clean(" ".join(texts)))
        x, y = float(el["rect"]["x"]), float(el["rect"]["y"])
        if 330 <= y <= 680 and (
            norm in ("seguidores", "followers")
            or norm.endswith(" seguidores") or norm.endswith(" followers")
            or norm.startswith("seguidores ") or norm.startswith("followers ")
        ):
            key = (x, y, norm)
            if key not in distinct_labels:
                labels.append((el, texts, norm))
                distinct_labels.add(key)
    if len(labels) != 1:
        return None
    label, texts, norm = labels[0]
    if norm not in ("seguidores", "followers"):
        direct = parse_count(" ".join(texts))
        if direct is not None:
            return direct
    x, y = float(label["rect"]["x"]), float(label["rect"]["y"])
    candidates = []
    for el in elements:
        if el is label:
            continue
        pos = el["rect"]
        dx, dy = abs(float(pos["x"]) - x), y - float(pos["y"])
        if dx > 110 or not 0 < dy < 155:
            continue
        for text in element_texts(el) or []:
            stripped = clean(text)
            if not re.fullmatch(r"\d[\d.,]*\s*(?:mil|k|m|millones)?", stripped, re.I):
                continue
            value = parse_count(stripped)
            if value is not None:
                candidates.append((dy + dx / 3, value))
    candidates.sort()
    return candidates[0][1] if candidates else None


def read_tab(nav, tab_prefix, max_rows, expected_count=None):
    """Pulsa Siguiendo/Seguidores/Amigos y devuelve los handles visibles al recorrerla."""
    from mobile_client import element_center
    from tiktok_mobile_nav import _norm, _tiktok_elements, clean, element_texts
    target = None
    for element in _tiktok_elements(nav.tree()):
        text = _norm(clean((element_texts(element) or [""])[0]))
        if text.startswith(tab_prefix) and float(element["rect"]["y"]) < 330:
            target = element
    if target is None:
        return [], False
    x, y = element_center(target)
    nav.c.tap(x, y, nav.device.id)
    time.sleep(2.5)
    seen, order, empty = set(), [], 0
    while len(order) < max_rows and empty < 2:
        # Android puede exponer la misma cuenta varias veces en un solo árbol.
        # Deduplicar *al agregar*, no en una comprensión que consulta seen
        # antes de incorporarla: eso inflaría followers_read y la cobertura.
        added = 0
        for row in bulk.parse_follower_rows(nav.tree(), button_x=OWN_BUTTON_X):
            handle = str(row.get("handle") or "").strip().lstrip("@").casefold()
            if not handle or handle in seen:
                continue
            seen.add(handle)
            order.append(handle)
            added += 1
            if len(order) >= max_rows:
                break
        empty = empty + 1 if added == 0 else 0
        if len(order) >= max_rows or empty >= 2:
            break
        nav.c.swipe(540, 1900, 540, 650, duration_ms=520, device_id=nav.device.id)
        time.sleep(1.8)
    # No usar ausencias como negativos si la pantalla no se ha recorrido entera.
    # El contador está redondeado en UI (1,2 mil). Una lista que se atasca en
    # 400 de 2.000 NO es completa por mucho que se repitan las mismas filas.
    # Margen del 6 % para contadores abreviados, nunca para inventar positivos.
    # Sin contador no tenemos prueba independiente de cobertura; evitar
    # considerar dos pantallas repetidas como "llegó al final".
    # Los contadores inferiores a mil aparecen sin abreviar: exigir coincidencia.
    # Para cifras abreviadas se tolera el redondeo, sin truncar el mínimo
    # hacia abajo (p. ej. 2 seguidores nunca pueden contarse como 1).
    minimum_seen = (
        expected_count if expected_count < 1000
        else (expected_count * 94 + 99) // 100
    ) if expected_count is not None else 0
    complete = (
        expected_count is not None
        and empty >= 2
        and 0 < len(order) < max_rows
        and len(order) >= minimum_seen
    )
    return order[:max_rows], complete


def source_from_notes(notes):
    """Atribucion estable para las rutas TikTok que hoy generan follows."""
    notes = notes or ""
    match = re.search(r"bulk:(followers|mutual):([^|]+)", notes)
    if match:
        return f"{match.group(1)}:{match.group(2).strip()}"
    if "bulk:followback:" in notes:
        return "followback"
    if notes.startswith(("auto", "plan")):
        return "auto"
    return "otros"


def all_follows(today=None):
    """Primer follow confirmado por handle: [(handle, fecha_iso, fuente)]."""
    today = today or datetime.date.today()
    first = {}
    try:
        with open(bulk.REGISTRO_CSV, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if (row.get("tipo") or "").strip().casefold() != "follow":
                    continue
                if (row.get("resultado") or "").strip().casefold() != "confirmado":
                    continue
                handle = (row.get("cuenta") or "").strip().lstrip("@").casefold()
                if not handle:
                    continue
                try:
                    day = datetime.date.fromisoformat((row.get("fecha") or "")[:10])
                except ValueError:
                    continue
                if day > today:
                    continue
                current = first.get(handle)
                item = (handle, day.isoformat(), source_from_notes(row.get("notas")))
                if current is None or day < datetime.date.fromisoformat(current[1]):
                    first[handle] = item
    except OSError:
        pass
    return sorted(first.values(), key=lambda item: (item[1], item[0]))


def follows_by_source(min_age_days, today=None):
    """Compatibilidad: follows con al menos min_age_days dias."""
    today = today or datetime.date.today()
    return [
        item for item in all_follows(today)
        if (today - datetime.date.fromisoformat(item[1])).days >= min_age_days
    ]


def summarize(follows, reciprocal):
    """{fuente: {followed, back, rate}} con las fuentes ordenadas por tasa."""
    stats = {}
    reciprocal = {h.casefold() for h in reciprocal}
    for handle, _day, source in follows:
        entry = stats.setdefault(source, {"followed": 0, "back": 0})
        entry["followed"] += 1
        entry["back"] += 1 if handle in reciprocal else 0
    for entry in stats.values():
        entry["rate"] = round(entry["back"] / entry["followed"], 3) if entry["followed"] else 0.0
    return dict(sorted(stats.items(), key=lambda kv: (-kv[1]["rate"], -kv[1]["followed"], kv[0])))


<<<<<<< HEAD
=======
def _valid_snapshot_day(value):
    try:
        datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


>>>>>>> origin/research/public-reuse-parent
def load_audit_state(path=AUDIT_PATH):
    """No reiniciar la historia si el fichero existente está dañado."""
    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"estado de auditoría ilegible: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError("estado de auditoría sin objeto JSON")
    if data.get("observed_since"):
        try:
            datetime.date.fromisoformat(data["observed_since"])
        except (TypeError, ValueError) as exc:
            raise ValueError("fecha observed_since inválida") from exc
    if not isinstance(data.get("first_back_date", {}), dict):
        raise ValueError("first_back_date no es un objeto")
<<<<<<< HEAD
=======
    complete_dates = data.get("complete_dates", [])
    if not isinstance(complete_dates, list) or any(
        not isinstance(value, str) or not _valid_snapshot_day(value)
        for value in complete_dates
    ):
        raise ValueError("complete_dates inválido")

>>>>>>> origin/research/public-reuse-parent
    return data


def save_audit_state(data, path=AUDIT_PATH):
    """Escritura atómica: un fallo nunca trunca el histórico anterior."""
    temp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(temp, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=1)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def update_back_observations(follows, reciprocal, state, today=None):
    """Persiste la primera fecha en la que OBSERVAMOS que una cuenta ya nos sigue."""
    today = today or datetime.date.today()
    observed_since = state.get("observed_since") or today.isoformat()
    first_back = dict(state.get("first_back_date") or {})
    followed = {handle for handle, _day, _source in follows}
    for handle in {h.casefold() for h in reciprocal} & followed:
        first_back.setdefault(handle, today.isoformat())
    return observed_since, first_back


def partial_snapshot_state(follows, followers, state, today=None):
    """Conserva positivos observados sin cambiar tasas ni ranking con una lista incompleta."""
    today = today or datetime.date.today()
    observed_since, first_back = update_back_observations(follows, set(followers), state, today)
    return {
        **state,
        "observed_since": observed_since,
        "first_back_date": first_back,
        "last_partial_date": today.isoformat(),
        "last_partial_followers_read": len(followers),
        "coverage_complete": False,
    }


def deadline_summary(follows, first_back_date, observed_since, today=None, deadlines=DEADLINE_DAYS):
<<<<<<< HEAD
    """Conversion por deadline real observado.

    Solo entran follows hechos desde observed_since. Para D+N, la cuenta debe tener al
    menos N dias de edad y el primer follow-back observado debe caer como maximo N dias
    despues del follow.
    """
    today = today or datetime.date.today()
    observed_day = datetime.date.fromisoformat(observed_since)
    out = {}
    for days in deadlines:
        grouped = {}
        for handle, follow_iso, source in follows:
            # Ya era seguidor antes de nuestro follow: no es captación nueva.
            if source == "followback":
                continue
            follow_day = datetime.date.fromisoformat(follow_iso)
            if follow_day < observed_day or (today - follow_day).days < days:
                continue
            entry = grouped.setdefault(source, {"followed": 0, "back": 0})
            entry["followed"] += 1
            back_iso = first_back_date.get(handle)
            if back_iso:
                try:
                    back_day = datetime.date.fromisoformat(back_iso)
                except ValueError:
                    back_day = None
                if back_day is not None and back_day <= follow_day + datetime.timedelta(days=days):
                    entry["back"] += 1
        for entry in grouped.values():
            entry["rate"] = round(entry["back"] / entry["followed"], 3) if entry["followed"] else 0.0
        out[f"D+{days}"] = dict(sorted(
            grouped.items(),
            key=lambda kv: (-kv[1]["rate"], -kv[1]["followed"], kv[0]),
        ))
    return out


def update_seeds(stats):
    """Guarda el follow-back real de cada semilla para que pick_seeds priorice las mejores."""
=======
    """Compatibilidad de #33: delegar AL ÚNICO motor compartido (#77).

    Esta vista legacy incluye unknown implícitos como cero; el KPI certificado
    es 'cohorts_v2' y no debe usar 'deadlines' para selección de fuentes.
    """
    today = today or datetime.datetime.now(TZ).date()
    _v2, legacy = cohorts.project(follows, first_back_date, observed_since, today,
                                  deadlines=deadlines)
    return legacy

def update_seeds(stats):
    """Compatibilidad: guarda conteos observados, NUNCA un nuevo score operativo.

    El histórico no acredita identidad estable ni baseline de terceros y no
    permite convertir su tasa suavizada en prioridad de seguimiento.
    """
>>>>>>> origin/research/public-reuse-parent
    try:
        with open(bulk.SEEDS_PATH, encoding="utf-8") as stream:
            seeds = json.load(stream)
    except FileNotFoundError:
        seeds = {}
    except (OSError, ValueError) as exc:
        print(f"[audit] semillas ilegibles; se preserva el archivo original: {type(exc).__name__}")
        return False
    if not isinstance(seeds, dict):
        print("[audit] formato de semillas no es un objeto; se preserva el archivo original")
        return False
    for source, entry in stats.items():
        if source.startswith("followers:@"):
            seed = source.split("@", 1)[1]
            record = seeds.setdefault(seed, {})
            record.update({
                "followed": entry["followed"],
                "back": entry["back"],
<<<<<<< HEAD
                "rate": entry["rate"],
                "yield": round((entry["back"] + 1) / (entry["followed"] + 10), 4),
=======
                "rate": entry["rate"],  # observacional, no certificado
>>>>>>> origin/research/public-reuse-parent
            })
    save_audit_state(seeds, path=bulk.SEEDS_PATH)
    return True


def _print_deadlines(deadlines):
    for label, table in deadlines.items():
        followed = sum(entry["followed"] for entry in table.values())
        back = sum(entry["back"] for entry in table.values())
        if followed:
            print(f"[audit] {label}: {back}/{followed} ({back / followed:.0%})")
            for source, entry in list(table.items())[:8]:
                print(
                    f"[audit]   {source[:44]:44} "
                    f"{entry['back']:3}/{entry['followed']:<3} ({entry['rate']:.0%})"
                )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-rows", type=int, default=400)
    parser.add_argument("--min-age-days", type=int, default=3)
    parser.add_argument("--device", default=os.getenv("ANDROID_DEVICE_ID"))
    parser.add_argument("--every-hours", type=float, default=0, help="no repetir si la auditoria es mas reciente")
    args = parser.parse_args(argv)
    if args.max_rows < 1:
        parser.error("--max-rows debe ser positivo")
    if args.every_hours and os.path.exists(AUDIT_PATH) and (time.time() - os.path.getmtime(AUDIT_PATH)) / 3600 < args.every_hours:
        print(f"[audit] auditoria de hace menos de {args.every_hours:g} h: se omite")
        return 0
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    from mobile_client import MobileCliError, element_center
    from mobile_runtime import MobileSessionBusy, ensure_server, mobile_session_lock
    from tiktok_mobile_interact import MY_HANDLE, TikTokMobileAdapter
    from tiktok_mobile_nav import TikTokNavigator, _norm, _tiktok_elements, clean, element_texts
    try:
        with mobile_session_lock():
            client = ensure_server(device_id=args.device)
            adapter = TikTokMobileAdapter(client, args.device)
            nav = TikTokNavigator(adapter)
            adapter.verify_active_account(MY_HANDLE)
            time.sleep(1.5)
            profile_tree = nav.tree()
            expected_followers = profile_follower_count(profile_tree)
            scan_budget = adaptive_row_budget(args.max_rows, expected_followers)
            print(f"[audit] seguidores declarados={expected_followers}; lectura prevista hasta {scan_budget} filas")
            target = next((
                e for e in _tiktok_elements(profile_tree)
                if _norm(clean((element_texts(e) or [""])[0])) in ("siguiendo", "following")
                and 380 < float(e["rect"]["y"]) < 640
            ), None)
            if target is None:
                print("FALLO audit: no se encuentra el contador Siguiendo")
                return 0
            x, y = element_center(target)
            client.tap(x, y, adapter.device.id)
            time.sleep(3.0)
            followers, complete = read_tab(nav, "seguidores", scan_budget, expected_count=expected_followers)
            nav.return_to_feed()
    except MobileSessionBusy:
        print("MobileSessionBusy: el movil lo usa otra sesion; se omite la auditoria")
        return 0
    except (MobileCliError, RuntimeError) as exc:
        print(f"FALLO audit: {type(exc).__name__}: {str(exc)[:120]}")
        return 0

<<<<<<< HEAD
    today = datetime.date.today()
=======
    today = datetime.datetime.now(TZ).date()
>>>>>>> origin/research/public-reuse-parent
    follows = all_follows(today)
    if not complete:
        # Una lista parcial sí confirma positivos, pero no demuestra ausencias.
        # Preservar ese conocimiento sin sesgar las tasas ni tocar bulk_seeds.
        if followers:
            try:
                previous = load_audit_state()
            except ValueError as exc:
                print(f"[audit] {exc}; se conserva el archivo para revisión")
                return 0
            save_audit_state(partial_snapshot_state(follows, followers, previous, today))
        print("[audit] lectura incompleta: positivos conservados; tasas y semillas sin cambios")
        return 0

    reciprocal = set(followers)
    stats = summarize(
        [item for item in follows if (today - datetime.date.fromisoformat(item[1])).days >= args.min_age_days],
        reciprocal,
    )
    try:
        previous = load_audit_state()
    except ValueError as exc:
        print(f"[audit] {exc}; se conserva el archivo para revisión")
        return 0
    observed_since, first_back = update_back_observations(follows, reciprocal, previous, today)
<<<<<<< HEAD
    deadlines = deadline_summary(follows, first_back, observed_since, today)
=======
    # Historial de snapshots COMPLETOS; los parciales nunca incorporan fechas.
    previous_complete_dates = previous.get("complete_dates") or []
    complete_dates = list(dict.fromkeys([*previous_complete_dates, today.isoformat()]))
    cohorts_v2, deadlines = cohorts.project(
        follows, first_back, observed_since, today, complete_dates=complete_dates,
    )
>>>>>>> origin/research/public-reuse-parent

    audit = {
        "date": today.isoformat(),
        "observed_since": observed_since,
        "followers_read": len(followers),
        "followers_expected": expected_followers,
        "coverage_complete": True,
        "sources": stats,
        "deadlines": deadlines,
        "first_back_date": first_back,
<<<<<<< HEAD
=======
        "complete_dates": complete_dates,
        "cohorts_v2": {"schema_version": 2, "timezone": "Europe/Madrid",
                       "definition": "first_observed_positive_by_local_D+N",
                       "windows": cohorts_v2},
>>>>>>> origin/research/public-reuse-parent
    }
    save_audit_state(audit)
    update_seeds(stats)

    print(f"[audit] seguidores leidos {len(followers)}; observacion desde {observed_since}")
    for source, entry in list(stats.items())[:12]:
        print(
            f"[audit] {source[:48]:48} seguidas {entry['followed']:3} "
            f"devueltas {entry['back']:3} ({entry['rate']:.0%})"
        )
    _print_deadlines(deadlines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

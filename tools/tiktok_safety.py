"""Paradas compartidas de TikTok: estado local conservador, nunca cuota oficial."""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_TIKTOK")
COOLDOWN_PATH = os.environ.get("RRSS_TIKTOK_COOLDOWN_PATH") or os.path.join(ROOT, "bulk_cooldown.json")   # los tests apuntan a una ruta temporal: un descanso real (09/10 strikes=3) no debe romperlos
WARNINGS = re.compile(
    r"demasiado\s+(?:r[aá]pid|frecuen)|too fast|try again later|"
    r"int[eé]ntalo de nuevo m[aá]s tarde|actividad inusual|unusual activity|"
    r"comportamiento inusual|suspicious activity|has alcanzado el l[ií]mite|"
    r"reached the limit|no puedes seguir|can't follow|captcha|"
    r"verify you are human|verifica que eres humano|rate.limit.exceeded|"
    r"too many requests|(?:http|error)\s*429", re.I,
)


# 09/10: el aviso real de TikTok es SOLO de seguir («Estas usando la opcion de seguir con demasiada frecuencia»): revierte el follow, no impide dar like
# ni comentar. Se distingue de un captcha/aviso general para pausar unicamente los follows.
FOLLOW_LIMIT = re.compile(
    r"seguir\s+con\s+demasiada\s+frecuencia|usando\s+la\s+opci[oó]n\s+de\s+seguir|"
    r"no\s+puedes\s+seguir|can'?t\s+follow|following\s+too\s+(?:fast|frequently)|"
    r"follow(?:ing)?\s+limit|l[ií]mite\s+de\s+(?:seguidos|seguir)", re.I,
)
FOLLOW_LADDER = (60, 120, 240, 480)      # minutos por aviso consecutivo del dia (tope 8 h); la sonda real ajusta la escalera (limit_observations.csv)


class SafetyStateError(RuntimeError):
    pass


class SafetyBlocked(RuntimeError):
    pass


class SafetyWarning(RuntimeError):
    pass


class SafetyFollowLimit(SafetyWarning):
    """Limite de seguir de la plataforma: pausa solo los follows (like/comment siguen)."""


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _read(path=None):
    try:
        with open(path or COOLDOWN_PATH, encoding="utf-8") as f:
            value = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, UnicodeError) as exc:
        raise SafetyStateError("estado de TikTok ilegible; revisar manualmente") from exc
    if not isinstance(value, dict):
        raise SafetyStateError("estado de TikTok no es objeto")
    if value and not (value.get("until") or value.get("manual_review")):
        raise SafetyStateError("estado de TikTok inválido")
    if value.get("scope") not in (None, "follow"):
        raise SafetyStateError("ámbito de pausa inválido")
    return value


def _date(value):
    try:
        parsed = dt.datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise SafetyStateError("fecha de pausa inválida") from exc
    return parsed if parsed.tzinfo else parsed.astimezone()  # legacy: hora local


def follow_paused(path=None, *, now=None):
    """True si hay una pausa activa de ambito `follow` (los follows esperan; like/comment pueden seguir)."""
    state = _read(path)
    until = state.get("until")
    return bool(state.get("scope") == "follow" and until and _date(until) > (now or _now()))


def _follow_only(state, kind):
    """Una pausa de ambito `follow` no bloquea like/comment; con kind=None (llamadores antiguos / bulk) bloquea todo, como antes."""
    return state.get("scope") == "follow" and kind in ("like", "comment") and state.get("manual_review") is not True


def require_writable(path=None, *, now=None, kind=None):
    state = _read(path)
    if not state:
        return
    if _follow_only(state, kind):
        return
    if state.get("manual_review") is True:
        raise SafetyBlocked("se requiere revisión manual")
    if state.get("manual_review") not in (None, False):
        raise SafetyStateError("manual_review inválido")
    until = state.get("until")
    if until and _date(until) > (now or _now()):
        raise SafetyBlocked("pausa por aviso de TikTok")


def remaining_minutes(path=None, *, kind=None):
    state = _read(path)
    if _follow_only(state, kind):
        return 0.
    if state.get("manual_review") is True:
        return float("inf")
    until = state.get("until")
    return max(0., (_date(until) - _now()).total_seconds() / 60) if until else 0.


def restrict(reason, path=None, *, now=None):
    if reason not in ("warning", "rate", "challenge", "wrong_account", "uncertain", "follow_limit"):
        raise ValueError("señal desconocida")
    path = path or COOLDOWN_PATH
    now = now or _now()
    prev = _read(path)
    if reason == "follow_limit":
        return _restrict_follow(path, now, prev)
    try:
        old = int(prev.get("strikes", 0))
    except (TypeError, ValueError) as exc:
        raise SafetyStateError("strikes inválido") from exc
    strikes = old + 1 if prev.get("day") == now.date().isoformat() else 1
    minutes = min(240, 60 * (2 ** min(strikes - 1, 2)))
    until = now + dt.timedelta(minutes=minutes)
    if prev.get("until"):
        until = max(until, _date(prev["until"]))
    payload = dict(day=now.date().isoformat(), strikes=strikes, reason=reason,
                   until=until.isoformat(timespec="seconds"), manual_review=True)
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".tiktok_stop_", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return minutes


def _restrict_follow(path, now, prev):
    """Pausa SOLO de follows (sin revision manual). Si ya hay una pausa global activa, esa manda y no se rebaja."""
    if prev.get("scope") != "follow" and prev.get("until") and _date(prev["until"]) > now:
        return max(0., (_date(prev["until"]) - now).total_seconds() / 60)
    try:
        old = int(prev.get("strikes", 0))
    except (TypeError, ValueError) as exc:
        raise SafetyStateError("strikes inválido") from exc
    strikes = old + 1 if prev.get("day") == now.date().isoformat() else 1
    minutes = FOLLOW_LADDER[min(strikes - 1, len(FOLLOW_LADDER) - 1)]
    until = now + dt.timedelta(minutes=minutes)
    if prev.get("until") and prev.get("scope") == "follow":
        until = max(until, _date(prev["until"]))
    payload = dict(day=now.date().isoformat(), strikes=strikes, reason="follow_limit",
                   until=until.isoformat(timespec="seconds"), scope="follow")
    _write_state(path, payload)
    _log_observation(path, now, strikes, minutes)
    return minutes


def _write_state(path, payload):
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".tiktok_stop_", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _log_observation(path, now, strikes, minutes):
    """Memoria de limites reales (cuantas acciones llevabamos al saltar el aviso y cuanto se descanso). Nunca rompe la parada."""
    try:
        folder = os.path.dirname(os.path.abspath(path))
        counts = {"follow": "?", "like": "?", "comment": "?"}
        registro = os.path.join(folder, "registro_interacciones.csv")
        if os.path.exists(registro):
            counts, _ = recorded_actions(registro, today=now.astimezone().date())
        target = os.path.join(folder, "limit_observations.csv")
        new = not os.path.exists(target)
        with open(target, "a", newline="", encoding="utf-8") as stream:
            w = csv.writer(stream)
            if new:
                w.writerow(["ts", "tipo", "strikes_hoy", "descanso_min", "follows_hoy", "likes_hoy", "comments_hoy"])
            w.writerow([now.isoformat(timespec="seconds"), "follow_limit", strikes, minutes,
                        counts["follow"], counts["like"], counts["comment"]])
    except Exception:       # noqa: BLE001
        pass


def check_screen(tree):
    from tiktok_mobile_interact import _visible_text
    text = _visible_text(tree) or ""
    if FOLLOW_LIMIT.search(text):
        raise SafetyFollowLimit("limite de seguir de TikTok en pantalla")
    if WARNINGS.search(text):
        raise SafetyWarning("aviso de TikTok en pantalla")


def step_status(status):
    if status not in ("completed", "busy", "restricted", "local_error", "uncertain", "no_budget"):
        raise ValueError("estado de etapa desconocido")
    print(f"TIKTOK_STEP_STATUS={status}", flush=True)



def recorded_actions(path, *, today=None):
    """Cupos confirmados o inciertos; los cierres con intent_id anulan solo su intento.

    Filas legacy sin ID permanecen conservadoras hasta conciliación humana.
    El parser nunca escribe ni hace llamadas a TikTok.
    """
    today = today or dt.date.today()
    daily = {kind: set() for kind in ("follow", "like", "comment")}
    pending = set()
    intents = {}   # id -> (key, fecha_apertura, estado): máquina append-only
    try:
        stream = open(path, encoding="utf-8-sig", newline="")
    except FileNotFoundError:
        return {k: 0 for k in daily}, pending
    except OSError as exc:
        raise SafetyStateError("registro no legible") from exc
    with stream:
        try:
            reader = csv.DictReader(stream, strict=True)
            header = reader.fieldnames or []
            if (not {"fecha", "tipo", "cuenta", "post_resumen", "resultado"} <= set(header)
                    or len(header) != len(set(header))):
                raise SafetyStateError("registro sin columnas necesarias o con cabecera duplicada")
            for row in reader:
                # DictReader(strict=True) NO rechaza campos que faltan o sobran:
                # en un WAL truncado no se puede inferir que la acción no ocurrió.
                if None in row or any(row.get(column) is None for column in header):
                    raise SafetyStateError("fila de registro incompleta o con columnas adicionales")
                kind = (row.get("tipo") or "").strip().casefold()
                result = (row.get("resultado") or "").strip().casefold()
                if kind not in daily:
                    continue
                target = ((row.get("cuenta") or "").strip().lstrip("@").casefold() if kind == "follow"
                          else (row.get("post_resumen") or "").strip())
                if not target:
                    if result in ("confirmado", "publicado", "pendiente_verificacion"):
                        raise SafetyStateError("acción registrada sin objetivo")
                    continue
                key = (kind, target)
                note = str(row.get("notas") or "")
                matches = re.findall(r"(?:^|\s\|\s)intent_id=([a-f0-9]{32})(?=\s\||$)", note)
                # Un token truncado o duplicado no puede degradarse a legacy:
                # en un cierre falso podría liberar un ACK de forma insegura.
                markers = re.findall(r"(?:^|\s\|\s)intent_id=", note)
                if markers and (len(markers) != 1 or len(matches) != 1):
                    raise SafetyStateError("identificador de intención repetido o inválido")
                if matches:
                    iid = matches[0]
                    try:
                        event_day = dt.date.fromisoformat((row.get("fecha") or "").strip())
                    except (TypeError, ValueError) as exc:
                        raise SafetyStateError("fecha de intención inválida") from exc
                    if result not in (
                        "pendiente_verificacion", "confirmado", "publicado",
                        "saltado_ya_like", "saltado_ya_seguido",
                        "saltado_ya_comentado", "pendiente_aprobacion",
                    ) and not result.startswith("saltado_like_contexto:"):
                        raise SafetyStateError("transición de intención desconocida")
                    result_kind = {
                        "saltado_ya_like": "like",
                        "saltado_ya_seguido": "follow",
                        "saltado_ya_comentado": "comment",
                        "pendiente_aprobacion": "follow",     # solicitud a cuenta privada: el tap ocurrio, consume cuota
                    }.get(result)
                    if (result_kind is not None and kind != result_kind) or (
                        result.startswith("saltado_like_contexto:") and kind != "like"
                    ):
                        raise SafetyStateError("cierre de intención incompatible con acción")
                    previous = intents.get(iid)
                    if previous is not None and previous[0] != key:
                        raise SafetyStateError("intención reusada para otra acción")
                    if previous is None:
                        if result != "pendiente_verificacion":
                            raise SafetyStateError("cierre de intención sin apertura")
                        intents[iid] = (key, event_day.isoformat(), result)
                    else:
                        if event_day.isoformat() < previous[1]:
                            raise SafetyStateError("cierre anterior a la apertura")
                        if previous[2] != "pendiente_verificacion" or result == "pendiente_verificacion":
                            raise SafetyStateError("intención reabierta o cerrada dos veces")
                        # La cuota pertenece a la fecha de apertura; cerrar al día
                        # siguiente nunca traslada retroactivamente el intento.
                        intents[iid] = (key, previous[1], result)
                    continue
                # Sin ID: no suponer que un 'confirmado' posterior resuelve un
                # pending anterior, porque pudo proceder de otra ejecución.
                if result not in ("confirmado", "publicado", "pendiente_verificacion"):
                    continue
                if result == "pendiente_verificacion":
                    pending.add(key)
                if (row.get("fecha") or "")[:10] == today.isoformat():
                    daily[kind].add(key)
        except (csv.Error, UnicodeError) as exc:
            raise SafetyStateError("registro CSV corrupto") from exc
    for key, date, result in intents.values():
        if result == "pendiente_verificacion":
            pending.add(key)
        if result in ("pendiente_verificacion", "confirmado", "publicado", "pendiente_aprobacion") and date == today.isoformat():
            daily[key[0]].add(key)
    return {kind: len(keys) for kind, keys in daily.items()}, pending


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("status", "reset"))
    cmd = parser.parse_args(argv).command
    if cmd == "reset":
        try:
            os.unlink(COOLDOWN_PATH)
        except FileNotFoundError:
            pass
        print("Revisión humana: pausa local borrada; no prueba permiso de TikTok")
        return 0
    try:
        require_writable()
    except (SafetyBlocked, SafetyStateError) as exc:
        print(f"BLOQUEADO: {exc}")
        return 1
    print("SIN PAUSA ACTIVA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

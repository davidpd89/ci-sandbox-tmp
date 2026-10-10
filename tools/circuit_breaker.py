"""Cortacircuitos de salud por red (03/10/2026, propuesta de ChatGPT).

`volume_shape` controla CUANTO se actua; esto controla SI se debe actuar: si una red empieza a dar
limite de peticiones (429), pide volver a iniciar sesion / verificacion, o las rondas fallan seguidas,
se detienen las rondas de esa red un tiempo (en vez de seguir insistiendo desde las tareas programadas).
Estado en `<carpeta de la red>/cache/breaker.json`; se cierra solo al pasar el enfriamiento y
`python tools/circuit_breaker.py <red>` lo muestra (`reset` lo cierra a mano).

Senales: 'rate' (429) -> pausa 3 h; 'auth' (login/verificacion/suspension) -> pausa 12 h;
3 rondas seguidas fallidas sin senal -> pausa 6 h (se duplica por cada fallo extra, tope 24 h).
"""
import contextlib
import datetime
from email.utils import parsedate_to_datetime
from enum import Enum
import json
import os
import re
import sys
import time
import uuid
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # CPython 3.8 legacy
    ZoneInfo = None
    ZoneInfoNotFoundError = KeyError

RATE = re.compile(r"(?:HTTP|status|codigo|error|RateLimit)\D{0,15}429|RATE.?LIMIT|Too Many Requests", re.I)
AUTH = re.compile(r"checkpoint_required|challenge_required|verify it'?s you|account (?:has been |is )?(?:suspended|locked)|"
                  r"cuenta (?:suspendida|bloqueada)|(?:HTTP|status|codigo|error)\D{0,15}401\b|ExpiredToken|InvalidToken|"
                  r"token (?:caducado|expired)|session (?:expired|caducada)|inicia sesi[oó]n para continuar|"
                  r"unusual activity|actividad inusual|temporarily restricted|temporalmente restringid|"
                  r"account (?:is )?limited|automated behaviou?r", re.I)
CAPTCHA = re.compile(r"(?im)^(?:.*?)\b(?:captcha[_ ](?:required|requerido|detected|detectado)|recaptcha[_ ]challenge|verificaci[oó]n[_ ]captcha)(?=$|[\s.!:;,])")
PAUSE_HOURS = {"rate": 3, "auth": 12}
# Nunca tratar un ACK remoto incierto como error recuperable automáticamente.
MANUAL_HOLD_REASONS = frozenset(("edge_ack_uncertain", "bulk_uncertain",
                                 "tiktok_native_uncertain", "external_complaint"))

class FailureCause(str, Enum):
    """Taxonomía cerrada de diagnóstico; nunca equivale a publicar/reintentar."""
    PLAN = "plan"
    PREFLIGHT = "preflight"
    INELIGIBLE = "ineligible"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    CAPTCHA = "captcha"
    EDGE_TIMEOUT = "edge_timeout"
    REMOTE_5XX = "remote_5xx"
    STORAGE = "storage"
    UNKNOWN = "unknown"


def cause_for(*, stage, signal=None, code=None, output=""):
    """La señal crítica manda; el código HTTP necesita contexto explícito."""
    if signal == "auth":
        return FailureCause.CAPTCHA if CAPTCHA.search(output or "") else FailureCause.AUTH
    if signal == "rate":
        return FailureCause.RATE_LIMIT
    if stage in ("plan", "build", "decide", "write"):
        return FailureCause.PLAN
    if stage == "preflight":
        return FailureCause.PREFLIGHT
    if code == 500 or (isinstance(code, int) and 500 <= code <= 599):
        return FailureCause.REMOTE_5XX
    if stage == "edge_timeout":
        return FailureCause.EDGE_TIMEOUT
    if stage == "storage":
        return FailureCause.STORAGE
    if stage == "ineligible":
        return FailureCause.INELIGIBLE
    return FailureCause.UNKNOWN


def _madrid_timezone():
    if ZoneInfo is not None:
        try:
            return ZoneInfo("Europe/Madrid")
        except ZoneInfoNotFoundError:
            pass  # Windows sin tzdata: usar zona local configurada en el equipo
    return datetime.datetime.now().astimezone().tzinfo


def _clock(now=None):
    if now is None:
        return datetime.datetime.now(datetime.timezone.utc).astimezone(_madrid_timezone())
    if now.tzinfo is None:
        # Las marcas legacy sin offset pertenecen a hora local Madrid.
        # fold=1 en una hora repetida: evita reapertura prematura.
        return now.replace(tzinfo=_madrid_timezone(), fold=1)
    return now


def _instant(stamp):
    return _clock(stamp).astimezone(datetime.timezone.utc)


def parse_retry_after(value, *, now=None):
    """RFC 9110: delta-seconds o HTTP-date. No parsear mensajes sin cabecera."""
    if not isinstance(value, str) or len(value) > 128:
        return None
    value = value.strip()
    if re.fullmatch(r"[0-9]{1,9}", value):
        return int(value)
    try:
        date = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if date.tzinfo is None:
        return None
    return max(0, int((date.astimezone(datetime.timezone.utc) -
                       _instant(now)).total_seconds()))


def retry_after_from_output(output):
    """Sólo cabecera cercana a una línea HTTP 429, no el texto libre del post."""
    lines = (output or "").splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s*(?:HTTP(?:/\d(?:\.\d)?)?\s+429|(?:API )?(?:HTTP )?(?:status|error)[: =]+429)\b", line, re.I):
            for item in lines[i+1:i+5]:
                match = re.fullmatch(r"\s*Retry-After:\s*(.{1,128})\s*", item, re.I)
                if match:
                    return match.group(1)
    return None

FAILS_TO_OPEN, BASE_FAIL_HOURS, MAX_HOURS = 3, 6, 24


def detect(text):
    """Senal grave en la salida de una ronda: 'auth', 'rate' o None."""
    if AUTH.search(text or "") or CAPTCHA.search(text or ""):
        return "auth"
    if RATE.search(text or ""):
        return "rate"
    return None


def worst(signals):
    """La senal mas grave de varias (auth > rate > ninguna)."""
    found = {s for s in signals if s}
    return "auth" if "auth" in found else ("rate" if "rate" in found else None)


def _path(network_dir):
    return os.path.join(network_dir, "cache", "breaker.json")


def load(network_dir):
    """Ausencia = sin historial; corrupto/inaccesible = bloqueo hasta revisión."""
    try:
        with open(_path(network_dir), encoding="utf-8") as stream:
            state = json.load(stream)
        if (not isinstance(state, dict)
                or type(state.get("fails")) is not int
                or not 0 <= state["fails"] <= 1_000_000
                or "open_until" not in state
                or type(state.get("manual_hold", False)) is not bool
                or (state.get("manual_hold") and
                    state.get("manual_hold_reason") not in MANUAL_HOLD_REASONS)
                or (state["open_until"] is not None and
                    (not isinstance(state["open_until"], str) or
                     not state["open_until"] or len(state["open_until"]) > 48))):
            raise ValueError("estructura breaker inválida")
        return state
    except FileNotFoundError:
        return {"fails": 0, "open_until": None, "reason": ""}
    except (OSError, ValueError, TypeError):
        return {"fails": 0, "open_until": None, "reason": "estado_invalido",
                "invalid": True}


def _save(network_dir, state):
    """Publica el breaker de forma atómica; ningún lector ve JSON a medias."""
    folder = os.path.join(network_dir, "cache")
    os.makedirs(folder, exist_ok=True)
    target = _path(network_dir)
    # Temporal en el mismo volumen: os.replace no trunca el estado vigente
    # si falla la escritura o se interrumpe el proceso antes del reemplazo.
    tmp = os.path.join(folder, f".breaker.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "x", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=1)
            stream.flush()
            os.fsync(stream.fileno())  # datos del hold antes de publicar el JSON
        os.replace(tmp, target)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


@contextlib.contextmanager
def _state_guard(network_dir):
    """Mutex entre procesos; espera brevemente sin robar el turno de otro PID."""
    import action_ledger as al
    folder = os.path.join(network_dir, "cache")
    os.makedirs(folder, exist_ok=True)
    for attempt in range(40):
        guard = al.exclusive("breaker_state", directory=folder)
        try:
            guard.__enter__()
        except al.RoundBusy:
            if attempt == 39:
                raise
            time.sleep(0.05)
        else:
            break
    try:
        yield
    except BaseException:
        guard.__exit__(*sys.exc_info())
        raise
    else:
        guard.__exit__(None, None, None)


def write_preflight(network, *, root=None, now=None):
    """Comprobación común, solo lectura, para escritores fuera de mechanical_round.

    Nunca interpretar estado ausente como una credencial comprobada: solo
    determina si existe una pausa conocida. Los ejecutores deben llamarla
    inmediatamente antes de la acción remota (tras cualquier espera de lock).
    """
    allowed = ("bluesky", "mastodon", "x", "threads", "facebook",
               "pinterest", "reddit", "tiktok", "instagram")
    if not isinstance(network, str) or network not in allowed:
        return False, "red no admitida; no se permite escribir"
    if root is None:
        # En producción nunca usar un directorio de tests por un override
        # de entorno heredado accidentalmente del shell/Scheduler.
        root = os.path.join(os.path.dirname(__file__), "..")
        if os.environ.get("RRSS_BREAKER_TEST_MODE") == "1":
            root = os.environ.get("RRSS_BREAKER_ROOT") or root
    directory = os.path.join(root, "SISTEMA_DIARIO_" + network.upper())
    # Solo códigos estructurados: nunca copiar al log del ejecutor el campo
    # libre reason de un breaker.json heredado u originado por otra herramienta.
    state = load(directory)
    if state.get("invalid"):
        return False, "estado_invalido"
    if state.get("manual_hold"):
        return False, str(state.get("manual_hold_reason") or "revision_manual")
    permitted, _ = check(directory, now=now)
    return permitted, "" if permitted else "cooldown_activo"


def check(network_dir, now=None):
    """(permitido, motivo). El JSON corrupto no da permiso por defecto."""
    now = _clock(now)
    state = load(network_dir)
    if state.get("invalid"):
        return False, "estado cortacircuitos inválido; revisión manual necesaria"
    if state.get("manual_hold"):
        return False, ("Queja externa pendiente de revisión humana"
                       if state.get("manual_hold_reason") == "external_complaint"
                       else "ACK remoto incierto; requiere reconciliación y reset manual")
    until = state.get("open_until")
    if not until:
        return True, ""
    try:
        deadline = datetime.datetime.fromisoformat(until)
        if _instant(now) < _instant(deadline):
            return False, f"{state.get('reason') or 'fallos seguidos'}; pausada hasta {until[:22]}"
    except (TypeError, ValueError, OverflowError):
        return False, "caducidad del cortacircuitos inválida; revisión manual necesaria"
    return True, ""


def _record_unlocked(network_dir, ok, signal=None, now=None, reason="", retry_after=None, origin="mechanical_round"):
    """Anota una ronda; las señales críticas dominan incluso con exit=0.

    Se conserva el esquema legacy del breaker.json. Las pausas nuevas usan
    instantes UTC para sumar el plazo y hora de Madrid con offset para mostrarlo.
    """
    now = _clock(now)
    state = load(network_dir)
    if state.get("invalid"):
        raise ValueError("breaker inválido; no sobrescribir cuarentena")
    if state.get("manual_hold") and signal not in PAUSE_HOURS:
        # Ni una ronda que parezca satisfactoria revoca un ACK incierto.
        return state
    if signal in PAUSE_HOURS:
        hours = PAUSE_HOURS[signal]
        wait = datetime.timedelta(hours=hours)
        if signal == "rate" and retry_after is not None:
            delay = parse_retry_after(retry_after, now=now)
            if delay is not None:
                wait = max(wait, datetime.timedelta(seconds=delay))
        deadline = (_instant(now) + wait).astimezone(_madrid_timezone())
        previous = state.get("open_until")
        keep_previous = False
        if previous:
            try:
                existing = _instant(datetime.datetime.fromisoformat(previous))
                if existing >= _instant(deadline):
                    deadline = existing.astimezone(_madrid_timezone())
                    keep_previous = True
            except (TypeError, ValueError, OverflowError):
                raise ValueError("fecha de cuarentena previa corrupta")
        state.update(fails=state.get("fails", 0) + 1,
                     reason=(state.get("reason") if keep_previous else (reason or signal)),
                     open_until=deadline.isoformat(timespec="seconds"),
                     cause=(state.get("cause", FailureCause.UNKNOWN.value) if keep_previous
                            else FailureCause.RATE_LIMIT.value if signal == "rate"
                            else FailureCause.AUTH.value),
                     origin=(state.get("origin", "legacy") if keep_previous else str(origin)[:40]),
                     opened_at=(state.get("opened_at", now.isoformat(timespec="seconds"))
                                if keep_previous else now.isoformat(timespec="seconds")),
                     timezone="Europe/Madrid")
    elif ok:
        state = {"fails": 0, "open_until": None, "reason": ""}
    else:
        fails = state.get("fails", 0) + 1
        old_reason = state.get("reason")
        state.update(fails=fails, reason=reason or "rondas fallidas")
        if fails >= FAILS_TO_OPEN:
            hours = min(MAX_HOURS, BASE_FAIL_HOURS * 2 ** (fails - FAILS_TO_OPEN))
            deadline = (_instant(now) + datetime.timedelta(hours=hours)).astimezone(_madrid_timezone())
            previous = state.get("open_until")
            keep_previous = False
            if previous:
                try:
                    existing = _instant(datetime.datetime.fromisoformat(previous))
                    if existing >= _instant(deadline):
                        deadline = existing.astimezone(_madrid_timezone())
                        keep_previous = True
                except (TypeError, ValueError, OverflowError):
                    raise ValueError("fecha de cuarentena previa corrupta")
            state.update(open_until=deadline.isoformat(timespec="seconds"),
                         reason=old_reason if keep_previous else state["reason"],
                         cause=(state.get("cause", FailureCause.UNKNOWN.value)
                                if keep_previous else FailureCause.UNKNOWN.value),
                         origin=(state.get("origin", "legacy") if keep_previous
                                 else str(origin)[:40]),
                         opened_at=(state.get("opened_at", now.isoformat(timespec="seconds"))
                                    if keep_previous else now.isoformat(timespec="seconds")),
                         timezone="Europe/Madrid")
    _save(network_dir, state)
    return state


def record(network_dir, ok, signal=None, now=None, reason="", retry_after=None,
           origin="mechanical_round"):
    """Actualización indivisible por directorio; nunca perder una cuarentena concurrente."""
    with _state_guard(network_dir):
        return _record_unlocked(network_dir, ok, signal=signal, now=now,
                                reason=reason, retry_after=retry_after, origin=origin)


def hold_for_review(network_dir, reason, *, now=None, origin="mechanical_round"):
    """Bloqueo de una red hasta conciliación humana; independiente de cooldown."""
    if reason not in MANUAL_HOLD_REASONS:
        raise ValueError("motivo de revisión manual no permitido")
    with _state_guard(network_dir):
        state = load(network_dir)
        if state.get("invalid"):
            raise ValueError("breaker inválido; retención no persistida")
        if not state.get("manual_hold"):
            state.update(manual_hold=True, manual_hold_reason=reason,
                         manual_hold_at=_clock(now).isoformat(timespec="seconds"),
                         manual_hold_origin=str(origin)[:40])
            _save(network_dir, state)
        return state


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(__doc__)
        return 2
    if argv[0].lower() not in ("bluesky", "mastodon", "x", "threads", "facebook",
                               "pinterest", "reddit", "tiktok", "instagram"):
        print("red no admitida")
        return 2
    root = os.path.join(os.path.dirname(__file__), "..")
    directory = os.path.join(root, f"SISTEMA_DIARIO_{argv[0].upper()}")
    if "reset" in argv[1:]:
        with _state_guard(directory):
            current = load(directory)
            if current.get("invalid"):
                print("estado corrupto: no se autoriza reset sin investigar")
                return 2
            if (current.get("manual_hold_reason") == "external_complaint"
                    and "--revisado" not in argv[1:]):
                print("queja externa: requiere reset --revisado tras comprobar el aviso")
                return 2
            _save(directory, {"fails": 0, "open_until": None, "reason": ""})
        print(f"{argv[0]}: cortacircuitos cerrado a mano")
        return 0
    allowed, why = check(directory)
    print(f"{argv[0]}: {'cerrado (se puede actuar)' if allowed else 'ABIERTO: ' + why}; estado {load(directory)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

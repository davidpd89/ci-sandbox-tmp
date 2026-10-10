"""Cortacircuitos de salud por red (03/10/2026, propuesta de ChatGPT).

`volume_shape` controla CUANTO se actua; esto controla SI se debe actuar: si una red empieza a dar
limite de peticiones (429), pide volver a iniciar sesion / verificacion, o las rondas fallan seguidas,
se detienen las rondas de esa red un tiempo (en vez de seguir insistiendo desde las tareas programadas).
Estado en `<carpeta de la red>/cache/breaker.json`; se cierra solo al pasar el enfriamiento y
`python tools/circuit_breaker.py <red>` lo muestra (`reset` lo cierra a mano).

Senales: 'rate' (429) -> pausa 3 h; 'auth' (login/verificacion/suspension) -> pausa 12 h;
3 rondas seguidas fallidas sin senal -> pausa 6 h (se duplica por cada fallo extra, tope 24 h).
"""
import datetime
import json
import os
import re
import sys
import uuid

RATE = re.compile(r"(?:HTTP|status|codigo|error|RateLimit)\D{0,15}429|RATE.?LIMIT|Too Many Requests", re.I)
AUTH = re.compile(r"checkpoint_required|challenge_required|verify it'?s you|account (?:has been |is )?(?:suspended|locked)|"
                  r"cuenta (?:suspendida|bloqueada)|(?:HTTP|status|codigo|error)\D{0,15}401\b|ExpiredToken|InvalidToken|"
                  r"token (?:caducado|expired)|session (?:expired|caducada)|inicia sesi[oó]n para continuar|"
                  r"unusual activity|actividad inusual|temporarily restricted|temporalmente restringid|"
                  r"account (?:is )?limited|automated behaviou?r", re.I)
PAUSE_HOURS = {"rate": 3, "auth": 12}
FAILS_TO_OPEN, BASE_FAIL_HOURS, MAX_HOURS = 3, 6, 24


def detect(text):
    """Senal grave en la salida de una ronda: 'auth', 'rate' o None."""
    if AUTH.search(text or ""):
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
    try:
        with open(_path(network_dir), encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return {"fails": 0, "open_until": None, "reason": ""}


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
        os.replace(tmp, target)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def check(network_dir, now=None):
    """(permitido, motivo). Cerrado = se puede actuar."""
    now = now or datetime.datetime.now()
    state = load(network_dir)
    until = state.get("open_until")
    if until and now < datetime.datetime.fromisoformat(until):
        return False, f"{state.get('reason') or 'fallos seguidos'}; pausada hasta {until[:16]}"
    return True, ""


def record(network_dir, ok, signal=None, now=None, reason=""):
    """Anota el resultado de una ronda y devuelve el estado. Una senal grave abre el cortacircuitos al
    momento; un exito lo resetea."""
    now = now or datetime.datetime.now()
    state = load(network_dir)
    if signal in PAUSE_HOURS:
        hours = PAUSE_HOURS[signal]
        state.update(fails=state.get("fails", 0) + 1, reason=reason or signal,
                     open_until=(now + datetime.timedelta(hours=hours)).isoformat(timespec="minutes"))
    elif ok:
        state = {"fails": 0, "open_until": None, "reason": ""}
    else:
        fails = state.get("fails", 0) + 1
        state.update(fails=fails, reason=reason or "rondas fallidas")
        if fails >= FAILS_TO_OPEN:
            hours = min(MAX_HOURS, BASE_FAIL_HOURS * 2 ** (fails - FAILS_TO_OPEN))
            state["open_until"] = (now + datetime.timedelta(hours=hours)).isoformat(timespec="minutes")
    _save(network_dir, state)
    return state


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(__doc__)
        return 2
    root = os.path.join(os.path.dirname(__file__), "..")
    directory = os.path.join(root, f"SISTEMA_DIARIO_{argv[0].upper()}")
    if "reset" in argv[1:]:
        _save(directory, {"fails": 0, "open_until": None, "reason": ""})
        print(f"{argv[0]}: cortacircuitos cerrado a mano")
        return 0
    allowed, why = check(directory)
    print(f"{argv[0]}: {'cerrado (se puede actuar)' if allowed else 'ABIERTO: ' + why}; estado {load(directory)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

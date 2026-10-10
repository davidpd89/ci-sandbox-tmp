"""Ronda mecanica sin IA para Bluesky/Mastodon (02/10) - "mayor interaccion,
menor coste": descubrir, decidir con reglas y ejecutar likes/follows/favourites
sin gastar ni un token. La IA queda solo para lo editorial (replies con texto,
boosts/reposts/citas), que se hace aparte con growth_reply_view.py.

    python tools/mechanical_round.py bluesky
    python tools/mechanical_round.py mastodon [--dry]

Pasos (cada uno corta la ronda si falla), siempre empezando por dar like a toda
respuesta recibida (conversation_followups --like):
  Bluesky : prepare -> build (decisiones vacias; el builder anade auto_plan) -> execute
  Mastodon: prepare -> mastodon_auto_decide -> build -> execute
`--dry` se detiene tras construir el plan (no escribe nada en la red).
Volumen alto y variable (03/10): `--spread N` retrasa el arranque 0-N min al azar, `--daily N`
cambia el objetivo diario (por defecto Bluesky 700, Mastodon 500: 4-6 % del limite real de la
API), `--no-shape` ejecuta el plan sin recortar. Ver `volume_shape.py`.
Salida: un resumen corto; el log completo va a
SISTEMA_DIARIO_<RED>/cache/mech_<fecha>.log.
"""
import contextlib
import contextvars
import datetime
import json
import os
import random
import re
import subprocess
import sys
import time

import circuit_breaker as cb

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY = sys.executable

EDGE_WAIT_MINUTES = 120   # tiempo maximo que una ronda por navegador espera el turno del Edge antes de saltarse
LOCK_DIR = None  # carpeta de los bloqueos entre procesos (None = carpeta temporal del sistema); los tests usan una propia

PUBLISH_NETWORKS = {"bluesky", "mastodon", "threads", "x", "pinterest"}      # redes con publicacion automatica de fichas (content_publisher.py)
CONTENT_QUEUE_NETWORKS = {"bluesky", "mastodon", "threads", "x", "facebook", "instagram", "reddit", "pinterest", "tiktok"}

PIPELINES = {
    "bluesky": {
        "dir": "SISTEMA_DIARIO_BLUESKY",
        "decisions": "bluesky_mech_decisions.json",
        "plan": "bluesky_mech_plan.json",
        "pre": [[PY, "tools/conversation_followups.py", "bluesky", "--like"],
                [PY, "tools/bluesky_growth_flow.py", "prepare"],
                [PY, "tools/api_comment_writer.py", "bluesky", "--reset"]],      # 07/10: comentarios escritos por ChatGPT (sin IA la ronda no comentaba nada); escribe las decisiones
        "write_decisions": None,
        "decisions_default": {"actions": []},
        "build": [PY, "tools/bluesky_growth_flow.py", "build", "bluesky_mech_decisions.json",
                  "--plan", "bluesky_mech_plan.json"],
        "execute": [PY, "tools/bluesky_execute.py", "bluesky_mech_plan.json"],
        # 05/10: segunda fuente curada: editoriales/escritores/librerias -> quien les comenta -> follow + like (bluesky_seed_wave.py).
        # Se ejecuta despues del plan normal y su fallo no tumba la ronda.
        "post": [[PY, "tools/loyalty.py", "bluesky"],                                  # 07/10: fidelizacion (cosecha de quien nos da like/comenta/sigue + premio)
                 [PY, "tools/bluesky_execute.py", "SISTEMA_DIARIO_BLUESKY/bluesky_loyalty_plan.json"],
                 [PY, "tools/bluesky_seed_wave.py", "wave"],
                 [PY, "tools/bluesky_execute.py", "SISTEMA_DIARIO_BLUESKY/bluesky_seed_wave.json"],
                 # follow a cuentas con bio de nicho que siguen a gente (el 02/10 era "la mejor palanca"; antes solo se lanzaba a mano). Segundo escalon
                 # de volumen: lo que queda bajo el umbral del auto_plan pero cumple las senales de follow-back.
                 [PY, "tools/bluesky_followback_wave.py", "growth_state.json", "bluesky_follow_wave.json", "--max", "120"],
                 [PY, "tools/bluesky_execute.py", "bluesky_follow_wave.json"],
                 # los reposts automaticos (<=8 por ronda) caducan solos a los 5 dias, como pidio David (impacto a corto plazo): sin esto se acumularian en su perfil
                 [PY, "tools/bluesky_cleanup_ttl.py"],
                 # limpieza de a quien seguimos (06/10): sin devolver el follow tras 7 dias, o con biografia en otro idioma; solo cuentas que siguio el sistema
                 [PY, "tools/unfollow_cleanup.py", "bluesky", "--apply", "--max", "150"],
                 # autoauditoria + decision diaria de la rampa de volumen (05/10): el sistema detecta sus huecos y sube/baja de etapa solo
                 [PY, "tools/bluesky_self_audit.py", "--decide"],
                 [PY, "tools/reciprocity_stats.py", "bluesky", "--apply"]],      # 07/10: follow-back por hub (bayesiano); retira los hubs promovidos que no devuelven
    },
    "mastodon": {
        "dir": "SISTEMA_DIARIO_MASTODON",
        "decisions": "mastodon_mech_decisions.json",
        "plan": "mastodon_mech_plan.json",
        "pre": [[PY, "tools/conversation_followups.py", "mastodon", "--like"],
                [PY, "tools/mastodon_growth_flow.py", "prepare"],
                [PY, "tools/mastodon_auto_decide.py", "--max-pool-follows", "30",
                 "--out", "mastodon_mech_decisions.json"],
                [PY, "tools/api_comment_writer.py", "mastodon"]],      # 07/10: anade comentarios escritos por ChatGPT a las decisiones del auto_decide
        "write_decisions": None,  # lo escribe mastodon_auto_decide
        "build": [PY, "tools/mastodon_growth_flow.py", "build", "mastodon_mech_decisions.json",
                  "--plan", "mastodon_mech_plan.json"],
        "execute": [PY, "tools/mastodon_execute.py", "mastodon_mech_plan.json"],
        # autoauditoria + decision diaria de la rampa (05/10, clon de la de Bluesky); su fallo no tumba la ronda
        # los boosts automaticos (<=8 por ronda; paridad con los reposts de Bluesky, 06/10) caducan solos a los 5 dias, igual que alli
        "post": [[PY, "tools/loyalty.py", "mastodon"],                                 # 07/10: fidelizacion (cosecha + premio)
                 [PY, "tools/mastodon_execute.py", "SISTEMA_DIARIO_MASTODON/mastodon_loyalty_plan.json"],
                 [PY, "tools/mastodon_welcome.py", "--max", "3"],            # 06/10: bienvenida a quien se presenta en espanol y le interesan los libros (aprendido de la mencion de @rober)
                 [PY, "tools/mastodon_execute.py", "mastodon_welcome_plan.json"],
                 [PY, "tools/mastodon_cleanup_ttl.py"],
                 [PY, "tools/unfollow_cleanup.py", "mastodon", "--apply", "--max", "100"],
                 [PY, "tools/mastodon_self_audit.py", "--decide"],
                 [PY, "tools/reciprocity_stats.py", "mastodon", "--apply"]],
    },
    # Redes por navegador (03/10): el scan ya devuelve candidatos estructurados y un constructor mecanico
    # genera likes/follows; las replies siguen siendo editoriales. "browser" => un solo Edge: las rondas
    # de redes por navegador se turnan con el bloqueo `edge_browser`.
    "x": {
        "dir": "SISTEMA_DIARIO_X",
        "browser": True,
        # 06/10 (David: «quitale tanta restriccion, que tenga rondas y crezca como el resto»): las rondas/dia las pone la ETAPA de la rampa (volume_ramp.X_STAGES), como en Threads.
        "min_plan": 20,       # un plan mas pobre es fallo del scan, no "dia tranquilo": hay que reforzar a mano
        "decisions": None,
        "plan": "SISTEMA_DIARIO_X/x_plan.json",
        "pre": [[PY, "tools/x_scan.py"], [PY, "tools/x_build_plan.py"], [PY, "tools/reply_writer.py", "x"]],
        "write_decisions": None,
        "build": None,
        "execute": [PY, "tools/x_execute.py", "SISTEMA_DIARIO_X/x_plan.json"],
        # los retuits/citas propios caducan a los 7 dias (growth_policy.SHARE_TTL_DAYS) como los reposts de Bluesky y los boosts de Mastodon: perfil limpio
        "post": [[PY, "tools/x_cleanup_ttl.py"],
                 # 06/10: misma limpieza que Bluesky, Mastodon y Threads (sin devolver el follow tras 7 dias / otro idioma) y autoauditoria con decision diaria de la rampa
                 [PY, "tools/unfollow_cleanup.py", "x", "--apply", "--max", "25"],
                 [PY, "tools/x_self_audit.py", "--decide"],
                 # 07/10: perfiles verificados que siguen casi tantas cuentas como les siguen pasan a semillas (ciclo de hubs de reciprocidad, ver reciprocity.py)
                 [PY, "tools/reciprocity.py", "promote", "x"]],
    },
    "threads": {
        "dir": "SISTEMA_DIARIO_THREADS",
        "browser": True,
        "min_plan": 12,
        "decisions": None,
        "plan": "SISTEMA_DIARIO_THREADS/threads_plan.json",
        "pre": [[PY, "tools/threads_scan.py"], [PY, "tools/threads_build_plan.py"], [PY, "tools/reply_writer.py", "threads"]],
        "write_decisions": None,
        "build": None,
        "execute": [PY, "tools/threads_execute.py", "SISTEMA_DIARIO_THREADS/threads_plan.json"],
        # autoauditoria (05/10): vigila reserva, fiabilidad y avisos; la etapa sube sola ante dias sanos y baja ante avisos (06/10: David quito el limite solo-manual)
        "post": [[PY, "tools/reciprocity.py", "promote", "threads"],      # 07/10: hubs de reciprocidad (el dialogo de seguidores trae «Seguidos N»)
                 [PY, "tools/unfollow_cleanup.py", "threads", "--apply", "--max", "20"],      # 06/10: misma limpieza que Bluesky y Mastodon (sin devolver el follow tras 7 dias / otro idioma)
                 [PY, "tools/threads_self_audit.py", "--decide"]],
    },
    # 04/10 (David): Facebook, Instagram y Pinterest pasan a ronda diaria por navegador. Sin `volume_shape` (shape=False):
    # sus topes salen del propio flujo (10 follows/dia en Instagram, calentamiento suave) y no hay base diaria que modular.
    "facebook": {
        "dir": "SISTEMA_DIARIO_FACEBOOK",
        "browser": True,
        "shape": False,
        "runs_per_day": 6,     # 07/10 (David: cuotas mucho mas altas): 6 rondas al dia (13:30 + franjas 2-6) con consultas distintas cada una; reserva persistente
        "min_plan": 4,
        "decisions": None,
        "plan": "SISTEMA_DIARIO_FACEBOOK/facebook_plan.json",
        # likes por API oficial a los comentarios recibidos (gratis) + salida a paginas ajenas por navegador (la API no lo permite)
        "pre": [[PY, "tools/facebook_api.py", "likes", "--like"], [PY, "tools/facebook_scan.py"], [PY, "tools/facebook_build_plan.py"], [PY, "tools/reply_writer.py", "facebook"]],
        "write_decisions": None,
        "build": None,
        "execute": [PY, "tools/facebook_execute.py", "SISTEMA_DIARIO_FACEBOOK/facebook_plan.json"],
    },
    "instagram": {
        "dir": "SISTEMA_DIARIO_INSTAGRAM",
        "browser": True,
        "shape": False,
        "runs_per_day": 1,
        "min_plan": 6,
        "decisions": None,
        "plan": "SISTEMA_DIARIO_INSTAGRAM/instagram_plan.json",
        "pre": [[PY, "tools/instagram_commenters_scan.py"], [PY, "tools/instagram_build_plan.py"]],
        "write_decisions": None,
        "build": None,
        "execute": [PY, "tools/instagram_execute.py", "SISTEMA_DIARIO_INSTAGRAM/instagram_plan.json"],
    },
    "pinterest": {
        "dir": "SISTEMA_DIARIO_PINTEREST",
        "browser": True,
        "shape": False,
        "runs_per_day": 5,     # 07/10 (David: «0 movimiento»): 5 rondas al dia (14:30 + franjas 2-5), cada una con consultas distintas
        "min_plan": 20,
        "decisions": None,
        "plan": "SISTEMA_DIARIO_PINTEREST/pinterest_plan.json",
        "pre": [[PY, "tools/pinterest_growth.py", "scan"], [PY, "tools/pinterest_growth.py", "plan"]],
        "write_decisions": None,
        "build": None,
        "execute": [PY, "tools/pinterest_growth.py", "run"],
    },
}

# TikTok (movil Android, 06/10: la sesion «Android fisico con mobilecli y TikTok» entrego `growth_core.py`; David pidio integrarlo en el flujo comun). No lleva `browser`: el recurso que se turna es el
# MOVIL y los pasos de scan y ejecucion toman `mobile_runtime.mobile_session_lock` ellos mismos (no se envuelve aqui para no bloquearse a si mismos).
import growth_core
PIPELINES["tiktok"] = growth_core.pipeline_for("tiktok", PY)
PIPELINES["tiktok"]["pre"] = [[PY, "tools/tiktok_bulk_follow.py", "--max-follows", "120", "--max-minutes", "50"],      # 07/10: seguimiento masivo (followback, apoyo mutuo, listas): donde esta la gente que devuelve el follow; respeta su descanso por aviso de TikTok
                              [PY, "tools/tiktok_growth_flow.py", "prepare", "--reuse-hours", "5"], [PY, "tools/tiktok_comment_writer.py"]]          # 07/10: comentarios escritos por ChatGPT (sin IA no comentaba nada)
PIPELINES["tiktok"]["post"] = [[PY, "tools/tiktok_reciprocity_audit.py", "--min-age-days", "3", "--every-hours", "6"]]      # 07/10: follow-back real por fuente/semilla (alimenta la eleccion de semillas del seguimiento masivo)
PIPELINES["tiktok"]["build"] = [PY, "tools/tiktok_growth_flow.py", "build", "tiktok_decisions.json", "--plan", "tiktok_plan.json", "--no-follows"]
PIPELINES["tiktok"]["runs_per_day"] = 6      # 07/10 (David): 4 rondas hoy para ver el resultado manana

CONFIRMED = re.compile(r"^confirmado\s+(\w+)", re.MULTILINE)
SKIPPED = re.compile(r"^(saltado\w*|OMITIDO)", re.MULTILINE)
FAILED = re.compile(r"^(FALLO[^\n]*|PARADA[^\n]*)", re.MULTILINE)


def summarize(output):
    """Cuenta confirmadas por tipo, saltadas y fallos de la salida del ejecutor."""
    kinds = {}
    for kind in CONFIRMED.findall(output):
        kinds[kind] = kinds.get(kind, 0) + 1
    return {
        "confirmadas": kinds,
        "saltadas": len(SKIPPED.findall(output)),
        "fallos": [line[:160] for line in FAILED.findall(output)][:5],
    }


# El permiso de delegar Edge pertenece al contexto actual, NO a os.environ
# (compartido por todos los hilos). Solo default_runner lo pasa al hijo.
_BROWSER_OWNER_PID = contextvars.ContextVar("rrss_edge_owner_pid", default=None)


def default_runner(cmd):
    # No heredar permisos de Edge desde variables ambientales ajenas.
    keys = {"RRSS_BROWSER_LOCK_HELD", "RRSS_BROWSER_LOCK_OWNER_PID",
            "RRSS_BROWSER_LOCK_OWNER_BIRTH"}
    env = {key: value for key, value in os.environ.items() if key not in keys}
    env["PYTHONIOENCODING"] = "utf-8"
    owner_pid = _BROWSER_OWNER_PID.get()
    if owner_pid is not None:
        from process_identity import creation_token
        env["RRSS_BROWSER_LOCK_HELD"] = "edge_browser"
        env["RRSS_BROWSER_LOCK_OWNER_PID"] = str(owner_pid)
        birth = creation_token(owner_pid)
        if birth:
            env["RRSS_BROWSER_LOCK_OWNER_BIRTH"] = birth
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _local_python_error(text):
    """Solo la excepción final del proceso, no un texto de terceros intermedio."""
    lines = (text or "").strip().splitlines()
    if not lines:
        return None
    found = re.fullmatch(
        r"(?:[A-Za-z_][A-Za-z_0-9]*\.)*(NameError|SyntaxError|"
        r"ImportError|ModuleNotFoundError|FileNotFoundError|JSONDecodeError):[^\r\n]*",
        lines[-1][:2048],
    )
    return found.group(1) if found else None


def _remote_http_failure(text):
    """HTTP 403/5xx tipado en salida: dependencia, no JSON/plan inválido."""
    return bool(re.search(
        r"\b(?:HTTP|status|c[oó]digo|error)\D{0,12}(?:403|5\d\d)\b",
        text or "", re.IGNORECASE
    ))


def _pre_failure_kind(cmd):
    """Un scan/prepare remoto cuenta como ejecución; build/decide/write, plan."""
    script = os.path.basename(str(cmd[1])).lower()
    args = [str(part).lower() for part in cmd[2:]]
    remote_prepare = script in {
        "bluesky_growth_flow.py", "mastodon_growth_flow.py",
        "tiktok_growth_flow.py", "pinterest_growth.py",
    } and any(arg in ("scan", "prepare") for arg in args)
    if script.endswith("_scan.py") or remote_prepare or script == "tiktok_bulk_follow.py":
        return "scan", "execute"
    if "decide" in script:
        return "decide", "plan"
    if "writer" in script:
        return "write", "plan"
    if "build" in script or (script == "pinterest_growth.py" and "plan" in args):
        return "build", "plan"
    return "plan", "plan"


def _record_plan_failure(network, stage, log_path, cause="error"):
    """Persistencia mínima de aviso local, sin contenido de terceros."""
    import plan_failure_events
    return plan_failure_events.record(ROOT, network, stage, log_path, cause=cause)


def run(network, *, dry=False, runner=default_runner, today=None, out=print,
        spread_minutes=0, daily=None, shape=True, rng=None, sleeper=None, slot=None):
    import action_ledger as al
    import volume_shape as vs
    if slot and slot > vs.runs_per_day(network, PIPELINES.get(network)):
        # franjas extra programadas (05/10): solo corren si la etapa de la rampa pide tantas rondas al dia
        out(f"[{network}] franja {slot} > {vs.runs_per_day(network, PIPELINES.get(network))} rondas/dia de la etapa actual: no se lanza")
        return {"ok": True, "skipped": True, "log": None}
    if rng is None:
        import volume_shape as _vs
        now = datetime.datetime.now()
        seed = _vs.run_seed(today or datetime.date.today(), network, now.hour)
        rng = random.Random(seed)
        out(f"[{network}] semilla de la ronda {seed} (reproducible: fecha+red+hora)")
    if spread_minutes and not dry:
        # arranque con retraso aleatorio: las tareas programadas no deben salir siempre al segundo
        delay = rng.uniform(0, spread_minutes * 60)
        out(f"[{network}] arranque diferido {delay / 60:.1f} min (variacion humana)")
        (sleeper or time.sleep)(delay)
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(al.exclusive(f"round_{network}", directory=LOCK_DIR))
            if PIPELINES[network].get("browser"):
                # un solo Edge (CDP 9223): X y Threads no pueden usarlo a la vez
                # 06/10: con 8-10 rondas de Threads + las de X + FB/IG/Pinterest compartiendo UN Edge, una ronda que encontraba el turno ocupado se SALTABA entera; ahora espera
                # su turno (hasta EDGE_WAIT_MINUTES) en vez de perderse
                path = stack.enter_context(al.browser_session(wait_minutes=EDGE_WAIT_MINUTES, directory=LOCK_DIR))
                # Si ya somos hijos delegados, conservar el PID del propietario
                # original; no atribuir a este proceso un guard que no posee.
                owner_pid = (int(os.environ["RRSS_BROWSER_LOCK_OWNER_PID"])
                             if path is None and os.environ.get("RRSS_BROWSER_LOCK_OWNER_PID")
                             else os.getpid())
                token = _BROWSER_OWNER_PID.set(owner_pid)
                stack.callback(_BROWSER_OWNER_PID.reset, token)
            directory = os.path.join(ROOT, PIPELINES[network]["dir"])
            if not dry:
                allowed, why = cb.check(directory)
                if not allowed:
                    out(f"[{network}] cortacircuitos ABIERTO, no se actua: {why} (reset: python tools/circuit_breaker.py {network} reset)")
                    return {"ok": True, "skipped": True, "log": None}
            signals = []
            try:
                result = _run(network, dry=dry, runner=runner, today=today,
                              out=out, daily=daily, shape=shape, rng=rng,
                              signals=signals)
            except al.RoundBusy:
                raise
            except Exception as exc:
                # Error de orquestación local fuera del proceso hijo. No
                # confundirlo con una caída de la API ni ocultar la ronda.
                # No imprimir detalles: pueden contener rutas o credenciales.
                cause = type(exc).__name__
                out(f"[{network}] fallo interno al preparar la ronda: {cause}")
                result = {"ok": False, "stage": "plan", "failure_kind": "plan",
                          "error_reason": cause, "log": None}
            if not dry:
                signal = cb.worst(signals)
                # Una ronda omitida (móvil ocupado, sin acciones) no demuestra
                # recuperación de la red y NO debe resetear fallos antiguos.
                if result.get("skipped") and signal is None:
                    return result
                kind = result.get("failure_kind")
                if not result.get("ok") and kind not in ("plan", "execute"):
                    # Compatibilidad con retornos anteriores sin failure_kind:
                    # solo fases locales conocidas; lo demás cuenta como execute.
                    kind = ("plan" if result.get("stage") in
                            ("plan", "build", "preflight", "decide", "write")
                            else "execute")
                if result.get("ok", False) or signal is not None or kind == "execute":
                    # Un fallo del ejecutor (exit != 0) puede indicar Edge/API
                    # rota aun sin regex 429/auth; no excluirlo del breaker.
                    state = cb.record(directory, result.get("ok", False), signal=signal,
                                      reason=result.get("stage", kind or ""))
                    if state.get("open_until"):
                        out(f"[{network}] cortacircuitos ABIERTO hasta {state['open_until'][:16]} ({state.get('reason') or 'fallos seguidos'})")
                else:
                    saved = _record_plan_failure(network, result.get("stage") or "plan",
                                                 result.get("log"),
                                                 cause=result.get("error_reason") or
                                                 f"exit_{result.get('exit_code', 'unknown')}")
                    out(f"[{network}] FALLO_LOCAL_NO_BREAKER: etapa={result.get('stage') or 'plan'}, "
                        + ("evento en 00_OPERATIVO/cache/errores_plan"
                           if saved else "EVENTO_NO_PERSISTIDO; comprobar permisos de disco")
                        + "; revisar plan")
            return result
    except al.RoundBusy as exc:
        out(f"[{network}] otra ronda esta en curso, no se lanza otra a la vez: {exc}")
        return {"ok": False, "busy": True, "log": None}


def _phase_for_timing(label, cmd):
    """Fase estructural sin nombres de usuario ni argumentos privados."""
    script = os.path.basename(str(cmd[1])).lower() if len(cmd) > 1 else "desconocido"
    if label.startswith("post "):
        return "post", script
    if label.startswith("execute"):
        return "execute", script
    if script == "tiktok_bulk_follow.py":
        return "bulk", script
    if label == "build" or "_build_plan" in script or "writer" in script or "decide" in script:
        return "plan", script
    if "_scan" in script or "prepare" in cmd or "scan" in cmd:
        return "scan", script
    return "pre", script


def _time_runner(runner, cmd):
    """Cronometrar el subproceso sin cambiar la política de errores R5."""
    started = datetime.datetime.now().isoformat(timespec="seconds")
    before = time.monotonic()
    try:
        code, text = runner(cmd)
    except Exception as exc:
        code, text = 1, f"FALLO_LOCAL_RUNNER: {type(exc).__name__}"
    elapsed = max(0.0, time.monotonic() - before)
    ended = datetime.datetime.now().isoformat(timespec="seconds")
    return code, str(text or ""), started, ended, elapsed


def _run(network, *, dry=False, runner=default_runner, today=None, out=print,
         daily=None, shape=True, rng=None, signals=None):
    import volume_shape as vs
    rng = rng or random.Random()
    cfg = PIPELINES[network]
    shape = shape and cfg.get("shape", True)
    today = today or datetime.date.today()
    log_dir = os.path.join(ROOT, cfg["dir"], "cache")
    os.makedirs(log_dir, exist_ok=True)
    # una ronda por franja: el log lleva la hora para que las 3 rondas del dia no se pisen
    log_path = os.path.join(log_dir, f"mech_{today.isoformat()}_{datetime.datetime.now():%H%M}.log")
    transcript = []

    def step(label, cmd):
        code, text, started, ended, elapsed = _time_runner(runner, cmd)
        phase, script = _phase_for_timing(label, cmd)
        timing = (f"[TIEMPO_ETAPA] phase={phase} script={script} "
                  f"inicio={started} fin={ended} segundos={elapsed:.2f} exit={code}")
        if signals is not None:
            signals.append(cb.detect(text))
        transcript.append(f"===== {label} (exit {code}) =====\n{timing}\n{text}")
        out(f"[{network}] {timing}")
        with open(log_path, "w", encoding="utf-8") as stream:
            stream.write("\n".join(transcript))
        return code, text

    # 06/10 (David): cada ronda revisa si hay publicaciones pendientes u olvidadas de su red (sin gasto: lee las carpetas `publicaciones <Red> GPT` y, en Bluesky/Mastodon/Threads,
    # comprueba por API si ya estan publicadas). Solo avisa; nunca publica. Un fallo del aviso no tumba la ronda.
    if cfg.get("browser") and not dry:       # 06/10: workers del Edge pausados por una conexion muerta colgaban `connect_over_cdp` (receta de AGENTS.md, paso 1; inocuo)
        step("cdp_resume_workers", [PY, "tools/cdp_resume_workers.py"])
    if network in CONTENT_QUEUE_NETWORKS:
        code, text = step("content_queue_alert", [PY, "tools/content_queue_alert.py", network])
        if cb.detect(text):
            return {"ok": False, "stage": "execute", "failure_kind": "execute",
                    "exit_code": code, "log": log_path}
        for line in text.splitlines():
            if line.startswith(f"[{network}]") or line.startswith("   - "):
                out(line.rstrip())

    # 06/10 (David autoriza la publicacion automatica): si hay una ficha vencida y verificada como no publicada, se publica (maximo una por red y ronda; ver content_publisher.py)
    if network in PUBLISH_NETWORKS and not dry:
        code, text = step("content_publisher", [PY, "tools/content_publisher.py", network, "--apply"])
        if cb.detect(text):
            return {"ok": False, "stage": "execute", "failure_kind": "execute",
                    "exit_code": code, "log": log_path}
        for line in text.splitlines():
            if "PUBLICADA" in line or "ERROR" in line:
                out(line.rstrip())

    if cfg.get("decisions_default") is not None:        # decisiones que escribe un paso previo (api_comment_writer): nunca se reutilizan las de la ronda anterior
        try:
            os.remove(os.path.join(ROOT, cfg["decisions"]))
        except OSError:
            pass
    pre_confirmed = []
    pool_follows = rng.randint(35, 90)  # techo de follows de pool de ESTA ronda (variable)
    for cmd in cfg["pre"]:
        if "--max-pool-follows" in cmd:
            cmd = list(cmd)
            cmd[cmd.index("--max-pool-follows") + 1] = str(pool_follows)
        if dry and ("--like" in cmd or os.path.basename(cmd[1]) == "tiktok_bulk_follow.py"):
            continue  # no dar likes ni follows en --dry
        code, text = step(os.path.basename(cmd[1]) + " " + " ".join(cmd[2:3]), cmd)
        # No seguir preparando ni hacer nuevas acciones tras 429/auth.
        # La señal ya está registrada para cb.record en run().
        if cb.detect(text):
            return {"ok": False, "stage": "execute", "failure_kind": "execute",
                    "exit_code": code, "log": log_path}
        if "tiktok_bulk_follow" in cmd[1]:
            pre_confirmed.append(text or "")       # los follows del seguimiento masivo cuentan en el resumen de la ronda
        if "MobileSessionBusy" in (text or ""):          # 09/10: tiktok_bulk_follow sale con codigo 0 al encontrar el movil ocupado; exigir code != 0 dejaba seguir la ronda contra el movil ocupado
            # el movil lo usa otra sesion (la de TikTok trabaja con el mismo telefono): no es un fallo de la red ni debe abrir el cortacircuitos; se omite la ronda
            out(f"[{network}] movil ocupado por otra sesion: ronda omitida (se reintenta en la siguiente franja)")
            return {"ok": True, "skipped": True, "log": log_path}
        if code != 0 and "--like" in cmd:
            # dar like a las respuestas recibidas es un extra: si falla (bloqueo, 429, hilo
            # raro) no debe tumbar la ronda diaria entera
            out(f"[{network}] aviso: el paso de likes fallo (exit {code}); sigue la ronda; ver {log_path}")
            continue
        if code != 0:
            out(f"[{network}] parada en {cmd[1:3]} (exit {code}); ver {log_path}")
            stage, kind = _pre_failure_kind(cmd)
            # Incluso un constructor local puede depender de una API.
            # Un HTTP 5xx explícito no es un plan inválido.
            local_error = _local_python_error(text)
            if local_error and not cb.detect(text) and not _remote_http_failure(text):
                kind = "plan"  # NameError de scan no es caída de la cuenta
            elif kind == "plan" and _remote_http_failure(text):
                kind = "execute"
            return {"ok": False, "stage": stage, "failure_kind": kind,
                    "error_reason": local_error if kind == "plan" else None,
                    "exit_code": code, "log": log_path}

    if cfg["write_decisions"] is not None:
        with open(os.path.join(ROOT, cfg["decisions"]), "w", encoding="utf-8") as stream:
            json.dump(cfg["write_decisions"], stream)
    elif cfg.get("decisions_default") is not None and not os.path.exists(os.path.join(ROOT, cfg["decisions"])):
        with open(os.path.join(ROOT, cfg["decisions"]), "w", encoding="utf-8") as stream:      # el paso previo fallo: la ronda sigue sin comentarios
            json.dump(cfg["decisions_default"], stream)

    if cfg["build"] is not None:
        code, text = step("build", cfg["build"])
        if code != 0:
            out(f"[{network}] parada en build (exit {code}); ver {log_path}")
            remote = _remote_http_failure(text)
            return {"ok": False, "stage": "build",
                    "failure_kind": "execute" if remote else "plan",
                    "error_reason": None if remote else _local_python_error(text),
                    "exit_code": code, "log": log_path}
        planned = re.search(r'"actions":\s*(\d+)', text)
        planned = planned.group(1) if planned else "?"
    else:   # redes por navegador: el constructor mecanico ya escribio el plan en el ultimo paso previo
        try:
            with open(os.path.join(ROOT, cfg["plan"]), encoding="utf-8") as stream:
                planned = len(json.load(stream))
        except (OSError, ValueError):
            out(f"[{network}] parada: no hay plan construido; ver {log_path}")
            return {"ok": False, "stage": "plan", "failure_kind": "plan",
                    "error_reason": "plan_unavailable", "log": log_path}
    out(f"[{network}] plan construido: {planned} acciones")
    min_plan = cfg.get("min_plan")
    if min_plan and str(planned).isdigit() and int(planned) < min_plan:
        out(f"[{network}] AVISO plan pobre ({planned} < {min_plan}): es un fallo del scan, no un dia tranquilo; "
            f"reforzar a mano con la herramienta de la red (tools/{network}_interact.py)")
    if network in ("x", "threads", "facebook") and not dry:
        import reply_writer
        import reply_hold
        left = reply_writer.strip_bank(network, all_replies=reply_hold.held())       # 07/10: red de seguridad; nunca se publica una frase de banco sin pasar por el escritor
        if left:
            out(f"[{network}] {left} replies de banco sin reescribir pasadas a «me gusta»")
    if shape:
        # Volumen alto y variable (03/10): tope de la ronda = objetivo diario x semana x dia /
        # rondas, con ruido; si el plan lo supera se recorta en tres zonas (elite, muestra
        # ponderada, exploracion) y se aparta un pequeno grupo de control de follows.
        cap = vs.run_cap(network, today, rng, runs_per_day=vs.runs_per_day(network, cfg), daily=daily)
        done_today = _done_today(network, cfg, today)
        cap = vs.remaining_cap(cap, done_today, vs.daily_budget(network, today, daily))
        plan_path = os.path.join(ROOT, cfg["plan"])
        try:
            with open(plan_path, encoding="utf-8") as stream:
                plan = json.load(stream)
            before = len(plan)
            import repost_policy
            plan, dropped_shares = repost_policy.filter_plan(plan, repost_policy.done_today(os.path.join(ROOT, cfg["dir"], "registro_interacciones.csv"), today))
            if dropped_shares:
                out(f"[{network}] norma de reposts (max {repost_policy.MAX_PER_DAY}/dia, solo curados): {dropped_shares} reposts/boosts/citas quitados del plan")
            plan = vs.limit_per_target(plan, rng, already=_cheap_today(cfg, today))   # 1-3 likes por cuenta, no una rafaga sobre la misma
            trimmed = before - len(plan)
            plan, over_follows = vs.cap_follows(plan, vs.follow_budget_left(network, _follows_today(cfg, today), daily=daily, share=vs.follow_shares(network)[2]))
            import relationship_policy as rpol
            allowance = rpol.follow_allowance(*rpol.latest_counts(network), network=network)
            over_ratio = 0
            if allowance is not None:
                plan, over_ratio = vs.cap_follows(plan, allowance)         # 07/10 (David): seguidos parecidos a seguidores; el cupo se libera al dejar de seguir a quien no devuelve
                if over_ratio:
                    out(f"[{network}] proporcion seguidos/seguidores: cupo de follows nuevos {allowance}; {over_ratio} follows quitados del plan")
            held = []
            if not dry:
                plan, held = vs.split_holdout(plan, rng, share=vs.follow_shares(network)[3])
            shaped = vs.shape_plan(plan, cap, rng, follow_share=vs.follow_shares(network)[0], hard_follow_max=vs.follow_shares(network)[1])
            if held or len(shaped) != len(plan):
                with open(plan_path, "w", encoding="utf-8") as stream:
                    json.dump(shaped, stream, ensure_ascii=False, indent=1)
            if held:
                _record_holdout(network, cfg, held, today)
            out(f"[{network}] volumen del dia x{vs.day_factor(today, network)} (semana x{vs.week_factor(today, network)}); "
                f"tope de esta ronda {cap} (hoy ya {done_today}); plan {len(plan) + len(held)} -> {len(shaped)} acciones"
                + (f"; {trimmed} likes de cuentas repetidas omitidos" if trimmed else "")
                + (f"; {len(held)} follows apartados como grupo de control" if held else "")
                + (f"; {over_follows} follows quitados por el tope diario del 15 %" if over_follows else ""))
        except (OSError, ValueError) as exc:
            out(f"[{network}] aviso: no se pudo ajustar el volumen ({exc}); se ejecuta el plan completo")
    if dry:
        out(f"[{network}] --dry: no se ejecuta. Plan en {cfg['plan']}")
        return {"ok": True, "dry": True, "log": log_path}

    code, text = step("execute", cfg["execute"])
    if "VIGILANTE:" in text and cfg.get("browser") and not cb.detect(text):
        # 06/10: un Edge colgado (el vigilante aborto el ejecutor tras 5 min sin actividad): se reanudan los workers (receta de AGENTS.md) y se reintenta UNA vez; lo ya hecho se
        # salta solo (like «ya dado», follow «ya seguido») y el registro va accion a accion, asi que no se pierde ni se duplica nada.
        out(f"[{network}] aviso: el navegador se colgo; se reanudan los workers y se reintenta el plan una vez")
        step("cdp_resume_workers", [PY, "tools/cdp_resume_workers.py"])
        retry_code, retry_text = step("execute (reintento tras vigilante)", cfg["execute"])
        code, text = retry_code, text + chr(10) + retry_text
    summary = summarize(text)
    for bulk_text in pre_confirmed:
        for kind, n in summarize(bulk_text)["confirmadas"].items():
            summary["confirmadas"][kind] = summary["confirmadas"].get(kind, 0) + n
    for extra in ([] if cb.detect(text) else cfg.get("post", [])):  # no actuar después de rate/auth
        extra_code, extra_text = step("post " + os.path.basename(extra[1]) + " " + " ".join(extra[2:3]), extra)
        if cb.detect(extra_text):
            # El paso puede haber confirmado acciones ANTES de recibir 429:
            # conservar ese volumen en el resumen, nunca repetirlo a ciegas.
            for kind, n in summarize(extra_text)["confirmadas"].items():
                summary["confirmadas"][kind] = summary["confirmadas"].get(kind, 0) + n
            out(f"[{network}] aviso: señal 429/auth en paso extra; detenida la cadena post")
            break
        if extra_code != 0:
            out(f"[{network}] aviso: el paso extra {extra[1:3]} fallo (exit {extra_code}); ver {log_path}")
            continue
        for kind, n in summarize(extra_text)["confirmadas"].items():
            summary["confirmadas"][kind] = summary["confirmadas"].get(kind, 0) + n
    done = sum(summary["confirmadas"].values())
    out(f"[{network}] {done} confirmadas {summary['confirmadas']}, "
        f"{summary['saltadas']} saltadas, {len(summary['fallos'])} fallos")
    for line in summary["fallos"]:
        out(f"   ! {line}")
    metrics = re.findall(r"Metricas finales:.*", text)
    if metrics:
        out(f"[{network}] {metrics[-1]}")
    preflight_failed = "FALLO DE PREFLIGHT" in text
    if preflight_failed:
        out(f"[{network}] el preflight del plan fallo: no se ejecuto nada")
    return {"ok": code == 0 and not preflight_failed and cb.worst(signals or []) is None,
            "failure_kind": "plan" if preflight_failed else "execute",
            "stage": "preflight" if preflight_failed else "execute",
            "exit_code": code, "summary": summary, "log": log_path}


def _done_today(network, cfg, today):
    """Acciones confirmadas hoy en el ledger de la red (0 si no se puede leer)."""
    import action_ledger as al
    try:
        midnight = datetime.datetime.combine(today, datetime.time.min).timestamp()
        ledger = al.ActionLedger(os.path.join(ROOT, cfg["dir"], "cache", "action_ledger.sqlite"))
        return ledger.count_since(midnight)
    except Exception:
        return 0


def _cheap_today(cfg, today):
    """{handle: likes/favoritos ya confirmados hoy}: base del limite por cuenta y dia."""
    import csv
    path = os.path.join(ROOT, cfg["dir"], "registro_interacciones.csv")
    counts = {}
    try:
        with open(path, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if (row.get("fecha") or "")[:10] != today.isoformat() or row.get("resultado") not in ("confirmado", "publicado"):   # Mastodon anota «publicado»: el limite por cuenta y dia no lo contaba
                    continue
                kinds = (row.get("tipo") or "").split("+")
                if not any(k in ("like", "favourite") for k in kinds):
                    continue
                handle = (row.get("cuenta") or "").lstrip("@").casefold()
                if handle and not handle.startswith("http"):
                    counts[handle] = counts.get(handle, 0) + 1
    except OSError:
        pass
    return counts


def _follows_today(cfg, today):
    """Follows confirmados hoy en el registro de la red (Bluesky: «confirmado»; Mastodon: «publicado»)."""
    import csv
    path = os.path.join(ROOT, cfg["dir"], "registro_interacciones.csv")
    done = 0
    try:
        with open(path, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if (row.get("fecha") or "")[:10] == today.isoformat() and row.get("resultado") in ("confirmado", "publicado") and "follow" in (row.get("tipo") or "").split("+"):
                    done += 1
    except OSError:
        pass
    return done


def _record_holdout(network, cfg, held, today):
    """Anota los follows apartados (grupo de control) y los bloquea en el ledger para que
    ninguna otra ronda los siga: asi se puede medir el seguimiento organico."""
    import csv
    import action_ledger as al
    base = os.path.join(ROOT, cfg["dir"])
    path = os.path.join(base, "holdout.csv")
    new = not os.path.exists(path)
    ledger = al.ActionLedger(os.path.join(base, "cache", "action_ledger.sqlite"))
    with open(path, "a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        if new:
            writer.writerow(["fecha", "cuenta", "tipo", "motivo"])
        for item in held:
            handle = str(item.get("handle") or "").lstrip("@")
            writer.writerow([today.isoformat(), "@" + handle, item.get("kind", "follow"), item.get("motivo", "")])
            ledger.hold("follow", ledger.target_for("follow", item))


def _int_option(argv, name, default=None):
    return int(argv[argv.index(name) + 1]) if name in argv else default


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in PIPELINES:
        print(__doc__)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    result = run(argv[0], dry="--dry" in argv, spread_minutes=_int_option(argv, "--spread", 0) or 0,
                 daily=_int_option(argv, "--daily"), shape="--no-shape" not in argv, slot=_int_option(argv, "--slot"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

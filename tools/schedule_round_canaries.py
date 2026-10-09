"""R6.2: prepara la tarea opcional del canario sin instalarla por defecto.

Solo --install puede modificar Task Scheduler. Nunca usa /F, credenciales,
SYSTEM, una ventana de consola ni permisos elevados para la ejecución.
"""
from __future__ import annotations

import argparse
import ntpath
import pathlib
import subprocess
import sys

TASK_NAME = "RRSS_Canarios_Rondas"
VALID_INTERVALS = (30, 60)
RUNNER = "run_round_canaries_scheduled.py"


def python_pair(executable):
    """Fija un par python.exe/pythonw.exe del mismo entorno, incluido venv."""
    raw = str(executable)
    basename = ntpath.basename(raw).casefold()
    if basename not in {"python.exe", "pythonw.exe"}:
        raise ValueError("se requiere python.exe o pythonw.exe de una instalación concreta")
    prefix = raw[:-len(basename)]
    return pathlib.Path(prefix + "python.exe"), pathlib.Path(prefix + "pythonw.exe")


def create_command(root, *, python_exe=None, interval=30):
    """Argumentos de schtasks, sin shell ni sobrescritura."""
    if interval not in VALID_INTERVALS:
        raise ValueError("intervalo permitido: 30 o 60 minutos")
    root = pathlib.Path(root).resolve()
    _, gui = python_pair(python_exe or sys.executable)
    script = root / "tools" / RUNNER
    task_run = subprocess.list2cmdline([str(gui), str(script)])
    if len(task_run) > 262:
        raise ValueError("ruta demasiado larga para /TR (262 caracteres); acortar rutas")
    return ["schtasks", "/Create", "/SC", "MINUTE", "/MO", str(interval),
            "/TN", TASK_NAME, "/TR", task_run, "/RL", "LIMITED", "/IT"]


def query_command():
    """Comprobación de solo lectura independiente del idioma de Windows.

    Enumerar con -ErrorAction Stop evita confundir fallos CIM/permisos con ausencia.
    Se consulta la raíz, que es donde schtasks /TN sin ruta crea esta tarea.
    """
    ps = (
        "$ErrorActionPreference='Stop'; "
        "try { "
        "$tasks=@(Get-ScheduledTask -ErrorAction Stop); "
        "$found=@($tasks | Where-Object { "
        "$_.TaskName -eq 'RRSS_Canarios_Rondas' -and $_.TaskPath -eq '\\' }); "
        "if ($found.Count -gt 0) { [Console]::Out.Write('EXISTS') } "
        "else { [Console]::Out.Write('ABSENT') }; exit 0 "
        "} catch { [Console]::Error.Write('TASK_QUERY_FAILED'); exit 2 }"
    )
    return ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", ps]


def _ensure_rondas_active(root):
    """Nunca crear un canario activo durante una parada global solicitada."""
    flag = root / "00_OPERATIVO" / "cola_parar.flag"
    try:
        flag.stat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise RuntimeError("no se pudo verificar la señal de parada") from exc
    raise RuntimeError(
        "las rondas están detenidas; ejecutar INICIAR_RONDAS antes de instalar"
    )


def preflight_command(root, console):
    """Importar dependencias offline con el intérprete que usará la tarea."""
    code = ("import json, csv, sys; "
            "sys.path.insert(0, sys.argv[1]); "
            "import round_canaries, mobile_runtime, run_round_canaries_scheduled")
    return [str(console), "-I", "-c", code, str(pathlib.Path(root) / "tools")]


def install(root, *, python_exe=None, interval=30, platform=None, run=None):
    """Crear una sola tarea por autorización explícita, abortando ante incertidumbre."""
    if (sys.platform if platform is None else platform) != "win32":
        raise RuntimeError("la instalación del canario solo está disponible en Windows")
    root = pathlib.Path(root).resolve()
    _ensure_rondas_active(root)
    for filename in ("round_canaries.py", RUNNER):
        if not (root / "tools" / filename).is_file():
            raise FileNotFoundError(f"falta {filename}; no se crea una tarea rota")
    console, gui = python_pair(python_exe or sys.executable)
    command = create_command(root, python_exe=python_exe, interval=interval)
    if not console.is_file() or not gui.is_file():
        raise FileNotFoundError("python.exe y pythonw.exe deben existir en el mismo entorno")
    run = run or subprocess.run
    # Verificar el Python concreto usado, sin ejecutarlo bajo pythonw sin consola.
    check = run(preflight_command(root, console),
                capture_output=True, text=True, timeout=15)
    if check.returncode != 0:
        raise RuntimeError("el Python seleccionado no importa json/csv ni los módulos del canario")
    probe = run(query_command(), capture_output=True, text=True, timeout=30)
    if probe.returncode != 0 or probe.stdout.strip() not in {"EXISTS", "ABSENT"}:
        raise RuntimeError("consulta de tareas ambigua: no se modifica Task Scheduler")
    if probe.stdout.strip() == "EXISTS":
        raise RuntimeError(f"la tarea {TASK_NAME} ya existe; no se sobrescribe")
    # Evita crear una nueva tarea si PARAR se ha invocado durante el preflight.
    # No sustituye un bloqueo compartido con rondas_control.ps1: existe una
    # pequeña carrera que deberá verificarse al probar el Windows real.
    _ensure_rondas_active(root)
    # Si otro instalador crea la tarea entre consulta y alta, /F no está presente.
    # No responder afirmativamente a ninguna pregunta de sustitución.
    result = run(command, input="N\n", capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError("Windows no confirmó el alta; comprobar estado sin reintentar a ciegas")
    return TASK_NAME


def main(argv=None):
    parser = argparse.ArgumentParser(description="Canario RRSS opcional para Windows")
    parser.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[1]))
    parser.add_argument("--interval", type=int, choices=VALID_INTERVALS, default=30)
    parser.add_argument("--install", action="store_true", help="MODIFICA Windows: crea tarea")
    args = parser.parse_args(argv)
    # En Linux el ensayo ilustra /TR, pero NO identifica el Python de Windows.
    preview_python = None
    if not args.install and sys.platform != "win32":
        preview_python = str(pathlib.Path(sys.executable).with_name("python.exe"))
    command = create_command(args.root, python_exe=preview_python, interval=args.interval)
    if not args.install:
        print("ENSAYO: no se ha creado ninguna tarea. Validar las rutas en el PC Windows.")
        print(subprocess.list2cmdline(command))
        return 0
    print(f"Tarea creada: {install(args.root, interval=args.interval)}; no publica contenido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

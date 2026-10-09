"""Cola de rondas del dia (07/10/2026, David): en vez de una tarea por franja horaria, las rondas se ejecutan UNA TRAS OTRA y se mide cuanto tarda cada una.

«Empiezas con X, cuando termine pasas a Threads, cuando termine a Facebook... y vamos viendo los tiempos, el resultado y cuantas rondas nos dan por red y dia.»

Tres cadenas en paralelo (no comparten recurso):
  * WEB (un solo Edge, turno `edge_browser`): X, Threads, Facebook y Pinterest, de una en una; se elige siempre la red a la que le quede mayor fraccion de sus rondas del dia.
  * API: Bluesky y Mastodon, cada una su cadena, espaciadas a lo largo del dia (no usan el Edge).
  * MOVIL: TikTok, de una en una con descanso entre rondas.

Cada ronda es `mechanical_round.py <red>` en un proceso aparte; la cola anota en `00_OPERATIVO/tiempos_rondas.csv` inicio, fin, minutos y resultado. Termina de lanzar rondas a las 23:20.

    python tools/round_queue.py [--dry] [--until 23:20]
"""
from __future__ import annotations

import csv
import contextlib
import datetime
import io
import os
import random
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.dirname(__file__))
PY = sys.executable
LOG = os.path.join(ROOT, "00_OPERATIVO", "tiempos_rondas.csv")
STARTED = time.time()
# 08/10 (David): INICIAR_RONDAS con la cola ya en marcha deja «recargar» (cada cadena acaba su ronda, no lanza otra y la cola se relanza sola con el
# codigo nuevo, siguiendo donde iba gracias a tiempos_rondas.csv); PARAR_RONDAS deja «parar». Solo cuentan las senales posteriores al arranque del proceso.
RELOAD_FLAG = os.path.join(ROOT, "00_OPERATIVO", "cola_recargar.flag")
STOP_FLAG = os.path.join(ROOT, "00_OPERATIVO", "cola_parar.flag")
QUEUE_LOCK_DIR = os.path.join(ROOT, "00_OPERATIVO")        # un bloqueo POR CADENA (cola_rondas_web.lock, ..._api.lock, ..._tiktok.lock)


def control_signal(started=None):
    """«parar» o «recargar» si se pidio despues de arrancar este proceso; None si no."""
    started = STARTED if started is None else started
    for name, path in (("parar", STOP_FLAG), ("recargar", RELOAD_FLAG)):
        try:
            if os.path.getmtime(path) >= started:
                return name
        except OSError:
            pass
    return None


def nap(seconds, step=15):
    """Espera interrumpible: vuelve en cuanto se pide parar o recargar."""
    end = time.time() + seconds
    while time.time() < end:
        if control_signal():
            return
        time.sleep(min(step, max(0.0, end - time.time())))


def _pid_alive(pid):
    """Con incertidumbre no declarar muerto a un propietario."""
    try:
        from mobile_runtime import _pid_alive as alive
        return alive(pid)
    except Exception:
        return True


def _process_birth(pid):
    """ID de inicio: texto=proceso vivo; ''=muerto; None=estado no verificable."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.GetProcessTimes.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        # SYNCHRONIZE (0x100000) es necesario además de QUERY_LIMITED_INFORMATION.
        handle = kernel.OpenProcess(0x00101000, False, int(pid))
        if not handle:
            return "" if ctypes.get_last_error() == 87 else None
        try:
            # A process can exit with code 259. Detect termination from the
            # signaled process handle instead of relying on STILL_ACTIVE.
            wait = kernel.WaitForSingleObject(handle, 0)
            if wait == 0:           # WAIT_OBJECT_0: terminated
                return ""
            if wait != 258:         # WAIT_TIMEOUT: still active; others uncertain
                return None
            exit_code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return None
            if exit_code.value != 259:
                return ""
            times = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in times)):
                return None
            created = times[0]
            return str((created.dwHighDateTime << 32) | created.dwLowDateTime)
        finally:
            kernel.CloseHandle(handle)
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{int(pid)}/stat", encoding="ascii") as stream:
                data = stream.read()
            fields = data.rsplit(")", 1)[1].strip().split()
            if len(fields) < 20:
                return None
            if fields[0] in ("Z", "X"):
                return ""
            return fields[19]
        except (FileNotFoundError, ProcessLookupError):
            return ""
        except (OSError, ValueError, IndexError):
            return None
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return ""
    except OSError:
        return None
    return None


def _owner_token():
    pid = os.getpid()
    birth = _process_birth(pid)
    return f"{pid}:{birth}" if birth else str(pid)


def _owner_is_live(text):
    match = re.fullmatch(r"([1-9][0-9]*)(?::([1-9][0-9]*))?", text.strip())
    if match is None:
        return False
    pid, birth = int(match.group(1)), match.group(2)
    if birth is None:
        return _pid_alive(pid)  # formatos anteriores
    actual = _process_birth(pid)
    return actual is None or actual == birth


def _same_snapshot(a, b):
    return (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) == (
        b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns, b.st_ctime_ns)


@contextlib.contextmanager
def _recovery_guard(path):
    """Guard estable del SO; no borrar .guard ni siquiera al parar."""
    fd = None
    held = False
    try:
        fd = os.open(path + ".guard", os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o600)
    except OSError:
        yield False
        return
    try:
        if os.name == "nt":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                held = True
            except OSError:
                pass
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held = True
            except OSError:
                pass
        yield held
    finally:
        if fd is not None:
            if held:
                try:
                    if os.name == "nt":
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(fd)


def _lock_path(chain):
    return os.path.join(QUEUE_LOCK_DIR, f"cola_rondas_{chain}.lock")


LOCK_ORPHAN_GRACE_SECONDS = 60
LOCK_HEARTBEAT_SECONDS = 30


def _recover_orphan_marker(path):
    """Se invoca solo dentro del guard de adquisición; no afecta a otros procesos."""
    try:
        stat = os.stat(path)
        if time.time() - stat.st_mtime < LOCK_ORPHAN_GRACE_SECONDS:
            return False
        with open(path, encoding="ascii", errors="replace") as stream:
            owner_text = stream.read().strip()
        if _owner_is_live(owner_text):
            return False
        latest = os.stat(path)
        if not _same_snapshot(stat, latest):
            return False
        os.unlink(path)
        return True
    except OSError:
        return False


def take_chain_lock(chain):
    """O_EXCL exclusivo y recuperación protegida por guard de SO de corta duración."""
    path = _lock_path(chain)
    token = _owner_token()
    # Todos los candidatos usan el mismo guard: un recuperador lento no borra
    # una adquisición recién efectuada por otro recuperador.
    with _recovery_guard(path) as acquired:
        if not acquired:
            return False
        for attempt in range(3):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                try:
                    stat = os.stat(path)
                    with open(path, encoding="utf-8", errors="replace") as stream:
                        owner_text = stream.read().strip()
                    if _owner_is_live(owner_text):
                        if time.time() - stat.st_mtime > 15 * 60:
                            print(f"[cola] ATENCION: {chain} vivo sin latido; no se roba", flush=True)
                        return False
                    valid = re.fullmatch(r"[1-9][0-9]*(?::[1-9][0-9]*)?", owner_text)
                    if valid is None and time.time() - stat.st_mtime < LOCK_ORPHAN_GRACE_SECONDS:
                        return False
                except OSError:
                    return False
                reclaim = path + ".reclaim"
                try:
                    marker_fd = os.open(reclaim, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    if attempt < 2 and _recover_orphan_marker(reclaim):
                        continue
                    return False
                except OSError:
                    return False
                try:
                    with os.fdopen(marker_fd, "w", encoding="ascii") as stream:
                        stream.write(token)
                    latest = os.stat(path)
                    with open(path, encoding="utf-8", errors="replace") as stream:
                        current = stream.read().strip()
                    if current != owner_text or not _same_snapshot(stat, latest):
                        return False
                    if _owner_is_live(current):
                        return False
                    valid = re.fullmatch(r"[1-9][0-9]*(?::[1-9][0-9]*)?", current)
                    if valid is None and time.time() - latest.st_mtime < LOCK_ORPHAN_GRACE_SECONDS:
                        return False
                    os.unlink(path)
                except OSError:
                    return False
                finally:
                    try:
                        with open(reclaim, encoding="ascii") as stream:
                            mine = stream.read().strip() == token
                        if mine:
                            os.unlink(reclaim)
                    except OSError:
                        pass
                continue
            except OSError:
                return False
            try:
                with os.fdopen(fd, "w", encoding="ascii") as stream:
                    stream.write(token)
            except BaseException:
                try:
                    os.unlink(path)
                except OSError:
                    pass
                raise
            return True
    return False


def release_chain_lock(chain):
    """Suelta solo un lock propio y serializa la decisión frente a nuevos dueños.

    Devuelve True únicamente cuando pudo eliminar su propiedad. El formato
    PID legado también se acepta para cerrar una cadena anterior al upgrade.
    """
    path = _lock_path(chain)
    with _recovery_guard(path) as guarded:
        if not guarded:
            return False
        try:
            with open(path, encoding="ascii") as stream:
                text = stream.read().strip()
            if text not in (_owner_token(), str(os.getpid())):
                return False
            os.unlink(path)  # Windows: fuera del with abierto
            return True
        except (OSError, UnicodeError):
            return False


def _heartbeat_owned_locks(chains, stop):
    """La actualización de mtime no debe aplicarse a un lock recién sustituido."""
    while not stop.wait(LOCK_HEARTBEAT_SECONDS):
        for chain in chains:
            path = _lock_path(chain)
            with _recovery_guard(path) as guarded:
                if not guarded:
                    continue
                try:
                    with open(path, encoding="ascii") as stream:
                        if stream.read().strip() == _owner_token():
                            os.utime(path, None)
                except (OSError, UnicodeError):
                    pass


def relaunch(script_args, log_name):
    """Lanza de nuevo el mismo script (con el codigo que haya ahora en disco), separado de esta ventana, con su salida al log."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    path = os.path.join(ROOT, "00_OPERATIVO", log_name)
    try:
        log = open(path, "a", encoding="utf-8")
    except OSError:                          # 08/10: la tarea programada (cmd >>) o PowerShell pueden tener el log abierto en exclusiva: la recarga NUNCA debe morir por eso
        log = open(path[:-4] + f"_{os.getpid()}.log", "a", encoding="utf-8")
    with log:
        subprocess.Popen([PY, "-u"] + list(script_args), cwd=ROOT, stdout=log,
                         stderr=subprocess.STDOUT, creationflags=flags,
                         env={**os.environ, "PYTHONIOENCODING": "utf-8"})


WEB = ("x", "threads", "facebook", "pinterest")
API = ("bluesky", "mastodon")
PHONE = ("tiktok",)
SUMMARY = re.compile(r"\[(\w+)\] (\d+) confirmadas (\{.*?\}), (\d+) saltadas, (\d+) fallos")
_write_lock = threading.Lock()

ROUND_CSV_COLUMNS = (
    "fecha", "red", "inicio", "fin", "minutos", "estado",
    "confirmadas", "saltadas", "fallos", "codigo",
)
ROUND_CSV_LOCK_TIMEOUT_SECONDS = 15.0
ROUND_CSV_LEGACY_COLUMNS = ("fecha", "red", "estado")


def _recover_incomplete_csv_tail(stream):
    """Repair an unterminated tail; preserve a valid legacy row without newline.

    The lock is held by the caller. A malformed tail must not be glued to
    the next record. A *complete* legacy final row must not be discarded.
    """
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    if not size:
        return False
    stream.seek(size - 1)
    if stream.read(1) == b"\n":
        stream.seek(0, os.SEEK_END)
        return False

    position = size
    previous_newline = -1
    while position:
        start = max(0, position - 4096)
        stream.seek(start)
        block = stream.read(position - start)
        newline = block.rfind(b"\n")
        if newline >= 0:
            previous_newline = start + newline
            break
        position = start

    offset = previous_newline + 1
    tail_size = size - offset
    if tail_size <= 65536:
        stream.seek(offset)
        raw = stream.read(tail_size)
        try:
            parsed = list(csv.reader(
                io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True))
        except (csv.Error, UnicodeError):
            parsed = []
        if len(parsed) == 1:
            fields = parsed[0]
            if (fields in (list(ROUND_CSV_COLUMNS), list(ROUND_CSV_LEGACY_COLUMNS))
                    or (len(fields) == len(ROUND_CSV_LEGACY_COLUMNS)
                        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", fields[0])
                        and fields[2] in ("ok", "parcial", "ocupada", "saltada", "error"))
                    or (
                    len(fields) == len(ROUND_CSV_COLUMNS)
                    and fields[5] in ("ok", "parcial", "ocupada", "saltada", "error")
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", fields[0])
                    and re.fullmatch(r"\d{2}:\d{2}:\d{2}", fields[2])
                    and re.fullmatch(r"\d{2}:\d{2}:\d{2}", fields[3])
                    and fields[7].isdigit() and fields[8].isdigit()
                    and re.fullmatch(r"-?\d+", fields[9]))):
                stream.seek(0, os.SEEK_END)
                stream.write(b"\r\n" if not raw.endswith(b"\r") else b"\n")
                return True

    stream.truncate(offset)
    stream.seek(0, os.SEEK_END)
    return True


def _read_round_csv_rows():
    """Read a consistent CSV snapshot under the same process-wide writer guard.

    Never substitute an empty ledger for lock failure or corruption: that
    could cause a previously confirmed round to be replayed after restart.
    """
    directory = os.path.dirname(LOG)
    if directory:
        os.makedirs(directory, exist_ok=True)
    deadline = time.monotonic() + ROUND_CSV_LOCK_TIMEOUT_SECONDS
    with _write_lock:
        return _read_round_csv_rows_locked(deadline)


def _read_round_csv_rows_locked(deadline):
    """Read with the in-process mutex already held."""
    while True:
        with _recovery_guard(LOG + ".writer") as locked:
            if locked:
                try:
                    with open(LOG, "r+b") as stream:
                        repaired = _recover_incomplete_csv_tail(stream)
                        if repaired:
                            stream.flush()
                            os.fsync(stream.fileno())
                        stream.seek(0)
                        data = stream.read()
                except FileNotFoundError:
                    return []
                if not data:
                    return []
                last = data.rfind(b"\n")
                if last < 0:
                    raise OSError("Cabecera CSV incompleta; revisar antes de reanudar")
                try:
                    reader = csv.DictReader(
                        io.StringIO(data[:last + 1].decode("utf-8-sig"), newline=""),
                        strict=True)
                    if reader.fieldnames not in (
                            list(ROUND_CSV_COLUMNS), list(ROUND_CSV_LEGACY_COLUMNS)):
                        raise ValueError("Cabecera CSV distinta del contrato esperado")
                    rows = list(reader)
                    if any(None in row or any(value is None for value in row.values())
                           for row in rows):
                        raise ValueError("CSV contiene filas con ancho incorrecto")
                except (csv.Error, ValueError, UnicodeError) as exc:
                    raise OSError("CSV inconsistente; no reanudar rondas a ciegas") from exc
                return rows
        if time.monotonic() >= deadline:
            raise OSError("No se pudo leer el CSV con exclusion interproceso")
        time.sleep(0.02 + random.random() * 0.05)


def _append_round_csv(row):
    """Append one durable row, recovering a crashed writer's partial tail."""
    if len(row) != len(ROUND_CSV_COLUMNS):
        raise ValueError("Fila de tiempos_rondas.csv con columnas incorrectas")
    if any("\r" in str(value) or "\n" in str(value) for value in row):
        raise ValueError("Fila CSV con saltos de linea internos incompatibles con recuperacion")
    directory = os.path.dirname(LOG)
    if directory:
        os.makedirs(directory, exist_ok=True)
    deadline = time.monotonic() + ROUND_CSV_LOCK_TIMEOUT_SECONDS
    with _write_lock:
        while True:
            with _recovery_guard(LOG + ".writer") as locked:
                if locked:
                    with open(LOG, "a+b") as stream:
                        stream.seek(0)
                        first_line = stream.readline()
                        if first_line:
                            try:
                                header = next(csv.reader(
                                    io.StringIO(first_line.decode("utf-8-sig"), newline="")))
                            except (csv.Error, UnicodeError) as exc:
                                raise ValueError("Cabecera CSV ilegible") from exc
                            if header != list(ROUND_CSV_COLUMNS):
                                raise ValueError(
                                    "CSV antiguo o incompatible: conservar y migrar antes de escribir")
                        _recover_incomplete_csv_tail(stream)
                        stream.seek(0, os.SEEK_END)
                        empty = stream.tell() == 0
                        buffer = io.StringIO(newline="")
                        writer = csv.writer(buffer)
                        if empty:
                            writer.writerow(ROUND_CSV_COLUMNS)
                        writer.writerow(row)
                        stream.write(buffer.getvalue().encode("utf-8"))
                        stream.flush()
                        os.fsync(stream.fileno())
                    return
            if time.monotonic() >= deadline:
                raise OSError("No se pudo adquirir la exclusion de tiempos_rondas.csv")
            time.sleep(0.02 + random.random() * 0.05)


def rounds_target(network):
    """Rondas del dia que pide la etapa/configuracion de la red."""
    import mechanical_round as mr
    import volume_shape as vs
    return vs.runs_per_day(network, mr.PIPELINES.get(network))


def next_web(done, targets):
    """Red web a la que le queda mayor fraccion de rondas; None si todas cumplieron."""
    best, best_left = None, 0.0
    for network in WEB:
        total = targets.get(network, 0)
        left = (total - done.get(network, 0)) / total if total else 0.0
        if left > best_left + 1e-9:
            best, best_left = network, left
    return best


def done_today(today=None):
    """Rondas ya lanzadas hoy segun el CSV de tiempos (para reanudar la cola sin repetir)."""
    today = (today or datetime.date.today()).isoformat()
    done = {}
    for row in _read_round_csv_rows():
        if row.get("fecha") == today and row.get("estado") in ("ok", "parcial"):
            done[row["red"]] = done.get(row["red"], 0) + 1
    return done


def run_round(network):
    start = datetime.datetime.now()
    proc = subprocess.run([PY, "-u", os.path.join("tools", "mechanical_round.py"), network], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = (proc.stdout or "") + (proc.stderr or "")
    end = datetime.datetime.now()
    found = [summary for summary in SUMMARY.findall(out) if summary[0] == network]
    # GROUPS: red, total NUMÉRICO, desglose de confirmadas, saltadas, fallos.
    # La columna CSV "confirmadas" almacena históricamente el desglose,
    # no el total. Conservar ese contrato para panel e informes existentes.
    confirmed, skipped, failed = ("", 0, 0)
    confirmed_n = 0
    if found:
        _, total, confirmed, skipped, failed = found[-1]
        confirmed_n = int(total)
    # No inferir éxito solo de returncode: puede haber 39 acciones confirmadas
    # y una etapa fallida; tampoco un 0 significa éxito si todas se saltaron.
    failed_n = int(failed) if found else 0
    is_busy = "otra ronda esta en curso" in out
    is_skipped = any(signal in out for signal in
                     ("no se lanza", "cortacircuitos ABIERTO", "MobileSessionBusy"))
    # Las confirmaciones probadas tienen prioridad frente a bloqueos posteriores:
    # reintentar la ronda completa podría duplicar acciones remotas.
    if confirmed_n:
        state = "parcial" if proc.returncode != 0 or failed_n or is_busy or is_skipped else "ok"
    elif is_busy:
        state = "ocupada"
    elif is_skipped:
        state = "saltada"
    elif not found:
        state = "error" if proc.returncode != 0 else "saltada"
    elif failed_n or proc.returncode != 0:
        state = "error"               # sin acciones confirmadas
    else:
        state = "saltada"             # solo saltos, sin una accion confirmada
    row = [start.date().isoformat(), network, start.strftime("%H:%M:%S"), end.strftime("%H:%M:%S"), round((end - start).total_seconds() / 60, 1), state, confirmed, skipped, failed, proc.returncode]
    _append_round_csv(row)
    print(f"[cola] {network}: {state} en {row[4]} min {confirmed} saltadas={skipped} fallos={failed}", flush=True)
    return state


def deadline_from(text):
    hour, minute = (int(x) for x in text.split(":"))
    return datetime.datetime.combine(datetime.date.today(), datetime.time(hour, minute))


def classify_round_state(state, failures, *, network=None, now=None):
    """(cuenta como realizada, segundos de espera, alerta). Una política para 3 cadenas.

    failures cuenta solo errores consecutivos, no recursos ocupados ni saltos.
    El jitter +/-20% es propio; no sustituye Retry-After ni el cortacircuitos.
    Nunca repetir automáticamente un lote con acciones confirmadas (parcial).
    """
    if state in ("ok", "parcial"):
        return True, 0.0, False
    if state == "ocupada":
        return False, random.uniform(120, 300), False
    if state == "saltada":
        delay = random.uniform(12 * 60 * .8, 12 * 60 * 1.2)
        if network:
            try:
                import circuit_breaker
                directory = os.path.join(ROOT, f"SISTEMA_DIARIO_{network.upper()}")
                breaker = circuit_breaker.load(directory)
                opened = breaker.get("open_until") if isinstance(breaker, dict) else None
                if opened:
                    until = datetime.datetime.fromisoformat(opened)
                    remaining = (until - (now or datetime.datetime.now())).total_seconds()
                    delay = max(delay, remaining)
            except (OSError, ValueError, TypeError, OverflowError):
                # Un breaker malformado no justifica un bucle rápido.
                pass
        return False, delay, False
    # El estado desconocido NO acredita ninguna acción confirmada.
    failures = max(1, failures)
    base = 2 * 60 * 60 if failures >= 6 else (900, 1800, 3600)[min(failures - 1, 2)]
    return False, random.uniform(base * .8, base * 1.2), failures >= 3


def nap_before_deadline(seconds, until):
    """No mantener una cadena despierta esperando más allá del cierre diario."""
    remaining = (until - datetime.datetime.now()).total_seconds()
    if remaining > 0:
        nap(min(seconds, remaining))


def retry_snapshot_today(now=None):
    """Restituye errores seguidos y enfriamientos tras recarga, solo leyendo el CSV.

    Un reinicio no permite saltarse la espera de un error ya registrado. Ante
    jitter no persistido, se toma el extremo superior del intervalo. No puede
    resolver un crash antes de que el ejecutor escriba la fila.
    """
    now = now or datetime.datetime.now()
    states = {}
    for row in _read_round_csv_rows():
        network = row.get("red")
        state = row.get("estado")
        if (row.get("fecha") != now.date().isoformat()
                or network not in WEB + API + PHONE + ("tiktok_bulk",)
                or state not in ("ok", "parcial", "ocupada", "saltada", "error")):
            continue
        try:
            clock = datetime.time.fromisoformat(row["fin"])
            when = now.replace(hour=clock.hour, minute=clock.minute,
                               second=clock.second, microsecond=clock.microsecond)
        except (TypeError, ValueError, KeyError):
            continue
        # Ignorar registros con horario futuro (reloj reajustado).
        if when > now:
            continue
        failures = states.get(network, (0, None))[0]
        if state in ("ok", "parcial"):
            states[network] = (0, None)
            continue
        if state == "error":
            failures += 1
        if state == "ocupada":
            delay = 300.0
        elif state == "saltada":
            _, breaker_delay, _ = classify_round_state(
                state, failures,
                network="tiktok" if network == "tiktok_bulk" else network,
                now=when)
            delay = max(12 * 60 * 1.2, breaker_delay)
        else:
            base = 2 * 60 * 60 if failures >= 6 else (
                900, 1800, 3600)[min(failures - 1, 2)]
            delay = base * 1.2
        states[network] = (failures, when + datetime.timedelta(seconds=delay))
    return states



def web_chain(until, targets, done):
    """Éxitos/parciales consumen cuota; cada red fallida cede el Edge a otras."""
    recovered = retry_snapshot_today()
    retry_after = {n: previous for n, (_, previous) in recovered.items()
                   if n in WEB and previous is not None}
    failures = {n: count for n, (count, _) in recovered.items() if n in WEB}
    while datetime.datetime.now() < until and not control_signal():
        moment = datetime.datetime.now()
        eligible = {n: target for n, target in targets.items()
                    if n in WEB and retry_after.get(n, moment) <= moment}
        network = next_web(done, eligible)
        if not network:
            remaining = [n for n in WEB if done.get(n, 0) < targets.get(n, 0)]
            if not remaining:
                print("[cola] web: todas las rondas del dia cumplidas", flush=True)
                return
            soonest = min(retry_after.get(n, moment) for n in remaining)
            nap_before_deadline(max(1, min(60, (soonest - moment).total_seconds())), until)
            continue

        state = run_round(network)
        if state in ("ok", "parcial"):
            failures[network] = 0
        elif state not in ("ocupada", "saltada"):
            failures[network] = failures.get(network, 0) + 1
        counts, delay, alert = classify_round_state(
            state, failures.get(network, 0), network=network)
        if counts:
            done[network] = done.get(network, 0) + 1
            retry_after.pop(network, None)
        else:
            retry_after[network] = datetime.datetime.now() + datetime.timedelta(seconds=delay)
            print(f"[cola] web/{network}: {state}; pendiente; espera {delay / 60:.1f} min"
                  + ("; ALERTA: errores repetidos" if alert else ""), flush=True)

        try:
            import edge_trim
            edge_trim.trim(lambda *a: None)
        except Exception:
            pass
        nap_before_deadline(random.uniform(30, 120), until)


def budget_left(network):
    """Acciones que le quedan por hacer hoy a una red por API segun su presupuesto diario (0 si no se puede calcular)."""
    try:
        import mechanical_round as mr
        import volume_shape as vs
        today = datetime.date.today()
        return vs.daily_budget(network, today) - mr._done_today(network, mr.PIPELINES[network], today)
    except Exception:
        return 0


EXTRA_ROUND_MIN_BUDGET = 300      # 07/10: cumplidas las rondas del dia, si queda presupuesto se siguen lanzando (Bluesky llegaba al 50 % del objetivo con las 6 rondas)


def spaced_chain(network, until, target, done_count, label):
    """API: no terminar el resto del día por seis fallos ni repetir parciales."""
    left = target - done_count
    failures, resume_at = retry_snapshot_today().get(network, (0, None))
    if resume_at:
        nap_before_deadline(max(0, (resume_at - datetime.datetime.now()).total_seconds()), until)
    while datetime.datetime.now() < until and not control_signal():
        if left <= 0 and budget_left(network) < EXTRA_ROUND_MIN_BUDGET:
            break
        state = run_round(network)
        if state in ("ok", "parcial"):
            failures = 0
        elif state not in ("ocupada", "saltada"):
            failures += 1
        counts, delay, alert = classify_round_state(state, failures, network=network)
        if counts:
            left -= 1
            nap_before_deadline(random.uniform(8 * 60, 18 * 60), until)
        else:
            print(f"[cola] {label}: {state}; espera {delay / 60:.1f} min"
                  + ("; ALERTA: errores repetidos" if alert else ""), flush=True)
            nap_before_deadline(delay, until)
    print(f"[cola] {label}: cadena terminada", flush=True)


def run_bulk():
    """Sesion de seguimiento masivo de TikTok (tiktok_bulk_follow.py) registrada en el CSV como red `tiktok_bulk`."""
    start = datetime.datetime.now()
    proc = subprocess.run([PY, "-u", os.path.join("tools", "tiktok_bulk_follow.py"), "--max-follows", "120", "--max-minutes", "50"], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = (proc.stdout or "") + (proc.stderr or "")
    end = datetime.datetime.now()
    follows = len(re.findall(r"^confirmado\s+follow", out, re.MULTILINE))
    unavailable = "en descanso" in out or "MobileSessionBusy" in out
    failures = bool(re.search(r"^FALLO", out, re.MULTILINE))
    stopped = bool(re.search(r"^PARADA", out, re.MULTILINE))
    if follows:
        state = "parcial" if proc.returncode != 0 or unavailable or failures or stopped else "ok"
    elif failures or proc.returncode != 0:
        state = "error"
    else:
        state = "saltada"
    row = [start.date().isoformat(), "tiktok_bulk", start.strftime("%H:%M:%S"), end.strftime("%H:%M:%S"), round((end - start).total_seconds() / 60, 1), state, "{'follow': %d}" % follows, 0, len(re.findall(r"^(FALLO|PARADA)", out, re.MULTILINE)), proc.returncode]
    _append_round_csv(row)
    print(f"[cola] tiktok_bulk: {state} en {row[4]} min follows={follows}", flush=True)
    return state, out


def phone_chain(until, target, done_count):
    """TikTok: respetar descanso móvil; normal y bulk comparten clasificación."""
    left = target - done_count
    last_normal = None
    recovered = retry_snapshot_today()
    normal_errors, normal_at = recovered.get("tiktok", (0, None))
    bulk_errors, bulk_at = recovered.get("tiktok_bulk", (0, None))
    while datetime.datetime.now() < until and not control_signal():
        try:
            import tiktok_bulk_follow as bulk
            cooling = bulk.cooldown_left() > 0
        except Exception:
            cooling = True
        due_normal = left > 0 and (last_normal is None or
                                   (datetime.datetime.now() - last_normal).total_seconds() >= 100 * 60)
        if not cooling and not due_normal and bulk_at and datetime.datetime.now() < bulk_at:
            # Mientras el bulk está enfriado, no dormir más allá de la
            # siguiente ronda normal pendiente (cada 100 minutos).
            current = datetime.datetime.now()
            wait = (bulk_at - current).total_seconds()
            if left > 0 and last_normal is not None:
                normal_due = (last_normal + datetime.timedelta(minutes=100) - current).total_seconds()
                wait = min(wait, max(1, normal_due))
            nap_before_deadline(wait, until)
            continue
        if (not cooling and not (due_normal and last_normal is None)
                and (not bulk_at or datetime.datetime.now() >= bulk_at)):
            state, _ = run_bulk()
            bulk_at = None
            if state in ("ok", "parcial"):
                bulk_errors = 0
            elif state not in ("ocupada", "saltada"):
                bulk_errors += 1
            counts, delay, alert = classify_round_state(state, bulk_errors, network="tiktok")
            if alert:
                print("[cola] tiktok_bulk: ALERTA errores repetidos", flush=True)
            nap_before_deadline(random.uniform(8 * 60, 15 * 60) if counts else delay, until)
            if not due_normal:
                continue
            if datetime.datetime.now() >= until or control_signal():
                break
        if left > 0 and (due_normal or cooling):
            if normal_at and datetime.datetime.now() < normal_at:
                nap_before_deadline((normal_at - datetime.datetime.now()).total_seconds(), until)
                continue
            state = run_round("tiktok")
            normal_at = None
            if state in ("ok", "parcial"):
                normal_errors = 0
            elif state not in ("ocupada", "saltada"):
                normal_errors += 1
            counts, delay, alert = classify_round_state(state, normal_errors, network="tiktok")
            if counts:
                left -= 1
                last_normal = datetime.datetime.now()
            if alert:
                print("[cola] tiktok: ALERTA errores repetidos", flush=True)
            nap_before_deadline(random.uniform(4 * 60, 9 * 60) if counts else delay, until)
        elif cooling:
            nap_before_deadline(10 * 60, until)
    print("[cola] tiktok: cadena terminada", flush=True)


def ensure_reply_worker(until):
    """Trabajador de la cola de respuestas de ChatGPT (reply_queue.py): una sola instancia; las rondas por API/movil encolan y no esperan el navegador."""
    try:
        import reply_queue
        if reply_queue.worker_running():
            return
        try:                                  # 08/10: Edge propio de ChatGPT (9224) para que el trabajador no espere a las rondas web; si no arranca, usa el 9223 como antes
            import chatgpt_edge
            if not chatgpt_edge.port_open():
                print(f"[cola] Edge de ChatGPT (9224): {'arrancado' if chatgpt_edge.start() else 'no arranco, se usa el 9223'}", flush=True)
        except Exception as exc:
            print(f"[cola] Edge de ChatGPT no disponible ({type(exc).__name__}); se usa el 9223", flush=True)
        log = open(os.path.join(ROOT, "00_OPERATIVO", "reply_worker.log"), "a", encoding="utf-8")
        subprocess.Popen([PY, "-u", os.path.join("tools", "reply_queue.py"), "loop", "--until", f"{until:%H:%M}"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                         env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        print("[cola] trabajador de respuestas arrancado", flush=True)
    except Exception as exc:
        print(f"[cola] no se pudo arrancar el trabajador de respuestas: {exc}", flush=True)


CHAINS = ("web", "api", "tiktok")


def _run_lock_probe(argv):
    """Ensayo CLI aislado: nunca abre Edge, tareas, colas ni datos operativos."""
    if "--dry" not in argv or "--only" not in argv:
        print("[probe] requiere --dry --only <cadena>", flush=True)
        return 2
    try:
        chain = argv[argv.index("--only") + 1]
        directory = os.path.realpath(argv[argv.index("--lock-probe") + 1])
        seconds = float(argv[argv.index("--probe-hold") + 1]) if "--probe-hold" in argv else 0.0
    except (ValueError, IndexError):
        print("[probe] argumentos invalidos", flush=True)
        return 2
    if chain not in CHAINS or not os.path.isdir(directory) or not (0 <= seconds <= 5):
        print("[probe] cadena, directorio o espera invalidos", flush=True)
        return 2
    root = os.path.realpath(ROOT)
    try:
        if os.path.commonpath((root, directory)) == root:
            print("[probe] directorio operativo prohibido", flush=True)
            return 2
    except ValueError:  # unidades diferentes en Windows: fuera del repositorio
        pass
    global QUEUE_LOCK_DIR
    original = QUEUE_LOCK_DIR
    acquired = False
    try:
        QUEUE_LOCK_DIR = directory
        acquired = take_chain_lock(chain)
        print("[probe] HELD" if acquired else "[probe] BLOCKED", flush=True)
        if acquired:
            time.sleep(seconds)
        return 0
    finally:
        if acquired:
            release_chain_lock(chain)
        QUEUE_LOCK_DIR = original


def launch_independent(argv):
    """08/10 (David): tres colas INDEPENDIENTES, cada una en su propio proceso (WEB: X, Threads, Facebook, Pinterest; API: Bluesky y Mastodon; MOVIL: TikTok).
    Una no espera a otra, y recargar o parar una no toca las demas. Este proceso solo las lanza y espera (asi la tarea programada sigue «en ejecucion»).
    Cada cadena escribe en 00_OPERATIVO/cola_rondas_<cadena>.log."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    procs = []
    for chain in CHAINS:
        log = open(os.path.join(QUEUE_LOCK_DIR, f"cola_rondas_{chain}.log"), "a", encoding="utf-8")
        procs.append(subprocess.Popen([PY, "-u", os.path.join("tools", "round_queue.py"), "--only", chain] + list(argv), cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                      creationflags=flags, env={**os.environ, "PYTHONIOENCODING": "utf-8"}))
        log.close()                                   # el hijo ya heredo su propio manejador
        print(f"[cola] cadena {chain}: proceso {procs[-1].pid} (log cola_rondas_{chain}.log)", flush=True)
        time.sleep(2)
    for proc in procs:
        proc.wait()
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if "--lock-probe" in argv:
        return _run_lock_probe(argv)
    if "--only" not in argv and "--dry" not in argv:
        return launch_independent(argv)
    until = deadline_from(argv[argv.index("--until") + 1] if "--until" in argv else "23:20")
    targets = {n: rounds_target(n) for n in WEB + API + PHONE}
    if "--dry" in argv:
        done = done_today()
        print(f"[cola] objetivos {targets}; ya hechas hoy {done}; hasta {until:%H:%M}", flush=True)
        return 0
    wanted = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else {"web", "api", "tiktok"}
    mine = {chain for chain in sorted(wanted) if take_chain_lock(chain)}
    for chain in sorted(wanted - mine):
        print(f"[cola] la cadena {chain} ya la lleva otra cola viva: esta no la repite", flush=True)
    if not mine:
        print("[cola] no queda ninguna cadena libre: no se lanza otra cola", flush=True)
        return 0
    heartbeat_stop = threading.Event()
    heartbeat = None
    heartbeat_started = False
    reload_allowed = False
    try:
        # Snapshot DESPUÉS de adquirir la propiedad, no antes: un propietario
        # anterior podría haber confirmado una ronda durante la espera.
        done = done_today()
        print(f"[cola] objetivos {targets}; ya hechas hoy {done}; hasta {until:%H:%M}", flush=True)
        heartbeat = threading.Thread(target=_heartbeat_owned_locks, args=(tuple(mine), heartbeat_stop), daemon=True)
        heartbeat.start()
        heartbeat_started = True
        reload_allowed = True
        return _run_chains(argv, until, targets, done, only=mine)
    finally:
        heartbeat_stop.set()
        if heartbeat_started:
            heartbeat.join(timeout=2)
        released = {chain: release_chain_lock(chain) for chain in mine}
        if reload_allowed and control_signal() == "recargar" and all(released.values()):
            # No relanzar hasta confirmar que liberamos todos los locks.
            # Si falla, una nueva cola moriría por la posesión del padre.
            print("[cola] recarga pedida: se relanza con el codigo nuevo y sigue donde iba", flush=True)
            relaunch([os.path.join("tools", "round_queue.py")] + argv, f"cola_rondas_{next(iter(mine))}.log" if len(mine) == 1 else "cola_rondas_recarga.log")
        elif control_signal() == "recargar":
            print(f"[cola] recarga retenida: no se liberaron todos los locks: {released}", flush=True)


def _run_chains(argv, until, targets, done, only=None):
    ensure_reply_worker(until)
    only = only if only is not None else (set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else {"web", "api", "tiktok"})
    chains = []
    if "web" in only:
        chains.append(threading.Thread(target=web_chain, args=(until, targets, done), name="web", daemon=True))
    if "api" in only:
        for network in API:
            chains.append(threading.Thread(target=spaced_chain, args=(network, until, targets[network], done.get(network, 0), network), name=network, daemon=True))
    if "tiktok" in only:
        chains.append(threading.Thread(target=phone_chain, args=(until, targets["tiktok"], done.get("tiktok", 0)), name="tiktok", daemon=True))
    for thread in chains:
        thread.start()
        nap(5)
    for thread in chains:
        thread.join()
    print("[cola] " + {"parar": "parada pedida (PARAR_RONDAS)", "recargar": "rondas en curso terminadas; recargando"}.get(control_signal(), "fin del dia"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Ciclo de vida local de mobilecli para los pipelines Android.

No instala nada. Arranca únicamente el servidor local ya instalado y exige la
versión validada por el proyecto. Equivalente móvil al ensure-browser, pero sin
abrir ninguna red social.
"""
from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
import time

from mobile_client import (
    DEFAULT_BASE_URL,
    MobileCliClient,
    MobileCliError,
    MobileCliTransportError,
)


EXPECTED_VERSION = "1.0.17"
LISTEN = "127.0.0.1:12000"
DEFAULT_LOCK_PATH = os.path.join(tempfile.gettempdir(), "rrss-autorademo-mobile.lock")


class MobileRuntimeError(RuntimeError):
    pass


class MobileSessionBusy(MobileRuntimeError):
    pass


def _pid_alive(pid) -> bool:
    """True si el proceso existe (o no se puede saber: mejor bloquear que pisar una sesion viva del movil)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return True
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return kernel32.GetLastError() == 5
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@contextlib.contextmanager
def mobile_session_lock(path: str | None = None, *, stale_after: float = 6 * 3600):
    """Impide que dos procesos del repo controlen el mismo Android a la vez."""
    path = path or os.getenv("MOBILE_SESSION_LOCK") or DEFAULT_LOCK_PATH
    token = f"{os.getpid()}:{time.time_ns()}"
    for attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, token.encode("ascii"))
            finally:
                os.close(fd)
            break
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(path)
            except OSError:
                age = 0
            # 07/10: un proceso matado (timeout, cierre de sesion) dejaba el bloqueo 6 h y las rondas de TikTok se saltaban con el movil libre: si el PID del dueno ya no existe, el bloqueo es suyo y se retira
            try:
                with open(path, encoding="ascii") as stream:
                    owner_pid = stream.read().strip().split(":")[0]
            except OSError:
                owner_pid = None
            if attempt == 0 and owner_pid and not _pid_alive(owner_pid):
                try:
                    os.remove(path)
                    continue
                except OSError:
                    pass
            if attempt == 0 and age > stale_after:
                try:
                    os.remove(path)
                    continue
                except OSError:
                    pass
            raise MobileSessionBusy(
                f"móvil ocupado por otra sesión del repo: {path}"
            )
    try:
        yield path
    finally:
        try:
            with open(path, encoding="ascii") as stream:
                current = stream.read().strip()
            if current == token:
                os.remove(path)
        except OSError:
            pass


def _argv(binary: str, *args: str) -> list[str]:
    if os.name == "nt" and binary.casefold().endswith((".cmd", ".bat")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", binary, *args]
    return [binary, *args]


def _version_of(binary: str) -> str:
    completed = subprocess.run(
        _argv(binary, "--version"),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    output = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode != 0:
        raise MobileRuntimeError(f"mobilecli --version falló: {output}")
    # Release oficial: "mobilecli version 1.0.17".
    version = output.rsplit(" ", 1)[-1]
    if version != EXPECTED_VERSION:
        raise MobileRuntimeError(
            f"mobilecli {EXPECTED_VERSION} requerido; encontrado {version!r}"
        )
    return version


def ensure_server(
    *,
    base_url: str = DEFAULT_BASE_URL,
    device_id: str | None = None,
    startup_timeout: float = 15.0,
) -> MobileCliClient:
    """Devuelve un cliente listo; si hace falta levanta el HTTP local."""
    client = MobileCliClient(base_url=base_url, device_id=device_id)
    try:
        info = client.server_info()
    except MobileCliTransportError:
        info = None

    if info is not None:
        if str(info.get("version", "")) != EXPECTED_VERSION:
            raise MobileRuntimeError(
                f"servidor mobilecli inesperado: {info.get('version')!r}"
            )
        # El servidor existe. Si falta el Xiaomi, propagar ese error en vez de
        # intentar levantar otro proceso sobre el mismo puerto.
        client.select_device(device_id)
        return client

    binary = shutil.which("mobilecli")
    if not binary:
        raise MobileRuntimeError(
            "mobilecli no está en PATH; instalar explícitamente "
            "npm install -g mobilecli@1.0.17"
        )
    _version_of(binary)

    creationflags = 0
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    subprocess.Popen(
        _argv(binary, "server", "start", "--listen", LISTEN),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        start_new_session=(os.name != "nt"),
    )

    deadline = time.monotonic() + max(1.0, float(startup_timeout))
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        client = MobileCliClient(base_url=base_url, device_id=device_id)
        try:
            info = client.server_info()
        except MobileCliTransportError as exc:
            last_error = exc
            time.sleep(0.4)
            continue
        if str(info.get("version", "")) != EXPECTED_VERSION:
            raise MobileRuntimeError(
                f"servidor mobilecli inesperado: {info.get('version')!r}"
            )
        # Desde aquí el servidor ya está listo. Un error de dispositivo no es
        # "startup": propagar ADB/selección inmediatamente.
        client.select_device(device_id)
        return client
    raise MobileRuntimeError(
        f"mobilecli no quedó disponible en {base_url}: {last_error}"
    )


def stop_server(*, base_url: str = DEFAULT_BASE_URL) -> bool:
    """Apaga solo el front HTTP; el daemon puede seguir vivo por diseño."""
    try:
        MobileCliClient(base_url=base_url).server_shutdown()
        return True
    except MobileCliError:
        return False

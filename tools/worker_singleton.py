"""Singleton entre procesos para reply_queue, sin archivos de bloqueo huérfanos.

El fichero worker.lock conserva el PID para monitorización (canarios).
worker.lock.oslock es PERMANENTE: lo que se bloquea es una región del
descriptor abierto. Windows msvcrt y Unix fcntl liberan el bloqueo al
cerrar el descriptor o terminar el proceso, incluso por caída abrupta.
NUNCA se elimina el guard: su inodo/ruta debe seguir siendo estable.
"""
from __future__ import annotations

import contextlib
import errno
import os
import pathlib
import sys

from action_ledger import _pid_alive


def _legacy_pid_alive(pid: int) -> bool:
    """Comprueba un PID heredado sin considerar activo un zombi Linux.

    `kill(pid, 0)` confirma la presencia del PID incluso si terminó y
    aún no fue recogido por su padre. Si /proc no es legible, falla cerrado.
    """
    if not _pid_alive(pid):
        return False
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/status", encoding="utf-8", errors="replace") as stream:
                for line in stream:
                    if line.startswith("State:"):
                        return line.split()[1] not in ("Z", "X")
        except (OSError, IndexError):
            pass  # No se puede certificar que terminó: respetar PID legado.
    return True


def _take(fd: int) -> None:
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release(fd: int) -> None:
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)


@contextlib.contextmanager
def claim(pid_file: str | os.PathLike):
    """Devuelve True si esta llamada posee el turno exclusivo del worker.

    Un guard del SO evita la carrera de worker_running() + open("w").
    En transición se comprueba el PID legado de un worker viejo vivo,
    ya que la versión previa no conocía el nuevo .oslock.
    """
    pid_file = pathlib.Path(pid_file)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    guard = str(pid_file) + ".oslock"
    fd = os.open(guard, os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0), 0o600)
    acquired = False
    wrote_pid = False
    try:
        try:
            _take(fd)
        except OSError as exc:
            # La colisión no es un error fatal; permisos, IO y otros fallos
            # sí deben propagarse sin crear ni tocar el fichero PID.
            if exc.errno in (errno.EACCES, errno.EAGAIN) or getattr(exc, "winerror", None) in (33, 36):
                yield False
                return
            raise
        acquired = True
        try:
            existing = int(pid_file.read_text(encoding="ascii").strip())
        except FileNotFoundError:
            existing = 0
        except (ValueError, UnicodeError):
            existing = 0  # PID legado malformado, protegido aún por OS lock
        # Otros errores de E/S (permiso, recurso inaccesible) se propagan:
        # no se debe truncar un fichero que no ha podido inspeccionarse.
        if existing > 0 and existing != os.getpid() and _legacy_pid_alive(existing):
            yield False  # despliegue con worker de versión anterior aún vivo
            return

        # Fichero PID legible por los canarios existentes. Nadie más puede
        # entrar en este bloque mientras se sostiene el bloqueo del SO.
        pid_file.write_text(str(os.getpid()), encoding="ascii")
        wrote_pid = True
        yield True
    finally:
        if wrote_pid:
            try:
                if pid_file.read_text(encoding="ascii").strip() == str(os.getpid()):
                    pid_file.unlink()
            except (OSError, UnicodeError):
                pass
        try:
            if acquired:
                _release(fd)
        finally:
            os.close(fd)

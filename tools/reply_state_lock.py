"""Exclusión breve de pending.json + answers.json entre productores y trabajador.

Guard PERMANENTE: nunca borrar el fichero .lock, ni siquiera tras un crash.
No es el singleton del worker (#126); protege transacciones JSON. Biblioteca estándar.
Los procesos anteriores al despliegue no conocen el guard: detenerlos antes de migrar.
"""
from __future__ import annotations

import contextlib
import errno
import os
import threading
import time

_LOCAL_LOCK = threading.RLock()
_LOCAL_GUARDS = threading.local()


def _take(fd):
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release(fd):
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)


@contextlib.contextmanager
def state_guard(pending_path, timeout=12.0):
    """Un lock común a todas las escrituras: IO inesperado falla cerrado."""
    guard = os.path.join(os.path.dirname(os.path.abspath(pending_path)), "reply_state.lock")
    with _LOCAL_LOCK:
        # Un helper de almacenamiento puede entrar aquí estando ya en una
        # transacción del mismo hilo. No abrir un segundo descriptor y
        # bloquear el byte otra vez: flock/msvcrt pueden autobloquearse.
        owned = getattr(_LOCAL_GUARDS, "paths", None)
        if owned is None:
            owned = set()
            _LOCAL_GUARDS.paths = owned
        if guard in owned:
            yield
            return
        os.makedirs(os.path.dirname(guard), exist_ok=True)
        fd = os.open(guard, os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0), 0o600)
        acquired = False
        try:
            if not os.fstat(fd).st_size:
                os.write(fd, b"0")
            deadline = time.monotonic() + timeout
            while True:
                try:
                    _take(fd)
                    acquired = True
                    break
                except OSError as exc:
                    busy = exc.errno in (errno.EACCES, errno.EAGAIN) or getattr(exc, "winerror", None) in (33, 36)
                    if not busy:
                        raise
                    if time.monotonic() >= deadline:
                        raise TimeoutError("COLA_OCUPADA: el estado JSON no se ha modificado") from exc
                    time.sleep(0.05)
            owned.add(guard)
            try:
                yield
            finally:
                owned.remove(guard)
        finally:
            try:
                if acquired:
                    _release(fd)
            finally:
                os.close(fd)

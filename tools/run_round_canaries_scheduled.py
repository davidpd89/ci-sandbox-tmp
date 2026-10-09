"""Ejecutor offline de canarios para pythonw/Task Scheduler.

No abre ventanas ni envía datos. Guarda un log acotado sin rutas ni mensajes
privados y actualiza un latido solo cuando el canario ha terminado bien.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import logging
from logging.handlers import RotatingFileHandler
import os
import pathlib
import sys


class CheckedRotatingFileHandler(RotatingFileHandler):
    """No convertir fallos de disco durante el log en éxitos silenciosos."""

    def handleError(self, record):
        error = sys.exc_info()[1]
        if error is not None:
            raise error
        raise OSError("no se pudo escribir el log de canarios")


def run_once(root, *, canary=None, now=None):
    root = pathlib.Path(root).resolve()
    folder = root / "00_OPERATIVO"
    folder.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"canary_schedule_{os.getpid()}_{id(folder)}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = CheckedRotatingFileHandler(folder / "canarios.log", maxBytes=131072,
                                  backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    try:
        try:
            if canary is None:
                from round_canaries import main as canary
            # El canario solo emite agregados; no se vuelcan excepciones ni datos
            # de terceros al log por accidente.
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = canary(["--root", str(root)])
        except Exception as exc:
            logger.error("canario_excepcion=%s", type(exc).__name__)
            return 2
        if code != 0:
            logger.error("canario_codigo=%s", code if isinstance(code, int) else "INVALIDO")
            return 2
        # Si la escritura del log falla, NO avanzar el latido.
        logger.info("canario_ok")
        timestamp = (now or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="seconds")
        heartbeat = folder / "canarios_ultimo_ok.txt"
        temporary = heartbeat.with_name(f"{heartbeat.name}.{os.getpid()}.tmp")
        try:
            temporary.write_text(timestamp + "\n", encoding="utf-8")
            os.replace(temporary, heartbeat)
        finally:
            temporary.unlink(missing_ok=True)
        return 0
    finally:
        logger.removeHandler(handler)
        handler.close()


def main():
    try:
        return run_once(pathlib.Path(__file__).resolve().parents[1])
    except Exception:
        # pythonw no posee consola; el Programador conserva LastRunResult != 0.
        return 3


if __name__ == "__main__":
    sys.exit(main())

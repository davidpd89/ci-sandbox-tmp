"""Utilidades ADB comunes a cualquier automatización Android del repo (no sabe de redes).

mobilecli cubre UI (tap/swipe/dump); lo que no cubre se pide a `adb shell` aquí: estado real del
teclado, actividad en primer plano, copiar ficheros al móvil y refrescar la galería. Una sola
implementación para TikTok y las próximas redes móviles.
"""
from __future__ import annotations

import os
import shutil
import subprocess

DEFAULT_ADB_DIRS = (r"C:\Android\platform-tools",)


def adb_path() -> str:
    found = shutil.which("adb")
    if found:
        return found
    for directory in DEFAULT_ADB_DIRS:
        candidate = os.path.join(directory, "adb.exe")
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError("adb no encontrado en PATH ni en C:\Android\platform-tools")


def run(args: list[str], *, serial: str | None = None, timeout: float = 20.0) -> str:
    cmd = [adb_path()] + (["-s", serial] if serial else []) + args
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    return proc.stdout or ""


def keyboard_shown(serial: str | None = None) -> bool:
    """True si el teclado (IME) está realmente visible. Fiable, a diferencia de inferirlo del
    árbol de accesibilidad (la barra 'Añadir comentario…' existe aunque no haya teclado)."""
    out = run(["shell", "dumpsys", "input_method"], serial=serial)
    for line in out.splitlines():
        if "mInputShown=" in line:
            return "mInputShown=true" in line
    return False


def foreground_component(serial: str | None = None) -> str:
    out = run(["shell", "dumpsys", "window"], serial=serial)
    for line in out.splitlines():
        if "mCurrentFocus" in line:
            return line.strip()
    return ""


def push_media(local_path: str, remote_dir: str = "/sdcard/Pictures/", serial: str | None = None) -> str:
    """Copia una imagen al móvil y avisa a la galería para que la vea en el selector."""
    remote = remote_dir.rstrip("/") + "/" + os.path.basename(local_path)
    run(["push", local_path, remote], serial=serial, timeout=60)
    run(["shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
         "-d", f"file://{remote}"], serial=serial)
    return remote

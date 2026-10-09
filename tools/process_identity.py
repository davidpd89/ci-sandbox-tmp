"""Identidad de proceso para locks: PID solo no distingue reutilización.

None = no verificable. Nunca interpretar None como prueba de muerte.
No añade dependencias ni crea procesos o ficheros.
"""
import os
import sys


def creation_token(pid):
    """Token estable durante la vida del proceso, distinto tras reutilizar PID."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetProcessTimes.argtypes = (
            ctypes.c_void_p,
            *([ctypes.POINTER(wintypes.FILETIME)] * 4)
        )
        kernel.GetProcessTimes.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            values = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in values)):
                return None
            started = values[0]
            ticks = (started.dwHighDateTime << 32) | started.dwLowDateTime
            return f"w{ticks}" if ticks else None
        finally:
            kernel.CloseHandle(handle)
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/stat", encoding="ascii") as stream:
                proc = stream.read()
            fields = proc.rsplit(")", 1)[1].strip().split()
            if len(fields) < 20:
                return None
            with open("/proc/sys/kernel/random/boot_id", encoding="ascii") as stream:
                boot = stream.read().strip().replace("-", "")
            ticks = int(fields[19])  # starttime = campo 22 de /proc/pid/stat
            if len(boot) != 32 or not all(c in "0123456789abcdef" for c in boot.lower()):
                return None
            return f"l{boot.lower()}_{ticks}" if ticks > 0 else None
        except (OSError, ValueError, IndexError):
            return None
    return None


def valid_token(value):
    """Solo un token con forma reconocible autoriza distinguir PID reciclado."""
    if not isinstance(value, str):
        return False
    if value.startswith("w"):
        return len(value) >= 12 and value[1:].isdigit()
    if value.startswith("l"):
        boot, sep, ticks = value[1:].partition("_")
        return sep == "_" and len(boot) == 32 and all(
            ch in "0123456789abcdef" for ch in boot
        ) and ticks.isdigit() and int(ticks) > 0
    return False

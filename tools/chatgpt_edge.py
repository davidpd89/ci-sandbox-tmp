"""Edge DEDICADO a ChatGPT (CDP 9224), separado del Edge de las redes (CDP 9223) (08/10/2026, David).

Por que existe: el trabajador de la cola de respuestas (`reply_queue.py`) consulta a ChatGPT dentro del Edge 9223 y necesita su turno (`edge_browser`), que las rondas web
(X, Threads, Facebook, Pinterest) ocupan una hora seguida: el 08/10 el trabajador estuvo casi una hora sin escribir comentarios. Con un Edge propio y su propio turno
(`chatgpt_browser`) escribe siempre, en paralelo a las rondas. Las cadenas API y movil NO usan navegador (solo encolan textos), asi que no necesitan otro puerto.

    python tools/chatgpt_edge.py status         # ¿esta el Edge 9224 arriba y con ChatGPT con sesion?
    python tools/chatgpt_edge.py start          # lo arranca si no esta (perfil C:\\Temp\\rrss-davidporto-chatgpt)
    python tools/chatgpt_edge.py copy-session   # copia la sesion de ChatGPT del Edge 9223 al 9224 (cookies solo en memoria, no se guardan en ningun fichero)

La primera vez, si ChatGPT pide iniciar sesion, la inicia David en esa ventana (nunca se teclean contrasenas). El perfil guarda la sesion para siempre.
Nunca se mata `msedge.exe` en general: solo se cierra esta instancia por CDP (`Browser.close`).
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

PORT = int(os.environ.get("RRSS_CHATGPT_CDP_PORT", "9224"))
SOURCE_PORT = 9223
PROFILE = os.environ.get("RRSS_CHATGPT_EDGE_PROFILE", r"C:\Temp\rrss-davidporto-chatgpt")
EDGE = os.environ.get("RRSS_EDGE_EXE", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
START_URL = "https://chatgpt.com/"
COOKIE_DOMAINS = ("chatgpt.com", "openai.com", "oaistatic.com")


def port_open(port=PORT, host="127.0.0.1", timeout=0.6):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def edge_args(port=PORT, profile=PROFILE):
    """Argumentos del Edge dedicado: ligero (RAM justa en este PC) y sin tocar el Edge personal ni el 9223."""
    return [
        f"--remote-debugging-port={port}", f"--user-data-dir={profile}", "--edge-skip-compat-layer-relaunch",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-background-networking",
        "--disable-sync", START_URL,
    ]


def start(wait_seconds=25):
    """Arranca el Edge de ChatGPT si no esta. Devuelve True si queda escuchando."""
    if port_open():
        return True
    if not os.path.exists(EDGE):
        print(f"[chatgpt_edge] no se encuentra {EDGE}", flush=True)
        return False
    os.makedirs(PROFILE, exist_ok=True)
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([EDGE] + edge_args(), creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if port_open():
            return True
        time.sleep(1)
    return False


class _Cdp:
    """Cliente CDP crudo del navegador (solo lectura/escritura de cookies): no usa Playwright, asi que no molesta a las rondas que usan el 9223."""

    def __init__(self, port):
        import json
        import urllib.request
        import websocket
        info = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5))
        self._json = json
        self.ws = websocket.create_connection(info["webSocketDebuggerUrl"], timeout=10, suppress_origin=True)
        self.n = 0

    def call(self, method, params=None):
        self.n += 1
        deadline = time.monotonic() + 10
        self.ws.send(self._json.dumps({"id": self.n, "method": method, "params": params or {}}))
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"CDP {method}: plazo de respuesta agotado")
            self.ws.settimeout(remaining)
            reply = self._json.loads(self.ws.recv())
            if reply.get("id") == self.n:
                if "error" in reply:
                    # Evitar propagar detalles que podrían contener datos de la cuenta.
                    raise RuntimeError(f"CDP {method}: error remoto")
                return reply.get("result", {})

    def close(self):
        self.ws.close()


def _is_chatgpt_cookie(cookie):
    if not isinstance(cookie, dict):
        return False
    domain = str(cookie.get("domain") or "").lstrip(".").lower().rstrip(".")
    return any(domain == root or domain.endswith("." + root) for root in COOKIE_DOMAINS)


def has_chatgpt_session(port=PORT):
    """True si hay cookies de sesion de ChatGPT en ese Edge (solo cuenta; no imprime valores)."""
    cdp = _Cdp(port)
    try:
        return any("session-token" in c.get("name", "") for c in cdp.call("Storage.getCookies").get("cookies", []) if _is_chatgpt_cookie(c))
    finally:
        cdp.close()


def copy_session():
    """Copia SOLO las cookies de ChatGPT/OpenAI del Edge 9223 al 9224 (por la memoria de este proceso, sin escribir ningun fichero). Devuelve cuantas."""
    source = _Cdp(SOURCE_PORT)
    try:
        cookies = [c for c in source.call("Storage.getCookies").get("cookies", []) if _is_chatgpt_cookie(c)]
    finally:
        source.close()
    if not cookies:
        return 0
    keep = ("name", "value", "domain", "path", "secure", "httpOnly", "sameSite", "expires", "priority", "sameParty", "sourceScheme", "sourcePort")
    params = [{k: c[k] for k in keep if k in c and not (k == "expires" and c[k] in (-1, None))} for c in cookies]
    target = _Cdp(PORT)
    try:
        target.call("Storage.setCookies", {"cookies": params})
    finally:
        target.close()
    return len(params)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    command = argv[0] if argv else "status"
    if command == "start":
        ok = start()
        print(f"[chatgpt_edge] Edge de ChatGPT {'listo' if ok else 'NO arranco'} en el puerto {PORT}")
        return 0 if ok else 1
    if command == "copy-session":
        if not port_open():
            print("[chatgpt_edge] el Edge 9224 no esta arriba: ejecuta primero `start`")
            return 1
        n = copy_session()
        print(f"[chatgpt_edge] {n} cookies de ChatGPT copiadas del 9223 al {PORT}")
        return 0 if n else 1
    if command == "status":
        up = port_open()
        print(f"[chatgpt_edge] puerto {PORT}: {'arriba' if up else 'CAIDO'}")
        if up:
            try:
                print(f"[chatgpt_edge] sesion de ChatGPT: {'si' if has_chatgpt_session() else 'NO (hay que iniciar sesion en esa ventana)'}")
            except Exception as exc:
                print(f"[chatgpt_edge] no se pudo comprobar la sesion: {type(exc).__name__}")
        return 0 if up else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())

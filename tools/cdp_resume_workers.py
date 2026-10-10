"""Reanuda los workers huerfanos del Edge compartido (04/10/2026).

Sintoma: `connect_over_cdp` de Playwright se cuelga con `<ws connected>` y nada mas. Causa probable: cada conexion que
muere a medias deja *workers* creados con "esperar al depurador" (`waitForDebuggerOnStart`); siguen pausados sin
nadie que les diga que arranquen y los siguientes `connect` se quedan esperandolos.

Esta herramienta NO mata procesos ni cierra pestanas: se adjunta a cada target `worker` / `service_worker` por CDP
crudo y envia `Runtime.runIfWaitingForDebugger` (inocuo si el worker ya corre). Despues desadjunta.

    python tools/cdp_resume_workers.py            # reanuda y lista
    python tools/cdp_resume_workers.py --list     # solo lista
"""
import json
import sys
import urllib.request

import websocket

PORT = 9223
TYPES = {"worker", "shared_worker", "service_worker", "other"}


def _browser_ws():
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=5))["webSocketDebuggerUrl"]


class Browser:
    def __init__(self):
        self.ws = websocket.create_connection(_browser_ws(), timeout=8, suppress_origin=True)
        self.n = 0

    def call(self, method, params=None, session=None):
        self.n += 1
        msg = {"id": self.n, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        self.ws.send(json.dumps(msg))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get("id") == self.n:
                return reply

    def close(self):
        self.ws.close()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    b = Browser()
    try:
        infos = b.call("Target.getTargets")["result"]["targetInfos"]
        workers = [t for t in infos if t["type"] in ("worker", "shared_worker")]
        print(f"targets={len(infos)} workers={len(workers)}")
        for t in workers:
            line = f"  {t['targetId'][:8]} {t['type']} attached={t.get('attached')} url={t['url'][:40]!r}"
            if "--list" not in argv:
                try:
                    session = b.call("Target.attachToTarget", {"targetId": t["targetId"], "flatten": True})["result"]["sessionId"]
                    reply = b.call("Runtime.runIfWaitingForDebugger", session=session)
                    b.call("Target.detachFromTarget", {"sessionId": session})
                    line += " -> reanudado" if "error" not in reply else f" -> error {reply['error']}"
                except Exception as exc:
                    line += f" -> fallo {exc}"
            print(line)
    finally:
        b.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

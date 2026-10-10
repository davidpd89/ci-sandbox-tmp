<<<<<<< HEAD
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
=======
"""Diagnóstico CDP de workers: por defecto y CLI exclusivamente SOLO LECTURA.

El comportamiento antiguo enviaba Runtime.runIfWaitingForDebugger a todos los
workers encontrados, sin propiedad verificable. Un worker puede pertenecer a
una pestaña ajena. Desde PR #58 NO se adjuntan ni reanudan targets externos.

    python tools/cdp_resume_workers.py
    python tools/cdp_resume_workers.py --list

Para recuperación operativa, identificar la causa sin modificar tabs de otras
cuentas. No ejecutar Target.closeTarget, Browser.close ni kill por PID.
"""
import json
import os
>>>>>>> origin/research/public-reuse-parent
import sys
import urllib.request

import websocket

<<<<<<< HEAD
PORT = 9223
TYPES = {"worker", "shared_worker", "service_worker", "other"}


def _browser_ws():
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=5))["webSocketDebuggerUrl"]
=======
PORT = int(os.environ.get("RRSS_SOCIAL_CDP_PORT", "9223"))


def _browser_ws():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=5) as stream:
        return json.load(stream)["webSocketDebuggerUrl"]
>>>>>>> origin/research/public-reuse-parent


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
<<<<<<< HEAD
=======
                if "error" in reply:
                    raise RuntimeError("CDP diagnóstico no disponible")
>>>>>>> origin/research/public-reuse-parent
                return reply

    def close(self):
        self.ws.close()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
<<<<<<< HEAD
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
=======
    if argv not in ([], ["--list"]):
        print("Modo de reanudación automática deshabilitado: ownership no verificable.")
        return 2
    browser = Browser()
    try:
        reply = browser.call("Target.getTargets")
        targets = reply.get("result", {}).get("targetInfos", [])
        if not isinstance(targets, list):
            raise RuntimeError("CDP devolvió lista de targets inválida")
        workers = [t for t in targets if isinstance(t, dict)
                   and t.get("type") in ("worker", "shared_worker")]
        print(f"targets={len(targets)} workers={len(workers)} diagnóstico_solo_lectura=1")
        for t in workers:
            target_id = str(t.get("targetId", ""))
            # Nunca imprimir URL, tokens ni identidad visible de los workers.
            print(f"  {target_id[:8]} {t['type']} attached={bool(t.get('attached'))} "
                  "(NO reanudado: propiedad no verificada)")
    finally:
        browser.close()
>>>>>>> origin/research/public-reuse-parent
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

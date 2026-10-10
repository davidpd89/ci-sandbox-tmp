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
import sys
import urllib.request

import websocket

PORT = int(os.environ.get("RRSS_SOCIAL_CDP_PORT", "9223"))


def _browser_ws():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=5) as stream:
        return json.load(stream)["webSocketDebuggerUrl"]


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
                if "error" in reply:
                    raise RuntimeError("CDP diagnóstico no disponible")
                return reply

    def close(self):
        self.ws.close()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

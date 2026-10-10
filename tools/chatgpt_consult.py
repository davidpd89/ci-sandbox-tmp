"""Consulta a ChatGPT (proyecto «MCP - RRSS Autora Demo») con ficheros adjuntos, por el Edge 9223 (05/10/2026).

Abre un chat NUEVO dentro del proyecto (pestana propia, no toca otras), adjunta los ficheros, pega la pregunta, espera a que
termine de responder (incluido el modo "pensando") y guarda la respuesta en un .md. Mejora a `ask_chatgpt_rrss.py`, que
necesitaba una pestana del proyecto ya abierta y no adjuntaba nada (tras reiniciar el Edge ya no la hay).

    python tools/chatgpt_consult.py pregunta.txt --attach a.txt b.txt --out respuesta.md [--wait-min 25]

Reglas de uso (David): preguntas ABIERTAS y exploratorias con el codigo adjunto («que falta, que se puede unificar»), no cerradas de si/no.
No adjuntar secretos (.env, tokens, *_tokens.json): `refuse_secret_files` lo impide.
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

PROJECT_URL = "https://chatgpt.com/g/g-p-6a3bc1e919148191a7b1f1faf854f6d1/project"
SECRET_NAMES = re.compile(r"(^\.env|token|secret|credential|password|\.pem$|\.key$)", re.I)
# 05/10: la interfaz de ChatGPT cambio y el atributo data-message-author-role desaparecio; el texto de la respuesta cuelga de MarkdownRoot.
ASSISTANT = '[data-message-author-role="assistant"], [class*="MarkdownRoot"]'
STOP_BUTTON = 'button[data-testid="stop-button"], button[aria-label*="Detener"], button[aria-label*="Stop"]'
SEND_BUTTON = 'button[data-testid="send-button"], button[type="submit"][aria-label="Enviar"], button[type="submit"][aria-label*="Send"]'


def refuse_secret_files(paths):
    for path in paths:
        name = os.path.basename(path)
        if SECRET_NAMES.search(name):
            raise ValueError(f"no se adjunta {name!r}: parece un fichero con secretos")
        with open(path, encoding="utf-8", errors="replace") as stream:
            head = stream.read(400000)
        if re.search(r"(EAA[A-Za-z0-9]{25,}|Bearer\s+[A-Za-z0-9_\-]{25,}|sk-[A-Za-z0-9]{20,})", head):
            raise ValueError(f"{name}: contiene algo con forma de token; revisar antes de enviar")


def browser_target():
    """(puerto, nombre del turno). Si el Edge dedicado a ChatGPT (9224) esta arriba se usa ese, con su propio turno (`chatgpt_browser`): las rondas web ocupan el 9223 una hora
    seguida y el trabajador de respuestas se quedaba sin escribir. Si no esta, se usa el 9223 compartido como siempre."""
    try:
        import chatgpt_edge
        if chatgpt_edge.port_open():
            return chatgpt_edge.PORT, "chatgpt_browser"
    except Exception:
        pass
    return 9223, "edge_browser"


def consult(question, attachments=(), wait_min=25):
    """El turno del navegador se toma SOLO para abrir el chat, adjuntar y enviar (1-2 min); la espera de la respuesta (puede ser
    de 30+ min en modo 'pensando') se hace sin el turno, en su propia pestana, para no bloquear las rondas programadas."""
    from playwright.sync_api import sync_playwright
    import action_ledger as al
    refuse_secret_files(attachments)
    p = sync_playwright().start()
    port, turn = browser_target()
    try:
        with al.browser_session(name=turn):
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=20000)
            ctx = browser.contexts[0]
            ctx.grant_permissions(["clipboard-read", "clipboard-write"])
            pg = ctx.new_page()
            pg.goto(PROJECT_URL, wait_until="domcontentloaded", timeout=40000)
            pg.wait_for_timeout(6000)
            if "auth" in pg.url or "login" in pg.url:
                raise RuntimeError("ChatGPT pide iniciar sesion: lo hace David, no se teclean contrasenas")
            if attachments:
                pg.locator("input[type=file]").first.set_input_files([os.path.abspath(a) for a in attachments])
                pg.wait_for_timeout(8000 + 3000 * len(attachments))
            box = pg.locator('[contenteditable="true"]').first
            box.click()
            pg.evaluate("(t) => navigator.clipboard.writeText(t)", question)
            pg.keyboard.press("Control+V")
            pg.wait_for_timeout(2500)
            pg.locator(SEND_BUTTON).first.click()
            pg.wait_for_timeout(8000)
        # --- fuera del turno: solo se lee esta pestana de ChatGPT ---
        deadline = time.time() + wait_min * 60
        last_len, stable = -1, 0
        while time.time() < deadline:
            pg.wait_for_timeout(4000)
            generating = pg.locator(STOP_BUTTON).count() > 0
            count = pg.locator(ASSISTANT).count()
            length = len(pg.locator(ASSISTANT).last.inner_text()) if count else 0
            stable = stable + 1 if (length == last_len and not generating and count) else 0
            last_len = length
            if stable >= 4 and length > 200:
                break
        if not pg.locator(ASSISTANT).count():
            raise RuntimeError("no hubo respuesta de ChatGPT dentro del plazo")
        answer = pg.locator(ASSISTANT).last.inner_text()
        url = pg.url
        pg.close()
        return answer, url
    finally:
        p.stop()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 2
    question = open(argv[0], encoding="utf-8").read()
    attach = []
    if "--attach" in argv:
        i = argv.index("--attach") + 1
        while i < len(argv) and not argv[i].startswith("--"):
            attach.append(argv[i])
            i += 1
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    wait = int(argv[argv.index("--wait-min") + 1]) if "--wait-min" in argv else 25
    answer, url = consult(question, attach, wait)
    if out:
        with open(out, "w", encoding="utf-8") as stream:
            stream.write(f"<!-- chat: {url} -->\n\n{answer}\n")
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

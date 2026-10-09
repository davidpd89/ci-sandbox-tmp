"""Threads: publica la presentacion con foto y la fija en el perfil (06/10/2026, David: «añade otro nuevo a Threads para fijarlo»).

El fijado se hace desde la interfaz (menu «···» del post -> «Fijar en el perfil»); la API oficial no lo ofrece. Idempotente: si el primer post del perfil ya es la presentacion y
esta fijado no publica otra vez.

    python tools/threads_pin.py --dry-run | python tools/threads_pin.py [--pin-only]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import threads_interact as t

PHOTO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "00_OPERATIVO", "RECURSOS", "assets", "perfil", "david-porto-retrato-bn.jpg"))
TEXT = ("Hola, soy Autora Demo, escritor gallego en Madrid. Escribo fantasía juvenil y novelas que dejan poso: «Samuel entre mundos» y «Las manecillas del recuerdo».\n\n"
        "¿Hablamos de libros, webs, escritura o de lo que os apetezca? Contadme qué estáis leyendo 👇\n\n"
        "🌐 autorademodiaz.com\n"
        "📖 Samuel entre mundos: https://www.amazon.es/dp/B0GB6LGQFH?tag=autorademo-21\n"
        "📖 Las manecillas del recuerdo: https://amzn.to/4zW6Yeu")


def pin_post(pg, permalink):
    """Fija el post `permalink` desde su menu «···». Devuelve True si queda fijado."""
    pg.goto(permalink, wait_until="domcontentloaded", timeout=25000)
    pg.wait_for_timeout(2500)
    t._check_bot_warning(pg)
    t._assert_active_account(pg)
    container = t._post_containers(pg).first
    for button in container.locator('div[role="button"]').all():
        title = button.evaluate('(el) => { const t = el.querySelector("svg title"); return t ? t.textContent : null; }')
        if title in ("Más", "More"):
            button.click()
            break
    else:
        raise RuntimeError("no se encontro el menu «Mas» del post")
    pg.wait_for_timeout(1200)
    item = pg.get_by_text("Fijar en el perfil", exact=False)
    if item.count() == 0:
        print("opciones del menu:", pg.inner_text("body")[-600:].replace("\n", " | "))
        raise RuntimeError("el menu no ofrece «Fijar en el perfil»")
    item.first.click()
    pg.wait_for_timeout(1500)
    for label in ("Fijar", "Confirmar", "Pin"):
        confirm = pg.get_by_role("button", name=label, exact=True)
        if confirm.count():
            confirm.first.click()
            pg.wait_for_timeout(1500)
            break
    return True


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    t._check_length(TEXT)
    t._check_spanish_orthography(TEXT)
    if "--dry-run" in argv:
        print(f"{len(TEXT)} caracteres\n{TEXT}\nfoto: {os.path.getsize(PHOTO)} bytes")
        return 0
    import action_ledger
    with action_ledger.browser_session(wait_minutes=30):
        t.ensure_browser()
        with t.session() as pg:
            permalink = None
            if "--pin-only" in argv:
                permalink = argv[argv.index("--pin-only") + 1]
            else:
                permalink = t.post(TEXT, PHOTO)
            print("permalink:", permalink)
            pin_post(pg, permalink)
            print("fijado (comprobar en el perfil)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

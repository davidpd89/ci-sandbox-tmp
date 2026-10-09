"""Quita el like de posts concretos de Threads (03/10/2026, David: no dar likes a cuentas de ligue/sexo).

Para cada `handle:fragmento` abre el perfil del autor, localiza el post por texto y, SOLO si lo tenemos con like
("Ya no me gusta"), pulsa para quitarlo. Nunca da likes. Un post que no aparece o que no estaba con like se
cuenta como "sin cambios".

    python tools/threads_unlike.py handle1:"fragmento del post" handle2:"otro fragmento"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import threads_interact as t


def unlike(pg, handle, fragment):
    pg.goto(f"https://www.threads.com/@{handle.lstrip('@')}", wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(2500)
    t._check_bot_warning(pg)
    t._assert_active_account(pg)
    index = t._find_container_by_text(pg, fragment)
    if index is None:
        return "no_encontrado"
    container = t._post_containers(pg).nth(index)
    button = t._find_action_button(container, "Ya no me gusta")
    if button is None:
        return "sin_like"
    button.click()
    pg.wait_for_timeout(1000)
    t._check_bot_warning(pg)
    return "quitado" if t._find_action_button(container, "Me gusta") is not None else "no_verificado"


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    items = [a.split(":", 1) for a in (sys.argv[1:] if argv is None else argv) if ":" in a]
    if not items:
        print(__doc__)
        return 2
    p, pg = t._connect()
    try:
        for handle, fragment in items:
            print(f"@{handle}: {unlike(pg, handle, fragment)}")
            pg.wait_for_timeout(2000)
    finally:
        p.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

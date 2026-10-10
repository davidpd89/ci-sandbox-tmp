"""Auditoria de solo lectura del perfil de Pinterest (07/10/2026): texto visible del perfil, de la pestana Creados y de Ajustes > Editar perfil, para ver que falta
(bio, foto, enlace, tableros, pines propios, secciones). No escribe nada.

    python tools/pinterest_profile_audit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pinterest_publish as pp
from playwright.sync_api import sync_playwright

PAGES = (
    ("perfil", "https://es.pinterest.com/davidportodiaz/"),
    ("creados", "https://es.pinterest.com/davidportodiaz/_created/"),
    ("guardados", "https://es.pinterest.com/davidportodiaz/_saved/"),
    ("editar_perfil", "https://es.pinterest.com/settings/profile/"),
    ("cuenta", "https://es.pinterest.com/settings/account-settings/"),
)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    import action_ledger
    with action_ledger.browser_session(wait_minutes=40):
        p = sync_playwright().start()
        try:
            browser = p.chromium.connect_over_cdp(pp.CDP_URL)
            pg = browser.contexts[0].new_page()
            pg.set_default_timeout(20000)
            try:
                for name, url in PAGES:
                    pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                    pg.wait_for_timeout(5000)
                    pp._check(pg)
                    text = pg.evaluate("() => document.body.innerText")
                    print(f"\n===== {name} ({url}) =====")
                    print(text[:2500])
                    inputs = pg.evaluate("() => [...document.querySelectorAll('input,textarea')].map(e => (e.id||e.name||e.type)+'='+(e.value||'').slice(0,120)).slice(0,25)")
                    if inputs:
                        print("--- campos:", inputs)
            finally:
                pg.close()
        finally:
            p.stop()


if __name__ == "__main__":
    main()

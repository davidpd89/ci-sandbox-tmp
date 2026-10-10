"""Cierra el compose de X si está abierto."""
import sys, time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9223", timeout=5000)
    pages = [pg for c in b.contexts for pg in c.pages]
    x = next((pg for pg in pages if "x.com" in pg.url), None)
    if x:
        x.bring_to_front()
        # Cerrar compose con Escape
        x.keyboard.press("Escape")
        time.sleep(0.5)
        x.keyboard.press("Escape")
        time.sleep(0.5)
        # Volver a home si hace falta
        if "compose" in x.url:
            x.goto("https://x.com/home")
            time.sleep(2)
        x.screenshot(path="C:/Temp/x_clean.png")
        print(f"X URL: {x.url}")
        print("Compose cerrado")
    else:
        print("X no encontrado")

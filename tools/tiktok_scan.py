"""
Fase 1 del pipeline diario de TikTok (22/09, primer dia de esta red) -
mismo patron que las otras cinco, pero deliberadamente MAS estrecho al
principio: TikTok disparo un captcha real el mismo dia solo con navegar a
una URL de busqueda (ver docstring de `tiktok_interact.py`), asi que la
busqueda queda fuera del scan automatico hasta investigarla mas a fondo
con mas cuidado (ver PENDIENTES.md). Unica fuente por ahora: el feed
"Siguiendo" (`_extract_feed_items`, estructurado, navegacion normal ya
confirmada como segura).

Filtrado automatico: descarta nuestro propio handle, contenido politico
(heuristico, `scan_common.py`), marca [NUEVA]/[CONOCIDA fecha=...] contra
registro_interacciones.csv.

Kind sugerida (anadido 23/09, mismo criterio que en las otras redes) para
abaratar decidir - NO para forzar mas volumen del que permite la tabla de
calentamiento progresivo de REGLAS.md (esa tabla es una medida de seguridad
real tras el incidente de captcha, no una omision a corregir).

Uso:
    python tools/tiktok_scan.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import tiktok_interact as tt
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_TIKTOK")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")


_suggest_kind = lambda *a, **k: sc.downgrade_for_opinion(_suggest_kind_raw(*a, **k), a[0], 'like')


def _suggest_kind_raw(text):
    return "comment" if sc.invites_conversation(text) else "like"


def scan():
    tt._refuse_if_paused()
    known = sc.known_accounts(REGISTRO_CSV)
    discarded = sc.discarded_handles(REGISTRO_CSV)
    candidates = []  # (handle, text, kind)

    p, pg = tt._connect()
    try:
        print("=== HEALTH ===")
        ok, msg = tt._health_check(pg)
        print(msg)
        if not ok:
            print("\nParando aqui - resolver esto antes de nada mas.")
            return

        print("\n=== RECOLECTANDO CANDIDATOS (feed Siguiendo) ===")
        tt._dump_following_feed(pg)
        seen = set()
        for handle, text in tt._extract_feed_items(pg):
            if not handle or handle in seen:
                continue
            seen.add(handle)
            if not sc.is_valid_candidate(handle, text, tt.MY_HANDLE, discarded):
                continue
            candidates.append((handle, text.replace("\n", " "), _suggest_kind(text)))

        print(f"\n=== CANDIDATOS FILTRADOS: {len(candidates)} (tras politica/dedupe) ===")
        by_kind = {}
        for handle, text, kind in candidates:
            by_kind[kind] = by_kind.get(kind, 0) + 1
            known_tag = f"[CONOCIDA fecha={known[handle]}] " if handle in known else "[NUEVA] "
            print(f"{known_tag}sugerido={kind} | @{handle}")
            print(f"   {text[:160]}")
        print(f"\nResumen por kind sugerida: {by_kind}")
    finally:
        p.stop()


if __name__ == "__main__":
    try:
        tt._refuse_if_paused()
        tt.ensure_browser()
        scan()
    except (tt.InteractionsPaused, tt.BotWarningDetected) as e:
        print(str(e))
        sys.exit(2)

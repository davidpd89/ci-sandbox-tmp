"""Informe único de la cola editorial. NO publica ni programa.

Desde el 28/09/2026 David publica/programa manualmente en la interfaz nativa de
cada red. Este script únicamente reúne fichas futuras/vencidas para revisión.
No importa runners de publicación y no ejecuta writes remotos.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import content_queue as cq

SOLO_INFORME = set(cq.RED_FOLDERS.keys())
SCHEDULE_NATIVO = set()
PUBLICA_CUANDO_VENCE = set()
RUNNERS = {}


def run(red):
    if red not in cq.RED_FOLDERS:
        raise ValueError(f"Red desconocida: {red}")

    issues = cq.pending_parse_issues(red, auto_only=False)
    if issues:
        print(f"[{red}] AVISO: {len(issues)} ficha(s) con datos incompletos.")
        for path, missing in issues:
            print(f"  - {path}: falta/invalidado {', '.join(missing)}")

    # Para trabajo manual interesa ver tanto lo futuro como lo ya vencido.
    items = cq.future_items(red) + cq.due_items(red)
    if not items:
        print(f"[{red}] nada pendiente.")
        return []

    print(
        f"[{red}] {len(items)} ficha(s) para revisión manual. "
        "Este comando NO publica ni programa."
    )
    for item in items:
        text = item.get("texto") or "(ver publicacion.md)"
        print(f"  {item['fecha_hora']} | {item['carpeta']}")
        print(f"    PENDIENTE MANUAL: {text[:120]}")
    return items


if __name__ == "__main__":
<<<<<<< HEAD
=======
    if "--calendar" in sys.argv[1:]:
        import publication_calendar
        raise SystemExit(publication_calendar.main([a for a in sys.argv[1:] if a != "--calendar"]))
>>>>>>> origin/research/public-reuse-parent
    redes = [sys.argv[1]] if len(sys.argv) > 1 else list(cq.RED_FOLDERS.keys())
    for red in redes:
        run(red)

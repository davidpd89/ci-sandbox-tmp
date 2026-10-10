"""Programa los 8 posts fallidos como texto-only (sin media)."""
import sys, time, subprocess
sys.stdout.reconfigure(encoding="utf-8")

script = r'C:\GIT\RRSS_DavidPorto\tools\x_schedule_post.py'

FAILED = [
    (2026,7,11,13,0, "Abrí una puerta que no estaba ahí. No estaba en los mapas. ¿Te ha pasado en fantasía? #PortalFantasy"),
    (2026,7,12,13,0, "03:16. El vaso sin tocar. Ese 'uno más' que era mentira. ¿Con qué libro? #Lectura"),
    (2026,7,12,21,0, "Nueve meses. 0 libros. El Kindle sigue cargado. ¿Con qué lo empezarías tú? #Lectores"),
    (2026,7,13,13,0, "Lo cerré. Volví a mi vida. Mentira. ¿Qué libro te dejó de resaca? #Libros"),
    (2026,7,13,21,0, "Se odian con demasiada precisión. Y yo ya he comprado el arroz. ¿El tuyo? #Romantasy"),
    (2026,7,18,13,0, "La leí veinte veces. La misma escena. No me cansa. ¿Cuál es la tuya? #Libros"),
    (2026,7,19,13,0, "El protagonista, bien. El secundario, todo. Sin defensa. ¿Con quién vas tú? #Lectores"),
    (2026,7,20,21,0, "Traía una nota dentro. Sin nombre. Sin contexto. Solo ahí, para mí. ¿Abrirías la nota? #LibrosUsados"),
]

ok = 0
for yr,mo,dy,hr,mn,text in FAILED:
    print(f"\n{dy:02d}/{mo:02d} {hr}:{mn:02d} — {text[:55]}")
    r = subprocess.run([sys.executable, script, text, "", str(yr), str(mo), str(dy), str(hr), str(mn)],
                       capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
    if r.returncode == 0:
        print("  ✓ Programado"); ok += 1
    else:
        err = (r.stdout + r.stderr)[-80:]
        print(f"  ✗ {err}")
    time.sleep(2)

print(f"\nProgramados: {ok}/{len(FAILED)}")

"""
Renderiza los 3 reels usando render_reel_v6_paced.py + los clips Ken Burns.
Cada reel: imagen animada (Ken Burns) + texto superpuesto + musica.

Reel 1 (Jul 23): bookstore editorial B&W — humor/identificacion lector
Reel 2 (Jul 24 tarde): mujer libro humor — pila pendientes
Reel 3 (Jul 25 tarde): acantilado/amor — texto emocional
"""
import sys
import subprocess
import os
from pathlib import Path
import imageio_ffmpeg

sys.stdout.reconfigure(encoding="utf-8")

TOOLS = Path(r"C:\GIT\RRSS_DavidPorto\tools")
REEL_SCRIPT = TOOLS / "reel_template" / "render_reel_v6_paced.py"
CLIPS = Path(r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\clips_ken_burns")
OUT = Path(r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\Reels_listos")
OUT.mkdir(exist_ok=True)

MUSIC = {
    "melancholic": r"C:\GIT\RRSS_DavidPorto\08_Usados_foto\perplexity\piezas\06-no-llega-a-tiempo\music_melancholic.mp3",
    "catwalk":     r"C:\GIT\RRSS_DavidPorto\tools\reel_template\clips_post2\music_catwalk.mp3",
    "relaxed":     r"C:\GIT\RRSS_DavidPorto\08_Usados_foto\perplexity\piezas\08-capitulo-mas-noche\music_relaxed.mp3",
}


def render(clip, texts, music_key, out_name, seg=2.0):
    out_path = OUT / out_name
    music_path = MUSIC[music_key]
    cmd = [
        "python", str(REEL_SCRIPT),
        str(out_path),
        music_path,
        "--clips", str(clip),
        "--seg", str(seg),
        "--texts",
    ] + texts
    print(f"\nRenderizando {out_name} ({music_key}, {seg}s/frase)...", flush=True)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", env=env,
        cwd=str(TOOLS / "reel_template")
    )
    if result.returncode != 0:
        print(f"  STDERR:\n{result.stderr[-600:]}", flush=True)
        return None
    print(f"  OK -> {out_path}", flush=True)
    return out_path


# ─────────────────────────────────────────────────────────────
# REEL 1 — Jul 23 — Bookstore editorial B&W
# Tema: "entro solo a mirar" — identificacion humor lector
# Musica: melancolica/indie (combina con B&W)
# Ritmo: 2s/frase, 8 frases = ~16s + intro
# ─────────────────────────────────────────────────────────────
reel1_texts = [
    "Entro solo a mirar.",
    "Lo digo de verdad.",
    "Esta vez no compro nada.",
    "Solo miro.",
    "Veinte minutos despues.",
    "Tres libros bajo el brazo.",
    "Cara de culpable.",
    "Ningun arrepentimiento.",
]

render(
    CLIPS / "clip_bookstore.mp4",
    reel1_texts,
    "melancholic",
    "reel_bookstore_jul23.mp4",
    seg=2.0,
)

# ─────────────────────────────────────────────────────────────
# REEL 2 — Jul 24 tarde — Humor lector / pila de pendientes
# Tema: comprar vs leer — aficiones distintas
# Musica: catwalk (upbeat, energia)
# Ritmo: 2.2s/frase, 7 frases = ~15s
# ─────────────────────────────────────────────────────────────
reel2_texts = [
    "Comprar libros.",
    "Y leer libros.",
    "Son aficiones distintas.",
    "Una para el presente.",
    "Otra para el yo futuro",
    "que nunca llega.",
    "Y aun asi: otro libro.",
]

render(
    CLIPS / "clip_humor.mp4",
    reel2_texts,
    "catwalk",
    "reel_humor_jul24.mp4",
    seg=2.2,
)

# ─────────────────────────────────────────────────────────────
# REEL 3 — Jul 25 tarde — Emocional / acantilado amor
# Tema: cuando un libro te hace sentir demasiado
# Musica: relaxed (suave, emotivo)
# Ritmo: 2.3s/frase, 7 frases = ~16s
# ─────────────────────────────────────────────────────────────
reel3_texts = [
    "Hay libros que te encuentran.",
    "No los eliges tu.",
    "Aparecen cuando algo en ti",
    "necesita ser dicho",
    "por alguien que no eres tu.",
    "Y ya no puedes volver",
    "al que eras antes de leerlo.",
]

render(
    CLIPS / "clip_emocional.mp4",
    reel3_texts,
    "relaxed",
    "reel_emocional_jul25.mp4",
    seg=2.3,
)

print("\n=== TODOS LOS REELS RENDERIZADOS ===")
for f in OUT.glob("*.mp4"):
    size_mb = f.stat().st_size / 1024 / 1024
    print(f"  {f.name} ({size_mb:.1f} MB)")

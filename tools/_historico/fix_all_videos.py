"""
Corrige los 5 vídeos del lote Jul 20-22:
1. DP-F0-081: llenar los 14s con 7 líneas × 2s
2. DP-F0-077: verificar y subir con nuevo nombre para forzar cache
3. DP-F0-082: REEMPLAZAR con concepto participativo "Tres palabras"
4. DP-F0-078: verificar y subir con nuevo nombre
5. DP-F0-083: llenar los 14s con texto más claro
Todos con --seg 2.0 y archivo nuevo (evita cache Metricool).
"""
import sys, io, subprocess
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()

SCRIPT = Path(r"C:\GIT\RRSS_DavidPorto\tools\reel_template\render_reel_v6_paced.py")
PIEZAS = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas")

def render(clips, texts, music, out, seg="2.0"):
    cmd = ([sys.executable, str(SCRIPT), str(out), str(music)]
           + ["--clips"] + [str(c) for c in clips]
           + ["--texts"] + texts
           + ["--seg", seg])
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    if r.returncode == 0:
        print(f"  ✓ {out.name} ({out.stat().st_size//1024}KB)")
        return True
    print(f"  ✗ {r.stderr.decode()[-100:]}")
    return False

def get_duration(clip):
    r = subprocess.run([FF, "-i", str(clip)], capture_output=True)
    for line in r.stderr.decode().split('\n'):
        if 'Duration' in line:
            parts = line.split('Duration:')[1].split(',')[0].strip()
            h, m, s = parts.split(':')
            return float(h)*3600 + float(m)*60 + float(s)
    return 0

# Música disponible sin repetir
MUSIC = {
    "warm": Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\tt-viaje\music.mp3"),
    "quiet": Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\03-la-gravedad-se-rinde\silent_descent.mp3"),
    "window": Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\03-cerrar-libro\music_ventana.mp3"),
    "gato": Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\04-gato-capitulo\music_gato.mp3"),
    "villano": Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\tt-villano-llave\music.mp3"),
}

# =============================================================
# 1. DP-F0-081 "La leí veinte veces" (concat 14.23s)
# =============================================================
print("=== DP-F0-081: La leí veinte veces ===")
concat_081 = PIEZAS / "23-misma-escena" / "concat.mp4"
dur = get_duration(concat_081)
n_lines = max(int(dur / 2.0), 4)
print(f"  Duración: {dur:.1f}s → {n_lines} líneas × 2s")
TEXTS_081 = [
    "La leí veinte veces.",
    "La misma escena.",
    "Sé lo que pasa.",
    "La leo igual.",
    "Cada vez.",
    "Como si fuera la primera.",
    "¿Cuál es la tuya?",
][:n_lines]
out_081 = PIEZAS / "23-misma-escena" / "reel_v2.mp4"
render([concat_081], TEXTS_081, MUSIC["gato"], out_081)

# =============================================================
# 2. DP-F0-077 "Este libro ya vivió" (Ken Burns 32s)
# Problema: Metricool cachea — nuevo nombre reel_v3
# =============================================================
print("\n=== DP-F0-077: Este libro ya vivió ===")
clips_077 = sorted((PIEZAS / "20-libro-ya-vivio" / "clips").glob("clip*.mp4"))
TEXTS_077 = [
    "Este libro ya vivió.",
    "Pasó por otras manos.",
    "Alguien lo subrayó.",
    "Alguien lo anotó.",
    "Alguien lo soltó.",
    "Y llegó a las mías.",
    "Traía una nota dentro.",
    "Sin firmar.",
    "Sin contexto.",
    "Solo la nota ahí.",
    "Dentro de mis páginas.",
    "No sé quién la puso.",
    "No sé a quién iba.",
    "Pero estaba ahí.",
    "Para mí.",
    "¿Te ha pasado algo así?",
]
out_077 = PIEZAS / "20-libro-ya-vivio" / "reel_v3.mp4"
render(clips_077, TEXTS_077, MUSIC["quiet"], out_077)

# =============================================================
# 3. DP-F0-082 REEMPLAZAR — "Tres palabras para venderme tu libro"
# Uso la misma carpeta pero texto completamente distinto
# =============================================================
print("\n=== DP-F0-082: NUEVO — Véndeme tu libro ===")
# Reutilizo el vídeo de esconder el libro (visualmente sigue siendo bueno)
# pero con texto que fuerza participación activa
concat_082 = PIEZAS / "24-libro-que-no-enseno" / "concat.mp4"
dur_082 = get_duration(concat_082)
TEXTS_082 = [
    "Véndeme tu libro favorito.",
    "Solo tres palabras.",
    "Sin 'adictivo'.",
    "Sin 'te atrapa'.",
    "Tres palabras tuyas.",
    "Las que a ti te cambió.",
    "Empieza en comentarios.",
]
out_082 = PIEZAS / "24-libro-que-no-enseno" / "reel_v2.mp4"
render([concat_082], TEXTS_082, MUSIC["warm"], out_082)

# =============================================================
# 4. DP-F0-078 "Olvidé el final" (Ken Burns 32s)
# Nuevo nombre reel_v3 para forzar cache
# =============================================================
print("\n=== DP-F0-078: Olvidé el final ===")
clips_078 = sorted((PIEZAS / "20-olvide-el-final" / "clips").glob("clip*.mp4"))
TEXTS_078 = [
    "Olvidé el final.",
    "Ni el nombre recuerdo.",
    "Solo que era largo.",
    "Que no podía parar.",
    "Que lo cerré despacio.",
    "Me quedé quieto.",
    "Sin hacer nada.",
    "Solo ahí.",
    "Con el libro cerrado.",
    "Sin saber muy bien.",
    "Qué había pasado.",
    "Eso no se olvida.",
    "Aunque se olvide todo.",
    "Hay libros así.",
    "Sin trama.",
    "¿Con qué libro?",
]
out_078 = PIEZAS / "20-olvide-el-final" / "reel_v3.mp4"
render(clips_078, TEXTS_078, MUSIC["window"], out_078)

# =============================================================
# 5. DP-F0-083 "El secundario, sin defensa" (concat 14.23s)
# =============================================================
print("\n=== DP-F0-083: El secundario ===")
concat_083 = PIEZAS / "25-secundario-roba-novela" / "concat.mp4"
dur_083 = get_duration(concat_083)
TEXTS_083 = [
    "El protagonista, bien.",
    "El secundario, todo.",
    "Aparece poco.",
    "Dice poco.",
    "Y aun así.",
    "Me quedo con él.",
    "¿Con quién vas tú?",
]
out_083 = PIEZAS / "25-secundario-roba-novela" / "reel_v2.mp4"
render([concat_083], TEXTS_083, MUSIC["villano"], out_083)

print("\n=== RESUMEN ===")
for f in [out_081, out_077, out_082, out_078, out_083]:
    ok = f.exists() and f.stat().st_size > 100000
    print(f"  {'✓' if ok else '✗'} {f.parent.name}/{f.name} ({f.stat().st_size//1024 if f.exists() else 0}KB)")

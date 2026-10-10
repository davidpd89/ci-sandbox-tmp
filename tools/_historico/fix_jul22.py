"""
1. Pone DP-F0-079 como draft (borrado efectivo de Jul 22)
2. Re-renderiza DP-F0-077 y 078 con --seg 2.0 y texto correcto (sin 'dolió')
3. Actualiza Metricool con el nuevo vídeo
"""
import sys, io, json, subprocess
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout
from metricool_client import call_tool

BLOG_ID = "6435452"
SCRIPT = Path(r"C:\GIT\RRSS_DavidPorto\tools\reel_template\render_reel_v6_paced.py")

# IDs de DP-F0-079 a borrar (todos los del 22 jul con "Doce euros")
IDS_079 = [344601162, 344601166, 344601168, 344601173, 344601181, 344601189]

def get_post(pid):
    r = call_tool("getScheduledPosts",{"brandId":BLOG_ID,"fromDate":"2026-07-22T00:00:00+02:00","toDate":"2026-07-22T23:59:00+02:00","timezone":"Europe/Madrid"})
    text = r["content"][0]["text"] if r.get("content") else ""
    raw = json.loads(text) if text else {}
    posts = raw.get("data") or raw.get("posts") or []
    return next((p for p in posts if p.get("id") == pid), None)

# === PASO 1: Poner DP-F0-079 como draft ===
print("=== BORRAR DP-F0-079 (como draft) ===")
NET_KEY = {"instagram":"instagramData","facebook":"facebookData","tiktok":"tiktokData",
           "threads":"threadsData","bluesky":"blueskyData","pinterest":"pinterestData"}

for pid in IDS_079:
    p = get_post(pid)
    if not p: print(f"  id={pid}: no encontrado"); continue
    net = next((pr.get("network") for pr in p.get("providers",[])), "?")
    info = {
        "autoPublish": False, "draft": True,
        "text": f"[BORRADO] {p.get('text','')[:20]}",
        "media": p.get("media",[]), "providers": p.get("providers",[]),
        "publicationDate": p.get("publicationDate",{}),
        "descendants":[],"firstCommentText":"","hasNotReadNotes":False,"shortener":False,"smartLinkData":{"ids":[]},
    }
    ck = NET_KEY.get(net)
    if ck and ck in p: info[ck] = p[ck]
    r = call_tool("updateScheduledPost",{"blogId":BLOG_ID,"id":str(pid),"uuid":p.get("uuid",""),"info":json.dumps(info,ensure_ascii=False)})
    print(f"  {net:12} id={pid}: {'OK' if not r.get('isError') else 'ERR'}")

# === PASO 2: Re-renderizar DP-F0-077 con --seg 2.0 y más líneas ===
print("\n=== RE-RENDER DP-F0-077 (Este libro ya vivió) ===")
# 4 clips × 8s = 32s, 16 líneas × 2s = 32s
CLIPS_077 = [
    Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\20-libro-ya-vivio\clips\clip1.mp4"),
    Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\20-libro-ya-vivio\clips\clip2.mp4"),
    Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\20-libro-ya-vivio\clips\clip3.mp4"),
    Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\20-libro-ya-vivio\clips\clip4.mp4"),
]
TEXTS_077 = [
    "Este libro ya vivió.",
    "Pasó por otras manos.",
    "Alguien lo subrayó.",
    "Alguien lo dejó ir.",
    "Traía una nota dentro.",
    "Sin firmar.",
    "No sé quién la escribió.",
    "No sé a quién iba.",
    "Solo sé que estaba ahí.",
    "Dentro de mi libro.",
    "Dentro de mi tarde.",
    "Dentro de algo que no era mío.",
    "Y ahora lo es.",
    "¿La abrirías?",
    "¿O la dejarías estar?",
    "¿Te ha pasado algo así?",
]
MUSIC_077 = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\03-la-gravedad-se-rinde\silent_descent.mp3")
OUT_077 = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\20-libro-ya-vivio\reel_v2.mp4")
cmd = ([sys.executable, str(SCRIPT), str(OUT_077), str(MUSIC_077)]
       + ["--clips"] + [str(c) for c in CLIPS_077]
       + ["--texts"] + TEXTS_077
       + ["--seg", "2.0"])
r = subprocess.run(cmd, capture_output=True, timeout=300)
if r.returncode == 0:
    print(f"  reel_v2.mp4: {OUT_077.stat().st_size//1024}KB OK")
else:
    print(f"  ERROR: {r.stderr.decode()[-200:]}")

# === PASO 3: Re-renderizar DP-F0-078 sin 'dolió' ===
print("\n=== RE-RENDER DP-F0-078 (Olvidé el final) ===")
CLIPS_078 = [
    Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\20-olvide-el-final\clips\clip1.mp4"),
    Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\20-olvide-el-final\clips\clip2.mp4"),
    Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\20-olvide-el-final\clips\clip3.mp4"),
    Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\20-olvide-el-final\clips\clip4.mp4"),
]
TEXTS_078 = [
    "Olvidé el final.",
    "Ni me acuerdo del nombre.",
    "Solo sé que era largo.",
    "Que no podía parar.",
    "Que lo cerré despacio.",
    "Que me quedé quieto un rato.",
    "Sin hacer nada.",
    "Solo ahí.",
    "Con el libro cerrado en la mano.",
    "Sin saber muy bien qué había pasado.",
    "Eso no se olvida.",
    "Aunque se olvide todo lo demás.",
    "Hay libros que son así.",
    "No te dejan trama.",
    "Te dejan una tarde entera.",
    "¿Con qué libro?",
]
MUSIC_078 = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\03-cerrar-libro\music_ventana.mp3")
OUT_078 = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\meta\piezas\20-olvide-el-final\reel_v2.mp4")
cmd2 = ([sys.executable, str(SCRIPT), str(OUT_078), str(MUSIC_078)]
        + ["--clips"] + [str(c) for c in CLIPS_078]
        + ["--texts"] + TEXTS_078
        + ["--seg", "2.0"])
r2 = subprocess.run(cmd2, capture_output=True, timeout=300)
if r2.returncode == 0:
    print(f"  reel_v2.mp4: {OUT_078.stat().st_size//1024}KB OK")
else:
    print(f"  ERROR: {r2.stderr.decode()[-200:]}")

print("\nListo. Pendiente: subir nuevos reel_v2 a GitHub Pages y actualizar posts en Metricool.")

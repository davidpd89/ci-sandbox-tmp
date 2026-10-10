"""
Descarga los 4 clips generados en Flow usando fetch del navegador (con cookies).
"""
import sys, io, base64, time
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9223"
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\09_Usados_video\flow\piezas\05-kindle-con-polvo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Los 4 UUIDs únicos detectados en la página
CLIP_UUIDS = [
    "bfea487e-4ecf-48bc-a3b0-83697ecd19c3",
    "4b8ed218-d2c7-40e5-ad33-d76cc74107c1",
    "2f2edca7-aed2-4da8-af08-0ae4dcbb1125",
    "10ccfbc1-8a43-4f8d-86cd-24726005fa59",
]

def fetch_via_browser(page, name: str, path: Path):
    """Descarga usando fetch del navegador con cookies de sesión."""
    url = f"https://labs.google/fx/api/trpc/media.getMediaUrlRedirect?name={name}"
    print(f"  Fetching {name[:20]}... ", end="", flush=True)
    result = page.evaluate("""
        async (url) => {
            try {
                const r = await fetch(url, {credentials: 'include'});
                if (!r.ok) return {error: r.status + ' ' + r.statusText, url: r.url};
                const contentType = r.headers.get('content-type') || '';
                const buf = await r.arrayBuffer();
                const bytes = new Uint8Array(buf);
                let b = '';
                // chunk-based btoa to avoid stack overflow on large files
                const CHUNK = 8192;
                for (let i = 0; i < bytes.length; i += CHUNK) {
                    b += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
                }
                return {b64: btoa(b), size: buf.byteLength, ct: contentType, finalUrl: r.url};
            } catch(e) {
                return {error: e.message};
            }
        }
    """, url)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        return False

    size_bytes = result.get("size", 0)
    ct = result.get("ct", "")
    final_url = result.get("finalUrl", "")
    print(f"{size_bytes//1024}KB ct={ct[:30]} url={final_url[:50]}")

    if size_bytes < 1000:
        print(f"  [SKIP] Archivo demasiado pequeño ({size_bytes}B)")
        return False

    path.write_bytes(base64.b64decode(result["b64"]))
    print(f"  Guardado: {path.name}")
    return True

def run():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL, timeout=15000)
        b.contexts[0].grant_permissions(["clipboard-read", "clipboard-write"])
        all_pages = [pg for c in b.contexts for pg in c.pages]
        flow = next(pg for pg in all_pages if "labs.google" in pg.url)
        flow.bring_to_front()

        for i, uuid in enumerate(CLIP_UUIDS, 1):
            cp = OUT_DIR / f"clip{i}.mp4"
            if cp.exists() and cp.stat().st_size > 50000:
                print(f"clip{i}: ya existe ({cp.stat().st_size//1024}KB)")
                continue
            print(f"\nclip{i}:")
            ok = fetch_via_browser(flow, uuid, cp)
            if not ok:
                # Intentar URL completa redirigida — a veces son .mp4 directas
                print(f"  Fallback: buscando en las peticiones de red recientes...")

        print("\n=== RESUMEN ===")
        for i in range(1, 6):
            cp = OUT_DIR / f"clip{i}.mp4"
            exists = cp.exists()
            size = cp.stat().st_size if exists else 0
            print(f"  clip{i}: {'✓' if exists and size>50000 else '✗'} ({size//1024}KB)")

if __name__ == "__main__":
    run()

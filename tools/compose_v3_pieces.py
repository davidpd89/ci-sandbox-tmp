"""
Procesa las imagenes _v3 y produce los assets listos para publicar:
- Redimensiona a 1080x1350 (4:5 Instagram estandar) recortando centrado
- Anade marca de agua "davidportodiaz.com" arriba a la derecha (texto blanco con
  sombra oscura discreta, no un parche rectangular)
- Genera un slide de CTA final para carruseles

Uso:
    python compose_v3_pieces.py         -> procesa las 10 _v3 estandar
    python compose_v3_pieces.py img1.png img2.png  -> archivos especificos
"""
import sys
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")

IMAGES_DIR = Path(r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\Imagenes david")
OUT_DIR = Path(r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\Piezas_listas")
OUT_DIR.mkdir(exist_ok=True)

# Formato estandar Instagram feed (4:5 portrait)
TARGET_W, TARGET_H = 1080, 1350

# Marca de agua
WATERMARK_TEXT = "davidportodiaz.com"
WATERMARK_FONT_SIZE = 28
WATERMARK_MARGIN = 24  # px desde el borde

ORIGINALS_V3 = [
    "1000106600_v3.png",
    "1000106601_v3.png",
    "1000106602_v3.png",
    "1000106603_v3.png",
    "1000106604_v3.png",
    "1000106605_v3.png",
    "1000106606_v3.png",
    "1000106608_v3.png",
    "1000106609_v3.png",
    "1000106610_v3.png",
]


def load_font(size: int):
    """Carga una fuente del sistema o fallback a la default de PIL."""
    candidates = [
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def resize_crop_center(img: Image.Image, w: int, h: int) -> Image.Image:
    """Redimensiona y recorta centrado al ratio exacto sin deformar."""
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    tgt_ratio = w / h
    if src_ratio > tgt_ratio:
        # mas ancho que el target: ajustar por alto y recortar lados
        new_h = h
        new_w = int(src_w * h / src_h)
    else:
        # mas alto que el target: ajustar por ancho y recortar arriba/abajo
        new_w = w
        new_h = int(src_h * w / src_w)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def add_watermark_topright(img: Image.Image, text: str, font_size: int = WATERMARK_FONT_SIZE) -> Image.Image:
    """
    Anade el texto de marca de agua arriba a la derecha con sombra difusa.
    No usa un parche opaco — solo texto con sombra para que sea legible sobre
    cualquier fondo sin parecer un elemento extrano pegado.
    """
    img = img.convert("RGBA")
    font = load_font(font_size)

    # --- Capa de sombra (blur) ---
    shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    # Medir texto
    bbox = shadow_draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = img.width - tw - WATERMARK_MARGIN
    y = WATERMARK_MARGIN
    # Sombra difusa: dibujar varias veces con offset y desenfoque
    for ox, oy in [(-2, -2), (2, 2), (-2, 2), (2, -2), (0, 2)]:
        shadow_draw.text((x + ox, y + oy), text, font=font, fill=(0, 0, 0, 160))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=2))

    # --- Capa de texto blanco ---
    text_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    text_draw.text((x, y), text, font=font, fill=(255, 255, 255, 220))

    # Componer
    result = Image.alpha_composite(img, shadow_layer)
    result = Image.alpha_composite(result, text_layer)
    return result.convert("RGB")


def make_cta_slide(w: int = TARGET_W, h: int = TARGET_H) -> Image.Image:
    """
    Crea un slide final de CTA para carruseles.
    Fondo oscuro con gradiente sutil + texto de accion.
    """
    # Fondo oscuro cargado (no negro puro)
    slide = Image.new("RGB", (w, h), (18, 16, 22))

    draw = ImageDraw.Draw(slide)

    # Franja decorativa superior
    for i in range(6):
        alpha = int(40 * (1 - i / 6))
        draw.line([(0, i), (w, i)], fill=(200, 160, 100, alpha))

    font_big = load_font(52)
    font_small = load_font(30)
    font_brand = load_font(24)

    # Emojis + CTAs
    ctas = [
        ("Guarda", "para releerlo despues"),
        ("Comparte", "con quien lo entiende"),
        ("Comenta", "tu version aqui abajo"),
        ("Like", "si te ha pasado esto"),
    ]

    # Calcula posicion vertical centrada
    line_h = 90
    total_h = len(ctas) * line_h + 60  # 60 para espacio extra
    start_y = (h - total_h) // 2 - 30

    for i, (action, complement) in enumerate(ctas):
        y = start_y + i * line_h
        # Icono/accion en dorado
        draw.text(
            (w // 2, y),
            action,
            font=font_big,
            fill=(220, 180, 100),
            anchor="mm",
        )
        draw.text(
            (w // 2, y + 50),
            complement,
            font=font_small,
            fill=(200, 200, 200),
            anchor="mm",
        )

    # Linea separadora
    sep_y = start_y + len(ctas) * line_h + 20
    draw.line([(w // 4, sep_y), (3 * w // 4, sep_y)], fill=(100, 80, 60), width=1)

    # Marca
    draw.text(
        (w // 2, sep_y + 35),
        WATERMARK_TEXT,
        font=font_brand,
        fill=(160, 130, 90),
        anchor="mm",
    )

    return slide


def process_image(src: Path, out_name: str = None) -> Path:
    """Redimensiona, recorta y anade marca de agua. Devuelve la ruta de salida."""
    img = Image.open(src).convert("RGB")
    img = resize_crop_center(img, TARGET_W, TARGET_H)
    img = add_watermark_topright(img, WATERMARK_TEXT)
    out = OUT_DIR / (out_name or src.name)
    img.save(out, "PNG", optimize=True)
    print(f"  OK: {out.name}", flush=True)
    return out


def main():
    if len(sys.argv) > 1:
        paths = [Path(a) for a in sys.argv[1:]]
    else:
        paths = [IMAGES_DIR / name for name in ORIGINALS_V3]

    print(f"Procesando {len(paths)} imagen(es) -> {OUT_DIR}", flush=True)
    results = []
    for p in paths:
        if not p.exists():
            print(f"  SKIP: {p.name} no existe", flush=True)
            continue
        results.append(process_image(p))

    # Generar slide CTA
    cta_path = OUT_DIR / "cta_final.png"
    make_cta_slide().save(cta_path, "PNG")
    print(f"  OK: {cta_path.name} (CTA slide)", flush=True)

    print(f"\nTotal: {len(results)} imagenes + 1 CTA -> {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()

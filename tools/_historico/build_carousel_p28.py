"""
Carrusel P28 — 5 escritores que consuelan.
Diseño editorial: fondo pergamino, foto circular, cita tipografica.
"""
import math, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).parent.parent
FONT_PATH = BASE / "tools/reel_template/fonts/PlayfairDisplay.ttf"
OUT_DIR = BASE / "09_Usados_video/meta/piezas/28-citas-escritores"
IMG_DIR = OUT_DIR

W, H = 1080, 1350  # 4:5
BG = (244, 237, 224)        # pergamino calido
DARK = (40, 30, 20)         # tinta oscura
ACCENT = (120, 80, 40)      # tono sepia/bronce
LIGHT_ACCENT = (180, 140, 90)
DIVIDER = (180, 160, 130)


def font(size, path=FONT_PATH):
    return ImageFont.truetype(str(path), size)


def draw_watermark(draw):
    f = font(22)
    text = "davidportodiaz.com"
    bb = draw.textbbox((0, 0), text, font=f)
    tw = bb[2] - bb[0]
    draw.text((W - tw - 28, 28), text, font=f, fill=(120, 100, 80, 180))


def draw_divider(draw, y, width=340):
    x0 = (W - width) // 2
    draw.line([(x0, y), (x0 + width, y)], fill=DIVIDER, width=2)


def circular_crop(img: Image.Image, size: int) -> Image.Image:
    img = img.convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([(0, 0), (size - 1, size - 1)], fill=255)
    # Apply mask
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    # Subtle sepia-ish toning for consistency
    r, g, b, a = out.split()
    out_rgb = Image.merge("RGB", (r, g, b))
    return out_rgb, a


def sepia(img: Image.Image) -> Image.Image:
    """Apply light sepia tone."""
    img = img.convert("RGB")
    r, g, b = img.split()
    r2 = r.point(lambda x: min(255, int(x * 1.05)))
    b2 = b.point(lambda x: int(x * 0.85))
    return Image.merge("RGB", (r2, g, b2))


def wrap_text(draw, text, font_obj, max_width):
    words = text.split()
    lines = []
    current = []
    for w in words:
        test = " ".join(current + [w])
        bb = draw.textbbox((0, 0), test, font=font_obj)
        if bb[2] - bb[0] > max_width and current:
            lines.append(" ".join(current))
            current = [w]
        else:
            current.append(w)
    if current:
        lines.append(" ".join(current))
    return lines


def make_writer_slide(
    writer_name: str,
    years: str,
    quote: str,
    photo_path: str | None,
    out_path: Path,
):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    photo_size = 360
    photo_y = 80

    if photo_path:
        try:
            photo_raw = Image.open(photo_path).convert("RGB")
            # Sepia tone for historical photos consistency
            photo_sepia = sepia(photo_raw)
            # Square crop first (center crop)
            pw, ph = photo_sepia.size
            side = min(pw, ph)
            left = (pw - side) // 2
            top = (ph - side) // 2
            photo_cropped = photo_sepia.crop((left, top, left + side, top + side))
            # Circular crop
            photo_circle = photo_cropped.convert("RGBA").resize(
                (photo_size, photo_size), Image.LANCZOS
            )
            mask = Image.new("L", (photo_size, photo_size), 0)
            ImageDraw.Draw(mask).ellipse(
                [(0, 0), (photo_size - 1, photo_size - 1)], fill=255
            )
            photo_final = Image.new("RGBA", (photo_size, photo_size), (*BG, 255))
            photo_final.paste(photo_circle, (0, 0), mask)
            # Subtle circle border
            border_img = Image.new("RGBA", (photo_size + 6, photo_size + 6), (0, 0, 0, 0))
            ImageDraw.Draw(border_img).ellipse(
                [(0, 0), (photo_size + 5, photo_size + 5)],
                outline=(*ACCENT, 200),
                width=3,
            )
            px = (W - photo_size) // 2
            img.paste(photo_final.convert("RGB"), (px, photo_y), mask)
            bx = (W - photo_size - 6) // 2
            img.paste(border_img, (bx, photo_y - 3), border_img)
            text_start_y = photo_y + photo_size + 32
        except Exception as e:
            print(f"  Foto error: {e}")
            text_start_y = photo_y + 40
    else:
        # No photo - big opening quote mark
        fq = font(200)
        draw.text((W // 2 - 60, -30), "“", font=fq, fill=(*ACCENT, 80))
        text_start_y = 160

    # Writer name
    f_name = font(64)
    bb = draw.textbbox((0, 0), writer_name, font=f_name)
    tw = bb[2] - bb[0]
    draw.text(((W - tw) // 2, text_start_y), writer_name, font=f_name, fill=DARK)
    text_start_y += bb[3] - bb[1] + 12

    # Years
    f_years = font(30)
    bb = draw.textbbox((0, 0), years, font=f_years)
    tw = bb[2] - bb[0]
    draw.text(((W - tw) // 2, text_start_y), years, font=f_years, fill=(*ACCENT,))
    text_start_y += bb[3] - bb[1] + 28

    # Divider
    draw_divider(draw, text_start_y)
    text_start_y += 28

    # Quote (wrapped)
    f_quote = font(38)
    quote_full = f"“{quote}”"
    lines = wrap_text(draw, quote_full, f_quote, W - 120)
    total_quote_h = sum(
        draw.textbbox((0, 0), ln, font=f_quote)[3] - draw.textbbox((0, 0), ln, font=f_quote)[1] + 14
        for ln in lines
    )
    # Center quote block vertically in remaining space
    remaining = H - 60 - text_start_y
    quote_y = text_start_y + max(0, (remaining - total_quote_h) // 2 - 20)
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=f_quote)
        tw = bb[2] - bb[0]
        lh = bb[3] - bb[1]
        draw.text(((W - tw) // 2, quote_y), line, font=f_quote, fill=DARK)
        quote_y += lh + 14

    draw_watermark(draw)
    img.save(str(out_path), quality=95)
    print(f"  {out_path.name} OK")


def make_title_slide(out_path: Path):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Large opening decoration
    f_deco = font(180)
    draw.text((W // 2 - 70, 60), "“", font=f_deco, fill=(*ACCENT, 90))

    # Title
    f_big = font(88)
    title1 = "5 escritores"
    bb = draw.textbbox((0, 0), title1, font=f_big)
    draw.text(((W - (bb[2] - bb[0])) // 2, 320), title1, font=f_big, fill=DARK)

    f_sub = font(56)
    title2 = "que consuelan"
    bb2 = draw.textbbox((0, 0), title2, font=f_sub)
    draw.text(((W - (bb2[2] - bb2[0])) // 2, 440), title2, font=f_sub, fill=ACCENT)

    draw_divider(draw, 560, 400)

    f_body = font(36)
    subtitle = "y la frase que te dejaron"
    bb3 = draw.textbbox((0, 0), subtitle, font=f_body)
    draw.text(((W - (bb3[2] - bb3[0])) // 2, 600), subtitle, font=f_body, fill=DARK)

    f_small = font(28)
    note = "Desliza →"
    bb4 = draw.textbbox((0, 0), note, font=f_small)
    draw.text(((W - (bb4[2] - bb4[0])) // 2, H - 100), note, font=f_small, fill=LIGHT_ACCENT)

    draw_watermark(draw)
    img.save(str(out_path), quality=95)
    print(f"  {out_path.name} OK")


def make_cta_slide(out_path: Path):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_big = font(80)
    q1 = "¿Qué escritor"
    bb = draw.textbbox((0, 0), q1, font=f_big)
    draw.text(((W - (bb[2] - bb[0])) // 2, 260), q1, font=f_big, fill=DARK)

    f_mid = font(60)
    q2 = "te salvó cuando"
    q3 = "más lo necesitabas?"
    for i, txt in enumerate([q2, q3]):
        bb = draw.textbbox((0, 0), txt, font=f_mid)
        draw.text(((W - (bb[2] - bb[0])) // 2, 370 + i * 78), txt, font=f_mid, fill=ACCENT)

    draw_divider(draw, 580, 400)

    f_cta = font(38)
    cta = "Cuéntamelo en comentarios"
    bb = draw.textbbox((0, 0), cta, font=f_cta)
    draw.text(((W - (bb[2] - bb[0])) // 2, 620), cta, font=f_cta, fill=DARK)

    f_web = font(32)
    web = "davidportodiaz.com"
    bb = draw.textbbox((0, 0), web, font=f_web)
    draw.text(((W - (bb[2] - bb[0])) // 2, H - 80), web, font=f_web, fill=ACCENT)

    img.save(str(out_path), quality=95)
    print(f"  {out_path.name} OK")


if __name__ == "__main__":
    print("=== Build P28 Carrusel Escritores ===")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    make_title_slide(OUT_DIR / "slide_00_titulo.png")

    writers = [
        {
            "name": "Franz Kafka",
            "years": "1883 – 1924",
            "photo": str(IMG_DIR / "img_kafka.png"),
            "quote": "Un libro debe ser el hacha que rompa el mar helado dentro de nosotros.",
            "out": "slide_01_kafka.png",
        },
        {
            "name": "Virginia Woolf",
            "years": "1882 – 1941",
            "photo": str(IMG_DIR / "img_woolf.png"),
            "quote": "Los libros son los espejos del alma.",
            "out": "slide_02_woolf.png",
        },
        {
            "name": "Julio Cortázar",
            "years": "1914 – 1984",
            "photo": str(IMG_DIR / "img_cortazar.png"),
            "quote": "Nada está perdido si se tiene el valor de proclamar que todo está perdido y empezar de nuevo.",
            "out": "slide_03_cortazar.png",
        },
        {
            "name": "Fiódor Dostoievski",
            "years": "1821 – 1881",
            "photo": str(IMG_DIR / "img_dostoievski.png"),
            "quote": "No hay nada más fantástico que la realidad.",
            "out": "slide_04_dostoievski.png",
        },
        {
            "name": "Jorge Luis Borges",
            "years": "1899 – 1986",
            "photo": None,
            "quote": "Que otros se jacten de las páginas que han escrito; a mí me enorgullecen las que he leído.",
            "out": "slide_05_borges.png",
        },
    ]

    for w in writers:
        make_writer_slide(
            writer_name=w["name"],
            years=w["years"],
            quote=w["quote"],
            photo_path=w["photo"],
            out_path=OUT_DIR / w["out"],
        )

    make_cta_slide(OUT_DIR / "slide_06_cta.png")

    print("\nP28 listo. Verificar visualmente antes de subir.")

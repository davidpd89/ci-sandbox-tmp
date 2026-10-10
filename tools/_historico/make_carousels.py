"""
Genera los 2 carruseles para Jul 24 manana y Jul 25 manana.

Carrusel A (Jul 24 mañana): 6 slides de citas de escritores celebres
  - Fondo oscuro elegante, tipografia clara, cita + autor
  - Escritores: Kafka, Borges, Woolf, Cortazar, Dostoevsky + CTA

Carrusel B (Jul 25 mañana): 4 slides "yo en teoria vs yo en realidad"
  - 4 slides narrativos usando las imagenes _v3 con texto superpuesto
  - Historia coherente que incita a compartir
"""
import sys
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")

W, H = 1080, 1350
OUT = Path(r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\Piezas_listas")
IMAGES = Path(r"C:\GIT\RRSS_DavidPorto\nuevo_flujo\Imagenes david")
OUT.mkdir(exist_ok=True)

BRAND = "davidportodiaz.com"


def load_font(size, bold=False):
    candidates_bold = [
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
    ]
    candidates_regular = [
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
    ]
    for path in (candidates_bold if bold else candidates_regular):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_text_centered(draw, text, y, w, font, color, line_spacing=8, max_w_ratio=0.85):
    """Dibuja texto centrado con wrapping automatico."""
    max_w = int(w * max_w_ratio)
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_w and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    total_h = 0
    line_heights = []
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        lh = bb[3] - bb[1]
        line_heights.append(lh)
        total_h += lh + line_spacing

    cur_y = y
    for i, line in enumerate(lines):
        bb = draw.textbbox((0, 0), line, font=font)
        lw = bb[2] - bb[0]
        draw.text(((w - lw) // 2, cur_y), line, font=font, fill=color)
        cur_y += line_heights[i] + line_spacing
    return cur_y  # siguiente linea y


def add_brand(draw, w, h, font_size=20):
    font = load_font(font_size)
    bb = draw.textbbox((0, 0), BRAND, font=font)
    bw = bb[2] - bb[0]
    draw.text(((w - bw) // 2, h - 48), BRAND, font=font, fill=(140, 120, 80))


# ─────────────────────────────────────────────────────────────
# CARRUSEL A — Citas de escritores celebres
# ─────────────────────────────────────────────────────────────

QUOTES = [
    {
        "author": "Franz Kafka",
        "years": "(1883-1924)",
        "quote": "Un libro debe ser el hacha que rompa el mar helado dentro de nosotros.",
        "accent": (180, 80, 60),   # rojo oxidado
        "bg": (12, 10, 16),
    },
    {
        "author": "Jorge Luis Borges",
        "years": "(1899-1986)",
        "quote": "Que otros se jacten de las paginas que han escrito; a mi me enorgullecen las que he leido.",
        "accent": (80, 140, 180),  # azul tranquilo
        "bg": (10, 14, 20),
    },
    {
        "author": "Virginia Woolf",
        "years": "(1882-1941)",
        "quote": "Uno no puede pensar bien, amar bien, dormir bien, si no ha comido bien. Y leer bien.",
        "accent": (160, 120, 180),  # lavanda
        "bg": (14, 10, 18),
    },
    {
        "author": "Julio Cortazar",
        "years": "(1914-1984)",
        "quote": "Andaba por la vida como si nada, pero por dentro habia un lector que lo veia todo diferente.",
        "accent": (80, 170, 120),  # verde suave
        "bg": (10, 16, 12),
    },
    {
        "author": "Fiodor Dostoievski",
        "years": "(1821-1881)",
        "quote": "El hombre es un misterio. Hay que descifrarlo, y si pasas toda la vida descifrando, no digas que has perdido el tiempo.",
        "accent": (200, 160, 80),  # ambar
        "bg": (16, 12, 8),
    },
]


def make_quote_card(q: dict, index: int) -> Path:
    img = Image.new("RGB", (W, H), q["bg"])
    draw = ImageDraw.Draw(img)

    # Franja decorativa superior con color de acento
    r, g, b = q["accent"]
    for i in range(4):
        alpha_f = 0.4 + 0.15 * i
        c = (int(r * alpha_f), int(g * alpha_f), int(b * alpha_f))
        draw.line([(0, i), (W, i)], fill=c)

    # Comillas decorativas grandes
    font_quote_mark = load_font(120, bold=True)
    draw.text((60, 60), "“", font=font_quote_mark, fill=(*q["accent"], 80))

    # Texto de la cita
    font_quote = load_font(40)
    y = draw_text_centered(
        draw,
        q["quote"],
        y=210,
        w=W,
        font=font_quote,
        color=(235, 230, 220),
        line_spacing=14,
        max_w_ratio=0.82,
    )

    # Linea separadora
    y += 48
    draw.line([(W // 4, y), (3 * W // 4, y)], fill=(*q["accent"],), width=1)
    y += 36

    # Nombre del autor
    font_author = load_font(36, bold=True)
    draw_text_centered(draw, f"-- {q['author']}", y=y, w=W, font=font_author, color=q["accent"])

    # Anos del autor
    font_years = load_font(24)
    bb_years = draw.textbbox((0, 0), q["years"], font=font_years)
    yw = bb_years[2] - bb_years[0]
    draw.text(((W - yw) // 2, y + 52), q["years"], font=font_years, fill=(160, 155, 148))

    # Numero de slide
    font_num = load_font(22)
    draw.text((W - 60, H - 90), f"{index}/5", font=font_num, fill=(100, 95, 90))

    # Marca
    add_brand(draw, W, H)

    out_path = OUT / f"quote_{index:02d}_{q['author'].split()[0].lower()}.png"
    img.save(out_path, "PNG")
    print(f"  Quote card: {out_path.name}", flush=True)
    return out_path


# Slide de apertura del carrusel (slide 0)
def make_quote_intro() -> Path:
    img = Image.new("RGB", (W, H), (14, 12, 18))
    draw = ImageDraw.Draw(img)

    # Lineas decorativas
    for i in range(3):
        draw.line([(W // 6, 200 + i * 4), (5 * W // 6, 200 + i * 4)], fill=(180, 140, 70), width=1)

    font_big = load_font(52, bold=True)
    font_sub = load_font(30)

    draw_text_centered(draw, "Frases que te cambian", y=260, w=W, font=font_big, color=(235, 210, 140))
    draw_text_centered(draw, "Los escritores que dejan huella no escriben para ser recordados.", y=400, w=W, font=font_sub, color=(195, 188, 178), line_spacing=12)
    draw_text_centered(draw, "Escriben para romperte algo por dentro.", y=490, w=W, font=font_sub, color=(195, 188, 178))

    for i in range(3):
        draw.line([(W // 6, H - 220 + i * 4), (5 * W // 6, H - 220 + i * 4)], fill=(180, 140, 70), width=1)

    draw_text_centered(draw, "Desliza para elegir el tuyo.", y=H - 180, w=W, font=load_font(28), color=(170, 145, 95))
    add_brand(draw, W, H)

    out_path = OUT / "quote_00_intro.png"
    img.save(out_path, "PNG")
    print(f"  Quote intro: {out_path.name}", flush=True)
    return out_path


# CTA slide
def make_cta_slide_quotes() -> Path:
    img = Image.new("RGB", (W, H), (14, 12, 18))
    draw = ImageDraw.Draw(img)

    font_big = load_font(54, bold=True)
    font_mid = load_font(32)
    font_small = load_font(26)

    draw_text_centered(draw, "Cual es la tuya?", y=200, w=W, font=font_big, color=(220, 180, 100))
    draw_text_centered(draw, "Comenta el nombre del autor que mas te ha roto.", y=320, w=W, font=font_mid, color=(200, 195, 185), line_spacing=10)

    items = [
        ("Guarda", "este carrusel para volver a ellas"),
        ("Comparte", "con alguien que las necesita"),
        ("Comenta", "tu frase favorita de las 5"),
        ("Like", "si alguna te ha tocado de verdad"),
    ]
    y = 500
    for action, rest in items:
        font_action = load_font(36, bold=True)
        font_rest = load_font(26)
        draw_text_centered(draw, action, y=y, w=W, font=font_action, color=(220, 180, 100))
        draw_text_centered(draw, rest, y=y + 46, w=W, font=font_rest, color=(185, 180, 170))
        y += 100

    add_brand(draw, W, H)
    out_path = OUT / "quote_cta.png"
    img.save(out_path, "PNG")
    print(f"  Quote CTA: {out_path.name}", flush=True)
    return out_path


print("=== Carrusel A: Citas de escritores ===")
quote_slides = []
quote_slides.append(make_quote_intro())
for i, q in enumerate(QUOTES, 1):
    quote_slides.append(make_quote_card(q, i))
quote_slides.append(make_cta_slide_quotes())
print(f"  Total slides: {len(quote_slides)}")


# ─────────────────────────────────────────────────────────────
# CARRUSEL B — "Yo en teoria vs yo en realidad"
# ─────────────────────────────────────────────────────────────

def add_text_overlay(img: Image.Image, lines: list, y_start: int,
                     font_size=42, color=(255,255,255), bold=False,
                     bg_alpha=170, line_spacing=10) -> Image.Image:
    """
    Superpone texto con fondo semitransparente sobre la imagen.
    """
    img = img.copy().convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = load_font(font_size, bold=bold)

    # Medir el bloque de texto
    max_line_w = 0
    total_h = 0
    measures = []
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        lw = bb[2] - bb[0]
        lh = bb[3] - bb[1]
        measures.append((lw, lh))
        max_line_w = max(max_line_w, lw)
        total_h += lh + line_spacing

    pad_x, pad_y = 36, 24
    box_x = (W - max_line_w) // 2 - pad_x
    box_y = y_start - pad_y
    box_w = max_line_w + pad_x * 2
    box_h = total_h + pad_y * 2

    # Fondo semitransparente redondeado (aprox con rectangulo)
    draw.rectangle([box_x, box_y, box_x + box_w, box_y + box_h],
                   fill=(0, 0, 0, bg_alpha))

    # Texto
    cur_y = y_start
    for i, line in enumerate(lines):
        lw, lh = measures[i]
        x = (W - lw) // 2
        draw.text((x, cur_y), line, font=font, fill=(*color, 255))
        cur_y += lh + line_spacing

    result = Image.alpha_composite(img, overlay)
    return result.convert("RGB")


def resize_crop_center(img, w, h):
    src_w, src_h = img.size
    if src_w / src_h > w / h:
        new_h = h
        new_w = int(src_w * h / src_h)
    else:
        new_w = w
        new_h = int(src_h * w / src_w)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


print("\n=== Carrusel B: Yo en teoria vs yo en realidad ===")

# Slide 1 — Portada con pregunta (fondo oscuro diseñado)
img1 = Image.new("RGB", (W, H), (16, 14, 22))
d1 = ImageDraw.Draw(img1)
draw_text_centered(d1, "La lectora", y=220, w=W, font=load_font(64, bold=True), color=(220, 190, 110))
draw_text_centered(d1, "que soy", y=310, w=W, font=load_font(64, bold=True), color=(220, 190, 110))
draw_text_centered(d1, "en teoria", y=400, w=W, font=load_font(64, bold=True), color=(220, 190, 110))
draw_text_centered(d1, "vs", y=530, w=W, font=load_font(40), color=(160, 155, 148))
draw_text_centered(d1, "la que soy", y=620, w=W, font=load_font(64, bold=True), color=(180, 120, 200))
draw_text_centered(d1, "en realidad", y=710, w=W, font=load_font(64, bold=True), color=(180, 120, 200))
draw_text_centered(d1, "Desliza. Te veo.", y=900, w=W, font=load_font(30), color=(170, 165, 155))
add_brand(d1, W, H)
slide_dualidad_portada = OUT / "dualidad_00_portada.png"
img1.save(slide_dualidad_portada)
print(f"  Slide portada: {slide_dualidad_portada.name}")

# Slide 2 — "Yo en teoria" (imagen orden/elegancia con texto)
img2 = Image.open(IMAGES / "1000106606_v3.png").convert("RGB")
img2 = resize_crop_center(img2, W, H)
# Oscurecer ligeramente la imagen para que el texto sea legible
darkened = Image.new("RGB", (W, H), (0, 0, 0))
img2 = Image.blend(img2, darkened, 0.15)
img2 = add_text_overlay(img2, [
    "Yo en teoria:",
], y_start=60, font_size=48, color=(220, 190, 110), bold=True, bg_alpha=140)
img2 = add_text_overlay(img2, [
    "Acabare el libro en 3 dias.",
    "Leer solo una hora al dia.",
    "Nada de quedarse hasta las 2am.",
    "Seguire el orden de la pila.",
], y_start=160, font_size=32, color=(240, 235, 220), bold=False, bg_alpha=120, line_spacing=14)
img2 = add_text_overlay(img2, [
    "(Desliza)",
], y_start=H - 120, font_size=26, color=(200, 190, 160), bg_alpha=100)
d2 = ImageDraw.Draw(img2)
add_brand(d2, W, H, font_size=22)
slide_teoria = OUT / "dualidad_01_teoria.png"
img2.save(slide_teoria)
print(f"  Slide teoria: {slide_teoria.name}")

# Slide 3 — "Yo en realidad" (imagen caotica/humoristica con texto)
img3 = Image.open(IMAGES / "1000106602_v3.png").convert("RGB")
img3 = resize_crop_center(img3, W, H)
darkened3 = Image.new("RGB", (W, H), (0, 0, 0))
img3 = Image.blend(img3, darkened3, 0.12)
img3 = add_text_overlay(img3, [
    "Yo en realidad:",
], y_start=60, font_size=48, color=(200, 120, 200), bold=True, bg_alpha=140)
img3 = add_text_overlay(img3, [
    "Las 3am. Tercer capitulo. No puedo parar.",
    "Me salte 2 de la pila. Sin remordimiento.",
    "Compre otro mientras aun leo este.",
    "Plan del sabado: leer. Resultado: leer.",
], y_start=160, font_size=32, color=(240, 235, 220), bold=False, bg_alpha=120, line_spacing=14)
img3 = add_text_overlay(img3, [
    "(Desliza)",
], y_start=H - 120, font_size=26, color=(200, 190, 160), bg_alpha=100)
d3 = ImageDraw.Draw(img3)
add_brand(d3, W, H, font_size=22)
slide_realidad = OUT / "dualidad_02_realidad.png"
img3.save(slide_realidad)
print(f"  Slide realidad: {slide_realidad.name}")

# Slide 4 — Giro final con imagen 1000106600_v3 (2-panel comic) + revelacion
img4 = Image.open(IMAGES / "1000106600_v3.png").convert("RGB")
img4 = resize_crop_center(img4, W, H)
darkened4 = Image.new("RGB", (W, H), (0, 0, 0))
img4 = Image.blend(img4, darkened4, 0.2)
img4 = add_text_overlay(img4, [
    "La verdad:",
], y_start=50, font_size=52, color=(220, 180, 100), bold=True, bg_alpha=150)
img4 = add_text_overlay(img4, [
    "No hay lectora 'en teoria'.",
    "Solo hay lectoras que aun",
    "no se han perdonado lo de la teoria.",
], y_start=150, font_size=36, color=(240, 235, 220), bold=False, bg_alpha=130, line_spacing=16)
img4 = add_text_overlay(img4, [
    "Comenta si eres de las segundas 👇",
], y_start=H - 200, font_size=30, color=(220, 200, 140), bg_alpha=140)
d4 = ImageDraw.Draw(img4)
add_brand(d4, W, H, font_size=22)
slide_verdad = OUT / "dualidad_03_verdad.png"
img4.save(slide_verdad)
print(f"  Slide verdad: {slide_verdad.name}")

# Slide 5 — CTA final
img5 = Image.new("RGB", (W, H), (16, 14, 22))
d5 = ImageDraw.Draw(img5)
draw_text_centered(d5, "Si te has visto aqui:", y=160, w=W, font=load_font(44, bold=True), color=(220, 190, 110))
items_b = [
    ("Guarda", "para enviarselo a tu complice"),
    ("Comenta", "tu realidad en una frase"),
    ("Comparte", "con quien tambien miente en teoria"),
    ("Like", "si la realidad gana siempre"),
]
y5 = 320
for action, rest in items_b:
    draw_text_centered(d5, action, y=y5, w=W, font=load_font(38, bold=True), color=(200, 160, 220))
    draw_text_centered(d5, rest, y=y5 + 46, w=W, font=load_font(26), color=(185, 180, 170))
    y5 += 100
add_brand(d5, W, H)
slide_cta_b = OUT / "dualidad_cta.png"
img5.save(slide_cta_b)
print(f"  Slide CTA: {slide_cta_b.name}")

# ─────────────────────────────────────────────────────────────
# Resumen
# ─────────────────────────────────────────────────────────────
print("\n=== RESUMEN ===")
print("Carrusel A (escritores) slides:")
for s in quote_slides:
    print(f"  {s.name}")
print("Carrusel B (dualidad) slides:")
for s in [slide_dualidad_portada, slide_teoria, slide_realidad, slide_verdad, slide_cta_b]:
    print(f"  {s.name}")
print("\nDone.")

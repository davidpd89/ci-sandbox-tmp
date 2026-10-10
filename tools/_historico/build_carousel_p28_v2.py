# -*- coding: utf-8 -*-
"""
Carrusel P28 v2: La imagen #601 (lector 4dias/3semanas/una noche) como portada.
Slides 2-6: 5 autores con citas sobre velocidad/ritmo lector.
Diseño: fondo negro editorial con tipografía blanca. Contraste con #601 (foto casual/moderna).
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess, imageio_ffmpeg

BASE = Path(__file__).parent.parent
FONT_PATH = BASE / "tools/reel_template/fonts/PlayfairDisplay.ttf"
OUT_DIR = BASE / "09_Usados_video/meta/piezas/28-citas-escritores"
ORIG_IMG = BASE / "nuevo_flujo/Imagenes david/1000106601_v3.png"
FF = imageio_ffmpeg.get_ffmpeg_exe()

W, H = 1080, 1350
BG_DARK = (12, 12, 14)
BG_CARD = (20, 20, 24)
GOLD = (212, 175, 95)
WHITE = (245, 242, 235)
GREY = (160, 155, 145)
ACCENT = (180, 140, 70)


def font(size):
    return ImageFont.truetype(str(FONT_PATH), size)


def draw_watermark(draw):
    f = font(22)
    text = "davidportodiaz.com"
    bb = draw.textbbox((0, 0), text, font=f)
    tw = bb[2] - bb[0]
    draw.text((W - tw - 24, 24), text, font=f, fill=(*GREY, 180))


def wrap_centered(draw, text, font_obj, max_w, x_center, y_start, line_gap=12):
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        bb = draw.textbbox((0, 0), test, font=font_obj)
        if bb[2] - bb[0] > max_w and cur:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))

    y = y_start
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font_obj)
        lw = bb[2] - bb[0]
        lh = bb[3] - bb[1]
        draw.text((x_center - lw // 2, y), line, font=font_obj, fill=WHITE)
        y += lh + line_gap
    return y


def make_slide_portada():
    """Slide 0: imagen #601 con watermark y titulo superpuesto."""
    out = OUT_DIR / "slide_00_portada.png"
    font_file = str(FONT_PATH).replace("\\", "/").replace(":", "\\:")
    filt = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={W}:{H},"
        # oscurecer un poco la parte inferior para el texto
        "vignette=PI/4"
    )
    r = subprocess.run(
        [FF, "-y", "-i", str(ORIG_IMG), "-vf", filt, "-frames:v", "1", str(out)],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])

    # Superponer texto con PIL
    img = Image.open(str(out)).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Overlay oscuro en parte inferior
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    for i in range(300):
        alpha = int(180 * i / 300)
        ov_draw.rectangle([(0, H - 300 + i), (W, H - 300 + i + 1)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    f_title = font(64)
    title = "¿En cuál de los tres"
    title2 = "estás ahora mismo?"
    for i, t in enumerate([title, title2]):
        bb = draw.textbbox((0, 0), t, font=f_title)
        x = (W - (bb[2] - bb[0])) // 2
        draw.text((x, H - 260 + i * 80), t, font=f_title, fill=WHITE)

    f_sub = font(28)
    sub = "Desliza →"
    bb = draw.textbbox((0, 0), sub, font=f_sub)
    draw.text(((W - (bb[2] - bb[0])) // 2, H - 80), sub, font=f_sub, fill=(*GOLD,))
    draw_watermark(draw)

    img.save(str(out), quality=95)
    print(f"  slide_00_portada.png OK")


def make_author_slide(name, years, quote, trivia, out_name):
    """Slide editorial oscuro: nombre del autor + cita + dato curiosio."""
    out = OUT_DIR / out_name
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Barra lateral decorativa
    draw.rectangle([(0, 0), (6, H)], fill=GOLD)

    y = 90
    # Comilla decorativa grande
    f_quote_deco = font(160)
    draw.text((50, y - 30), "“", font=f_quote_deco, fill=(*GOLD, 60))

    # Nombre del autor
    y = 180
    f_name = font(72)
    bb = draw.textbbox((0, 0), name, font=f_name)
    draw.text(((W - (bb[2] - bb[0])) // 2, y), name, font=f_name, fill=WHITE)
    y += bb[3] - bb[1] + 10

    # Años
    f_years = font(28)
    bb = draw.textbbox((0, 0), years, font=f_years)
    draw.text(((W - (bb[2] - bb[0])) // 2, y), years, font=f_years, fill=(*GOLD,))
    y += bb[3] - bb[1] + 50

    # Línea divisoria
    draw.line([(80, y), (W - 80, y)], fill=(*GOLD, 120), width=1)
    y += 40

    # Cita
    f_cita = font(42)
    y = wrap_centered(draw, f'"{quote}"', f_cita, W - 140, W // 2, y, line_gap=16)
    y += 50

    # Línea divisoria inferior
    draw.line([(80, y), (W - 80, y)], fill=(*GREY, 80), width=1)
    y += 40

    # Trivia/dato curioso
    f_trivia = font(30)
    y = wrap_centered(draw, trivia, f_trivia, W - 160, W // 2, y, line_gap=10)

    draw_watermark(draw)
    img.save(str(out), quality=95)
    print(f"  {out_name} OK")


def make_cta_slide():
    """Slide final: pregunta que invita a comentar."""
    out = OUT_DIR / "slide_06_cta_v2.png"
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (6, H)], fill=GOLD)

    y = H // 4
    f_q1 = font(80)
    q1 = "¿Cuál fue el último"
    bb = draw.textbbox((0, 0), q1, font=f_q1)
    draw.text(((W - (bb[2] - bb[0])) // 2, y), q1, font=f_q1, fill=WHITE)
    y += bb[3] - bb[1] + 20

    f_q2 = font(64)
    for line in ["libro que terminaste", "en una noche?"]:
        bb = draw.textbbox((0, 0), line, font=f_q2)
        draw.text(((W - (bb[2] - bb[0])) // 2, y), line, font=f_q2, fill=(*GOLD,))
        y += bb[3] - bb[1] + 16

    y += 50
    draw.line([(100, y), (W - 100, y)], fill=(*GOLD, 100), width=1)
    y += 40

    f_cta = font(36)
    cta = "Cuéntamelo en comentarios"
    bb = draw.textbbox((0, 0), cta, font=f_cta)
    draw.text(((W - (bb[2] - bb[0])) // 2, y), cta, font=f_cta, fill=WHITE)
    y += bb[3] - bb[1] + 20

    f_sub = font(28)
    sub = "(y cuántas horas dormiste después)"
    bb = draw.textbbox((0, 0), sub, font=f_sub)
    draw.text(((W - (bb[2] - bb[0])) // 2, y), sub, font=f_sub, fill=(*GREY,))

    f_web = font(28)
    web = "davidportodiaz.com"
    bb = draw.textbbox((0, 0), web, font=f_web)
    draw.text(((W - (bb[2] - bb[0])) // 2, H - 70), web, font=f_web, fill=(*GOLD,))

    img.save(str(out), quality=95)
    print("  slide_06_cta_v2.png OK")


if __name__ == "__main__":
    print("=== Carrusel P28 v2 — Lectores y sus velocidades ===")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    make_slide_portada()

    authors = [
        {
            "name": "Franz Kafka",
            "years": "1883 – 1924",
            "quote": "Un libro debe ser el hacha que rompa el mar helado dentro de nosotros.",
            "trivia": "Kafka escribía de madrugada, después de trabajar. Solo unas pocas horas. Nunca las suficientes.",
            "out": "slide_01_kafka.png",
        },
        {
            "name": "Virginia Woolf",
            "years": "1882 – 1941",
            "quote": "Los libros son los espejos del alma.",
            "trivia": "Leía y escribía en posición vertical, de pie, con un pupitre especial. Nunca sentada.",
            "out": "slide_02_woolf.png",
        },
        {
            "name": "Julio Cortázar",
            "years": "1914 – 1984",
            "quote": "Un libro se termina cuando el personaje ya no te necesita. No antes.",
            "trivia": "Cortázar leía en varios idiomas al mismo tiempo. Cambiaba de libro según el humor del día.",
            "out": "slide_03_cortazar.png",
        },
        {
            "name": "Fiódor Dostoievski",
            "years": "1821 – 1881",
            "quote": "No hay nada más fantástico que la realidad.",
            "trivia": "Dictaba sus novelas en voz alta. Escribía mientras hablaba. A veces no dormía en tres días.",
            "out": "slide_04_dostoievski.png",
        },
        {
            "name": "Jorge Luis Borges",
            "years": "1899 – 1986",
            "quote": "Que otros se jacten de las páginas que han escrito; a mí me enorgullecen las que he leído.",
            "trivia": "Cuando perdió la vista, siguió leyendo por memoria. Recitaba de memoria poemas completos en inglés.",
            "out": "slide_05_borges.png",
        },
    ]

    for a in authors:
        make_author_slide(a["name"], a["years"], a["quote"], a["trivia"], a["out"])

    make_cta_slide()

    print("\nP28 v2 listo. Revisar antes de subir.")

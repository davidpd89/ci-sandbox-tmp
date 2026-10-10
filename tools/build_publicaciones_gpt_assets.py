"""Regenera las laminas editoriales que no eran legibles en movil.

<<<<<<< HEAD
Las piezas parten de texto publicado en autorademodiaz.com. No usan
=======
Las piezas parten de texto publicado en davidportodiaz.com. No usan
>>>>>>> origin/research/public-reuse-parent
generacion de imagenes ni material de terceros.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
NAVY = "#10233f"
BLUE = "#1768ac"
GOLD = "#d4a72c"
INK = "#17202a"
MUTED = "#52606d"
WHITE = "#ffffff"
PALE = "#eef5fb"


def font(size, bold=False, serif=False):
    if serif:
        name = "georgiab.ttf" if bold else "georgia.ttf"
    else:
        name = "seguisb.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def wrap(draw, text, fnt, width):
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if draw.textlength(candidate, font=fnt) <= width:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def text_block(draw, xy, text, fnt, fill, width, spacing=18):
    x, y = xy
    for line in wrap(draw, text, fnt, width):
        draw.text((x, y), line, font=fnt, fill=fill)
        bbox = draw.textbbox((x, y), line or "Ag", font=fnt)
        y += bbox[3] - bbox[1] + spacing
    return y


<<<<<<< HEAD
def canvas(size=(1080, 1350), label="AUTORA DEMO DÍAZ"):
=======
def canvas(size=(1080, 1350), label="DAVID PORTO DÍAZ"):
>>>>>>> origin/research/public-reuse-parent
    im = Image.new("RGB", size, WHITE)
    d = ImageDraw.Draw(im)
    w, h = size
    d.rectangle((0, 0, w, 18), fill=GOLD)
    d.rectangle((0, 18, 34, h), fill=BLUE)
    d.text((76, 62), label, font=font(25, bold=True), fill=BLUE)
    d.line((76, 112, w - 76, 112), fill="#ccd7e2", width=2)
    return im, d


def footer(d, size, index, section):
    w, h = size
    d.line((76, h - 128, w - 76, h - 128), fill="#ccd7e2", width=2)
    d.text((76, h - 98), section, font=font(24, bold=True), fill=MUTED)
    right = str(index)
    d.text((w - 76 - d.textlength(right, font=font(28, bold=True)), h - 100), right,
           font=font(28, bold=True), fill=BLUE)


def quote_card(path, eyebrow, title, quote, index):
    size = (1080, 1350)
    im, d = canvas(size)
    d.text((76, 172), eyebrow.upper(), font=font(24, bold=True), fill=GOLD)
    y = text_block(d, (76, 225), title, font(58, bold=True, serif=True), NAVY, 900, 12)
    d.rectangle((76, y + 34, 1004, y + 42), fill=BLUE)
    y = text_block(d, (112, y + 102), quote, font(39, serif=True), INK, 820, 22)
    d.text((112, min(y + 38, 1110)), "Las manecillas del recuerdo", font=font(27, bold=True), fill=BLUE)
    footer(d, size, index, "Tres fragmentos · sin destripes")
    im.save(path, quality=95)


def info_card(path, eyebrow, title, bullets, index, section):
    size = (1080, 1350)
    im, d = canvas(size)
    d.text((76, 172), eyebrow.upper(), font=font(24, bold=True), fill=GOLD)
    y = text_block(d, (76, 225), title, font(58, bold=True, serif=True), NAVY, 900, 10) + 40
    for bullet in bullets:
        d.ellipse((78, y + 11, 96, y + 29), fill=GOLD)
        y = text_block(d, (124, y), bullet, font(35), INK, 825, 13) + 34
    footer(d, size, index, section)
    im.save(path, quality=95)


def compare_card(path):
    size = (1080, 1350)
    im, d = canvas(size)
    d.text((76, 172), "DOS PUERTAS DE ENTRADA", font=font(24, bold=True), fill=GOLD)
    text_block(d, (76, 225), "¿De dónde viene\nel protagonista?", font(57, bold=True, serif=True), NAVY, 900, 8)
    cards = [
        (76, 510, 508, 1050, "PORTAL FANTASY", "Empieza en nuestro mundo", "Cruza a otro mundo y debe aprender sus reglas."),
        (550, 510, 1004, 1050, "FANTASÍA ÉPICA", "Ya pertenece al mundo fantástico", "El conflicto nace dentro de una realidad que ya conoce."),
    ]
    for x1, y1, x2, y2, head, lead, body in cards:
        d.rounded_rectangle((x1, y1, x2, y2), radius=8, fill=PALE, outline="#bfd0df", width=3)
        d.rectangle((x1, y1, x2, y1 + 12), fill=BLUE)
        text_block(d, (x1 + 34, y1 + 52), head, font(24, bold=True), GOLD, x2 - x1 - 68, 8)
        y = text_block(d, (x1 + 34, y1 + 130), lead, font(38, bold=True, serif=True), NAVY, x2 - x1 - 68, 10)
        text_block(d, (x1 + 34, y + 38), body, font(30), INK, x2 - x1 - 68, 12)
    footer(d, size, "3/3", "Portal fantasy vs. fantasía épica")
    im.save(path, quality=95)


<<<<<<< HEAD
def pinterest_card(path, kicker, title, subtitle, count, body="Selección comentada: qué distingue cada libro y para qué lector puede encajar.", label="CUADERNO DE AUTORA DEMO DÍAZ"):
=======
def pinterest_card(path, kicker, title, subtitle, count, body="Selección comentada: qué distingue cada libro y para qué lector puede encajar.", label="CUADERNO DE DAVID PORTO DÍAZ"):
>>>>>>> origin/research/public-reuse-parent
    size = (1000, 1500)
    im, d = canvas(size, label)
    d.rectangle((76, 176, 924, 480), fill=NAVY)
    d.text((112, 218), kicker.upper(), font=font(25, bold=True), fill=GOLD)
    text_block(d, (112, 275), title, font(55, bold=True, serif=True), WHITE, 760, 10)
    d.text((76, 565), count, font=font(132, bold=True, serif=True), fill=BLUE)
    y = text_block(d, (76, 742), subtitle, font(42, bold=True, serif=True), INK, 840, 14)
    d.line((76, y + 45, 924, y + 45), fill=GOLD, width=8)
    text_block(d, (76, y + 92), body, font(31), MUTED, 840, 13)
<<<<<<< HEAD
    d.text((76, 1380), "autorademodiaz.com", font=font(28, bold=True), fill=BLUE)
=======
    d.text((76, 1380), "davidportodiaz.com", font=font(28, bold=True), fill=BLUE)
>>>>>>> origin/research/public-reuse-parent
    im.save(path, quality=95)


def main():
    ig1 = ROOT / "publicaciones Instagram GPT/2026-09-24"
    quote_card(ig1 / "fragmento-ritual-domingo.png", "Registro I · íntimo", "El ritual del domingo",
               "Este domingo el chocolate llevaba cinco minutos en la mesa y ninguno de los dos lo había tocado.", "2/4")
    quote_card(ig1 / "fragmento-precio-historia.png", "Registro II · humor negro", "El precio de una historia",
               "—¿Cuánto vale?\n—No está en venta. Es una pieza de museo.\n\n«Mentira número uno. Ahora a inflar la demanda».", "3/4")
    quote_card(ig1 / "fragmento-horas-silenciosas.png", "Registro III · futuro cercano", "Las horas silenciosas",
               "—¿Sabe? Mi generación no conoce este sonido. Para nosotros, las horas son silenciosas. Digitales.", "4/4")

    ig2 = ROOT / "publicaciones Instagram GPT/2026-09-26"
    info_card(ig2 / "lectores-beta-que-implica.png", "Programa privado", "¿Qué implica apuntarte?", [
        "Recibir material sin publicar de forma ocasional.",
        "Contar qué funciona, qué no y qué resulta confuso.",
        "Sin calendario fijo ni obligación de leerlo todo.",
    ], "2/3", "Lectores beta")
    info_card(ig2 / "lectores-beta-privacidad-baja.png", "Programa privado", "Tu correo, con un solo propósito", [
        "Se usa únicamente para el programa de lectores beta.",
        "La lista está separada de la newsletter general.",
        "Puedes darte de baja cuando quieras.",
    ], "3/3", "Privacidad y baja")

    tt1 = ROOT / "publicaciones TikTok GPT/2026-09-25"
    info_card(tt1 / "portal-fantasy-vs-fantasia-epica-02.png", "La diferencia útil", "Todo empieza aquí", [
        "Portal fantasy: el protagonista viene de nuestro mundo.",
        "Fantasía épica: el protagonista ya vive en el mundo fantástico.",
    ], "2/3", "Desliza para comparar")
    compare_card(tt1 / "portal-fantasy-vs-fantasia-epica-03.png")

    tt2 = ROOT / "publicaciones TikTok GPT/2026-09-27"
    info_card(tt2 / "worldbuilding-noveris-02.png", "La pregunta que lo cambió todo", "¿Por qué existe Noveris justo ahí?", [
        "Si la ciudad pudiera estar en cualquier sitio, todavía es decorado.",
        "La ubicación tiene que cambiar cómo se vive dentro de ella.",
    ], "2/3", "Worldbuilding de Noveris")
    info_card(tt2 / "worldbuilding-noveris-03.png", "Una respuesta deja huella", "La ciudad empieza a vivir", [
        "Los barrios se acercan al acceso.",
        "La arquitectura mezcla varios planos.",
        "El mercado cambia con los ciclos.",
        "Los recursos crean rutas y conflictos.",
    ], "3/3", "Worldbuilding de Noveris")

    pin = ROOT / "publicaciones Pinterest GPT"
    pinterest_card(pin / "2026-09-25/fantasia-juvenil-espanola-2025-2026.png",
                   "Lecturas en español", "Fantasía juvenil española", "Publicada en 2025 y 2026", "2025—26")
    pinterest_card(pin / "2026-09-27/libros-portal-fantasy-espanol.png",
                   "Guía de lectura", "Portal fantasy juvenil en español", "Diez puertas para elegir la próxima lectura", "10")


if __name__ == "__main__":
    main()

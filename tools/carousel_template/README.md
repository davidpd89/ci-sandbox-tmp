# Carousel template — sistema canónico 1080×1350

Herramienta común para los carruseles de Instagram que no necesitan un renderer especializado.

## Qué resuelve

- tratamiento de color fijo sobre foto real;
- crop 4:5 sin deformar;
- barra de marca, contador, kicker, titular y cue;
- texto final renderizado con HTML/CSS, nunca por IA;
- PNG 1080×1350 reproducible.

No sustituye los renderers específicos de `met_bookish_memes`, `literary_places`, `fake_books`, `microcomic`, etc.

## Instalación

```bash
python -m pip install -r tools/carousel_template/requirements.txt
python -m playwright install chromium
```

El renderer usa Playfair Display 700 + Inter 600/700. Debe tener acceso a `fonts.googleapis.com` y `fonts.gstatic.com`. Si las fuentes auditadas no cargan, termina con `CAROUSEL_RENDER_BLOCKED`; no exporta con una sustitución silenciosa.

## 1. Preparar foto

```bash
python tools/carousel_template/grade_image.py \
  assets/original.jpg \
  build/foto_tratada.jpg \
  0.45
```

El tercer argumento controla el centro vertical del recorte: `0` arriba, `0.5` centro, `1` abajo.

Receta fija:
- saturación ×0.78;
- contraste ×1.15;
- brillo ×0.80;
- blend terracota `(180,110,60)` al 16%;
- salida 1080×1350.

## 2. Renderizar slide

Intermedia:

```bash
python tools/carousel_template/render_slide.py \
  build/foto_tratada.jpg \
  "ARCHIVO" \
  "Aquí va el título<br>de la slide" \
  "02 / 05" \
  build/slide_02.png \
  --cue swipe
```

Última:

```bash
python tools/carousel_template/render_slide.py \
  build/foto_tratada.jpg \
  "CIERRE" \
  "Aquí va la frase final" \
  "05 / 05" \
  build/slide_05.png \
  --cue save
```

`--cue save` renderiza **solo `GUARDA`**. No añade `LIKE`, `COMENTA`, `SIGUE` ni ninguna segunda acción. Si el kit requiere otra CTA, debe declararla en su renderer/manifest específico; no se inventa aquí.

## Reglas

1. Foto/archivo real primero. Si una familia necesita imagen generada, debe documentar referencia real → JSON → KEEP/CHANGE y no entra aquí automáticamente.
2. No deformar portadas, archivos, mapas ni arquitectura.
3. `render_slide.py` acepta solo `<br>` dentro del título; cualquier otra etiqueta se escapa.
4. Revisar el PNG completo. Un proceso reproducible no convierte un mal crop en uno bueno.
5. La última slide usa `--cue save`; intermedias `--cue swipe`. `--cue none` existe para familias que no deben llevar CTA visual.
6. El renderer no programa ni publica nada.
7. `CAROUSEL_RENDER_BLOCKED` = STOP; no aprobar ni exportar un lote con tipografías sustitutas.

## Gate mínimo antes de lote

- resolución exacta 1080×1350;
- Playfair Display 700 + Inter 600/700 cargadas;
- texto sin cortes ni desbordes;
- sujeto principal no tapado;
- ningún logo/marca accidental;
- tildes y ñ correctas;
- contador correcto;
- kicker idéntico dentro de la misma serie cuando así lo exige el kit;
- `--cue save` muestra una sola acción: guardar;
- si el asset tiene licencia/crédito obligatorio, el kit especializado debe incorporarlo: esta plantilla genérica no lo inventa.

## Relación con la guía maestra

Este directorio implementa las herramientas que `04_Assets/sistema_carrusel_instagram.md` ya daba por existentes. Desde 18/08/2026 la ruta canónica en el repositorio es:

`tools/carousel_template/`

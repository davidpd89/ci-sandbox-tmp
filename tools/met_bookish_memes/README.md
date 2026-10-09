# IG-12 — Cuadros con problemas de lector

Herramientas deterministas para producir los 6 carruseles IG-12 con obras Open Access de The Metropolitan Museum of Art.

## Dependencias

```bash
python -m pip install pillow
```

`download_met.py` usa solo la biblioteca estándar para red. No requiere API key.

El kit permite una sans neutra, sin estética antigua. El renderer usa este orden fijo:
1. DejaVu Sans / DejaVu Sans Bold;
2. Arial / Arial Bold.

Ambas familias están dentro de la dirección visual autorizada. Si no encuentra ninguna, aborta con `IG12_RENDER_BLOCKED`; no cae a `ImageFont.load_default()` ni deja que cada máquina elija otra fuente.

## Flujo exacto

Desde la raíz del repo:

```bash
python tools/met_bookish_memes/download_met.py
```

La descarga solo es válida si aparecen seis líneas `PUBLIC_DOMAIN_OK`. El script aborta si The Met deja de marcar una obra como dominio público, desaparece `primaryImage`, cambia el `objectID` o no coincide título/autor esperado.

Render del gate:

```bash
python tools/met_bookish_memes/render_carousel.py --item ig12_01
python tools/met_bookish_memes/render_carousel.py --item ig12_02
```

Abrir:

- `tools/met_bookish_memes/output/ig12_01_slide1.png`
- `tools/met_bookish_memes/output/ig12_01_slide2.png`
- `tools/met_bookish_memes/output/ig12_02_slide1.png`
- `tools/met_bookish_memes/output/ig12_02_slide2.png`

Si ambos pasan el gate documentado en Drive, generar lote:

```bash
python tools/met_bookish_memes/render_carousel.py --all
```

## Gate

Pasa solo si:

1. la obra sigue pareciendo reproducción de museo, no plantilla decorativa;
2. el texto de slide 1 se entiende en menos de ~1,5 s;
3. no se tapa cara/libro/manos: el texto vive fuera de la obra;
4. slide 2 conserva la obra limpia y acredita The Met / Public Domain;
5. no se añade marco, sepia, emoji, “efecto antiguo” ni material IA;
6. el caption no vuelve a explicar literalmente el chiste;
7. no se añade una experiencia personal de David;
8. IG-12-06 muestra en la ficha visual `Women Conversing` + `India · siglo XVII`; `Autor no identificado en ficha` se conserva como dato de validación, no como texto añadido a la creatividad.

Si las dos primeras piezas parecen meme genérico, cancelar IG-12. No arreglarlo con ornamentos.

## Regla de integridad

- No sustituir un `object_id` por otra obra “parecida”.
- No usar una reproducción de Google Images/Pinterest.
- No retocar colores/caras/manos de la obra.
- No insertar el texto dentro del lienzo: siempre va en la banda editorial externa.
- `manifest.json` es la fuente única para copy, ALT y calendario.
- `artist` puede conservar un dato de QA distinto de `display_artist`; el renderer usa `display_artist` solo cuando el manifest lo declara expresamente.
- No programar sin aprobación humana.

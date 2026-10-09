# TT-02 — Fragmentos reales de Las manecillas del recuerdo

Pipeline cerrado para las tres publicaciones Photo Mode del documento Drive `TT-02 — Serie fragmentos reales Manecillas faceless — 3 publicaciones listas`.

No genera escenas. Slides 1–9 usan la fotografía Pexels principal exacta de cada pieza con crops/zoom deterministas. Slide 10 inserta la portada real de Drive sin modificarla.

## Fuentes canónicas

Texto permitido:
- Drive `28_MANECILLAS_FRAGMENTOS_POSTS_Y_PAGINAS_2026-08-16.md`
- ID `1CtjHvvy7BxBm-H7I5CXh5p7wK3QcykCt`

Portada obligatoria:
- Drive ID `1SClEck69kTqbqorViNxks1t1Axwu-Vy1`
- `portada-las-manecillas-del-recuerdo-1024x1536.png`
- 1024×1536
- SHA-256 `1361ed45dad7cfea9f9e07de08369ef4e656867f9ecc370c429571cfba0b1e8b`

El renderer aborta con `TT02_COVER_BLOCKED` si el archivo no coincide. No usar otra exportación, una captura, un mockup ni una reconstrucción IA.

## Dependencias

```bash
python -m pip install playwright pillow
python -m playwright install chromium
```

Necesita Playfair Display 700 + Inter 600/700. Si no cargan, `TT02_RENDER_BLOCKED`.

## 1. Preparar portada

Descargar exactamente el archivo del Drive ID anterior y guardarlo como:

```text
build/tt02/assets/portada-las-manecillas-del-recuerdo-1024x1536.png
```

No hay que comprobar visualmente si “parece la portada correcta”: el hash lo hace el renderer.

## 2. Descargar stock exacto

El downloader ya existente de IG-02 acepta este manifest porque comparte el mismo esquema de referencias Pexels:

```bash
python tools/writing_carousel/fetch_references.py \
  tools/manecillas_slideshow/tt02_manifest.json \
  --out build/tt02/assets \
  --item tt02_01
```

Para las tres:

```bash
python tools/writing_carousel/fetch_references.py \
  tools/manecillas_slideshow/tt02_manifest.json \
  --out build/tt02/assets
```

Reglas:
- solo se descarga `reference_url`;
- `backup_reference_url` no se usa automáticamente;
- si Pexels deja de exponer `Free to use`, STOP;
- el sidecar debe conservar URL y licencia exactas;
- no se busca una foto “parecida”.

## 3. Gate OLA 2 — TT-02-01

```bash
python tools/manecillas_slideshow/render_manecillas_slideshow.py \
  tools/manecillas_slideshow/tt02_manifest.json \
  --assets build/tt02/assets \
  --out build/tt02 \
  --item tt02_01
```

Revisar las diez PNG en móvil:
- 1080×1920 exactos;
- la foto real se reconoce como una única escena coherente, no como nueve imágenes falsamente distintas;
- el zoom/crop avanza sin deformar a abuelo/nieto;
- el texto coincide carácter por carácter con `tt02_manifest.json`;
- slide 1 es paráfrasis y dice `Fragmento real · Las manecillas del recuerdo`;
- slide 9 termina exactamente en `Van siete veces, pensó.` y añade `El fragmento se corta aquí.`;
- no aparece ninguna línea posterior del libro;
- slide 10 usa la portada real validada por hash;
- no aparecen `ya disponible`, precio, tienda ni URL de venta;
- cuatro hashtags exactos en metadata;
- ninguna dependencia de audio.

Si TT-02-01 falla visualmente, corregir `crop_y`/`zoom` o el renderer. No generar otra familia de personas para “arreglarlo”.

## 4. Lote

Solo después del gate:

```bash
python tools/manecillas_slideshow/render_manecillas_slideshow.py \
  tools/manecillas_slideshow/tt02_manifest.json \
  --assets build/tt02/assets \
  --out build/tt02 \
  --all
```

Cada pieza produce `01.png`…`10.png` + `metadata.json`.

## 5. Publicación

El pipeline termina en `RENDERED_NOT_SCHEDULED`.

Las fechas y las 10:00 del manifest son propuestas históricas. Antes de usarlas:
1. reconsultar Best Time;
2. reconsultar planner y colisiones;
3. no programar, mover ni sustituir nada en Metricool sin autorización expresa de David;
4. si se publica, usar Photo Mode nativo y mantener el orden 01→10;
5. audio opcional y prescindible; el slideshow debe funcionar completamente en silencio.

## 6. Canon y copyright

- no ampliar citas desde memoria, PDF antiguo ni otro borrador;
- no mezclar escenas;
- no convertir una frase de personaje en opinión de David;
- si cambia la maqueta, reabrir el documento canónico antes de producir;
- `tt02_manifest.json` contiene solo los tres fragmentos ya declarados públicos en el documento 28.

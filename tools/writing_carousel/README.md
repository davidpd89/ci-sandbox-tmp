# IG-02 — Checklists de escritura guardables

Pipeline ejecutable para las seis publicaciones del documento Drive `IG-02 — Serie carruseles de escritura guardables — 6 publicaciones listas`.

La ruta principal no genera imágenes: usa **una referencia Pexels exacta por carrusel** y la reutiliza con encuadres deterministas. Esto evita mutaciones de personas/objetos y cumple la prioridad stock real > generación IA. Las variantes image-to-image del documento quedan solo como fallback futuro, no como paso obligatorio.

## Dependencias

```bash
python -m pip install playwright
python -m playwright install chromium
```

El renderer necesita Playfair Display 700 + Inter 500/700 desde Google Fonts. Si no cargan, termina con `IG02_RENDER_BLOCKED`.

## 1. Gate de referencias — OLA 2

Primero descargar únicamente las dos referencias del gate:

```bash
python tools/writing_carousel/fetch_references.py \
  tools/writing_carousel/ig02_manifest.json \
  --out build/ig02/assets \
  --item ig02_01

python tools/writing_carousel/fetch_references.py \
  tools/writing_carousel/ig02_manifest.json \
  --out build/ig02/assets \
  --item ig02_02
```

El downloader:
- abre solo la `reference_url` declarada;
- exige que Pexels siga mostrando la señal `Free to use`;
- descarga `og:image`;
- guarda el asset con nombre exacto;
- guarda sidecar con URL, licencia y trazabilidad;
- nunca busca una foto parecida si la referencia falla.

STOP si la página ya no abre, cambia la licencia/señal o el asset descargado no es una fotografía humana real utilizable.

## 2. Render del gate

```bash
python tools/writing_carousel/render_writing_carousel.py \
  tools/writing_carousel/ig02_manifest.json \
  --assets build/ig02/assets \
  --out build/ig02 \
  --item ig02_01

python tools/writing_carousel/render_writing_carousel.py \
  tools/writing_carousel/ig02_manifest.json \
  --assets build/ig02/assets \
  --out build/ig02 \
  --item ig02_02
```

Cada post produce PNG numerados y `metadata.json` con caption, hashtags, fuente, licencia, fecha propuesta y la marca `RENDERED_NOT_SCHEDULED`.

## 3. QA visual obligatorio

Revisar IG-02-01 e IG-02-02 completos en móvil antes de renderizar el lote:
- 1080×1350 exactos;
- ninguna línea cortada ni cuerpo fuera de zona segura;
- Playfair Display 700 e Inter cargadas, sin fallback silencioso;
- la foto sigue pareciendo fotografía real, no un filtro “fantasy”;
- el mismo asset se reconoce como sistema deliberado, no como ocho imágenes fingidamente distintas;
- el texto de cada slide coincide con `ig02_manifest.json`;
<<<<<<< HEAD
- marca exacta `AUTORA DEMO DÍAZ`, sin `.com` ni logo grande;
=======
- marca exacta `DAVID PORTO DÍAZ`, sin `.com` ni logo grande;
>>>>>>> origin/research/public-reuse-parent
- slides intermedias: solo `DESLIZA →`;
- última slide: solo el CTA `GUARDA…` exacto del manifest;
- caption no repite literalmente el titular;
- cuatro hashtags exactos.

Si el mismo fondo vuelve ilegible una slide concreta, corregir `crop_y` en el manifest y volver a renderizar. No retocar el PNG a mano.

## 4. Lote

Solo después del gate:

```bash
python tools/writing_carousel/fetch_references.py \
  tools/writing_carousel/ig02_manifest.json \
  --out build/ig02/assets

python tools/writing_carousel/render_writing_carousel.py \
  tools/writing_carousel/ig02_manifest.json \
  --assets build/ig02/assets \
  --out build/ig02 \
  --all
```

## 5. Calendario y Metricool

Las fechas del manifest son **propuestas históricas del kit**, no órdenes de publicación. Antes de usar una:
1. volver a consultar planner y Best Time;
2. comprobar colisiones y el estado real del calendario;
3. no programar, mover, borrar ni sustituir nada en Metricool sin autorización expresa de David.

Este pipeline no contiene ninguna llamada a Metricool.

## 6. Fallo y recuperación

- referencia caída/licencia dudosa → STOP; usar la query de respaldo documentada en Drive y registrar una nueva referencia exacta antes de cambiar el manifest;
- fuente no carga → STOP con `IG02_RENDER_BLOCKED`;
- overflow → corregir renderer/manifest una vez, no seis PNG;
- gate visual flojo → no producir el lote;
- buen gate pero bajo rendimiento → aplicar los umbrales del documento Drive; no “arreglar” cambiando hashtags.

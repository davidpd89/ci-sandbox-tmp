# TT-05 — Clásicos en 2 slides

Renderer determinista para `TT-05`. No usa IA ni imágenes externas: genera dos PNG 1080×1920 por pieza a partir de texto auditado.

## Dependencias

```bash
python -m pip install playwright
python -m playwright install chromium
```

El CSS usa exactamente Playfair Display 700 e Inter 500/600 servidas por Google Fonts. El renderer comprueba que las tres variantes estén realmente cargadas antes de hacer cada captura.

Requisitos de ejecución:
- acceso a `fonts.googleapis.com` y `fonts.gstatic.com`;
- Chromium instalado por Playwright;
- no sustituir las fuentes por equivalentes del sistema.

Si las fuentes no cargan, el renderer debe abortar. Ese fallo es deliberado: evita exportar una creatividad visualmente distinta sin que nadie lo note. Una sustitución tipográfica exige nueva revisión visual común del kit y actualización de este README; no se decide el día de producción.

## Gate

```bash
python tools/tiktok_excerpt/render_excerpt_cards.py tools/tiktok_excerpt/tt05_manifest.json --item tt05_01 --out build/tt05
python tools/tiktok_excerpt/render_excerpt_cards.py tools/tiktok_excerpt/tt05_manifest.json --item tt05_02 --out build/tt05
```

Abrir `01_hook.png` y `02_excerpt.png` en un móvil real.

PASS solo si:
- hook legible en menos de un segundo;
- cita legible sin zoom;
- highlights discretos y claros;
- la etiqueta `FRAGMENTO REAL · TEXTO REMAQUETADO` se entiende;
- no parece un facsímil falso ni una cita motivacional;
- puntuación y cita coinciden con la fuente.

Si falla, cambiar una vez el sistema común y volver a ejecutar 01+02. No retocar cada post por separado.

## Lote

```bash
python tools/tiktok_excerpt/render_excerpt_cards.py tools/tiktok_excerpt/tt05_manifest.json --out build/tt05
```

Salida por item:

```text
build/tt05/tt05_01/01_hook.png
build/tt05/tt05_01/02_excerpt.png
build/tt05/tt05_01/metadata.json
```

## Antes de publicar

1. Reabrir `source_url` del item y verificar literalmente la cita.
2. No sustituir la fuente por una edición moderna/captura comercial.
3. Copiar `title`, `caption` y los cuatro `hashtags` del manifest.
4. No añadir TTS, voz, CTA, mockup, portada ni fondo generado.
5. Publicar en Photo Mode como 2 imágenes y medir 72 h + 7 días.
6. Aprobación humana final obligatoria.

## Qué se está probando

No se prueba “si gustan los clásicos”. Se prueba si `hook corto -> fragmento real resaltado` produce más acciones significativas por 1.000 views que los formatos de dos pantallas TT-01/TT-03.

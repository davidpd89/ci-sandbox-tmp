# FB-02 — Historias de objetos-libro en 30 segundos

Pipeline determinista para los seis Reels de `FB-02`. No usa IA generativa, voz, TTS ni B-roll. Cada vídeo nace de un único activo histórico real + texto auditado + movimiento 2D.

## Dependencias

```bash
python -m pip install pillow
```

Además:
- `ffmpeg` debe estar en PATH;
- `fontconfig` debe aportar `fc-match`;
- Playfair Display Bold, Inter Regular e Inter Bold deben estar instaladas localmente.

El renderer comprueba la familia devuelta por fontconfig y aborta si resuelve otra tipografía. No existe fallback automático a DejaVu ni a otra familia: cambiar tipografía exige nueva revisión visual común del kit.

No incluir ni distribuir archivos de fuentes en el repositorio.

## 1. Descargar los activos exactos

```bash
python tools/facebook_story_reel/download_assets.py \
  tools/facebook_story_reel/fb02_manifest.json \
  --out build/fb02/assets
```

Para una sola pieza:

```bash
python tools/facebook_story_reel/download_assets.py \
  tools/facebook_story_reel/fb02_manifest.json \
  --out build/fb02/assets \
  --item fb02_01
```

La descarga de Commons se resuelve por API y guarda un `fb02_XX.source.json` con URL original y metadata de licencia. Además valida `asset_audit` del manifest: si la licencia ya no contiene el valor esperado, aborta; en `fb02_06` también exige que el campo de autor siga conteniendo `pellethepoet`. No descarga un sustituto silenciosamente.

La volvelle usa exclusivamente el `og:image` de la página PICRYL declarada y NO recibe `PASS` automático: el sidecar queda como `MANUAL_REVALIDATION_REQUIRED`. Antes de producirla hay que revalidar British Library + Europeana tal como exige el kit.

Si una fuente falla o el gate de asset falla, NO buscar automáticamente otro objeto. La herramienta aborta.

## 2. Gate técnico

```bash
python tools/facebook_story_reel/render_story_reel.py \
  tools/facebook_story_reel/fb02_manifest.json \
  --assets build/fb02/assets \
  --out build/fb02 \
  --item fb02_01

python tools/facebook_story_reel/render_story_reel.py \
  tools/facebook_story_reel/fb02_manifest.json \
  --assets build/fb02/assets \
  --out build/fb02 \
  --item fb02_06
```

Abrir ambos `reel.mp4` en móvil y revisar especialmente:
- primer texto legible antes de 2 s;
- activo real domina la pieza;
- ningún bloque exige pausar;
- aparece información nueva alrededor de 10, 20 y 27 s;
- fundidos y zoom son discretos;
- crédito/licencia final legible;
- el vídeo se entiende al 100% en silencio;
- `fb02_06` conserva `pellethepoet · CC BY 2.0`.

Si el gate falla, corregir el sistema común una sola vez. No retocar seis Reels individualmente para salvar la plantilla.

## 3. Lote

```bash
python tools/facebook_story_reel/render_story_reel.py \
  tools/facebook_story_reel/fb02_manifest.json \
  --assets build/fb02/assets \
  --out build/fb02
```

Salida:

```text
build/fb02/fb02_01/01.png ... 06.png
build/fb02/fb02_01/reel.mp4
build/fb02/fb02_01/metadata.json
```

El MP4 es 1080×1920, H.264, 30 fps, aproximadamente 29 s por los fundidos y SIN pista de audio.

## 4. QA antes de publicar

1. Reabrir `source_url` y `fact_source` del item.
2. Confirmar que el sidecar `source.json` dice `asset_gate: PASS` en los items Commons.
3. Para la volvelle, reabrir British Library + Europeana; si no se sostiene la identificación Sloane 702 ff.21v–22, cancelar esa pieza.
4. Copiar caption y 3 hashtags desde el manifest; no añadir pregunta/CTA.
5. No añadir música, TTS o voz para “rellenar” silencio. El experimento se diseñó para funcionar sin audio.
6. No reutilizar el MP4 en Instagram/TikTok sin un kit específico de esa red.
7. Aprobación humana final antes de programar.

## Estado de prueba del renderer — 18/08/2026

`render_story_reel.py` se compiló y se ejecutó localmente con un activo de prueba 1600×1000 y el bloque textual más largo de FB-02-01. Resultado:
- seis PNG generados;
- MP4 H.264 generado por ffmpeg;
- duración comprobada: 29,0 s;
- 1080×1920 a 30 fps;
- sin desbordes visibles en el bloque largo probado.

Esto valida el pipeline técnico, NO el gate visual con las fotografías históricas reales. Ese gate sigue pendiente y se ejecuta con `fb02_01` + `fb02_06` antes del lote.

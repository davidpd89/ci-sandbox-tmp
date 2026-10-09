# Text carousel — carrusel tipográfico documental

Renderer especializado para familias donde el contenido ES texto/documento y añadir una foto sería decoración sin función.

Primera implementación: `IG-17 — Una palabra, un viaje`.

## Instalación

```bash
python -m pip install playwright
python -m playwright install chromium
```

Fuentes auditadas:
- Playfair Display 600/700/900;
- Inter 500/600/700;
- Noto Sans 600 para la cadena etimológica y caracteres que exigen mayor cobertura Unicode.

Se cargan desde Google Fonts. La máquina de render debe tener acceso a `fonts.googleapis.com` y `fonts.gstatic.com`. Si una variante no carga, el renderer aborta con `TEXT_CAROUSEL_BLOCKED`; no exporta con Arial, Georgia u otro fallback silencioso.

## Render de prueba

```bash
python tools/text_carousel/render_text_carousel.py \
  tools/text_carousel/ig17_manifest.json \
  --item ig17_01 \
  --out build/ig17
```

Genera:
- `ig17_01_s1.png`
- `ig17_01_s2.png`
- `ig17_01_s3.png`
- `ig17_01_s4.png`

## Lote

```bash
python tools/text_carousel/render_text_carousel.py \
  tools/text_carousel/ig17_manifest.json \
  --all \
  --out build/ig17
```

Resultado: 24 PNG, cuatro por cada una de las seis palabras.

## Gate IG-17

Antes del lote, renderizar `ig17_01` y `ig17_02`.

PASA si:
- 1080×1350 exactos;
- `OJALÁ` y `PERSONA` no desbordan;
- `wa šá lláh`, `φersu`, `persōna`, tildes y signos aparecen correctamente;
- la cadena etimológica usa Noto Sans 600 y cabe sin cuerpo minúsculo;
- S3 se lee en móvil;
- la URL DLE de S4 no se corta;
- no parece una “frase motivacional” sobre fondo plano: jerarquía de palabra → cadena → explicación → fuente es clara;
- no se añade una ilustración por llenar espacio.

Si un carácter no aparece correctamente pese a Noto Sans, **STOP**. No convertirlo en imagen generada ni aceptar un fallback distinto por máquina. Corregir primero la familia tipográfica común y repetir `ig17_01` + `ig17_02`.

## Fuente de verdad

El manifest contiene el copy ya revisado. Antes de producir en 2027:
1. abrir las seis URLs del DLE;
2. comprobar que la etimología sigue igual;
3. si cambia, actualizar primero el documento Drive y este manifest;
4. renderizar después.

No editar el PNG manualmente para corregir una etimología.

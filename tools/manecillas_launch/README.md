# IG-06 — lanzamiento de «Las manecillas del recuerdo»

Pipeline reproducible para las tres piezas del 03/09, 05/09 y 07/09. Transcribe el kit autoritativo de Drive `IG-06 — Lanzamiento Manecillas desde historia real del tiempo — 3 carruseles listos`.

No crea publicaciones y no accede a Metricool. Las fechas del manifest son sustituciones propuestas de posts existentes; `RENDERED_NOT_SCHEDULED` es obligatorio hasta aprobación humana.

## Dependencias

```bash
python -m pip install pillow playwright
python -m playwright install chromium
```

Tipografías: Playfair Display 700 + Inter 500/600. El renderer puede cargarlas desde Google Fonts o recibir rutas locales con `--playfair-font` y `--inter-font`. No guardar ni distribuir archivos de fuentes en este repositorio.

## 1. Descargar y revalidar activos históricos

```bash
python tools/manecillas_launch/fetch_assets.py \
  tools/manecillas_launch/ig06_manifest.json \
  --out build/ig06_assets
```

El script bloquea si:
- `Trench watch 1916 gold.jpg` deja de figurar con licencia de dominio público en Commons;
- The Met 199408 deja de ser `Public Domain`, cambia de objeto/título o pierde imagen principal;
- la fotografía CC0 del reloj de Lincoln cambia de licencia.

Las fuentes factuales (Smithsonian / The Met) se reabren además el día de producción. El asset visual no sustituye la fuente factual.

## 2. Portada oficial

Usar exclusivamente el fichero Drive `portada-las-manecillas-del-recuerdo-1024x1536.png` (ID `1SClEck69kTqbqorViNxks1t1Axwu-Vy1`). El renderer exige 1024×1536 y SHA-256:

`1361ed45dad7cfea9f9e07de08369ef4e656867f9ecc370c429571cfba0b1e8b`

No recrear, recolorear, generar mockup 3D ni pasar la portada por IA.

## 3. Render

```bash
python tools/manecillas_launch/render_launch.py \
  tools/manecillas_launch/ig06_manifest.json \
  --assets build/ig06_assets \
  --cover /ruta/portada-las-manecillas-del-recuerdo-1024x1536.png \
  --out build/ig06
```

Genera 21 PNG 1080×1350 + `ig06_render_manifest.json` con hashes. La portada se valida antes de abrir Chromium. Si Playfair/Inter no cargan, aborta: no hay fallback silencioso.

## 4. Gate visual obligatorio

Revisar primero las 7 slides de `ig06_01` en móvil y después el lote:
- historia real comprensible antes de aparecer el libro;
- el reloj no queda tapado por titulares;
- slide 5 funciona como puente, no como anuncio;
- fragmentos exactamente iguales al documento canónico;
- portada 2D real, legible y sin deformación;
- `Publicado hoy` solo en IG-06-01 si se mantiene el 03/09/2026;
- caption no repite literalmente el titular visual;
- cero precio, «cómpralo», CTA comercial o comentario fijado.

## 5. Metricool

Tras aprobación explícita, **actualizar** los posts existentes; no crear otros encima:
- 03/09 18:00 → `348656152` → IG-06-01;
- 05/09 18:00 → `348656248` → IG-06-02;
- 07/09 18:00 → `348657759` → IG-06-03.

Mantener 18:00 salvo que una nueva consulta de Best Time aporte señal real. Estas tres piezas consumen el bloque promocional de lanzamiento; no añadir otra serie comercial inmediata.

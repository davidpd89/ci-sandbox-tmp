# Documentary carousel — carruseles documentales cerrados

Renderer reutilizable para carruseles con archivo real, mapas, arquitectura, objetos o recursos documentales.

No busca imágenes. El manifest fija el nombre local esperado y la URL exacta de la fuente. Si falta el asset, el proceso se detiene con `MISSING_ASSET`; no selecciona un sustituto.

## Instalación

```bash
python -m pip install playwright
python -m playwright install chromium
```

El sistema visual usa exactamente:
- Inter 500/600/700;
- Playfair Display 600/700/900.

Las fuentes se cargan desde Google Fonts. La máquina de render debe tener acceso a `fonts.googleapis.com` y `fonts.gstatic.com`. Antes de cada captura el renderer comprueba las seis variantes; si alguna no carga, aborta con `DOCUMENTARY_RENDER_BLOCKED`.

No aceptar Georgia/Arial como fallback silencioso. Una sustitución tipográfica cambia saltos de línea, densidad y jerarquía y exige nueva revisión visual común de la plantilla.

## Estructura del manifest

```json
{
  "series": "IG-XX",
  "posts": [{
    "id": "igxx_01",
    "caption": "...",
    "hashtags": ["#..."],
    "slides": [{
      "mode": "image_title",
      "image": "igxx_01.jpg",
      "source_url": "https://fuente-oficial-o-commons/...",
      "fit": "contain",
      "kicker": "ARCHIVO",
      "title": "Texto exacto",
      "credit": "Autor · licencia",
      "cue": "swipe"
    }]
  }]
}
```

Modos:
- `image_title`: imagen completa + titular;
- `image_body`: imagen superior + explicación inferior;
- `source_image`: igual que `image_body`, pensado para ficha/fuente;
- `text`: pieza tipográfica sin imagen.

`fit`: `cover` para fotografía; `contain` para manuscritos, mapas, carteles y objetos que no deben recortarse.

## Render de prueba

```bash
python tools/documentary_carousel/render_documentary.py \
  tools/documentary_carousel/manifests/ig15.json \
  --item ig15_01 \
  --assets build/ig15/assets \
  --out build/ig15
```

Si falta el archivo, devuelve por ejemplo:

```text
MISSING_ASSET: .../build/ig15/assets/ig15_01.jpg
SOURCE: https://commons.wikimedia.org/wiki/File:...
No se busca sustituto automáticamente.
```

Ese mensaje es deliberado: abrir la fuente indicada, descargar el original y guardar con el nombre exacto. Si fuente/licencia han cambiado, se corrige primero el kit/manifest.

Si las fuentes no cargan, devuelve `DOCUMENTARY_RENDER_BLOCKED`. No continuar el lote hasta resolverlo y volver a ejecutar el gate.

## Lote

```bash
python tools/documentary_carousel/render_documentary.py \
  tools/documentary_carousel/manifests/ig15.json \
  --all \
  --assets build/ig15/assets \
  --out build/ig15
```

## Gate

Antes del lote, cada manifest debe señalar las piezas de prueba definidas en `gate_items`; no reducir ese conjunto por comodidad.

Comprobar:
- 1080×1350;
- ningún overflow;
- Playfair Display e Inter reales, no fallback;
- el original no está deformado;
- `contain` en mapas/manuscritos cuando el recorte cambiaría información;
- crédito/licencia legible si corresponde;
- caption no repite el gancho;
- el texto no parece una plantilla de IA aplicada en serie;
- ninguna imagen se sustituye sin actualizar el manifest.

## Qué NO hace

- no descarga automáticamente desde Google Images;
- no inventa assets;
- no llama a un generador de imagen;
- no modifica colores internos de mapas/manuscritos;
- no programa en Metricool.

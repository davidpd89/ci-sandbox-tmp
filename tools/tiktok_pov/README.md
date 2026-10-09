# TT-01 — POV en 2 pantallas

Pipeline ejecutable para `TT-01 — Serie faceless POV en 2 pantallas — 10 publicaciones listas`.

No crea ideas ni sustituye el kit editorial. El manifest contiene copy final, referencias Pexels exactas, JSON visual, KEEP/CHANGE, prompts opcionales y nombres de asset. El renderer compone las dos tarjetas finales.

## Principio visual vigente

**Ruta principal: fotografía real directa.**

La serie no necesita que cada anomalía fantástica exista físicamente en la foto. El texto puede contener la rareza mientras la imagen aporta un espacio/persona creíble. Esto reduce señales de IA, mutaciones de identidad y coste de producción.

Orden de preferencia:
1. referencia Pexels exacta usada directamente si ya sostiene la escena;
2. recorte/reencuadre/exposición deterministas sobre esa foto;
3. edición localizada desde la foto real si un cambio visual añade información indispensable;
4. image-to-image solo como última opción y siempre con KEEP/CHANGE explícito.

No transformar por transformar.

## Dependencias

```bash
python -m pip install playwright
python -m playwright install chromium
```

El renderer carga explícitamente **Playfair Display 700 + Inter 600**. Si esas fuentes no cargan, debe terminar con `TT01_RENDER_BLOCKED`; no se acepta un fallback silencioso.

## 1. Descargar referencias exactas

Gate OLA 1:

```bash
python tools/tiktok_pov/fetch_references.py \
  tools/tiktok_pov/tt01_manifest.json \
  --out build/tt01/assets \
  --item tt01_01

python tools/tiktok_pov/fetch_references.py \
  tools/tiktok_pov/tt01_manifest.json \
  --out build/tt01/assets \
  --item tt01_02
```

Para el lote:

```bash
python tools/tiktok_pov/fetch_references.py \
  tools/tiktok_pov/tt01_manifest.json \
  --out build/tt01/assets
```

El downloader:
- abre únicamente la `reference_url` declarada;
- exige página Pexels y señal de licencia/uso esperada;
- resuelve el asset declarado;
- guarda `tt01_XX_ref.jpg`;
- guarda `tt01_XX.reference.json` con procedencia y especificación visual;
- nunca busca otra foto si la referencia falla.

Consultar licencia vigente antes de un lote grande:
https://www.pexels.com/es-es/license/

## 2. Preparar fondos finales — ruta principal SIN IA

Para TT-01-01 y TT-01-02, empezar con la referencia real.

Copiar conscientemente la referencia a los fondos finales o generar dos crops derivados del mismo archivo:

```text
build/tt01/assets/tt01_01_s1.jpg
build/tt01/assets/tt01_01_s2.jpg
build/tt01/assets/tt01_02_s1.jpg
build/tt01/assets/tt01_02_s2.jpg
```

La segunda pantalla puede usar:
- mismo archivo con crop más cerrado;
- desplazamiento determinista;
- leve zoom;
- otra zona del mismo asset si mantiene continuidad.

No hace falta «mostrar» literalmente la puerta imposible o la memoria perfecta del villano. La fotografía crea situación; el texto introduce la ficción.

### Cuándo SÍ editar/generar

Solo si el elemento visual es necesario para entender la pieza sin texto o mejora claramente la lectura.

Entonces:
1. partir de `tt01_XX_ref.jpg`;
2. usar el `visual_json` como contrato;
3. escribir explícitamente `MANTENER / CAMBIAR / NO CAMBIAR`;
4. hacer una edición localizada;
5. slide 2 debe editar slide 1, no regenerarse desde cero;
6. guardar la decisión en metadata.

Prompts base y protocolo:
`01_Estrategia/PROMPTS_PRODUCCION_HUMANA_2026-08-20.md`.

Los `generation_prompt` del manifest son especificaciones disponibles, **no una orden de generar siempre**.

## 3. Gate técnico con stock real

Se puede comprobar tipografía, zonas seguras, legibilidad y funcionamiento usando directamente la referencia:

```bash
python tools/tiktok_pov/render_pov_cards.py \
  tools/tiktok_pov/tt01_manifest.json \
  --assets build/tt01/assets \
  --out build/tt01 \
  --item tt01_01 \
  --reference-fallback
```

El nombre histórico `--reference-fallback` significa aquí «usar el asset real declarado», no «buscar un sustituto».

`metadata.json` quedará con `production_status: TECHNICAL_GATE_ONLY` si el proceso se ejecuta en modo técnico. Ese resultado no autoriza publicación.

## 4. Gate OLA 1 con fondos finales

Cuando existan los cuatro fondos finales del gate:

```bash
python tools/tiktok_pov/render_pov_cards.py \
  tools/tiktok_pov/tt01_manifest.json \
  --assets build/tt01/assets \
  --out build/tt01 \
  --item tt01_01

python tools/tiktok_pov/render_pov_cards.py \
  tools/tiktok_pov/tt01_manifest.json \
  --assets build/tt01/assets \
  --out build/tt01 \
  --item tt01_02
```

Revisar en móvil:
- 1080×1920 exactos;
- Playfair Display 700 e Inter 600 sin fallback;
- hook entendible en menos de 2 s;
- payoff sin cortes;
- foto base realmente fotográfica y no «demasiado perfecta»;
- si hay personas: anatomía/gesto naturales;
- si hay edición: continuidad real entre slide 1 y 2;
- ninguna letra generada dentro de la foto;
- marca pequeña, no protagonista;
- caption aporta una capa diferente del texto visual.

### Gate de voz adicional

Leer TT-01-01 y TT-01-02 seguidos.

STOP si ambos captions hacen exactamente:
`explicación del hook → intensificación → frase redonda`.

La serie puede compartir formato visual, no una plantilla de pensamiento.

## 5. Lote

Solo después de aprobar visualmente TT-01-01 y TT-01-02:

```bash
python tools/tiktok_pov/render_pov_cards.py \
  tools/tiktok_pov/tt01_manifest.json \
  --assets build/tt01/assets \
  --out build/tt01
```

Antes de producir los ocho restantes, revisar cada referencia y decidir por item:

```text
production_route: REAL_DIRECT | REAL_EDIT | IMAGE_TO_IMAGE_JUSTIFIED
reason:
```

La opción por defecto es `REAL_DIRECT`.

Salida por pieza:

```text
build/tt01/tt01_01/01_hook.png
build/tt01/tt01_01/02_payoff.png
build/tt01/tt01_01/metadata.json
```

## Bloqueos

STOP si:
- la referencia exacta ya no abre o su licencia/uso no es compatible;
- un script sustituye silenciosamente el asset;
- se genera una persona nueva sin que exista razón visual real;
- slide 2 cambia identidad, ropa, arquitectura o luz cuando debía ser continuidad;
- el resultado parece CGI/ilustración/IA pulida;
- aparece texto generado dentro de la imagen;
- alguien reescribe hook/payoff/caption el día de producción en vez de actualizar primero el manifest;
- un caption fabrica experiencia personal de David;
- se añade CTA/pregunta por rutina.

## Referencias operativas

- voz y criterio: `01_Estrategia/Guia de marca y contenidos.md`
- QA: `01_Estrategia/checklist_calidad_post.md`
- prompts: `01_Estrategia/PROMPTS_PRODUCCION_HUMANA_2026-08-20.md`
- referencias/licencias: `01_Estrategia/REFERENCIAS_INSPIRACION_VERIFICADAS_2026-08-20.md`

No programa ni publica nada.
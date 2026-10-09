# tools/archive_impossible — IG-11 «Archivo imposible»

Kit editorial autoritativo: Drive `IG-11 — Archivo imposible — 4 juegos históricos listos`.

Objetivo: descargar los originales directamente de Library of Congress, verificar metadata/derechos esperados y producir 4 slides por episodio sin IA.

## 1. Dependencias

```bash
python -m pip install requests pillow qrcode
```

Además:
- `fontconfig` debe aportar `fc-match`;
- Inter Regular e Inter Bold/SemiBold deben estar instaladas localmente.

No GPU. No API key. No navegador automatizado. No generador de imágenes.

El renderer comprueba que fontconfig resuelva realmente la familia Inter. Si recibe DejaVu, Liberation, Arial u otro sustituto, aborta con `IG11_RENDER_BLOCKED`. No se permite la antigua caída a `ImageFont.load_default()`.

Los anacronismos se construyen localmente con geometría determinista de Pillow; el QR se genera con `qrcode`. No hay modelo generativo ni asset buscado por el renderer.

## 2. Descargar y verificar fuentes

```bash
python tools/archive_impossible/fetch_loc_assets.py \
  tools/archive_impossible/ig11_manifest.json \
  --out assets/archive_impossible
```

El script consulta cada item con `?fo=json&at=item,resources`, busca el mejor JPEG LOC disponible y valida que la metadata actual siga conteniendo:

- reproduction number esperado;
- fecha esperada;
- autor/fuente esperada;
- frase `No known restrictions`.

Si cualquiera falla, SE DETIENE. No renderizar con una ficha que ya no coincide.

Se guardan por episodio:

```text
ig11_01_original.jpg
ig11_01_metadata.json
...
ig11_04_original.jpg
ig11_04_metadata.json
```

No borrar los metadata JSON: son parte del asset y de la trazabilidad.

## 3. Render

```bash
python tools/archive_impossible/render_archive_impossible.py \
  tools/archive_impossible/ig11_manifest.json \
  --assets assets/archive_impossible \
  --out build/ig11
```

Crea:

```text
build/ig11/ig11_01/ig11_01_s1.png ... s4.png
...
build/ig11/ig11_04/ig11_04_s1.png ... s4.png
build/ig11/ig11_render_manifest.json
```

Slides:
1. montaje completo + objeto moderno;
2. crop/zoom + pista;
3. mismo foco + revelación/anillo; en QR puede aplicarse `overlay.reveal_scale` del manifest;
4. original SIN objeto + crédito.

## 4. Gate visual obligatorio

Revisar IG-11-01 y IG-11-04 antes de producir el lote.

### IG-11-01

El móvil debe caer físicamente SOBRE una mesa o superficie creíble.

Si no ocurre:
- modificar SOLO `overlay.x`, `overlay.y` y `focus.x/y` en `ig11_manifest.json`;
- volver a renderizar;
- registrar el valor definitivo;
- no cambiar tipo/tamaño/texto.

### IG-11-04

El manifest fija `reveal_scale: 1.62` para que el QR sea discreto en la búsqueda y mayor en la revelación. No volver a decidir ese tamaño el día de producción.

Escanear el QR de slide 3 con OTRO dispositivo.
Debe abrir exactamente el item LOC declarado en `overlay.target` y coincidir con `item_url` del episodio.

Si no escanea:
1. NO cambiar destino ni regenerar con IA;
2. revisar que el QR no quede cortado por el crop;
3. si hace falta, reducir `focus.zoom` una sola vez y registrar el valor definitivo;
4. volver a probar físicamente.

Nunca sustituir el QR por una imagen generada.

## 5. Gate histórico

Abrir los cuatro `*_metadata.json` y comprobar:

- title;
- date;
- creator;
- rights;
- reproduction number;
- download URL.

IG-11-02: el original llegó sin título. No borrar la nota que explica que la relación con la sala de biblioteca es `possibly related`.

IG-11-03: comprobar `LC-DIG-fsa-8d29039`.

## 6. Síntoma → corrección

### El objeto añadido se ve demasiado obvio

Reducir `overlay.scale` 10–15%. No intentar fotorrealismo con IA.

### El objeto parece pegatina barata

Eso es preferible a fingir autenticidad histórica. Se puede:
- reducir saturación/contraste del objeto dentro del código;
- girarlo unos grados;
- ajustar escala.

NO añadir sombras generativas ni reconstruir la mesa.

### El puzzle es demasiado difícil

No agrandar el objeto primero. Hacer slide 2 más útil cambiando el texto de pista SOLO en futura temporada. IG-11 v1 ya está cerrado; no reescribir después de ver un resultado aislado.

### El crop de slide 2/3 no muestra el objeto

Corregir `focus.x/y` para que coincida con `overlay.x/y`. Ese es un error técnico, no una decisión creativa.

### El original tiene barras negras

Correcto: slide 4 usa `contain` para mostrar el original completo. No recortarlo para llenar el canvas.

### Falta Inter

STOP. Instalar Inter Regular + Bold/SemiBold y repetir. No editar el PNG después ni aceptar una fuente alternativa por máquina.

## 7. Qué NO se modifica

- personas del archivo;
- rostros/manos;
- color del original;
- fondo;
- contraste del original en slide 4;
- fecha/autor/título;
- objeto elegido por episodio;
- copy del kit.

## 8. Flujo de publicación

1. descargar/validar fuentes;
2. renderizar;
3. pasar gate visual e histórico;
4. abrir kit Drive;
5. copiar caption/hashtags exactos;
6. comprobar planner Metricool;
7. aprobar humanamente;
8. programar solo con autorización expresa.

No programar desde este README: el copy final vive en Drive.

## 9. Métrica

La slide 1 pregunta visualmente, pero el KPI no exige comentario.

Priorizar:
- shares;
- saves;
- comentarios espontáneos;
- avance/reach si Instagram lo expone.

Si genera comentarios pero no guardados/compartidos, el juego entretiene pero la ficha histórica no aporta suficiente valor.

## 10. Versionado

`IG-11_ARCHIVO_IMPOSIBLE_v1` se congela cuando se publique el primer episodio.

Ajustes X/Y previos al primer post son QA técnico y no requieren v2.
Cambiar objeto, copy, estructura o fuente después de publicar sí requiere una nueva versión/temporada.

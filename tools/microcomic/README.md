# tools/microcomic — ejecución del piloto IG-08 / TT-04

Este directorio convierte los JSON de `scenes/` en 5 PNG por episodio:

- slides 1–4: un panel por imagen;
- slide 5: tira completa 2×2 preparada para compartir, sin recortar los paneles.
- footer Instagram común: web, `Like`, `Comenta`, `Envía`, `Guarda` y CTA inferior.

No utiliza IA ni API de imagen. El personaje se construye con SVG/HTML determinista y su geometría/paleta se cargan directamente desde `character_lector_a_v1.json`.

## 1. Dependencias

Desde la raíz del repo:

```bash
python -m pip install playwright pillow
```

El renderer intenta usar, por este orden:

1. Edge instalado en `C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe`;
2. Chrome instalado en `C:/Program Files/Google/Chrome/Application/chrome.exe`;
3. Chromium cacheado por Playwright, si existe.

Por tanto, en esta máquina no hace falta descargar Chromium si Edge/Chrome ya están disponibles.

No hace falta GPU, Canva, ComfyUI ni claves API.

La familia **Inter** queda vendorizada en `tools/microcomic/fonts/Inter-4.1/InterVariable.ttf`, descargada desde la release oficial RSMS/GitHub. El sistema fija Inter 650/700 y no permite que Chromium sustituya silenciosamente por Arial u otra sans.

Trazabilidad:

- `tools/microcomic/fonts/INTER_SOURCE.json`
- `tools/microcomic/fonts/Inter-4.1/LICENSE.txt`

### 1.1 Preflight tipográfico obligatorio

Antes del primer render de IG-08 y siempre que se cambie de máquina/entorno:

```bash
python tools/microcomic/check_fonts.py
```

Resultado válido:

```text
OK: Inter disponible en Chromium para IG-08/TT-04.
```

Si falla, **STOP**. El propio renderer vuelve a cargar Inter mediante `@font-face` desde el archivo vendorizado + `local("Inter")` y termina con `IG08_RENDER_BLOCKED` si no está disponible; el preflight externo no es la única defensa.

## 2. Biblia de personaje — autoridad técnica

`tools/microcomic/character_lector_a_v1.json` no es documentación decorativa: el renderer la lee en cada ejecución.

La v1 fija, entre otros valores:
- cabeza 132×144 px;
- ojos normales 12 px de diámetro;
- torso 250×300 px;
- extremidades 36 px;
- trazo 12 px;
- paperback genérico 130×200 px;
- paleta exacta;
- `wardrobe_locked=true`;
- expresiones permitidas: `neutral`, `cansado`, `alarma`, `sospecha`, `contento`, `resignado`.

Cada escena debe declarar `character_version: LECTOR_A_v1`. El renderer bloquea:
- una versión distinta;
- una expresión/acción/setting desconocidos;
- un override `style` por episodio;
- una referencia que no sea la Pexels exacta declarada;
- ausencia de licencia Pexels.

El manifest de salida guarda `character_version` y el SHA-256 de `character_lector_a_v1.json`. Antes de que IG-08-01 pase el gate se puede corregir la biblia si el personaje falla; una vez aprobada la v1, cualquier cambio posterior exige `LECTOR_A_v2`, no una mutación silenciosa.

## 3. Primer render obligatorio

NO renderizar los seis episodios de golpe la primera vez.

Primero:

```bash
python tools/microcomic/check_fonts.py
python tools/microcomic/render_microcomic.py \
  tools/microcomic/scenes/ig08_01.json \
  --out build/microcomic/ig08_01
```

Se crean:

```text
ig08_01_slide_1.png
ig08_01_slide_2.png
ig08_01_slide_3.png
ig08_01_slide_4.png
ig08_01_slide_5_full.png
ig08_01_manifest.json
```

El manifest debe contener:
- `character_version: LECTOR_A_v1`;
- `character_sha256`;
- referencia Pexels y licencia;
- `slide5_fit: contain`;
- `font_family: Inter local, required`;
- `status: RENDERED_NOT_SCHEDULED`.

Abrir los cinco PNG a tamaño completo y también reducidos aproximadamente al ancho de un móvil.

## 4. Gate visual antes de producir el lote

IG-08-01 pasa solo si:

- el personaje se lee como adulto joven simple, no como clipart infantil;
- cabeza/pelo/ropa son idénticos en 1–4 y coinciden con la biblia;
- el paperback se ve fino, no como caja;
- los bocadillos no cubren cara/manos/objeto clave;
- 23:48 / 00:36 / 01:52 / 02:31 se leen sin esfuerzo;
- la diferencia neutral → cansado → alarma se entiende sin exageración anime;
- slide 5 contiene completos los cuatro paneles: `object-fit: contain`, nunca `cover`;
- web, botones sociales y CTA no pisan el dibujo ni el texto;
- slide 5 puede enviarse aislada y el chiste sigue funcionando;
- no parece que se haya pedido a una IA «hazme un cómic sobre lectores».

Si falla el PERSONAJE, corregir biblia/renderer una vez y volver a empezar. No arreglar panel por panel.

Si falla SOLO un bocadillo, corregir coordenadas en el JSON de esa escena.

## 5. Síntoma → corrección

### Parece infantil

No añadir detalle.

Probar en este orden:
1. revisar primero que el renderer esté usando la geometría de `character_lector_a_v1.json`;
2. si el gate inicial todavía no ha sido aprobado, ajustar la biblia una sola vez;
3. reducir curvatura de boca antes de añadir detalle;
4. quitar cualquier gesto exagerado.

No añadir nariz, pestañas, dedos ni sombras.

### Parece una presentación corporativa

- quitar texto, no añadir iconos;
- comprobar que el panel contiene una acción física;
- no convertir la última viñeta en moraleja.

### El bocadillo pesa demasiado

- recortar palabras primero solo si el kit editorial lo permite; si el texto está fijado, no reescribirlo para que quepa;
- después corregir coordenadas/anchura;
- NO bajar de ~40 px en el texto del panel.

### No se entiende quién habla

- mover cola del bocadillo;
- si es voz fuera de campo, apuntar hacia borde lateral;
- no añadir etiquetas de nombre.

### Personaje cambia entre episodios

Eso debe provocar bloqueo o un hash distinto. Comparar `character_version` + `character_sha256` de los manifests. Si el cambio es deliberado después del gate, crear `LECTOR_A_v2`; no editar v1 silenciosamente.

### Se parece demasiado a la foto Pexels

La foto solo es referencia de pose. Cara, pelo, ropa, objeto y entorno finales salen de la biblia/renderer, no de una conversión de la identidad fotografiada.

### IG-08-06 no comunica «quedan pocas páginas»

La slide 1 debe seguir **sin texto**. La acción `bed_pages` activa un bloque de páginas claro en el borde del paperback (`near_end`); si a tamaño móvil no se entiende, corregir esa geometría. No reintroducir `Quedan doce páginas.` dentro de la viñeta.

## 6. Renderizar el lote después del gate

Windows PowerShell:

```powershell
python tools/microcomic/check_fonts.py
1..6 | ForEach-Object {
  $id = "ig08_{0:D2}" -f $_
  python tools/microcomic/render_microcomic.py "tools/microcomic/scenes/$id.json" --out "build/microcomic/$id"
}
```

Bash:

```bash
python tools/microcomic/check_fonts.py
for n in 01 02 03 04 05 06; do
  python tools/microcomic/render_microcomic.py \
    "tools/microcomic/scenes/ig08_${n}.json" \
    --out "build/microcomic/ig08_${n}"
done
```

No programar desde este pipeline. Las fechas del kit son propuestas históricas: reconsultar planner y Best Time; cualquier cambio/programación en Metricool requiere autorización expresa de David.

## 7. Fuentes y trazabilidad

Cada scene JSON contiene:
- `reference_url`;
- `source_license`;
- `keep`;
- `change`;
- `character_version`;
- cuatro paneles cerrados.

El renderer genera `_manifest.json` con esos datos, archivos creados, SHA de la biblia y estado `RENDERED_NOT_SCHEDULED`.

No borrar los manifests: son la trazabilidad del asset.

## 8. Texto

El texto vive en JSON y se renderiza como SVG/HTML. Nunca pedir a un generador de imágenes que escriba el diálogo.

Antes de publicar:
1. abrir la ficha Drive IG-08;
2. comparar cada frase del PNG contra su sección;
3. revisar tildes, signos y hora;
4. comprobar que el caption NO aparece dentro del dibujo;
5. en IG-08-06 comprobar que la primera viñeta no contiene `Quedan doce páginas.` ni otro texto añadido.

## 9. Adaptación TikTok TT-04 — comando exacto

No volver a dibujar y no usar un editor manual.

`tools/microcomic/make_tiktok_frames.py` toma los cinco PNG 1080×1350 del episodio, los centra sobre 1080×1920 `#F6F0E6`, conserva proporción y no estira.

Después de renderizar IG-08-01:

```bash
python tools/microcomic/check_fonts.py
python tools/microcomic/make_tiktok_frames.py \
  build/microcomic/ig08_01 \
  --out build/microcomic/tt04_01
```

Salida exacta:

```text
build/microcomic/tt04_01/
  tt_frame_1.png
  tt_frame_2.png
  tt_frame_3.png
  tt_frame_4.png
  tt_frame_5.png
```

El script aborta si no encuentra exactamente cinco PNG de slide. Orden Photo Mode: panel 1 → panel 2 → panel 3 → panel 4 → tira completa.

Para el lote completo, después de que IG-08-01 supere el gate:

```bash
python tools/microcomic/check_fonts.py
for n in 01 02 03 04 05 06; do
  python tools/microcomic/make_tiktok_frames.py \
    "build/microcomic/ig08_${n}" \
    --out "build/microcomic/tt04_${n}"
done
```

No modificar texto, personaje ni composición para TikTok: TT-04 prueba la misma pieza en Photo Mode, no una reinterpretación.

## 10. Fuente autoritativa

- Sistema: `04_Assets/sistema_microcomic_social.md`
- Kit editorial: Drive `IG-08 — Microcómic lector simple — 6 carruseles listos`
- Adaptación TikTok: Drive `TT-04 — Microcómic lector simple en Photo Mode — 6 publicaciones listas`
- Personaje: `character_lector_a_v1.json`
- Escenas: `scenes/ig08_01.json` … `ig08_06.json`
- Renderer: `render_microcomic.py`
- Conversor TikTok: `make_tiktok_frames.py`
- Preflight tipográfico: `check_fonts.py`

Si hay contradicción: el kit editorial manda en diálogo/caption/mecánica; `character_lector_a_v1.json` manda en paleta/geometría del personaje; los scene JSON son la transcripción ejecutable de cada episodio. STOP si una de esas tres superficies discrepa.

# tools/interactive_story — IG-09 «La puerta 4B»

Objetivo: tener técnicamente preparadas todas las ramas antes de publicar, pero NO comprometer cuatro semanas de calendario por adelantado. El público elige A/B y las dos ramas están renderizadas; la continuación depende del gate de participación de EP1.

Fuente editorial: Drive `IG-09 — La puerta 4B — ficción interactiva A/B en 4 semanas`, id `1rT3jZC6dC1KcF7WD6xIV0bFvJYistTHf04AYOu3AlPQ`.

## 1. Dependencias

```bash
python -m pip install playwright
python -m playwright install chromium
```

No usa IA ni API.

Fuentes auditadas obligatorias:
- Playfair Display 700;
- Inter 600/700/800.

Se cargan desde Google Fonts. La máquina de producción debe tener acceso a `fonts.googleapis.com` y `fonts.gstatic.com`. El renderer verifica las cuatro variantes antes de cada captura y aborta con `IG09_RENDER_BLOCKED` si falta alguna. No se permite continuar con Georgia/Arial como fallback silencioso.

## 2. Descargar exactamente 4 imágenes

Crear:

```text
assets/interactive_story/
  ep1_door.jpg
  ep2_old_photo.jpg
  ep3_station.jpg
  ep4_album.jpg
```

Fuentes:

`ep1_door.jpg`
https://www.pexels.com/photo/door-2524160/

`ep2_old_photo.jpg`
https://www.pexels.com/photo/old-photograph-lying-on-desk-9258338/

`ep3_station.jpg`
https://www.pexels.com/photo/photo-of-empty-train-station-platform-1536302/

`ep4_album.jpg`
https://www.pexels.com/photo/hand-on-photo-album-on-desk-10272685/

Licencia:
https://www.pexels.com/es-es/license/

No sustituir por imágenes de Google. Si una desaparece, usar únicamente los backups documentados en el kit de Drive y actualizar `ig09_story.json`.

## 3. Render completo

```bash
python tools/interactive_story/render_interactive_story.py \
  tools/interactive_story/ig09_story.json \
  --assets assets/interactive_story \
  --out build/ig09
```

El renderer falla de forma explícita si falta cualquier asset o si las fuentes auditadas no cargan.

Genera:

```text
build/ig09/
  ig09_ep01/
    ig09_ep01_s1.png
    ig09_ep01_s2.png
    ig09_ep01_s3.png
    ig09_ep01_s4.png
  ig09_ep02/
    ig09_ep02_s1_A.png
    ig09_ep02_s1_B.png
    ig09_ep02_s2.png
    ig09_ep02_s3.png
    ig09_ep02_s4.png
  ig09_ep03/
    ig09_ep03_s1_A.png
    ig09_ep03_s1_B.png
    ig09_ep03_s2.png
    ig09_ep03_s3.png
    ig09_ep03_s4.png
  ig09_ep04/
    ig09_ep04_s1_A.png
    ig09_ep04_s1_B.png
    ig09_ep04_s2.png
    ig09_ep04_s3.png
    ig09_ep04_s4.png
  manifest_render.json
```

Preparar las ramas no obliga a publicarlas. Sirve para que, si EP1 funciona, la historia pueda continuar sin improvisar.

## 4. Gate visual

Revisar primero EP1 y una variante A/B de EP2.

Debe pasar:
- texto legible a ancho de móvil;
- foto sigue pareciendo foto, no póster generado;
- overlay no aplasta por completo la imagen;
- `A/B` parece interfaz editorial simple, no gamificación infantil;
- Playfair Display e Inter son las familias realmente cargadas;
- `NO LA USES AQUÍ.` aparece en Inter 800, separado del relato en Playfair, tal como fija el kit;
- la firma no llama la atención;
- ningún texto toca borde;
- no aparece barra, guion o placeholder técnico;
- las comillas españolas y tildes están correctas.

Si aparece `IG09_RENDER_BLOCKED`, resolver la carga de fuentes y repetir. No aceptar una exportación con fallback del sistema.

## 5. Gate DE PARTICIPACIÓN — obligatorio tras EP1

Motivo: datos propios de Instagram revisados el 18/08/2026 muestran que los carruseles seriales recientes de Alicia tuvieron solo 5–14 de reach orgánico por pieza y 0 guardados/comentarios. No son una comparación idéntica con IG-09, pero sí una señal suficiente para NO comprometer cuatro episodios antes de demostrar que la interacción A/B funciona en esta cuenta.

Publicar SOLO EP1 inicialmente.

Leer a 72 h:
- votos A/B válidos;
- comentarios totales;
- compartidos;
- guardados;
- reach.

`CONTINÚA` si hay **≥2 votos A/B válidos**. El mecanismo central es la elección; dos personas reales ya justifican probar EP2 con el tamaño actual de la cuenta.

`STOP` si hay 0–1 voto válido a 72 h. No publicar EP2 “para ver si arranca después”. Archivar las ramas restantes como material preparado, no como deuda de calendario.

El reach NO rescata por sí solo el piloto: si 100 personas lo ven y nadie elige, falló el mecanismo que estábamos probando.

Si continúa, aplicar el mismo criterio después de EP2: ≥2 votos válidos para publicar EP3. Igual para EP3→EP4.

## 6. Error → corrección

### El texto tapa demasiado la foto
Recortar palabras antes que bajar fuente. No mover texto a una zona incoherente solo para “salvar” el asset.

### La foto inset parece una foto histórica auténtica
Añadir/agrandar el pie `PASILLO · 1987` / `ANDÉN · SIN FECHA` y mantener el lenguaje de ficción. Nunca afirmar en caption que es documento real.

### Las opciones parecen botones de app
Reducir borde y fondo; mantener A/B como tipografía editorial. No añadir iconos, flechas ni emojis.

### Falta espacio en una rama
Recortar redacción de ESA rama en el JSON. No reducir todas las fuentes de la serie.

### La imagen Pexels no descarga en la misma proporción esperada
No deformar. `background-size: cover` hace crop automático. Ajustar una propiedad futura `background-position` si hace falta; documentar el cambio.

## 7. Seleccionar rama después del voto

No editar texto.

EP2:
- gana A → usar `ig09_ep02_s1_A.png`
- gana B → usar `ig09_ep02_s1_B.png`

EP3: igual.
EP4: igual.

Slides 2–4 son comunes. El antiguo `sobre / consigna` del archivo maestro editorial ya está resuelto en el JSON como texto neutro: `Dentro aparece una fotografía.` No hay que editar esa slide según el voto.

## 8. Conteo

Cierre: domingo 20:00 Europe/Madrid.

Válido:
- comentario que empieza claramente por A/B;
- o nombra de forma inequívoca la acción.

Una cuenta = un voto. Primera elección manda.

Empate: gana la opción cuyo primer voto válido apareció antes cronológicamente. No elegir manualmente “la mejor rama”.

Registrar en:

```text
results/ig09_ep01.md
results/ig09_ep02.md
results/ig09_ep03.md
```

Formato:

```text
A=0
B=0
ganador=A|B
cierre=YYYY-MM-DDT20:00:00+01:00
notas=
```

## 9. Publicación

EP1 sí puede programarse de antemano cuando llegue su turno de piloto.

EP2–4: NO programar antes de superar el gate de participación del episodio anterior. Después del recuento, seleccionar el PNG de apertura correspondiente y publicar solo si el piloto sigue vivo.

Caption/hashtags: copiar del kit Drive, no desde memoria.

## 10. Por qué no hay generador de imágenes

Esta historia funciona mejor con:
- puerta real;
- fotografía real;
- estación real;
- álbum real;
- ficción construida mediante texto/composición.

Añadir IA no resuelve un hueco. Solo introduciría una señal visual artificial y un nuevo punto de fallo.

## 11. Versionado

`IG-09_LA_PUERTA_4B_v1` queda congelada una vez publicado EP1.

No reescribir una rama después de ver qué opción gana. Si surge una mejora, guardarla para otra historia. Esa disciplina evita que la “elección” del público sea decorativa.

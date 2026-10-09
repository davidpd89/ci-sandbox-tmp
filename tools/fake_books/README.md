# tools/fake_books — IG-14 «Libros que no existen»

Kit editorial: Drive `IG-14 — Libros que no existen — 6 carruseles tipográficos listos`.

Este sistema genera 12 PNG (6 portadas imaginarias + 6 contraportadas) sin IA, stock, logos, ISBN ni mockups. Son piezas tipográficas; no representan libros reales existentes.

## 1. Dependencias

```bash
python -m pip install pillow fonttools
```

Además, la máquina de producción debe tener `fontconfig`/`fc-match` y estos estilos instalados localmente:
- Playfair Display ExtraBold = peso 800;
- Inter SemiBold = peso 600;
- Inter Medium = peso 500.

El kit de Drive y el renderer usan esos tres pesos. No hay Georgia, Arial, DejaVu, Liberation ni otro fallback.

El renderer comprueba dos cosas antes de exportar:
1. que fontconfig resuelva la familia correcta;
2. que resuelva también el ESTILO/peso correcto, no solo una variante cualquiera de esa familia.

Si falla, termina con `IG14_RENDER_BLOCKED`.

No incluir ni distribuir archivos de fuentes en el repositorio.

## 2. Fuentes de verdad

La producción tiene dos ficheros complementarios, ambos obligatorios:

- `ig14_manifest.json` → copy VISUAL, paleta, símbolo y estructura gráfica;
- `ig14_social_copy.json` → caption, hashtags y comentario fijado de los seis episodios.

No volver a Drive a copiar captions a mano el día de producción. Drive conserva explicación, evidencia y contexto; los dos JSON son la transcripción ejecutable.

Los IDs `ig14_01…ig14_06` deben coincidir exactamente y en el mismo orden en ambos archivos. CI bloquea divergencias.

## 3. Render

```bash
python tools/fake_books/render_fake_books.py \
  tools/fake_books/ig14_manifest.json \
  --out build/ig14
```

Salida:

```text
ig14_01_s1.png
ig14_01_s2.png
...
ig14_06_s2.png
ig14_render_manifest.json
```

El manifest de render debe indicar:
- `font_policy: Playfair Display 800 + Inter 600/500; no fallback`;
- las 12 rutas de salida;
- `status: RENDERED_NOT_SCHEDULED`.

El renderer no toca Metricool.

## 4. Overflow = STOP

El sistema intenta ajustar cada bloque dentro de una caja cerrada, pero no exporta “lo que salga” si el tamaño mínimo sigue desbordando.

`IG14_RENDER_BLOCKED` si:
- un título no cabe ni al mínimo autorizado;
- el subtítulo invade la zona del símbolo;
- una línea de `INCLUYE` rebasa el ancho;
- el listado invade el pie de marca;
- la slide final no mide 1080×1350.

Corregir manifest/layout y volver a renderizar. No recortar, encoger horizontalmente ni retocar el PNG después.

## 5. Gate visual

Abrir los 12 PNG en cuadrícula y después cada pareja a tamaño móvil.

Debe cumplirse:
- las seis piezas parecen la misma colección sin parecer clones;
- `EDICIÓN IMAGINARIA` se lee sin dominar;
- `NO EXISTE. DE MOMENTO.` se entiende sin ambigüedad;
- nadie puede confundir la pieza con un lanzamiento real;
- ningún símbolo parece logo de una editorial/marca;
- título > subtítulo > símbolo > pie: jerarquía clara;
- el título se entiende en menos de un segundo;
- slide 2 se puede leer en <6 segundos;
- no hay fuente minúscula para “hacer caber” el texto;
- no hay decoración añadida por miedo al espacio vacío.

## 6. Gate de voz

La gracia debe estar ya en el título/contraportada. El caption no explica por qué es gracioso.

Comprobar:
- una sola frase de caption;
- cero pregunta automática;
- cero primera persona inventada;
- cero `Etiqueta a...`;
- cero comentario fijado extra: `first_comment` permanece `null` en esta temporada;
- al leer los seis captions seguidos, no forman una plantilla de «frase ingeniosa + moraleja»;
- hashtags describen comunidad/situación, no intentan “hacer viral” la pieza.

## 7. Si un título no cabe

No reducir por debajo del mínimo cerrado por el renderer.

Orden de corrección:
1. comprobar salto de línea previsto en JSON;
2. revisar si el bloque editorial puede ganar espacio sin romper el sistema;
3. si sigue sin caber, reabrir el kit: probablemente el título necesita edición.

No condensar tipografía horizontalmente y no modificar solo una PNG.

## 8. Si parece demasiado Canva

No añadir fotografía.

Revisar:
- símbolo demasiado complejo → simplificar en el renderer para toda la familia si el problema se repite;
- demasiados tamaños → volver a 3 niveles;
- fondo con textura → quitar;
- sombra → quitar;
- marco decorativo → quitar.

La marca de esta familia es austeridad + título hiperconcreto.

## 9. Si parece una portada real engañosa

El problema no se arregla con letra pequeña.

Comprobar primero que:
- slide 1 dice exactamente `EDICIÓN IMAGINARIA`;
- slide 2 dice exactamente `NO EXISTE. DE MOMENTO.`;
- no hay ISBN, editorial ficticia, precio, estrellas, reseña ni sello de venta;
- `brand_line` conserva `ARCHIVO DE PROBLEMAS DE LECTORES · AUTORA DEMO DÍAZ`.

Si aun así parece un producto real, FAIL visual y revisar el sistema completo antes de producir el lote.

## 10. Copy social

Fuente ejecutable:
`tools/fake_books/ig14_social_copy.json`.

No generar captions desde el título el día de producción y no copiar una versión antigua de Drive.

No programar nada desde este directorio. Las fechas del kit son propuestas históricas y deben revalidarse contra planner/Best Time; cualquier programación/cambio en Metricool requiere autorización expresa de David.

## 11. Métrica

El objetivo es `share/save`, no like.

Si un diseño recibe likes y casi ningún share/save:
- no cambiar paleta;
- no añadir una tercera slide;
- no poner pregunta;
- revisar en futura temporada si el problema descrito era suficientemente reconocible.

## 12. Versionado

`IG-14_LIBROS_QUE_NO_EXISTEN_v1` se congela al publicar el primer post.

Una temporada 2 puede añadir seis títulos nuevos, pero:
- conserva disclosures;
- conserva la familia de símbolos;
- puede rotar paletas;
- NO copia la sintaxis exacta del título ganador seis veces.

Referencias generales de voz/prompts/fuentes:
- `01_Estrategia/Guia de marca y contenidos.md`
- `01_Estrategia/PROMPTS_PRODUCCION_HUMANA_2026-08-20.md`
- `01_Estrategia/REFERENCIAS_INSPIRACION_VERIFICADAS_2026-08-20.md`

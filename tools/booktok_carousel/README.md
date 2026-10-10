# IG-01 - BookTok verificable

Sistema ejecutable para la carpeta:

`nuevas ideas rrss/02 - Instagram/IG-01 - SISTEMA carruseles BookTok verificables`

El objetivo es crear carruseles 1080x1350 sobre libros verificables: portadas reales, fondos suaves visibles, copy editorial y botones sociales de la marca.

## Estado aprobado

`ig01_01` es la base visual aprobada. Mantener este patron:

- fondo fotografico suave, visible y variado; nunca negro plano;
- portadas oficiales completas, sin deformar ni recortar titulo/autor;
- marca superior izquierda: `DAVID PORTO DIAZ`;
- esquina superior derecha: contador `01/06`, `02/06`, etc. y debajo `davidportodiaz.com`;
- abajo izquierda: `DESLIZA ->` salvo la ultima, donde puede cambiar a `GUARDA`;
- abajo derecha: iconos/acciones de like, comenta, guarda y envia;
- textos breves, legibles en movil, sin bloques tipo PowerPoint;
- nada de precios, estrellas, falsa opinion personal ni "top actual" si no esta verificado.

## Archivos clave

- `ig01_manifest.json`: contenido, fuentes, portadas, fondos, captions y hashtags.
- `fetch_assets.py`: descarga portadas oficiales y fondos declarados.
- `render_booktok.py`: genera los PNG finales.
- `export_review.py`: copia la publicacion renderizada a `nuevas ideas rrss` con fuentes, output, caption y QA.

No retocar PNG a mano. Si algo sale mal, corregir manifest o renderer y volver a generar.

## Dependencias

Python usado en este equipo:

```powershell
& 'C:\Program Files\LibreOffice\program\python.exe'
```

Paquetes necesarios:

```powershell
& 'C:\Program Files\LibreOffice\program\python.exe' -m pip install playwright pillow requests beautifulsoup4
```

El render usa Playwright con navegador del sistema cuando esta disponible. No abrir navegadores nuevos para este flujo si el navegador normal del usuario ya esta configurado.

## Crear o actualizar una publicacion

1. Editar `ig01_manifest.json`.

Cada post debe tener:

- `id`: por ejemplo `ig01_02`;
- `review_slug`: nombre exacto de la carpeta revisable;
- `caption` y `hashtags`;
- `slides` con `cover`, `covers`, `background`, `title`, `body`, `label` o `cta`.

2. Descargar assets declarados.

```powershell
& 'C:\Program Files\LibreOffice\program\python.exe' tools/booktok_carousel/fetch_assets.py tools/booktok_carousel/ig01_manifest.json --out build/ig01/assets --all
```

El downloader guarda tambien sidecars `.source.json`. Si una fuente no coincide con el libro esperado, hay que parar y corregir la fuente; no sustituir por una portada parecida.

3. Renderizar el post.

```powershell
& 'C:\Program Files\LibreOffice\program\python.exe' tools/booktok_carousel/render_booktok.py tools/booktok_carousel/ig01_manifest.json --assets build/ig01/assets --out build/ig01 --post ig01_02
```

Para renderizar todos:

```powershell
& 'C:\Program Files\LibreOffice\program\python.exe' tools/booktok_carousel/render_booktok.py tools/booktok_carousel/ig01_manifest.json --assets build/ig01/assets --out build/ig01
```

4. Exportar a carpeta revisable.

```powershell
& 'C:\Program Files\LibreOffice\program\python.exe' tools/booktok_carousel/export_review.py tools/booktok_carousel/ig01_manifest.json --assets build/ig01/assets --build build/ig01 --post ig01_02
```

Esto crea/actualiza:

- `01_PUBLICACIONES/<review_slug>/04_OUTPUT/01.png...`;
- `01_PUBLICACIONES/<review_slug>/04_OUTPUT/contact_sheet.jpg`;
- `01_PUBLICACIONES/<review_slug>/01_FUENTES/`;
- `01_PUBLICACIONES/<review_slug>/caption.txt`;
- `05_QA/IG-01-XX_contact_sheet.jpg`.

## Fondos suaves

Los fondos disponibles estan en `soft_backgrounds`.

Si una slide no declara `background`, el renderer usa `default_soft_background_cycle` para evitar el negro plano. Aun asi, para posts importantes conviene asignar fondo por slide en el manifest.

Regla visual: el fondo debe notarse, pero no competir con portada ni texto.

## Checklist de calidad

Antes de dar un post por cerrado:

- revisar `contact_sheet.jpg` completo;
- confirmar que no se repite la misma foto en todas las slides;
- confirmar `davidportodiaz.com` bajo el contador;
- confirmar botones inferiores e indicador `DESLIZA ->`;
- comprobar que cada portada corresponde exactamente al libro citado;
- leer caption y hashtags;
- mirar que el texto importante sea blanco/grande y lo auxiliar vaya en acento o menor jerarquia;
- no publicar si falta una fuente o se ha usado una imagen de relleno sin trazabilidad.

## Bloqueos

STOP si:

- una portada no es oficial o no corresponde a la edicion;
- un fondo queda negro o demasiado protagonista;
- el render corta textos, portadas o botones;
- el copy parece IA generica;
- se introduce una opinion personal de David no documentada;
- se mezclan frases de libros, explicaciones de autores o poesia dentro de este sistema.

Para otros formatos usar sus sistemas separados: IG-FRASES, IG-POESIA, IG-02, Facebook o TikTok.

# Pipeline de media y assets para nueve redes — PR #28

Investigación y prototipo offline, **10/10/2026**. Base: `research/public-reuse-parent`.
No se ejecutan acciones en redes. No se copiaron bytes/código ajenos; se consume la
dependencia pública Pillow ya instalada. El mecanismo no sustituye QA editorial.

## Hueco observado en código real

- En `tools/content_queue.py`, `_parse_media_entries` extrae ruta/ALT y solo
  comprueba `os.path.isfile`; `pending_parse_issues` no decodifica medios.
- `tools/content_publisher.py::blockers_of` (anterior) aceptaba archivos
  existentes de cualquier contenido, incluso un `.jpg` corrupto, antes del
  adaptador de publicación.
- Contrastado con **repositorio privado**
  `davidpd89/rrss-davidporto-CODE` rama `integracion/crecimiento-2026-10`:
  los dos módulos conservan este comportamiento y `requirements-ci.txt`
  ya incluye `Pillow>=10,<12`. La preparación de Metricool
  `nuevas ideas rrss/02 — Instagram/00_PLANIFICACION_METRICOOL/preparar_media_publica_metricool.py`
  usa Pillow al convertir en PNG, pero no valida antes de publicar ni protege
  en el banco multired. **No se trasladaron fotos, credenciales ni datos del privado**.
- `tools/run_content_queue.py` en el espejo es de **solo informe**;
  `tools/content_publisher.py` dispone de un flujo aparte. Este cambio se
  aplica a `blockers_of` y al API standalone; no convierte el informe en
  publicador ni modifica colas WEB/API/MOBILE.

## Evaluación de opciones públicas verificadas

Los SHAs fijan exactamente la revisión consultada. Licencias según archivos
de proyecto (cuando la clasificación automática aparece `NOASSERTION`,
se consulta `LICENSE`/`pyproject.toml`).

| Proyecto / revisión inmutable | Licencia / actividad | Compatibilidad / coste | Decisión |
|---|---|---|---|
| [Pillow @8796d567](https://github.com/python-pillow/Pillow/tree/8796d5676b67dce5332a32a2e876f6b361358fbe) | MIT-CMU según LICENSE/pyproject, commit 10/10/2026 | Windows/Linux, Python 3.11; **ya presente** | **Reutilizar** API `Image.open`, `ImageOps.exif_transpose`, `thumbnail`, compresión, decodificación |
| [ImageHash @be8a26d](https://github.com/JohannesBuchner/imagehash/tree/be8a26d82c89a2b314823597e1efb9172c4f9326) | BSD-2-Clause, commit 05/10/2026 | Python, requiere nuevas dependencias NumPy/SciPy/PyWavelets según algoritmo | No instalar para una advertencia opcional: dHash básico implementado en ~10 líneas sobre Pillow; si necesita catálogo persistente, evaluar ImageHash |
| [imageio-ffmpeg @ae47d80](https://github.com/imageio/imageio-ffmpeg/tree/ae47d8028c237ca5507ceef1b843ee427b442887) | BSD-2-Clause, commit 16/01/2025 | Windows/Linux y 3.11, distribuye binarios grandes FFmpeg | No incluir binarios en preflight; `ffprobe` instalado en host es suficiente para inspección local |
| [pymediainfo @daf3596](https://github.com/sbraz/pymediainfo/tree/daf3596e33686c17639d4bd1a4f560983f24ea35) | Revisar LICENSE antes de vendorización; GitHub no resuelve SPDX automáticamente; último commit 12/02/2025 | Windows/Linux 3.11; rueda con librería nativa | No adoptar: incorporación nativa innecesaria para lectura básica de tracks |

**Licencias:** ninguna fuente se ha copiado al repositorio. Pillow MIT-CMU
puede reutilizarse como dependencia con sus avisos mantenidos en su paquete.
El código propio no es un trasplante de ImageHash ni FFmpeg. No añadir una
segunda librería por un control que ya cubre Pillow.

## Contrato implantado

`tools/media_preflight.py`: `inspect_asset(path, network, alt, root, max_bytes)`
devuelve `{network, filename, kind, errors, warnings, metadata}`.
Errores = medio inexistente, ruta fuera de root/symlink escapado, fichero vacío,
extension no reconocida, fichero de imagen malformado, ALT ausente para imagen,
formato/extension incompatible, animación sin tratamiento, límites de bytes
**conocidos o configurados**, vídeo sin análisis, codecs/contenedor de video
no compatibles con **perfil de salida común** H.264/AAC/MP4.

Advertencias (no bloqueantes): resolución baja, aspecto fuera de relación
preferida y orientación EXIF. Las relaciones `PREFERRED_RATIOS` son guías
editoriales configurables, **no** límites oficiales por red. El ALT se exige
para cada imagen pero la calidad semántica y adecuación al español requieren
revisión humana. No se infieren autores, veracidad, derechos ni procedencia
fotográfica por análisis de píxeles.

**Fuente de límite:** Bluesky anunció la ampliación de 1 a **2 MB** en
abril-junio de 2026; lexicon [`app.bsky.embed.images` @d8801e2](https://github.com/bluesky-social/atproto/blob/d8801e2a17fe7062b7aa674475b384ead7518a17/lexicons/app/bsky/embed/images.json)
(`maxSize: 2000000`). No mantener el límite obsoleto de 1 MB.
Resto de redes: **sin límite inventado**; `max_bytes` es inyectable por
adaptador/instancia. Los perfiles pueden necesitar comprobación por operación,
endpoint o servidor. Un video no verificado por faltar ffprobe se marca como
**incompatible/no verificado**, no como aprobado.

`inspect_item` reutiliza el banco de `content_queue` y alimenta
`content_publisher.blockers_of`, ejecutado por `eligible` antes del
adaptador. Es lectura pura: no modifica texto, fichas, colas ni archivos.
Las tres colas operativas no cambian de prioridad ni volumen.

`prepare_image(source, output)` **opt-in**, no ejecutado automáticamente en
publicación: normaliza EXIF, contiene sin recorte ni upscale, convierte a
JPEG/PNG, quita metadatos de exportación y preserva proporciones y originales.
`thumbnail` genera vista previa a ruta **distinta** y `find_duplicates`
propone duplicados por SHA-256 y dHash; son **avisos**, nunca borrados ni
decisiones automáticas de creatividad. dHash no distingue bien imágenes
uniformes y su distancia no prueba igualdad semántica.

## Ejecución reproducible — offline

```powershell
py -3.11 -m pip install -r requirements-ci.txt
py -3.11 -m pytest -q tests/test_media_preflight.py tests/test_content_publisher.py tests/test_content_queue_offline.py
py -3.11 tools/media_preflight.py instagram "ruta\\foto.jpg" --alt "Persona leyendo junto a la ventana"
```

Si se inspecciona vídeo, `ffprobe` debe estar disponible en PATH; la suite
de prueba lo simula y **no invoca FFmpeg real**. Esta rama no ejecuta
publicaciones, navegadores, cuentas, ni uploads. Las imágenes de prueba se
generan íntegramente en `TemporaryDirectory`.

## Antes / después y aceptación

| Caso offline | Antes | Ahora |
|---|---|---|
| JPG con bytes falsos y archivo existente | pasa control de existencia | `image_corrupt` impide elegibilidad |
| Foto JPEG sana + ALT | pasa | pasa con hash, resolución y ratio |
| Archivo de vídeo sin probe | no inspeccionado | `video_unverified`; evita aprobación falsa |
| Persona en foto vertical | sin preparación común | conversión explícita conserva ratio y original |
| Duplicado binario | no detectado | SHA-256 identifica, no borra |
| Dos imágenes visualmente similares | no detectadas | aviso dHash orientativo |
| Acceso fuera de carpeta por symlink | `_safe_media_path` protege al parsear | comprobación adicional en el preflight |

Pruebas: `tests/test_media_preflight.py` + suite de regresión del publicador y
cola. La CI de GitHub, si está habilitada, debe confirmar Windows/Ubuntu y
tests completos. **Canario supervisado pendiente** en máquina real; las
pruebas sintéticas no certifican códecs, endpoints, Android ni Edge en vivo.

## Auditoría adversarial (segunda pasada)

1. Se detectó un supuesto inicial **incorrecto** (1 MB de Bluesky), refutado
   por el lexicon actual: corregido a 2 MB con SHA de referencia.
2. Una extensión `.jpg` podría contener PNG válido: ahora genera
   `image_extension` para evitar MIME/extension contradictorios.
3. Un preflight aislado sin adaptador no impediría publicar: se conectó con
   `blockers_of`, **antes** de las 3 clases de ejecutores.
4. Restricciones de aspecto eran falsos bloqueos para fotografías originales:
   solo advertencias. No se recorta automáticamente.
5. Los duplicados perceptuales no implican misma foto ni copy: solo reportan
   candidatos, nunca eliminan.

## Integración, mantenimiento y reversibilidad

Para retirar: revertir import y `reasons.extend(...inspect_item...)` en
`tools/content_publisher.py`; eliminar módulo y tests. No hay migraciones,
nuevas tablas, flags, jobs, credenciales, estados ni cambios de esquema.

Limitaciones: compatible a nivel de Python 3.11/Pillow, pero no se ha probado
Windows vivo, máquina móvil, Edge, metadatos de audio complejos, múltiples
instancias Mastodon, fotogramas corruptos intermedios ni aceptación real de
cada API. La inspección de video confía en metadatos de ffprobe; no es una
decodificación integral de todos los frames. La calidad y tono humano
deben seguir en revisión editorial manual. Antes de una integración privada,
Claude debe verificar los publicadores paralelos que omitan `blockers_of`
y conectar el mismo contrato en esos puntos si corresponde, sin duplicarlo.

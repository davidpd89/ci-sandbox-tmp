# QA en puntos de salida finales — PR #106

Fecha de investigación: 10/10/2026. Rama `research/voice-output-finalization-parity`.
El auditor `tools/spanish_voice_quality.py` de #79 ya se encuentra en la base sincronizada `737fc011` y en el repositorio oficial; #79 se cerró sin merge formal.
La PR #106 **no trae una copia** del auditor: importa `spanish_voice_quality.audit` en el último preflight.
La actualización sobre la base actual incorpora el módulo real. Si falta durante el despliegue, cualquier llamada nueva a QA falla
sin enviar. El código original de esta rama puede ejecutarse sin él mientras no pase por salidas auditadas.

## Problema y alcance comprobado

- Espejo `ci-sandbox-tmp`, HEAD inicial `4ea955d05811c288e688f9a22f03dcfad54e2557`: no había adaptador final.
- #79, HEAD leído `b09e5dcf50daba1b552e4d8da939c69741c2258d`: `reply_writer` audita en construcción;
  `content_publisher.run` audita las fichas de Bluesky, Mastodon, Threads, X,
  Facebook, Instagram y Pinterest. No garantiza ejecutores alternativos.
- Oficial privado, rama `integracion/crecimiento-2026-10`, solo lectura:
  `tools/content_publisher.py` blob `f5120bb2141f29e88549497c09ec438b02ebc22d`,
  `tools/reddit_publish.py` blob `51b068459a73c9a91cd0a4daa760c01a556cad9e`,
  `tools/tiktok_mobile_interact.py` blob `212a514a452ba52d5844a02588499eb0d421f8fa`.
  No se extrajeron datos ni copiaron módulos privados.
- El código ya existente que hace límites, guardas de edad, origen GPT, preflight de sesión,
  deduplicación, contadores e intenciones remotas permanece intacto.

## Inventario: 'conectado' significa en ESTA PR + #79; no implica canario en vivo

| Red | WEB | API | MOBILE | Responsable/punto final |
|---|---|---|---|---|
| X | **conectado** banco, replies/citas y fichas #79 | pendiente (API sin ruta acreditada) | no aplicable verificado | `x_bank_publish.main`, `x_execute.run_plan`, `content_publisher.run` |
| Threads | **conectado** replies web y fichas #79 | **conectado** replies API | no aplicable verificado | `threads_execute.run_plan` + `content_publisher.run` |
| Facebook | **conectado** comentarios propios/externos y fichas #79 | pendiente (otras salidas API directas) | no aplicable verificado | `facebook_execute.run_plan` + `content_publisher.run` |
| Pinterest | **conectado** directo, pin diario, fichas #79 | pendiente (lectores API, sin publicación auditada) | no aplicable verificado | `pinterest_publish.publish_pin` antes de CDP; el preflight final revisa título, descripción y ALT aunque exista aviso previo |
| Reddit | **conectado** banco/post/comentario/reply | pendiente (sin ruta API acreditada) | no aplicable verificado | `reddit_publish.publish_post` antes de intención/clic, `reddit_interact.comment`, `reddit_comments.reply_in_thread` |
| Bluesky | no aplicable verificado a publicaciones | **conectado** replies/citas y fichas #79 | no aplicable verificado | `bluesky_execute.run_plan` + `content_publisher.run` |
| Mastodon | no aplicable verificado a publicaciones | **conectado** replies y fichas #79 | no aplicable verificado | `mastodon_execute._do` + `content_publisher.run` |
| TikTok | no aplicable en ruta móvil actual | pendiente (sin publicación API acreditada) | **conectado** comentarios | `TikTokMobileAdapter.comment` antes de abrir destino; constructor `reply_writer` separado |
| Instagram | **conectado** comentarios WEB y fichas #79 | pendiente (salidas nativas API sin trazar) | **conectado** comentarios con `RRSS_INSTAGRAM_BACKEND=mobile`; pendiente publicación humana sin ejecutor | `instagram_execute.run_plan` (cola según backend), `content_publisher.run` + informe manual |

Toda ficha que se muestra como **pendiente manual** en `content_queue_alert.main` se revisa por
`inspect_fields(..., queue=None)`: se desconoce su transporte final, y por tanto **no** se
finge que es WEB ni se afirma que se ha capturado un clic manual. Esta es solo una revisión editorial
previa al informe; nunca convierte un recordatorio en un publicador.

La cobertura real pendiente está enumerada, no se infiere de que el auditor acepte nueve redes.
Se integraron seis despachadores adicionales (`x_execute`, `bluesky_execute`,
`mastodon_execute`, `threads_execute`, `facebook_execute`, `instagram_execute`)
sin modificar los clientes de bajo nivel ni las plantillas de vídeo. Los comentarios que nacen en
`reply_writer` pueden recibir una revisión en generación y otra **final en ejecución**
si atraviesan las rutas directas instrumentadas: son fases distintas, no dos llamadas durante
una misma construcción. En Pinterest hay dos fases diferentes: el aviso editorial de #79 y el preflight
final que audita título, descripción y ALT. Es deliberado porque el adaptador
`advisory()` de #79 devuelve `[]` ante fallos técnicos; no acredita validación efectiva.

## Decisión y contrato técnico

`voice_output_finalization.inspect(text, network, queue)` acepta la cadena original y devuelve
los findings sin modificar la entrada. Un `hint`, `warning` o `error` editorial **no**
impide el envío; solo se registran códigos y etiquetas red/cola, nunca el cuerpo, usuario ni URL.
Los campos independientes (título, descripción, ALT, cuerpo) usan `inspect_fields`.
Para salidas automáticas la cola es explícita WEB/API/MOBILE. Para un aviso manual es `None`.

Si hay excepción técnica, falta el módulo o se altera `schema_version=1`, red/cola, `changed=False` o `findings` esperado,
`VoicePreflightUnavailable` impide alcanzar el envío. Esta distinción preserva la
política de **no bloquear por estilo**, pero evita considerar diagnóstico inexistente un OK.
No hay reintentos de acción ni autoedición de tildes, títulos, citas, hashtags, URLs o
saltos de línea. Se mantiene la procedencia es-ES de #79.

## Alternativas públicas estudiadas: SHA fijado y decisión

| Repositorio/commit comprobado a 10/10/2026 | Licencia SPDX | Actividad y compatibilidad | Resolución |
|---|---|---|---|
| [barrust/pyspellchecker](https://github.com/barrust/pyspellchecker/commit/f72172c4ddb3d1c3464cf500cc2420a4831a2b55) | MIT | commit 23/07/2026; Python >=3.10, 3.11 compatible, sin Windows específico requerido; ya usado opcionalmente por #79 | Reutilización indirecta vía auditor, sin segundo motor |
| [jxmorris12/language_tool_python](https://github.com/jxmorris12/language_tool_python/commit/6c935da8ef739b22d62c13cd682cb9a2922e4f98) | GPL-3.0-only | commit 03/10/2026, Python 3.11 en metadata; JVM/proceso externo para comprobación completa | No añadir JVM/red/latencia ni duplicar motor |
| [codespell-project/codespell](https://github.com/codespell-project/codespell/commit/54cc31bc819f4af008b58a29ab16b5173dc1ff3b) | GPL-2.0-only | commit 09/10/2026; Windows y Python 3.11 declarados | Orientado a faltas comunes en ficheros/código, no a español conversacional con citas |

## Licencias y procedencia

Fuente primaria: https://github.com/barrust/pyspellchecker/commit/f72172c4ddb3d1c3464cf500cc2420a4831a2b55
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/barrust/pyspellchecker/commit/f72172c4ddb3d1c3464cf500cc2420a4831a2b55

Los campos anteriores acreditan una **alternativa evaluada**, no código externo
copiado a la PR #106. El adaptador nuevo es original y solo importa en ejecución
la API propia de la PR #79. Los proyectos GPL de la tabla son comparables, no
código derivado ni dependencia incorporada.

La solución seleccionada es la menor reutilización permitida: consumir la API estable
de #79 (stdlib, sin dependencias nuevas para este puente). No se incorporó código de terceros;
se mantienen licencias y atribuciones en enlaces de investigación. Metadatos consultados en
GitHub y PyPI, y decisión contrastada con `docs/research/spanish-voice-locale-quality.md` de #79.

## Pruebas, métricas y despliegue

```sh
python -m compileall -q tools/voice_output_finalization.py tools/x_bank_publish.py tools/reddit_publish.py tools/reddit_comments.py tools/reddit_interact.py tools/tiktok_mobile_interact.py tools/pinterest_publish.py tools/content_publisher.py tools/content_queue_alert.py tools/bluesky_execute.py tools/mastodon_execute.py tools/threads_execute.py tools/facebook_execute.py tools/instagram_execute.py tools/x_execute.py
python -m unittest discover -s tests -p test_voice_output_finalization.py -v
```

Resultado contrastado en el HEAD `bbb1256aef78d1828fb221e3542530f7d1a9b958`:
[CI offline](https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38023070577),
La revisión anterior pasó 25/25. La base sincronizada y los nuevos tests de integración superan 28/28 en Ubuntu y Windows Python 3.11, CI: https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38049627273.
El runner Windows necesita `tzdata` (ya consta en `requirements-ci.txt`);
se instala en el workflow aislado sin contactar con cuentas sociales.

En CI `.github/workflows/voice-output-finalization.yml` ejecuta tests offline
en Windows y Ubuntu, Python 3.11, sin token de red social ni acciones reales.
Los tests de fallo usan dobles del auditor; además, hay una prueba con el auditor real presente en la base y pruebas con seis publicadores falsos para demostrar bloqueo técnico, no mutación y auditoría por campo.

Métrica de cobertura documentada antes/después:
- Antes: 0 de los **13 grupos de salida adicional** instrumentados aquí con QA final:
  X banco, Reddit banco, Reddit comentario directo, Reddit reply incrustado, TikTok MOBILE,
  Pinterest directo (incluye pin diario), aviso de ficha manual, y seis ejecutores
  de salida (X, Bluesky, Mastodon, Threads, Facebook e Instagram).
- Después: **13/13 grupos con llamada explícita comprobable** más cobertura parcial de #79,
  **solo cuando el módulo esté disponible**. También hay gate final para seis publicadores automáticos, además del Pinterest directo. Esto mide puntos de inserción, no nueve redes
  plenamente integradas ni tasa real de detección.
- Contratos simulados: matriz 9 × 3; inmutabilidad de cadenas Unicode y formatos protegidos;
  fallos técnicos antes del punto de escritura; sin cambios en resultados editoriales.

## Retirada y segunda revisión adversarial

1. **Crítico — auditor real de #79:** resuelto mediante la actualización sobre `737fc011`, donde el módulo ya existe. #79 cerrada sin merge formal; no fusionar su código otra vez sin comparar.
2. **Alto — Pinterest puede omitir QA final de la descripción:** corregido eliminando
   `voice_checked=True`. El aviso previo de #79 es informativo y no garantiza éxito;
   ahora todas las vías auditadas revisan los tres campos antes de abrir CDP.
3. **Alto — inferencia incorrecta de WEB en salidas manuales:** corregido a `queue=None`.
   El informe manual no demuestra publicación ni cola.
4. **Medio — auditor editorial lento/no disponible:** fallo técnico controlado corta
   antes de la acción, hallazgo editorial nunca bloquea; registrar tasa y duración en canario.
5. **Medio — pruebas de frontera por análisis estático:** AST confirma el orden, no
   demuestra comportamiento UI ni CDP en vivo. Requiere canarios supervisados
   por Claude con el auditor ya integrado en la base. En Reddit el formulario puede quedar en borrador ante un
   fallo después de rellenarlo, pero no se pulsa Publicar.
6. **Corregido en la segunda pasada:** los despachadores de reply/cita de
   Threads API, Bluesky API, Mastodon API y comentarios WEB de X/Facebook/Instagram
   no pasaban por la revisión final; ahora llaman al mismo puente antes del transporte.
7. **Corregido — alerta manual frágil:** fallo técnico del auditor impedía escribir
   `PENDIENTES_PUBLICACION.md`. Ahora la alerta registra el fallo sin suprimir el informe;
   este flujo nunca ejecuta una acción social.
8. **Pendiente:** rutas SDK fuera de los despachadores inventariados y publicación
   manual móvil/WEB no observada. Solo canarios supervisados pueden acreditar esos caminos.

**Rollback:** revertir los commits de #106; no hay cambios de esquema,
flags persistentes nuevos ni migraciones de estado. Antes de activar en despliegue,
verificar la API del auditor presente, pasar suite completa, comparar fixtures y probar canarios supervisados
en Windows/Edge/móvil sin atribuir una ejecución real a estos tests.

## Auditoría final sobre base sincronizada

- Actualizada esta rama sobre el commit de base `737fc011` mediante merge de dos padres, sin fusionar la PR; se mantienen `circuit_breaker.write_preflight`, ledger, POST/ACK y salvaguardas de las redes.
- Se añade `voice_output_finalization.inspect_fields` en `content_publisher.run`, inmediatamente antes del despachador, para Bluesky, Mastodon, Threads, X, Facebook e Instagram; se inspeccionan texto exacto y ALT disponibles, con cola WEB/API verdadera. Una excepción técnica ocurre fuera del bloque que reconcilia errores posteriores al envío.
- Pinterest usa el control directo en `publish_pin` para título, descripción y ALT antes de Playwright, sin doble gate final. `--apply` falso conserva comportamiento informativo.
- La PR #121 no es implementación independiente: contiene solo `.gitignore` encima del antiguo HEAD #106. #119 se solapa en investigación lingüística, no obliga a crear un motor nuevo.
- CI específico Ubuntu/Windows 28/28 verde: https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38049627273. Gate general rojo en live manifest: #106 ausente en `children.json` de la rama padre #10; corregirlo en padre, no en esta hija: https://github.com/davidpd89/ci-sandbox-tmp/actions/runs/38049627302.
- Pendiente: suite completa en entorno oficial, smoke supervisado Windows/Edge, TikTok Android, trazabilidad de salidas API/manual no integradas; no se han ejecutado acciones sociales.

## Actualización adversarial de revisión (10/10/2026)

La rama incorpora el commit padre `250ccb019fb8683311df48c7d02d6c6d2b73a47b` mediante merge de dos padres sin alterar los módulos del sistema social; es 0 behind.
Tras los comentarios de Perplexity se refuerza el esquema completo de findings (severidad, offsets enteros, consejo y código limitado a un identificador sin contenido) y se verifica antes de auditar que todos los campos son texto. Regresiones añadidas: texto vacío y protegido, bytes y tipos inválidos, claves Unicode, errores parciales, 27 llamadas concurrentes y 12.000 caracteres sin fuga en el log.

No se adopta el context manager propuesto: su `yield` no demuestra que se invoque la auditoría, y su `except` engloba fallos del publicador remoto, confundiendo ACK incierto con error técnico de QA. Se conserva un adaptador único (`voice_output_finalization.inspect`) y cada frontera irreversible llama explícitamente antes de actuar, con cola nativa, dos líneas por ejecutor y sin mutar el transportador. El `audit_id` propuesto basado solo en red/cola/códigos no identifica una auditoría concreta y produciría colisiones; tampoco se añaden contadores persistentes ni nuevas escrituras sin contrato de métricas. No se añade un `ThreadPoolExecutor` como pseudo-timeout: no cancela el trabajo bloqueado y dejaría tareas de auditoría posteriores al envío. Un motor opcional Java/lenguaje queda fuera de esta PR y de los requisitos de QA de salida, sin duplicar #79/#119.

La propuesta de dividir la PR por red choca con la aceptación de una única puerta compartida y una matriz coherente. El diff operativo por red se limita a pequeños puntos de llamada que requieren revisión conjunta; separar diez PR nuevas generaría dependencias circulares o ventanas con paridad parcial. Se mantiene #106 canónica y se documenta el riesgo de port selectivo al oficial.

La actualización del índice de hijos de campaña es propiedad de la PR padre #10: el último commit parent solo registró #204, no #106. Por tanto, el gate live del padre puede seguir rechazando a #106 sin que el código de QA esté roto. No se modifica el manifiesto en esta hija ni se atribuye a esta PR capacidad para corregirlo sin romper la coordinación.

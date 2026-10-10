# QA en puntos de salida finales — PR #106

Fecha de investigación: 10/10/2026. Rama \`research/voice-output-finalization-parity\`.
Dependencia obligatoria **#79** \`tools/spanish_voice_quality.py\` (abierta en esta fecha).
La PR #106 **no trae una copia** del auditor: importa \`spanish_voice_quality.audit\` en el último preflight.
Antes de integrar #106, fusionar y verificar #79; si falta el módulo, cualquier llamada nueva a QA falla
sin enviar. El código original de esta rama puede ejecutarse sin él mientras no pase por salidas auditadas.

## Origen y alcance comprobado

- Espejo \`ci-sandbox-tmp\`, HEAD inicial \`4ea955d05811c288e688f9a22f03dcfad54e2557\`: no había adaptador final.
- #79, HEAD leído \`b09e5dcf50daba1b552e4d8da939c69741c2258d\`: \`reply_writer\` audita en construcción;
  \`content_publisher.run\` audita las fichas de Bluesky, Mastodon, Threads, X,
  Facebook, Instagram y Pinterest. No garantiza ejecutores alternativos.
- Oficial privado, rama \`integracion/crecimiento-2026-10\`, solo lectura:
  \`tools/content_publisher.py\` blob \`f5120bb2141f29e88549497c09ec438b02ebc22d\`,
  \`tools/reddit_publish.py\` blob \`51b068459a73c9a91cd0a4daa760c01a556cad9e\`,
  \`tools/tiktok_mobile_interact.py\` blob \`212a514a452ba52d5844a02588499eb0d421f8fa\`.
  No se extrajeron datos ni copiaron módulos privados.
- El código ya existente que hace límites, guardas de edad, origen GPT, preflight de sesión,
  deduplicación, contadores e intenciones remotas permanece intacto.

## Inventario: 'conectado' significa en ESTA PR + #79; no implica canario en vivo

| Red | WEB | API | MOBILE | Responsable/punto final |
|---|---|---|---|---|
| X | **conectado** banco; fichas #79 | pendiente (sin salida analizada) | no aplicable verificado | \`x_bank_publish.main\` antes de \`x.post\`; \`content_publisher.run\` |
| Threads | **conectado** fichas #79 | pendiente (respuestas/API fuera de esta tarea) | no aplicable verificado | \`content_publisher.run\`, \`reply_writer\` constructor |
| Facebook | **conectado** fichas #79 | pendiente (respuesta directa/API por trazar) | no aplicable verificado | \`content_publisher.run\` |
| Pinterest | **conectado** directo, pin diario, fichas #79 | pendiente (lectores API, sin publicación auditada) | no aplicable verificado | \`pinterest_publish.publish_pin\` antes de CDP; \`voice_checked=True\` evita repetir descripción ya revisada |
| Reddit | **conectado** banco/post/comentario/reply | pendiente (sin ruta API acreditada) | no aplicable verificado | \`reddit_publish.publish_post\` antes de intención/clic, \`reddit_interact.comment\`, \`reddit_comments.reply_in_thread\` |
| Bluesky | no aplicable verificado a publicaciones | **conectado** fichas #79; replies generadas por escritor, envío independiente pendiente | no aplicable verificado | \`content_publisher.run\`, \`reply_writer\` |
| Mastodon | no aplicable verificado a publicaciones | **conectado** fichas #79; replies independientes pendientes | no aplicable verificado | \`content_publisher.run\`, \`reply_writer\` |
| TikTok | no aplicable en ruta móvil actual | pendiente (sin publicación API acreditada) | **conectado** comentarios | \`TikTokMobileAdapter.comment\` antes de abrir destino; constructor \`reply_writer\` separado |
| Instagram | **conectado** fichas #79 | pendiente (respuesta/API directa sin comprobar) | pendiente (salidas manuales sin ejecutor confirmado) | \`content_publisher.run\` + informe manual |

Toda ficha que se muestra como **pendiente manual** en \`content_queue_alert.main\` se revisa por
\`inspect_fields(..., queue=None)\`: se desconoce su transporte final, y por tanto **no** se
finge que es WEB ni se afirma que se ha capturado un clic manual. Esta es solo una revisión editorial
previa al informe; nunca convierte un recordatorio en un publicador.

La cobertura real pendiente está enumerada, no se infiere de que el auditor acepte nueve redes.
En particular, no se tocó \`threads_api\`, \`facebook_api\`, \`bluesky_interact\`,
\`mastodon_interact\`, ni plantillas de vídeo. Los comentarios que nacen en
\`reply_writer\` pueden recibir una revisión en generación y otra **final en ejecución**
si atraviesan las rutas directas instrumentadas: son fases distintas, no dos llamadas durante
una misma construcción. La excepción de Pinterest \`voice_checked=True\` impide una
segunda revisión de la misma descripción en la cadena de fichas #79.

## Contrato y seguridad técnica

\`voice_output_finalization.inspect(text, network, queue)\` acepta la cadena original y devuelve
los findings sin modificar la entrada. Un \`hint\`, \`warning\` o \`error\` editorial **no**
impide el envío; solo se registran códigos y etiquetas red/cola, nunca el cuerpo, usuario ni URL.
Los campos independientes (título, descripción, ALT, cuerpo) usan \`inspect_fields\`.
Para salidas automáticas la cola es explícita WEB/API/MOBILE. Para un aviso manual es \`None\`.

Si hay excepción técnica, falta #79 o se altera \`changed=False\` o \`findings\` esperado,
\`VoicePreflightUnavailable\` impide alcanzar el envío. Esta distinción preserva la
política de **no bloquear por estilo**, pero evita considerar diagnóstico inexistente un OK.
No hay reintentos de acción ni autoedición de tildes, títulos, citas, hashtags, URLs o
saltos de línea. Se mantiene la procedencia es-ES de #79.

## Alternativas públicas estudiadas: SHA fijado y decisión

| Repositorio/commit comprobado a 10/10/2026 | Licencia SPDX | Actividad y compatibilidad | Resolución |
|---|---|---|---|
| [barrust/pyspellchecker](https://github.com/barrust/pyspellchecker/commit/f72172c4ddb3d1c3464cf500cc2420a4831a2b55) | MIT | commit 23/07/2026; Python >=3.10, 3.11 compatible, sin Windows específico requerido; ya usado opcionalmente por #79 | Reutilización indirecta vía auditor, sin segundo motor |
| [jxmorris12/language_tool_python](https://github.com/jxmorris12/language_tool_python/commit/6c935da8ef739b22d62c13cd682cb9a2922e4f98) | GPL-3.0-only | commit 03/10/2026, Python 3.11 en metadata; JVM/proceso externo para comprobación completa | No añadir JVM/red/latencia ni duplicar motor |
| [codespell-project/codespell](https://github.com/codespell-project/codespell/commit/54cc31bc819f4af008b58a29ab16b5173dc1ff3b) | GPL-2.0-only | commit 09/10/2026; Windows y Python 3.11 declarados | Orientado a faltas comunes en ficheros/código, no a español conversacional con citas |
 
La solución seleccionada es la menor reutilización permitida: consumir la API estable
de #79 (stdlib, sin dependencias nuevas para este puente). No se incorporó código de terceros;
se mantienen licencias y atribuciones en enlaces de investigación. Metadatos consultados en
GitHub y PyPI, y decisión contrastada con \`docs/research/spanish-voice-locale-quality.md\` de #79.

## Reproducir, métricas y despliegue

\`\`\`sh
python -m compileall -q tools/voice_output_finalization.py tools/x_bank_publish.py tools/reddit_publish.py tools/reddit_comments.py tools/reddit_interact.py tools/tiktok_mobile_interact.py tools/pinterest_publish.py tools/content_publisher.py tools/content_queue_alert.py
python -m unittest discover -s tests -p test_voice_output_finalization.py -v
\`\`\`

En CI \`.github/workflows/voice-output-finalization.yml\` ejecuta tests offline
en Windows y Ubuntu, Python 3.11, sin token de red social ni acciones reales.
El auditor #79 se simula en tests de contrato porque no está fusionado en esta rama;
no se atribuye con ello una validación de producción.

Métrica de cobertura documentada antes/después:
- Antes: 0 de los **siete grupos de salida adicional** instrumentados aquí con QA final:
  X banco, Reddit banco, Reddit comentario directo, Reddit reply incrustado, TikTok MOBILE,
  Pinterest directo (incluye pin diario), aviso de ficha manual.
- Después: **7/7 rutas con llamada explícita comprobable** más cobertura parcial de #79,
  **solo cuando #79 esté disponible**. Esto mide puntos de inserción, no nueve redes
  plenamente integradas ni tasa real de detección.
- Contratos simulados: matriz 9 × 3; inmutabilidad de cadenas Unicode y formatos protegidos;
  fallos técnicos antes del punto de escritura; sin cambios en resultados editoriales.

## Segunda revisión adversarial y reversión

1. **Crítico — ausencia de #79:** rama #106 aislada no puede ejercer el motor real.
   Resuelto como dependencia explícita y preflight de fallo controlado; orden de merge obligatorio.
2. **Alto — doble QA de la descripción Pinterest:** se añadió \`voice_checked=True\` desde
   \`content_publisher\` para que el publicador directo revise solo título y ALT;
   pin diario directo revisa los tres campos.
3. **Alto — inferencia incorrecta de WEB en salidas manuales:** corregido a \`queue=None\`.
   El informe manual no demuestra publicación ni cola.
4. **Medio — auditor editorial lento/no disponible:** fallo técnico controlado corta
   antes de la acción, hallazgo editorial nunca bloquea; registrar tasa y duración en canario.
5. **Medio — pruebas de frontera por análisis estático:** AST confirma el orden, no
   demuestra comportamiento UI ni CDP en vivo. Requiere canarios supervisados
   por Claude tras integrar #79. En Reddit el formulario puede quedar en borrador ante un
   fallo después de rellenarlo, pero no se pulsa Publicar.
6. **Pendiente:** directos API de replies en Threads/Facebook/Bluesky/Mastodon y
   salidas manuales móviles no verificadas. Abrir trabajo independiente solo tras trazar
   con pruebas positivas y sin duplicar #79 o PR existentes.

**Rollback:** revertir los commits de #106; no hay cambios de esquema,
flags persistentes nuevos ni migraciones de estado. Antes de activar en despliegue,
integrar #79, pasar suite completa, comparar fixtures y probar canarios supervisados
en Windows/Edge/móvil sin atribuir una ejecución real a estos tests.

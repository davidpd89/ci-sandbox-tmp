# Implementación: conexión de selector multivariante a nueve redes

## Encargo para GPT

**Dependencia:** primero revisar e integrar PR #114 (`tools/reply_candidate_diversity.py`). Base de esta tarea: `research/public-reuse-parent`. No fusionar desde esta tarea, no accionar cuentas ni usar secretos.

**Problema concreto:** la PR #114 implementa ranking léxico offline de candidatos **ya validados por contexto**, pero `reply_writer.write_replies` actualmente solicita un único texto por post. No hay evidencia de que `context_approved` proceda de un evaluador independiente, ni integración real del selector con todos los puntos de salida. No aceptar un booleano autodeclarado por el propio generador como certificación. El nuevo módulo no es un preflight de publicación y no sustituye controles de voz ni procedencia.

**Trabajo requerido (código, no otro informe):**

1. Auditar las nueve redes X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram con rutas WEB/API/MOBILE/manual en la rama oficial `integracion/crecimiento-2026-10`. Distinguir capacidades wired, manual, ausentes, pausadas, no comprobadas. Instagram no debe declararse automatizada por existir un diccionario de límites.
2. Añadir etapa opt-in, **apagada por defecto**, que permita generar varios candidatos específicos de un post y ejecutar una **aprobación independiente** de pertinencia factual/contextual/voz o abstención. Nunca aprobar variantes solo por alta puntuación Distinct-N; jamás fabricar experiencias personales o detalles visuales no acreditados. Estandarizar el contrato global + adaptadores por red sin cambiar la ejecución en producción hasta completar los canarios.
3. Usar `select_approved(..., validator=reply_writer.valid_reply)` para los formatos que el escritor admita, con el preflight de voz #79/#106/#121, la procedencia de `reply_provenance` y bloqueo de medios no verificados de #74. Integrar en el último punto previo al efecto irreversible. Evitar doble publicación de candidatos y no registrar rechazo como éxito. No confiar únicamente en un `context_approved: true` llegado por JSON no verificado.
4. Conservar `null` como abstención genuina y caída segura existente; no convertir el fallo del módulo en comentario de banco. Asegurar que se actualiza la memoria de respuestas **solo** tras resultado confirmado, nunca al generar.
5. Tests offline: nueve redes, cada canal realmente soportado, nulos, contexto incompleto/visual sin verificar, back-to-back de candidatos, repetición interred, caracteres Unicode, feature flag OFF, reintentos, colisión de IDs, crash antes/después de ACK, origen del aprobado, errores de validador y anulación por QA. Windows y Linux Python 3.11. Registrar pruebas manuales pendientes de Edge/Android; no efectuar actividad en redes.
6. Investigación adicional solo donde haya un repo público **realmente mejor**, verificando licencia/SPDX, commit, fecha y coste Windows 3.11. Evitar crear otro `reply_research_eval`, `reply_blind_review`, banco de frases, motor de ranking de acciones o capa de procedencia.

**No solapamientos:** #72 trata benchmark; #74 contexto; #79/#106/#121 QA de voz; #22 memoria; #116 ranking de acciones; #114 selector offline. Aquí solo se implementa el **cableado del selector multivariante independiente al pipeline**. Comparar HEAD actuales antes de tocar código.

**Entregables:** commits de implementación, tests con salida real, matriz antes/después de las nueve redes, atribución de OSS si se reutiliza, rollback documentado, revisión adversarial separada y comentario final con limitaciones que Claude comprobará. No merge.

# Ficha de evidencia de reutilización (contrato CI)

Fuente primaria: https://github.com/chatwoot/chatwoot/tree/9f920b549c14491a4e587687a3eed5d21c6ccc7d
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: N/A (sin codigo incorporado)

## Problema
Los registros de interacción existen, pero faltaba una proyección local de historial y pendientes de conversación que evite duplicados y confusiones entre redes.

## Alternativas
Se contrastaron Chatwoot, Monica, EspoCRM y Twenty frente a continuar con CSV/ledger y librería estándar Python.

## Licencias y procedencia
Chatwoot núcleo MIT (excepto enterprise), Monica y EspoCRM AGPL-3.0, Twenty mezcla AGPL-3.0/MIT/enterprise. La línea SPDX anterior corresponde a la primera fuente analizada, no atribuye MIT al código original de esta PR. No se copió código de terceros.

## Decisión
Se reutiliza el patrón de fichas, tags y bandeja, pero se conserva la arquitectura existente. Proyección solo lectura sin nuevo servidor ni dependencia.

## Pruebas
12 tests sintéticos offline del HEAD original, aprobados en CI Ubuntu/Windows Python 3.11 en el workflow específico; el commit de revisión añade 3 regresiones (15 en total), cuyos checks deben comprobarse en su nuevo HEAD. Los checks del protocolo de campaña requieren este encabezado verificable.

## Retirada
Eliminar módulo, tests y workflow: ningún esquema existente ni estado operativo se modifica.

---

# Comunidad, CRM y fidelización — PR #25

**Fecha de contraste:** 10/10/2026. **Estado:** implementación de *proyección local de solo lectura*, no canario con cuentas; sin merge. Python >=3.11; bibliotecas externas añadidas: **cero**.

## Problema real y límites del encargo

Ya existen registros y políticas; falta una vista unificada y auditable de **a quién se atendió, quién volvió, qué hilo requiere revisión y por qué**. En el mirror se inspeccionaron tools/relationship_policy.py, tools/loyalty.py, tools/conversation_followups.py, tools/action_ledger.py y pruebas de paridad. El original privado (rama integracion/crecimiento-2026-10) mantiene esos módulos, con diferencias de versión: p. ej., tools/loyalty.py del mirror SHA d27b48a0fb9f086fd5d7553074036e920b2e6023 frente al oficial SHA c60cd8c70fed57fc840bb620ae7c8f5877e98381. No se copiaron archivos del oficial al mirror.

- La fuente inbound es 00_OPERATIVO/inbound_interacciones.csv (fecha, red, handle, tipo); **una señal por cuenta/tipo/día** según log_inbound: no son eventos individuales ni proporcionan ID de publicación.
- La fuente outbound por red es SISTEMA_DIARIO_<RED>/registro_interacciones.csv (fecha, cuenta, tipo, resultado), con resultados exitosos confirmado/publicado. Una respuesta nuestra a la cuenta **no demuestra** qué comentario o hilo concreto se contestó.
- Un índice opcional inbox JSON, obtenido **fuera** de esta herramienta con referencias y estado de respuesta verificados, permite construir pendientes por hilo. Sin ese índice, no se inventan pendientes. Es un contrato para adaptadores futuros, no un collector.
- Los textos originales no se copian a la salida: el historial conserva fecha, dirección y tipo; los metadatos del inbox incluyen solo red, handle, ref, thread, fecha, estado y calidad de contexto. Etiquetas explícitas, no inferencia de atributos sensibles. **No cruza** usuarios de distintas plataformas por similitud del handle.
- Es un informe de revisión humana; **no produce plan de acciones**, no consulta ni modifica redes ni toca bases de datos, cookies, estados reales o secretos.

## Comparativa de reutilización (piezas vigentes y licencias)

| Opción comprobada | Ref inmutable / mantenimiento observado | Licencia y entorno | Decisión técnica |
|---|---|---|---|
| [Chatwoot](https://github.com/chatwoot/chatwoot/tree/9f920b549c14491a4e587687a3eed5d21c6ccc7d) | v4.18.0, publicado 18/09/2026; repo activo 09/10/2026 | [MIT Expat para núcleo](https://github.com/chatwoot/chatwoot/blob/9f920b549c14491a4e587687a3eed5d21c6ccc7d/LICENSE), excepción enterprise; Ruby/Rails, PostgreSQL, Redis y frontend JS | Modelo inbox/conversación/estado útil; desplegar el servicio añade infraestructura y sincronización redundante. No copiar código. |
| [Monica](https://github.com/monicahq/monica/tree/32028ce3ce79cef38df5d27a297e5b20680f0065) | tag v4.1.2 del 04/05/2024; actividad en repo hasta 24/09/2026 (la *release* estable es antigua) | [AGPL-3.0](https://github.com/monicahq/monica/blob/32028ce3ce79cef38df5d27a297e5b20680f0065/LICENSE), PHP/Laravel y BD; no librería Python | Patrón de fichas/contacto/interacciones/recordatorios; no adaptar código bajo dependencia grande. |
| [EspoCRM](https://github.com/espocrm/espocrm/tree/6c369056e81038fdcbb6512d5d5df11db4ed6e03) | 10.0.9, publicado 29/09/2026; repo activo 09/10/2026 | [AGPL-3.0](https://github.com/espocrm/espocrm/blob/6c369056e81038fdcbb6512d5d5df11db4ed6e03/LICENSE.txt), PHP 8.3+, MySQL/MariaDB/PostgreSQL | Tags/tareas/filtros aprovechables como *patrones*; plataforma completa no mejora el coste de una lectura local. |
| [Twenty](https://github.com/twentyhq/twenty/tree/7e1431c84adbb264db98ab8b8d008a8401b6d4d6) | twenty/v2.45.0, publicado 05/10/2026; repo activo 09/10/2026 | [Licencia mixta](https://github.com/twentyhq/twenty/blob/7e1431c84adbb264db98ab8b8d008a8401b6d4d6/LICENSE): AGPLv3 predominante, partes MIT y enterprise; TS/NestJS, PostgreSQL, Redis | Objetos personalizables muy potentes, pero sobreingeniería para CSV + historial. No copiar. |
| **Continuidad del sistema** | CSV y ledger ya desplegados en el oficial; compatibilidad real observada en ficheros y tests existentes | Python 3.11 stdlib (csv, json, pathlib, datetime); Windows y Ubuntu sin servicios | **Elegida.** Extraer los patrones de CRM y construir una proyección mínima sin dependencia, nueva base ni ingesta duplicada. |

No se han incorporado líneas de terceros; **procedencia conceptual**: inbox/hilos Chatwoot, fichas e historial Monica, tags/tareas EspoCRM, campos extensibles Twenty. Las licencias indicadas no se atribuyen al código nuevo; los enlaces fijan versiones concretas. Mantenimiento = actividad/release a fecha de consulta, no garantía futura ni auditoría de todas las dependencias. Las tecnologías PHP/Rails/TS pueden funcionar en Windows con herramientas auxiliares; ninguna es una dependencia Python 3.11 directa.

## Implementación

- tools/community_crm.py: proyecta 9 redes; usa identidad canónica red+handle, agrega inbound coalescido, separa outbound confirmado, 90 días de historial y 14 de actividad/pendientes (configurables), deduplica por día/tipo/cuenta; mantiene la diferencia entre acciones realizadas y respuestas a un hilo.
- Inbox opcional JSON (lista): [{"network":"bluesky","handle":"lectora.bsky.social","ref":"at://...","thread":"at://...","date":"2026-10-09","answered":false,"context_quality":"complete"}]. "answered" **booleano verificado por el productor**; un status falso de procedencia no verificada no se convierte en canario. Selecciona por fecha el estado más reciente del hilo. Si hay refs distintas el mismo día (sin hora fiable), conserva una revisión de contexto cuando alguna sigue sin contestar; no supone que otra ref contestada sea posterior. El desempate answered=True solo se aplica al replay del **mismo ref**. Fecha futura excluida; ventana caducada nunca genera propuesta.
- Etiquetas opcionales JSON: {"bluesky:lectora.bsky.social":["lectura","fantasía"]}. Solo se aplican a contactos ya presentes; no se escribe una tabla de personas nuevas ni notas libres.
- Score de **ordenación explicable, no predictor entrenado**: comentarios 3 c/u (máx. 3), repost 2 (máx. 2), follow 2 (máx. 1), likes 1 (máx. 2), +2 por recurrencia en >=2 días, +1/2/3 por recencia de actividad, +5 si hay hilo pendiente. Se devuelven los componentes score_reasons. Se priorizan pendientes antes del score. No es el scoring multifuente experimental de la PR #69.
- by_lane informa WEB, API, MOBILE y UNASSIGNED: las asignaciones conocidas son X/Threads/Facebook/Pinterest=WEB, Bluesky/Mastodon=API, TikTok=MOBILE; Instagram=WEB (confirmado en tools/mechanical_round.py del oficial); Reddit queda UNASSIGNED hasta confirmar su adaptador/cola. **Nunca** se mezclan colas para ejecutar acciones.
- No se llama a relationship_policy.comment_allowed para autorizar respuesta: el informe prioriza **revisión**; la política, identidad de destino y preflight corresponden al ejecutor.

Ejemplo reproducible (solo ficheros locales, salida JSON a stdout):

    python tools/community_crm.py --inbound ./fixtures/inbound.csv --registries-root ./fixtures --inbox ./fixtures/inbox.json --labels ./fixtures/labels.json --as-of 2026-10-10

El comando exige paths explícitos, no lee por defecto estados reales. Sin inbox devuelve cero hilos pendientes, no genera falsos positivos. Para retirarlo: borrar tools/community_crm.py, su suite y su workflow. No hay migraciones ni cambios de esquema existentes que revertir.

## Prueba reproducible y mejora medible en fixture sintético

    python -m unittest discover -s tests -p test_community_crm.py -v

**12 pruebas offline locales, 12/12 verdes, Python 3.13.5 Linux (entorno disponible)**. CI añadida para Python 3.11 en Ubuntu y Windows, con checkout/setup-python fijados a SHA y sin acceso a cuentas ni red social; comprobar el resultado del HEAD de la PR antes del merge. No declarar verificado Windows hasta ejecución remota satisfactoria.

Fixture central: cinco filas inbox con dos registros para el mismo ref, dos refs del mismo hilo, uno respondido en otra red y uno con edad excesiva. Lectura ingenua = 5 entradas a revisar; **proyección = 1 hilo pendiente** (80 % menos elementos candidatos en esta prueba artificial, no medición de producción). Tres filas inbound de un mismo contacto/tipo/día con replay se consolidan en el recuento. Un outbound confirmado dirigido a la cuenta **no cierra** falsamente el hilo pendiente. Los tests prueban también reapertura por evento posterior, red aislada, fechas futuras, etiquetas, stdout JSON, ausencia de escrituras y error ante refs contradictorias.

## Segunda revisión adversarial (en esta PR)

1. **Error detectado en la primera prueba:** se buscaba la subcadena "text" en todo el JSON, pero "context_quality" contiene esas letras; se corrigió para comprobar que los objetos de historial no tienen campo text. 12/12 tras la corrección.
2. **Replay contradictorio:** el mismo ref con distintos handles/hilos ahora falla; a igualdad de fecha y estado, se prioriza context_quality=complete. Se añadieron casos de inversión de orden para probar determinismo.
3. **Respuesta de otra persona distinta:** claves aisladas por red. Un CSV outbound sin ref no elimina un pendiente concreto. "answered" inválido o red desconocida detiene la proyección, evitando estados de revisión equívocos.
4. **Hilo envejecido:** más de 14 días no produce pendiente aunque exista actividad reciente con esa cuenta. Un reply nuevo posterior a uno contestado reabre el hilo; un reply contestado posterior lo cierra.
5. **Coste/capacidad:** sin servicios residentes ni consultas remotas, cada CSV se lee una vez; proyección en memoria, adecuada para el volumen actual. Sin benchmark de millones de filas ni latencia Windows real; añadir streaming incremental solo ante evidencia de tamaño operativo real.

## Riesgos residuales y entrega a Claude

- La normalización por handle no conserva identidad cuando cambia un nombre; **no** fusionar alias automáticamente. Una futura migración a identificadores estables requiere contrato por red y compatibilidad con CSV legados.
- El CSV inbound agrupa por día; no sirve para contar volumen exacto de comentarios. Las refs y estado answered se deben obtener con colectores específicos existentes o verificados, no inferirse de texto ni de acciones nuestras. Sin productor para inbox, este módulo ofrece historial y score, **no** recuperación automática de pendientes.
- La etiqueta es un dato manual local; no existe UI ni escritura de tareas. El JSON de salida contiene handles y referencias, por lo que se mantiene fuera de commits/logs de datos reales.
- El modo UNASSIGNED no inventa capacidades de Reddit. Claude debe verificar su cola al integrar, mantener el ledger de idempotencia y el cutoff de destino de los ejecutores.
- PR #69 se ocupa de scoring engagement/colas de premios; PR #86 de funnel y atribución. No abrir una PR duplicada por esas funciones. El nuevo módulo es únicamente la capa de lectura y continuidad CRM.
- No hay canario supervisado ni prueba en Edge, móvil, API real o Windows vivo al elaborar este informe. La integración debe comenzar con export **sintético** o canario supervisado separado; ninguna prueba offline demuestra resultados de seguimiento reales.


## Revisión independiente del controlador (10/10/2026)

En una segunda pasada se detectaron y corrigieron tres casos: (1) un CSV inbound explícito ausente devolvía un informe vacío válido; ahora produce error, mientras los registros de una red aún no inicializada siguen siendo opcionales; (2) dos refs distintas del mismo hilo en el mismo día podían ocultar un pendiente si una estaba marcada answered=True, pese a no existir marca horaria para ordenarlas: ahora generan **review_context**, nunca una acción automática; (3) Instagram figuraba UNASSIGNED pese a tener browser=True en tools/mechanical_round.py del oficial, y ahora se clasifica WEB. Se añaden tres tests sintéticos. No se crea un productor de inbox ni se vincula la proyección al ejecutor.

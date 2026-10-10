# PR #74 — comentarios anclados a evidencia (10/10/2026)

## Problema y alcance

En el espejo, el generador de tools/reply_writer.py valida límites, forma, arranques repetidos y JSON, pero esas reglas no acreditan que cada frase se refiera al post concreto. El campo de contexto no recoge de forma homogénea cuerpo, padres, material visual y origen para las nueve redes. El encargo de la PR solicita un contexto común, pruebas por afirmación y medidas de respuestas, continuidad y valor percibido.

Esta PR aporta un módulo REAL, independiente y solo offline: tools/reply_context_grounding.py. No cambia ejecución, colas, sesión de ChatGPT, cuentas, credenciales ni estados operativos. No hay publicaciones reales ni generación mediante un modelo.

Funciones:
- build_packet: paquete común de X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram y colas WEB/API/MOBILE; evidencia de texto, cuerpo, padres y descripciones visuales verificadas; autor y timestamp UTC; edad máxima configurable y contexto parcial indicado.
- render_packet: bloque JSON determinista con IDs, fuente y procedencia y aviso de que el texto ajeno no contiene instrucciones.
- audit_reply: cada unidad/sentencia debe aportar cita literal con ID presente en la fuente de ese post; devuelve rechazo, abstención o needs_semantic_review. Coincidencia literal NO demuestra verdad, pertinencia, tono ni no-invención.
- packet_fingerprint y audit_draft: fijan destino, red y contenido exacto del contexto antes de auditar; un cambio de objetivo o texto fuente invalida la propuesta offline. El hash NO es firma de autenticidad.
- tally y summarize_outcomes: métricas de proceso y resultados descriptivos sintéticos/autorizados, separados por variante y red. Desconocido no se contabiliza como falso; numeradores y denominadores son explícitos.

Pruebas: tests/test_reply_context_grounding.py y .github/workflows/research74-context-grounding.yml con unittest/py_compile en Ubuntu y Windows, Python 3.11. Instagram figura solo en el CONTRATO, no se ha demostrado un pipeline de ingesta/evidencia real para Instagram.

## Código oficial privado: consulta solo lectura

Consultada la rama integracion/crecimiento-2026-10 de davidpd89/rrss-davidporto-CODE, revisión 5449513d9b545d0a6a72abf066ab6a779bfdad71. Existían herramientas de trabajo H1 en tools/reply_context_trial.py, tests/test_reply_context_trial.py, tests/fixtures/reply_74_context_synthetic.json y 00_OPERATIVO/PR_74_CONTEXTUALIDAD_H1_OFFLINE.md. H1 ofrece prompts baseline/alternativa idénticos en la entrada, con política contextual sin cuotas artificiales; sigue offline. No se han copiado esos ficheros al espejo. La implementación pública de esta PR es OTRA pieza complementaria: paquete de evidencia comprobable por frase, destino y huella.

También se consultó .github/pr-scopes/2026-10-45-procedencia-contextual-respuestas.md: el sistema oficial protege destino real, contenido y GPT proof antes de ejecutar. No reemplazar ni duplicar esos controles en el espejo; esta prueba de texto es editorial y offline. En el espejo se inspeccionaron tools/reply_writer.py, tools/reply_queue.py, tools/conversation_followups.py, el documento tasks/64-context-grounded-commenting.md y el protocolo docs/open-source-scouting/PROTOCOL.md.

## Investigación pública: licencia, mantenimiento y decisión

Fecha de corte 10/10/2026; licencias contrastadas en LICENSE y compatibilidad en pyproject.toml. Enlaces fijados a commits, no solo a README mutable.

| Candidato | Licencia / actividad / compatibilidad | Resultado |
| --- | --- | --- |
| [Haystack, c5e13354](https://github.com/deepset-ai/haystack/tree/c5e13354117d1376d4d8caf0efe77abe80120fc0) | Apache-2.0, commit 09/10/2026, Python >=3.10, clasificador Python 3.11 y OS-independent | Patrones de origen y pipelines reutilizables; la dependencia trae motor, OpenAI/Pydantic, HTTP y otros paquetes sin resolver la trazabilidad literal de frases. No instalado. |
| [DSPy, f1260ff1](https://github.com/stanfordnlp/dspy/tree/f1260ff14610286cb295c7d3a5ee2cbfd0ba5cb9) | MIT, commit 08/10/2026, Python >=3.10 y <3.15, clasificador POSIX; Windows no acreditado aquí | Optimización de prompts con proveedor/modelo; coste y superficie innecesarios para checks offline. No instalado. |
| [Ragas, 298b6827](https://github.com/vibrantlabsai/ragas/tree/298b68274234c060deacab3cf5fb52aa3a20e885) | Apache-2.0, commit 24/02/2026, Python >=3.9, dependencias LLM/datasets/LangChain | Puede evaluar faithfulness semántica en estudio posterior con datos autorizados, pero no es un verificador determinista barato ni local sin modelo. No instalado. |
| [Microsoft GraphRAG, 5faaaf4f](https://github.com/microsoft/graphrag/tree/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f) | MIT, commit 08/10/2026, propio README indica mantenimiento | Indexación/grafo desproporcionados para posts cortos; no instalado. |
| Código propio mínimo de Python 3.11 y contratos existentes | Sin paquetes externos nuevos, Windows/Ubuntu por CI | Elegido: integrable como función pura, fácil de retirar, sin estado. Se adaptan patrones de procedencia; NO se copia código de terceros ni licencias. |

La actividad reciente de un repositorio no demuestra que cada funcionalidad esté mantenida o probada en Windows. La selección se justifica por la función limitada, no por supuesta superioridad global. Revisar versiones y licencias de nuevo si se plantea instalar un framework en el futuro.

## Contrato de fuentes y pruebas de suficiencia

Entrada mínima por plataforma: network, queue, target_id estable, published_at ISO 8601 con zona, context_status (complete, partial o visual_unverified); text o post_body o elemento visual acreditado. Campos opcionales: author, reply_to_us, parents cronológicos y visual; cada padre necesita stable_id y booleano literal verified True; cada visual necesita asset_id, description, provenance (human_verified/vision_verified/ocr_verified) y booleano literal verified True.

El collector debe aportar los datos, NUNCA inventarlos. Una publicación solo visual es evaluable si existe descripción verificada; una foto sin interpretación no autoriza inventar colores, símbolos, portada ni acciones vistas. El autor se muestra como metadato, no como evidencia de su biografía. Los padres ausentes no se reconstruyen. Contexto parcial se conserva explícito; los posts textual y autónomamente suficientes no quedan bloqueados por defecto.

El límite inicial para edad es max_age_hours=168 y el planificador debe configurarlo por red. Una fecha naive, inexistente, posterior al margen tolerado o más antigua que el umbral deja el paquete ineligible (sin respuesta). La comparación usa UTC y no modifica el destino. Se admite acotar tamaños y máximo de ocho padres y seis descripciones para evitar contexto arbitrariamente grande.

Ejemplo de evaluación *simulada*: contenido Reddit con título Audiolibros y cuerpo Busco una narración sobria. La frase candidata Buscas una narración sobria debe llevar evidence id=body y quote=Busco una narración sobria. Una coincidencia exacta permite needs_semantic_review, NO publicación automática. El objeto draft debe transportar también network, target_id y context_fingerprint producido sobre esa instantánea. Una cita del post A no sirve al post B.

## Medición honesta frente al sistema actual

| Caso sintético | Validación formal existente | Auditoría nueva |
| --- | --- | --- |
| Comentario de longitud válida con cita de otro post | No comprueba fuente | Rechaza cita inexistente en fuente del contexto |
| Reutilización para otra URL/ID | Guarda procedencia en ejecutores privados, no en valid_reply | audit_draft rechaza otro destino/red |
| Texto original cambia desde preparación | Validación formal no conoce snapshot | Nueva huella -> rechazo |
| Descripción de foto no vista | Generador no puede verificar visual | Omite visual no verificado |
| Dos frases, una sin cita | No exige cobertura | Rechaza la unidad descubierta |
| Conclusión falsa con palabras literalmente citadas | No garantiza semántica | **Puede pasar la cita: obliga a revisión semántica** |

Los tests demuestran contratos, no que los comentarios sean más humanos o provoquen más respuestas. Para comparación real posterior se necesita evaluación ciega con #72 y H1 del oficial con entradas equivalentes, aprobación humana y variantes trazables. summarize_outcomes admite registros autorizados o sintéticos: network, variant (baseline o H1), sample_id, published, received_reply (booleano o null), continuation_turns (entero o null), perceived_value (rating editorial 1–5 o null). Devuelve samples, published, reply_observed, replies_received, continuations_observed, continuation_turns, value_ratings, value_sum, reply_rate_observed y average_perceived_value. No convierte valores ausentes en ceros. No se ha ejecutado un A/B con usuarios ni se pueden inferir efectos causales del código.

## Ejecución y evidencias

Comandos offline:

    python -m unittest discover -s tests -p test_reply_context_grounding.py -v
    python -m py_compile tools/reply_context_grounding.py tests/test_reply_context_grounding.py

Workflow separado, sin permisos de escritura, sobre ubuntu-latest y windows-latest con Python 3.11. Los checks actuales son tests simulados, no Edge vivo, navegador real o canario móvil; no prueban adaptadores de las nueve redes. Deben comprobarse en el HEAD final. El validador de campaña y suite general del espejo siguen siendo independientes.

## Segunda revisión adversarial

1. Swap entre A y B, incluso con texto idéntico: audit_draft exige target_id/red exactos y packet_fingerprint, con regresión.
2. Texto fuente o autor actualizado, timestamp o cola modificados: distinta huella, regresión. Una huella SHA-256 local no protege contra actor con escritura del mismo host.
3. Multimedia: verified literal True, tipo de procedencia reconocido y asset_id; se eliminan elementos visuales no acreditados. No se prueba que un modelo visual haya interpretado realmente la imagen; responsabilidad del adaptador.
4. Padres y respuestas a nosotros: padre ausente produce abstención, los turnos inciertos no se acreditan, cronología proporcionada no se reconstruye.
5. Post antiguo/horario: timezone explícita y edad, pruebas de borde. Evita que timestamp inexistente permita necroposting silencioso.
6. Sesgo léxico: la coincidencia puede respaldar texto sarcástico, alucinación por implicatura o interpretación falsa. La distinción needs_semantic_review no puede relajarse para publicar directamente.
7. Inyección de prompt: evidencia es dato no confiable, se serializa; el texto suministrado puede contener instrucciones maliciosas, no se ejecuta. El aviso no constituye protección formal de un LLM.
8. Métricas: muestras desconocidas o no publicadas tienen denominadores propios, no se reportan tasas cuando faltan observaciones. La evaluación de utilidad percibida depende de evaluadores humanos.
9. Dependencias: ninguna. Rollback = retirar el módulo, tests, workflow y doc. No hay archivos operativos, migración, productores o estado persistente.
10. Cobertura: sin integración productiva real ni comprobación de Edge/Android. Coordinar con #72 (benchmark), #73 (corpus), #75 (repetición), #77 (hilos), #79 (voz) y herramientas del oficial antes de un despliegue. No abrir PR adicional redundante.

**Sin merge y sin aprobación automática de comentarios. El controlador Claude debe revisar HEAD, CI y pruebas E2E con sus correspondientes permisos antes de integrar cualquier consumidor.**

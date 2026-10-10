# Reciprocidad y fidelización de relaciones

Fuente: informe de Perplexity (https://www.perplexity.ai/search/fb4368ec-e85c-45a1-b8d8-cd8780a5d27c), generado 10/10/2026.

Informe: CRM social de relaciones, máquinas de estado y fidelización multired
Resumen

Para el sistema de crecimiento de David Porto conviene no adoptar un CRM completo, sino construir una capa propia de CRM de relaciones sociales sobre eventos ya capturados por los adaptadores de red. La combinación más aprovechable es PingCRM como referencia de modelo de datos, scoring relacional y recontacto; Retentioneering como motor analítico de secuencias, transiciones, embudos y retención; y una máquina de estados propia, ligera y agnóstica de red, para gobernar cuándo procede un follow-back, una respuesta o un recontacto.
github
+1

Hallazgos
Repositorio / proyecto	Licencia	Qué reutilizar	Aplicación al sistema	Riesgos técnicos

PingCRM
	AGPL-3.0	Modelo de contacto unificado, timeline de interacciones, resolución de identidad, score 0–10 de relación, detección de contactos “enfriándose” y sugerencias de follow-up no automáticas. 
github
	Es la referencia más directa para social_relationship, interaction_event, relationship_state y next_action_suggestion. Su lógica de recencia, frecuencia, reciprocidad y amplitud se puede reimplementar en Python sin copiar código. 
news.ycombinator
+1
	AGPL-3.0 exige apertura del código si se ofrece como servicio en red; mejor inspirarse en el modelo y escribir implementación propia. 
github


Retentioneering
	Apache-2.0	Eventstream, grafos de transición, matrices de pasos, Sankey, funnels, segmentación conductual y comparación de cohortes. 
github
	Convertir cada interacción social en eventos: comment_received, reply_sent, follow_received, profile_visit, dm_reply, link_click. Permite medir qué secuencias conducen a seguidor recurrente, conversación mantenida o visita al perfil. 
github
	Requiere normalizar eventos de ocho redes a un esquema común; las APIs y disponibilidad de señales difieren mucho. 
github


Socioboard
	Revisar licencia en el repositorio	Concepto de bandeja unificada, registros sociales compartidos, respuestas guardadas, flujos de aprobación y analítica social. 
github
	Útil como referencia de producto para la “bandeja de relaciones”: comentarios, menciones y respuestas en una sola cola priorizada.	Proyecto antiguo, ASP.NET/MySQL y con señales de mantenimiento limitado; no es buena base directa para un stack Python 3.11 moderno. 
github
+1


Frappe CRM
	Open source	Pipeline, tareas, tiempos de respuesta, automatización de seguimientos y conversaciones vinculadas a un registro. 
frappe
	Referencia para follow_up_task, sla_hours, cooldown_until y cola de acciones; no conviene integrarlo como CRM pesado para uso personal multired.	Es un CRM generalista orientado a ventas; añadiría complejidad operativa y de despliegue. 
frappe


InfluencerHub
	Indicada como open source en su README	Máquina de estados de campaña: borrador → negociación → activo → revisión → pago, con trazabilidad. 
github
	Patrón aplicable a la relación con un perfil: descubierto → observado → interactuado → conversacion → seguidor → recontactable → dormido.	Está orientado a campañas de influencers y pagos; hay que adaptar estados, eventos y reglas al nicho lector. 
github

Laudspeaker	AGPL en su núcleo, según el directorio GTM	Journeys de engagement, onboarding y automatizaciones basadas en eventos. 
github
+1
	Referencia para campañas de reactivación: “autor que comentó hace 14 días pero no respondió”, “seguidor activo sin interacción en 30 días”.	Más orientado a producto/SaaS que a CRM social; su licencia y alcance pueden pesar más que el beneficio. 
github


HasData social-listening-tool
	MIT	Escucha de menciones de marca y flujo básico de social listening. 
github
	Puede inspirar el módulo de detección de menciones a “David Porto”, títulos, sagas o palabras del nicho fantástico.	Verificar cobertura real de redes, calidad de extracción y mantenimiento antes de depender de él. 
github
Modelo recomendado
Entidad central: relación, no seguidor

El sistema debe tratar cada perfil como una relación longitudinal, no como una fila aislada:

person: identidad canónica, con alias por red.

social_account: cuenta concreta en X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok o Instagram.

interaction_event: comentario recibido, respuesta enviada, like, follow, mención, DM, guardado, repost o clic.

relationship_state: estado actual calculado, no escrito a mano.

action_opportunity: acción candidata con score, motivo, canal, caducidad y resultado.

outcome: follow-back, respuesta, nueva interacción, visita al perfil, conversación continuada o silencio.

PingCRM valida esta arquitectura: unifica timeline, resuelve la misma persona entre plataformas y calcula una puntuación relacional basada en recencia, frecuencia, reciprocidad y amplitud de interacción.
github

Máquina de estados de relación

Estados iniciales recomendados:

Estado	Entrada	Acción candidata	Salida
descubierto	Perfil del nicho detectado	Observar, guardar, valorar afinidad	observado
observado	Interés potencial, tema afín	Comentario contextual de bajo riesgo	interactuado
interactuado	Comentario o reacción enviada	Esperar respuesta; registrar resultado	conversacion / sin_respuesta
conversacion	Respuesta recibida	Responder con valor, sin repetir plantilla	relacion_calida
relacion_calida	2+ intercambios recíprocos	Follow-back si procede, compartir, mencionar con criterio	seguidor_reciprocо
seguidor_reciprocо	Follow mutuo y actividad sostenida	Mantener presencia, invitar a newsletter o lectura	lector_potencial
sin_respuesta	Sin respuesta tras ventana definida	Cooldown; recontacto solo si hay motivo nuevo	dormido
dormido	Inactividad prolongada	Reengagement por evento relevante, no por rutina	reactivado / archivado

La regla clave es que el recontacto debe depender de un motivo contextual —nuevo post, respuesta previa, interés demostrado, lanzamiento o tema compartido— y no de una cadencia mecánica. PingCRM sigue este principio al proponer borradores contextuales sin envío automático.
github

Score de relación

Propongo un score 0–100, descompuesto y auditable:

𝑆
=
0.25
𝑅
+
0.20
𝐹
+
0.20
𝑃
+
0.15
𝐴
+
0.10
𝐶
+
0.10
𝑁
S=0.25R+0.20F+0.20P+0.15A+0.10C+0.10N

𝑅
R: recencia de la última interacción.

𝐹
F: frecuencia de interacciones en 30/90 días.

𝑃
P: reciprocidad: respuestas, comentarios propios, follows o menciones recibidas frente a acciones enviadas.

𝐴
A: amplitud: número de redes o tipos de interacción.

𝐶
C: calidad: longitud, pregunta, intención, afinidad temática y sentimiento.

𝑁
N: novedad: evento reciente que justifica recontacto.

El score no debe decidir solo: debe alimentar una cola de oportunidades con motivo explicado, por ejemplo: “respondió a un hilo sobre romantasy hace 3 días; prioridad alta para respuesta humana”.

Métricas de fidelización multired
Métrica	Definición	Uso
Tasa de respuesta	Respuestas recibidas / comentarios o menciones enviados	Calidad de apertura conversacional
Reciprocidad neta	Interacciones entrantes / interacciones salientes	Detectar relaciones unilaterales
Follow-back rate	Follows mutuos / follows iniciados	Calidad de selección de perfiles
Continuidad conversacional	Conversaciones con 2+ turnos / conversaciones iniciadas	Capacidad de sostener diálogo
Retención a 7/30 días	Perfiles con nueva interacción tras la primera	Fidelización temprana
Tasa de reactivación	Perfiles dormido con interacción tras recontacto	Eficacia del recontacto
Profundidad multired	Nº de redes con interacción por persona	Identidad y afinidad real
Velocidad de respuesta	Tiempo medio hasta primera respuesta	Priorización operativa
Conversión a lector	Visita web, newsletter o compra atribuible / relación activa	Impacto de negocio

Retentioneering encaja bien aquí porque acepta una tabla mínima de user_id, event y timestamp, y ofrece transiciones, funnels, matrices de pasos, segmentos y clustering. Eso permite comparar, por ejemplo, qué secuencia produce más relaciones recíprocas: comentario → respuesta → follow frente a like → comentario → silencio.
github

Recomendación

Construir un módulo propio relationship_crm, con Retentioneering como dependencia analítica y PingCRM como referencia de producto, no como dependencia directa.

Sí reutilizar: esquemas conceptuales, métricas y patrones de scoring.

No copiar código de PingCRM salvo que el proyecto acepte las obligaciones de AGPL-3.0; su licencia exige disclosure si se usa en red.
github

Sí usar Retentioneering directamente: Apache-2.0, Python 3.10–3.13, tests, notebooks y API orientada a eventos; encaja con Python 3.11 y Windows.
github

Evitar Socioboard como base: su valor es conceptual, pero su stack y antigüedad lo hacen poco adecuado para integración actual.
github
+1

Plan de implementación en PR pequeñas
PR 1 — Esquema de eventos de relación

Crear tablas person, social_account, interaction_event, relationship_state, action_opportunity, outcome.

Definir enum de eventos común: comment_received, reply_sent, mention_received, follow_received, follow_sent, dm_received, dm_sent, profile_visit, link_click.

Tests: inserción de eventos desde dos redes, deduplicación y consulta de timeline.

PR 2 — Adaptadores de normalización

Añadir normalize_event(network, raw_event) para cada red.

Mapa común de autor, tipo de interacción, timestamp, URL, contenido y contexto.

Tests por red con fixtures mínimos y casos límite: menciones, respuestas anidadas, cuentas privadas y eventos sin URL.

PR 3 — Máquina de estados

Implementar transiciones declarativas en YAML o Python dataclasses.

Reglas de cooldown, ventana de espera y condiciones de recontacto.

Tests: cada transición válida, transiciones inválidas, reversión a dormido y prevención de bucles.

PR 4 — Score relacional

Calcular score 0–100 con componentes explicables.

Guardar histórico del score y los factores que lo produjeron.

Tests: perfiles nuevos, relación recíproca, relación unilateral, inactividad y reactivación.

PR 5 — Cola de oportunidades

Generar acciones candidatas: responder, seguir, observar, recontactar o archivar.

Cada oportunidad debe incluir reason, priority, expires_at y network.

Tests: no proponer recontacto sin motivo, respetar cooldown y priorizar conversaciones abiertas.

PR 6 — Analítica con Retentioneering

Exportar eventos a user_id, event, timestamp y metadatos de red.

Generar grafo de transiciones, funnel de relación y cohortes de retención a 7/30 días.

Tests: dataset sintético con rutas conocidas y validación de conteos.

PR 7 — Panel y aprendizaje

Dashboard con estados, score, oportunidades pendientes y métricas por red.

Registrar resultado de cada acción para aprender qué secuencias y plantillas funcionan.

Tests de regresión sobre métricas agregadas y exportación CSV/HTML.

Aplicación a todas las redes

X, Threads, Bluesky y Mastodon: fuertes para conversación pública, menciones y respuestas; priorizar comentarios contextuales y seguimiento de hilos.

Facebook: útil para grupos, páginas y comunidades lectoras; modelar interacciones en grupo como eventos con context_group.

Pinterest: menos conversacional; tratar guardados, clics y repins como señales de interés, con estados más lentos.

Reddit: priorizar hilos, respuestas útiles y karma/contexto de subreddit; evitar tratar un comentario como relación privada.

TikTok e Instagram: priorizar comentarios, respuestas a stories cuando existan, guardados y visitas; el DM debe ser una consecuencia de interacción previa.

Todas: el mismo estado relacional debe funcionar, pero los eventos disponibles, su semántica y la cadencia natural cambian por red.

Fuentes

PingCRM — CRM personal open source, AGPL-3.0, scoring relacional y follow-ups: 
https://github.com/sneg55/pingcrm
github

Discusión de lanzamiento de PingCRM con descripción del score y la lógica de recontacto: 
https://news.ycombinator.com/item?id=47423835
news.ycombinator

Retentioneering — analítica de eventos, journeys y retención, Apache-2.0: 
https://github.com/retentioneering/retentioneering-tools
github

Socioboard — social CRM y bandeja unificada: 
https://github.com/thinkgandhi/socioboard
github

Frappe CRM — seguimientos, tareas y automatización: 
https://frappe.io/crm
frappe

InfluencerHub — máquina de estados de campaña y CRM: 
https://github.com/Crynge/InfluencerHub
github

Directorio open source GTM con CRMs y plataformas de engagement: 
https://github.com/eliasstravik/open-source-gtm/blob/main/README.md
github

HasData social listening, MIT: 
https://github.com/HasData/social-listening-tool
github

# Métricas, atribución y experimentos de crecimiento

Fuente: informe de Perplexity (https://www.perplexity.ai/search/9cd32b06-aaed-43e9-9f53-e2ba0e6dbdd4), generado 10/10/2026.

Investigación: medir acciones que generan seguidores y conversaciones

Resumen ejecutivo: Para las nueve redes, la solución más robusta no es un “tool de social media” monolítico, sino un modelo de datos único (action, post, profile, interaction, outcome) alimentado por adaptadores por red, con atribución determinista por enlaces/UTM + ventana temporal, A/B bayesiano para poco volumen y un panel ligero tipo Metabase o GitHub Pages. Los repos públicos más aprovechables son Postiz (referencia de adaptadores y analítica multirred), PostHog (experimentos y eventos), Metabase (panel), bayesAB (inferencia con muestras pequeñas) y campaignlab (atribución de campañas ligera).

Hallazgos
Repositorio	Licencia	Qué reutilizar	Integración en el sistema	Riesgos técnicos	Tests propuestos

Postiz
	AGPL-3.0	Modelo de publicación multicanal, credenciales por red, analítica y bandeja de comentarios; soporta despliegue self-hosted. 
github
	Usar como referencia de adaptadores para X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram; extraer patrones de normalización de posts, comentarios y métricas.	AGPL obliga a publicar cambios si ofreces el servicio modificado; su esquema es más amplio de lo necesario.	Contract tests por red: crear/borrar acción de prueba, mapear métricas y comentarios al modelo común.

PostHog
	MIT Expat, salvo directorio ee	Eventos, feature flags, experimentos y análisis estadístico de impacto. 
github
	Registrar cada acción social como evento: action_executed, reply_sent, profile_visited, follow_gained, conversation_started. Usar experimentos para comparar plantillas, horarios y tipos de interacción.	Self-hosted recomendado hasta ~100k eventos/mes; para tu volumen es más que suficiente, pero Docker añade operativa. 
github
	Test de ingestión idempotente, asignación estable a variantes y cálculo de métricas por cohorte.

Metabase
	AGPL en la edición Open Source; licencia comercial en directorio enterprise	Dashboards SQL/no-SQL, preguntas guardadas, filtros y paneles compartibles. 
github
+1
	Conectar a PostgreSQL/SQLite del sistema y crear paneles: seguidores netos por acción, tasa de conversación, ranking por red, cohortes de plantilla y atribución.	No tiene conector nativo a GitHub ni a redes sociales: requiere sincronizar primero a base de datos. 
metabase
	Tests de vistas SQL: unicidad de action_id, integridad referencial y coincidencia entre eventos y outcomes.

bayesAB
	Revisar LICENSE del repo antes de copiar código	Métodos bayesianos A/B para Bernoulli, Poisson y otras distribuciones; pensado como alternativa a pruebas frecuentistas. 
github
+1
	Implementar comparación de variantes con pocos datos: p. ej., plantilla A frente a B para probabilidad de respuesta o conversación; Poisson para comentarios por post.	Es R, no Python; conviene portar la lógica o usarla como referencia metodológica.	Unit tests con datos simulados: priors, posterior, probabilidad de superioridad y robustez ante ceros.
campaignlab	Verificar licencia en el repositorio	UTM links, click attribution y conversión idempotente; FastAPI + SQLite. 
github
	Reutilizar el patrón de enlaces trazables y tabla de conversiones para atribuir visitas, altas de newsletter y ventas a acciones sociales.	Proyecto pequeño; auditar calidad, mantenimiento y seguridad antes de dependencia directa.	Tests de generación de UTM, deduplicación de clics/conversiones y atribución first-touch/last-touch.

Plausible Analytics
	AGPL-3.0 o posterior	Analítica web ligera, sin cookies, self-hosted. 
github
	Medir tráfico entrante desde bio, link-in-bio, hilos, pines y posts; cruzar utm_source, utm_medium y utm_campaign con acciones sociales.	Mide web, no interacciones nativas; requiere enlaces salientes correctos.	E2E: clic en enlace social → evento web → conversión registrada.

Awesome Data Analytics
	Lista curada; revisar licencias de cada entrada	Descubrimiento de herramientas BI y analítica. 
github
	Usar solo como mapa para alternativas de panel; no como dependencia.	Enlaces y proyectos pueden quedar obsoletos.	Revisión trimestral de enlaces y licencias.

social-media-management topic
	Varias licencias	Catálogo actual de plataformas self-hosted multirred, incluyendo proyectos con analítica persistente e inbox unificado. 
github
	Vigilar alternativas más ligeras que Postiz y detectar adaptadores nuevos para redes del nicho.	Calidad y licencias heterogéneas.	Checklist de evaluación: licencia, última actividad, cobertura de redes, API, exportación de datos.
Modelo único de datos

Una tabla central actions debe ser la unidad de aprendizaje: cada comentario, respuesta, follow, pin, repost, DM público o publicación es una acción medible.

text
network            -- x | threads | facebook | pinterest | reddit | bluesky | mastodon | tiktok | instagram
action_id          -- UUID estable
action_type        -- comment | reply | follow | post | pin | share | dm_public
target_post_id     -- normalizado por red
target_profile_id
template_id        -- plantilla o familia de copy
variant            -- A | B | C
executed_at
status             -- pending | success | failed | skipped

Y una tabla de resultados outcomes desacoplada en el tiempo:

text
action_id
outcome_type       -- reply_received | conversation_started | profile_follow | link_click | newsletter_signup | sale
occurred_at
value              -- 1 para eventos; importe o duración cuando aplique
attribution_rule   -- direct_link | temporal_window | thread_context
confidence         -- high | medium | low

Atribución en tres capas:

Directa: el usuario llega por enlace con UTM o URL corta generada desde action_id.

Conversacional: responde al comentario o inicia hilo tras la acción; se asocia por target_post_id, autor y ventana temporal.

Temporal: nuevo seguidor o visita al perfil dentro de una ventana configurable por red, por ejemplo 24–72 horas, con confidence menor.

A/B con pocos datos

Con audiencias pequeñas, evita decidir por “más likes”. Usa estas métricas jerárquicas:

Primaria: probabilidad de generar conversación (reply_received o conversation_started).

Secundarias: nuevos seguidores atribuidos, clics al perfil/web, guardados y alcance.

Guardarraíles: tasa de fallo de API, acciones ocultas, bloqueos y quejas.

Para cada experimento, usa un diseño bayesiano simple:

𝑃
(
𝜃
𝐴
>
𝜃
𝐵
∣
𝑑
𝑎
𝑡
𝑜
𝑠
)
P(θ
A
	​

>θ
B
	​

∣datos)

donde 
𝜃
θ es la probabilidad de conversación. Con pocos eventos, un prior Beta débil —por ejemplo 
𝐵
𝑒
𝑡
𝑎
(
1
,
1
)
Beta(1,1)— y actualización por aciertos/impresiones es preferible a exigir tamaños muestrales frecuentistas grandes. bayesAB sigue exactamente ese enfoque y permite modelar Bernoulli para CTR/conversión y Poisson para recuentos como comentarios.
github
+1

Regla práctica: no declares ganadora una variante hasta acumular al menos 30–50 acciones por variante o hasta que 
𝑃
(
𝜃
𝐴
>
𝜃
𝐵
)
P(θ
A
	​

>θ
B
	​

) supere 0,80–0,90 de forma sostenida. Para redes de muy bajo volumen, agrupa por familia de plantilla en vez de por copy exacto.

Recomendación

Arquitectura recomendada: PostgreSQL + adaptadores propios + PostHog opcional + Metabase.

Núcleo propio: modelo actions/outcomes y adaptadores por red; es la parte que debe ser tuya y estable.

Atribución: enlaces UTM/short-link con action_id; inspirarte en campaignlab sin depender de un proyecto pequeño sin madurez suficiente.
github

Experimentos: PostHog si quieres feature flags, experimentos y análisis integrado; su licencia MIT facilita reutilización, aunque el directorio ee tiene licencia distinta.
github

Panel: Metabase sobre la base de datos; es la vía más rápida para rankings, cohortes y filtros por red sin construir frontend.
github

Referencia multirred: Postiz, para aprender de su modelo de integraciones y analítica; no lo adoptes como núcleo si quieres mantener el sistema ligero y plenamente controlado.
github

Plan de implementación en PR pequeñas
PR 1 — Esquema común

Crear tablas networks, profiles, posts, actions, outcomes, templates, experiments.

Añadir índices por network, action_type, executed_at, template_id y variant.

Incluir migraciones y tests de integridad.

Criterio de aceptación: una acción de cualquier red puede registrarse con el mismo esquema.

PR 2 — Adaptador base y dos redes piloto

Definir interfaz SocialAdapter: fetch_target, execute_action, fetch_metrics, fetch_comments.

Implementar primero Reddit y Bluesky o Mastodon, por API más predecible y datos más estructurados.

Normalizar comentarios, respuestas y perfiles al modelo común.

Criterio de aceptación: mismos campos de salida para ambas redes.

PR 3 — Atribución por enlaces

Generar URLs con utm_source, utm_medium, utm_campaign y action_id.

Crear endpoint de redirección que registre clic y redirija a la web.

Guardar conversiones con deduplicación por action_id + outcome_type.

Criterio de aceptación: un clic desde una acción se atribuye de forma determinista.

PR 4 — Motor de outcomes y ventanas

Job diario que consulte respuestas, nuevos seguidores, menciones y comentarios.

Asociar outcomes por enlace directo, contexto de hilo y ventana temporal.

Escribir attribution_rule y confidence.

Criterio de aceptación: cada outcome tiene origen auditable.

PR 5 — A/B bayesiano ligero

Añadir tabla experiments y asignación determinista de variantes.

Implementar Beta-Bernoulli para conversación y Gamma-Poisson para comentarios.

Exponer P(A>B), intervalo creíble y decisión recomendada.

Criterio de aceptación: tests con casos de 10, 50 y 200 acciones por variante.

PR 6 — Panel Metabase

Conectar Metabase a PostgreSQL.

Crear dashboards: Ranking de acciones, Embudo por red, Cohortes de plantilla, Conversaciones atribuidas, Seguidores netos.

Exportar definiciones de dashboards como código versionado.

Criterio de aceptación: cualquier acción puede rastrearse desde panel hasta comentario original.

PR 7 — Extensión a las nueve redes

Añadir adaptadores restantes siguiendo la interfaz común.

Mantener un contrato JSON idéntico y tests de grabación/reproducción por red.

Activar ranking global y ranking por red.

Criterio de aceptación: el mismo experimento puede compararse entre X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram.

Aplicación transversal

X, Threads, Bluesky, Mastodon: prioriza respuestas contextualizadas y hilos; atribuye conversaciones por target_post_id y respuestas posteriores.

Facebook: mide comentarios, compartidos y clics desde grupos/páginas; usa ventanas más largas por menor velocidad de interacción.

Pinterest: el outcome principal es guardado, clic saliente y visita a ficha/libro; UTM es esencial.

Reddit: separa karma, respuestas y clics; una respuesta útil puede generar tráfico diferido.

TikTok e Instagram: usa enlace en bio o story como atribución directa; las métricas nativas sirven como señales secundarias.

Todos: registra también acciones fallidas y contexto; el ranking debe penalizar plantillas que generan silencio, no solo premiar volumen.

Fuentes

Postiz — repositorio, licencia AGPL-3.0 y capacidades de analítica self-hosted: 
https://github.com/gitroomhq/postiz-app
github

PostHog — eventos, experimentos, licencia y límites orientativos del despliegue open source: 
https://github.com/posthog/posthog
github

Metabase — repositorio y licenciación por ediciones: 
https://github.com/metabase/metabase
github

Metabase — necesidad de sincronizar datos externos antes de crear paneles: 
https://www.metabase.com/integrations/github
metabase

bayesAB — métodos bayesianos para A/B testing: 
https://github.com/FrankPortman/bayesAB
github

campaignlab — UTM, atribución de clics y conversión idempotente: 
https://github.com/topics/campaign-tracking
github

Plausible — analítica web ligera, self-hosted y AGPL: 
https://github.com/plausible/analytics
github

Tema GitHub de social media management — catálogo de proyectos multirred y licencias: 
https://github.com/topics/social-media-management
github

# Ranking de acciones prometedoras con aprendizaje por resultados

Fuente: informe de Perplexity (https://www.perplexity.ai/search/27519b00-207d-42e4-92da-0a0693d7d563), generado 10/10/2026.

Investigación: bandits contextuales para priorizar acciones sociales

Resumen. Para priorizar follow, respuesta y repost en X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram, recomiendo un núcleo común de bandit contextual basado en Vowpal Wabbit para producción online y MABWiser para experimentación rápida; contextualbandits puede servir como referencia y validación offline. Con pocos datos, el diseño debe ser conservador: pocos brazos, features reducidas, Thompson Sampling/LinUCB con priors, exploración mínima garantizada y recompensa compuesta por reciprocidad y engagement real, no por acción ejecutada.
github
+2

Hallazgos
Repositorio	Licencia	Qué reutilizar	Integración en el sistema	Riesgos técnicos	Tests propuestos
VowpalWabbit/vowpal_wabbit	BSD-3-Clause 
pypi
	Aprendizaje online, contextual bandits con --cb y --cb_explore_adf, hashing de features y modelos compactos. 
vowpalwabbit
+1
	Núcleo de ranking en producción: contexto de red + candidato + acción → probabilidad/valor esperado; actualización inmediata tras resultado.	Binario/dependencias nativas; formato de ejemplos propio; requiere serialización y versionado de modelos.	Unit: parseo de contexto; integración: predicción y learn con recompensa; regresión: mismo input produce misma acción con semilla.

fidelity/mabwiser
	Apache-2.0 
github
	LinUCB, LinTS, epsilon-greedy, UCB1, Thompson, políticas contextuales paramétricas y no paramétricas; simulación y paralelización. 
github
	Motor de backtesting y calibración: comparar políticas por red antes de promoverlas a producción.	Menos orientado a streaming masivo que VW; última release 2.7.4 en 2024, por lo que conviene aislarlo como dependencia de experimentación. 
github
	Simulaciones con datos históricos; comparación LinTS vs LinUCB vs epsilon-greedy; verificación de reproducibilidad con semilla.

david-cortes/contextualbandits
	BSD-2-Clause 
github
	LinUCB, Linear Thompson Sampling, variantes logísticas y adaptaciones de MAB; compatible con oráculos scikit-learn. 
github
+1
	Referencia secundaria y validador: reproducir decisiones del núcleo con modelos lineales simples.	Última versión 0.3.28 y actividad más lenta; no debe ser el motor principal. 
release-monitoring
+1
	Paridad de ranking con VW en dataset sintético; tests de decaimiento temporal y cold start.

PlaytikaOSS/pybandits
	MIT 
github
	Thompson Sampling contextual bayesiano basado en PyMC; útil para modelar incertidumbre con pocos eventos. 
github
	Módulo opcional de calibración bayesiana para redes de bajo volumen, como Mastodon o Bluesky al inicio.	PyMC puede ser pesado; inferencia más lenta que LinTS.	Tests de convergencia con pocos ejemplos; comparación contra LinTS; límite de tiempo de inferencia.

banditml/banditml
	GPL-3.0 
github
	Diseño ligero de bandit contextual para servicios Python en producción. 
github
	Inspiración arquitectónica: API de decisión y feedback separada del almacenamiento.	GPL-3.0 exige cautela si se copia código en un repo privado con distribución posterior; mejor usarlo como referencia conceptual.	Tests de contrato de API: select, reward, persistencia y recuperación.

fidelity/mab2rec
	Componentes reutilizables sobre MABWiser 
fidelity
	Composición de representación de contenido/usuario, selección de brazo y evaluación. 
fidelity
	Patrón para separar features, política y métricas; sirve de modelo para el adaptador multired.	Más orientado a recomendación de ítems que a acciones sociales.	Tests de pipeline: features → score → ranking → feedback → métrica.
Recomendación

Arquitectura homogénea: un solo “Decision Core” con esquema común de contexto, tres acciones base y adaptadores por red que solo traducen señales nativas a ese esquema.

Brazos: follow, reply, repost — y opcionalmente skip, para no obligar al modelo a actuar siempre.

Contexto común: red, tipo de perfil, tema/nicho, antigüedad del post, actividad reciente del autor, señales de interacción, hora local, idioma y afinidad temática.

Features por candidato: similitud semántica con fantasy/romantasy, probabilidad de respuesta humana, autor activo, tamaño y calidad de la conversación, señales de reciprocidad histórica.

Recompensa: no usar “acción realizada” como éxito. Usar una recompensa retardada compuesta, por ejemplo:

𝑟
=
0.35
⋅
𝑟
𝑒
𝑐
𝑖
𝑝
𝑟
𝑜
𝑐
𝑖
𝑑
𝑎
𝑑
+
0.30
⋅
𝑒
𝑛
𝑔
𝑎
𝑔
𝑒
𝑚
𝑒
𝑛
𝑡
+
0.20
⋅
𝑐
𝑜
𝑛
𝑣
𝑒
𝑟
𝑠
𝑎
𝑐
𝑖
𝑜
𝑛
+
0.15
⋅
𝑐
𝑎
𝑙
𝑖
𝑑
𝑎
𝑑
_
𝑝
𝑒
𝑟
𝑓
𝑖
𝑙
r=0.35⋅reciprocidad+0.30⋅engagement+0.20⋅conversacion+0.15⋅calidad_perfil

donde reciprocidad puede ser follow-back, respuesta recibida o interacción posterior; engagement, likes, reposts, comentarios o clics según la red; conversacion, respuestas sostenidas; y calidad_perfil, autor relevante del nicho. El feedback en bandits reales suele ser retardado, y Thompson Sampling es especialmente adecuado en ese escenario porque mantiene exploración estocástica aunque no lleguen actualizaciones inmediatas.
eugeneyan

Política inicial: LinTS con prior informativo y exploración acotada. Cuando haya al menos 300–500 resultados etiquetados por red, evaluar LinUCB y VW --cb_explore_adf; no empezar con modelos neuronales ni espacios grandes de acciones. VW soporta contextual bandits online y escenarios de acciones grandes, pero esa potencia no es necesaria en la fase inicial.
vowpalwabbit
+1

Calibración con pocos datos

Cold start por priors, no por azar puro. Asignar priors por acción y red a partir de reglas editoriales: reply suele tener mejor señal de reciprocidad que follow; repost es más seguro cuando el post ya tiene tracción.

Exploración mínima y controlada. Reservar un porcentaje pequeño de decisiones a exploración, con tope diario por red; el resto debe explotar la mejor política actual.

Agrupar redes por régimen de datos. Grupo A: X, Instagram, TikTok, Facebook, Reddit. Grupo B: Threads, Bluesky, Mastodon, Pinterest. Cada grupo puede compartir priors hasta alcanzar volumen propio.

Ventanas temporales cortas. Evaluar recompensa a 24 h, 72 h y 7 días; descontar señales antiguas para evitar que un follow-back esporádico domine el modelo.

Filtro de calidad previo. El bandit elige entre candidatos válidos; no debe usarse para decidir si comentar en posts irrelevantes. La candidatura ya debe pasar filtros de nicho, idioma y actividad.

Registro contrafactual. Guardar contexto, acción elegida, score, alternativas consideradas, timestamp y recompensa. VW está diseñado para aprender de datos de bandit ya recogidos o con exploración.
vowpalwabbit

Plan de implementación en PR pequeñas
PR	Alcance	Entregable
PR 1	Esquema común	ActionContext, ActionCandidate, ActionDecision, ActionFeedback y enum de redes/acciones.
PR 2	Recompensa	Calculador de recompensa con pesos configurables, ventanas de 24 h/72 h/7 días y decaimiento temporal.
PR 3	MABWiser	Adaptador LinTS y LinUCB, con persistencia JSON/SQLite y semilla reproducible.
PR 4	Backtesting	Simulador offline que reproduzca histórico y compare políticas por red y grupo de redes.
PR 5	VW	Adaptador de producción con --cb_explore_adf, feature hashing, guardado/carga de modelo y logging.
PR 6	Adaptadores	Normalización de señales por red hacia el esquema común; sin lógica de ranking duplicada.
PR 7	Ranking	Score final = bandit + reglas de seguridad/calidad + diversidad de autores y temas.
PR 8	Observabilidad	Métricas por red: CTR de acción, tasa de reciprocidad, engagement medio, exploración real y drift temporal.
Aplicación multired

X, Threads, Bluesky, Mastodon: reply y repost son señales más ricas que follow; priorizar conversación y reciprocidad.

Instagram y TikTok: follow puede tener recompensa más lenta; añadir interacciones como comentario, guardado o respuesta a story como señales de engagement cuando estén disponibles.

Facebook: agrupar por página/grupo y tipo de publicación; el contexto de comunidad importa más que el autor individual.

Pinterest: repost equivale funcionalmente a guardar/compartir; la recompensa debe priorizar guardados, clics y tráfico posterior.

Reddit: reply debe dominar; el karma, las respuestas recibidas y la permanencia del comentario son mejores recompensas que el follow.

Fuentes

MABWiser — GitHub
github

Mab2Rec — Bandit-based Recommenders
fidelity

contextualbandits — GitHub
github

contextualbandits — documentación
contextual-bandits

Vowpal Wabbit — Contextual Bandits
vowpalwabbit

Vowpal Wabbit — releases
github

vowpalwabbit — PyPI
pypi

PyBandits — GitHub
github

banditml — GitHub
github

Bandits for Recommender Systems — Eugene Yan
eugeneyan

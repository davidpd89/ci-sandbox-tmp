# Comentarios humanos y variados en Facebook (páginas y grupos)

Fuente: informe de Perplexity (https://www.perplexity.ai/search/07b1f82b-43e0-45f0-816a-4edf17cc54eb), generado 10/10/2026.

Informe mejorado: comentarios naturales de lectores y autores en Facebook
Resumen

Tras revisar el repo espejo y contrastar repos públicos, la conclusión se mantiene pero se acota: para Facebook conviene construir una capa de voz, variantes y evaluación de comentarios en español, no un bot nuevo de navegación ni otro pipeline de descubrimiento. El sistema ya dispone de ramas específicas de Facebook, comentarios humanos en español, evidencia contextual nativa y selección de candidatos de respuesta, de modo que cualquier PR debe enchufarse a esas piezas en vez de duplicarlas.

He eliminado del informe anterior las recomendaciones poco aprovechables: pruthvikurada/Facebook-Comment-Auto-Reply es un proyecto de 2017, sin madurez ni controles modernos; los scrapers genéricos solo sirven como referencia de esquema de datos, no como componente de ejecución; y langchain-ai/social-media-agent está orientado a curación y publicación de posts, no a comentarios conversacionales, por lo que no entra como dependencia recomendada.

Lectura del repo espejo

La rama main de davidpd89/ci-sandbox-tmp incluye 00_OPERATIVO, tests, tools y carpetas por red, entre ellas publicaciones Facebook GPT; además existen ramas directamente aplicables: research/perplexity-crecimiento-facebook, research/perplexity-comentarios-humanos-es, research/perplexity-facebook-hashtags-fuentes, research/native-context-evidence-adapters, research/reply-candidate-selection-wiring-9nets y research/spanish-orthography-inflection-regressions.

Por tanto, el diseño correcto es:

Reutilizar el descubrimiento, la evidencia nativa y las colas existentes.

Añadir un adaptador de Facebook para generación de comentarios, no un servicio paralelo.

Dejar la decisión final al ranking existente, alimentándolo con señales específicas de Facebook.

Separar claramente los perfiles de página de autora y grupo de lectores.

Patrón de comentario natural

Los comentarios españoles naturales suelen ser breves, coloquiales y con conectores como “totalmente”, “exacto”, “además”, “por eso” o “la verdad es que”; usan presente, omiten pronombres innecesarios y combinan reacción con experiencia personal.

Para el nicho de fantasía, romantasy y lectura, el patrón más robusto es:

Elemento	Regla	Ejemplo
Apertura	Reacción breve al detalle dominante	“Ay, esa escena me dejó con el corazón en un puño.”
Especificidad	Mención concreta al post	“El contraste entre ella y el guardián funciona muchísimo.”
Experiencia	Una frase personal, no un discurso	“A mí siempre me pasa que me enamoro del secundario.”
Pregunta	Opcional y ligera	“¿Lo escribirás desde su punto de vista también?”
Emojis	0–2, funcionales	“Jajaja, el caos romántico es real 😂”
Longitud por contexto
Contexto	Longitud objetivo	Estructura
Comentario en página	1–3 frases	Reacción + detalle concreto
Comentario en grupo	2–5 frases	Reacción + experiencia + pregunta o recomendación
Respuesta a comentario	1–2 frases	Reconocimiento + microaporte
Hilo con debate	2–4 frases	Postura + matiz + pregunta

Ejemplo para una portada de fantasía:

“Me encanta cómo la luz del título contrasta con el fondo. Da mucha sensación de historia oscura, pero con algo íntimo detrás. ¿La protagonista tiene alguna marca o símbolo importante?”

Ejemplo para un grupo de lectores:

“Totalmente, los enemigos a amantes funcionan cuando hay una razón real para desconfiar. Si además uno guarda un secreto que puede romper la alianza, ya me tengo. ¿Cuál es vuestro tropo inevitable?”

Hallazgos
Repo / fuente	Estado	Qué copiar	Integración	Riesgo técnico	Tests

lakpriya1s/hushreply
	Activo; 3 commits, estructura actual, AGPL-3.0	Rotación de respuestas determinista por comment_id, claim de comentario, cooldown, guardia de autocomentario y DRY_RUN	Portar la lógica de idempotencia y variantes al adaptador de respuestas de Facebook	TypeScript/Cloudflare Workers; hay que portarlo a Python del repo	Mismo comment_id no produce segunda respuesta; variantes no repetidas; cooldown funciona

thanhduy1706/ai-comment-bot
	Activo como repo; 12 estrellas, 7 commits, MIT	Prompt base de comentario “friendly, specific and engaging” y concepto de variantes humanas	Copiar solo el prompt y ampliarlo con contexto, tono y restricciones; no usar Selenium como ejecutor	Selenium frágil y dependiente del DOM de Facebook	Longitud, español, especificidad, ausencia de plantilla repetida

MasuRii/FBScrapeIdeas
	Actualizado en 2025; CLI con Playwright/Selenium y export CSV/JSON	Esquema de datos de posts y comentarios: texto, URL, timestamp, autor, comment_id, sentimiento y categoría	Usarlo como referencia para el modelo interno de oportunidades y comentarios, no como scraper productivo	Automatización de navegador y dependencia de UI	Validación de esquema: campos obligatorios, comment_id único, jerarquía de hilo

disrex-group/FB-Comments-Exporter-User-script
	Actualizado en 2025	Exportación de comentarios anidados a CSV/JSON con jerarquía	Inspiración para parent_comment_id, depth y reconstrucción de hilo	Userscript ligado al DOM	Test de relaciones padre/hijo y profundidad máxima

kevinzg/facebook-scraper
	Repositorio veterano; útil como referencia de campos	Estructura de comments_full, exportación CSV/JSON y límites de comentarios	Solo como contrato de datos para ingestión histórica o muestras	Proyecto antiguo; no usar como componente de ejecución	Test de normalización de comentarios y metadatos

LivXue/SoMe
	Benchmark académico AAAI 2026	Evaluación comparada de comentarios generados por agentes sociales	Inspiración para un evaluador offline de naturalidad, especificidad y variedad	Enfocado a investigación; requiere adaptación	Ranking humano/automático de candidatos; detección de comentarios genéricos

Social-Media-Capstone/Social-Media-Engagement-Forecasting
	Repositorio de investigación	Idea de que ciertas palabras y patrones impulsan engagement por nicho	Añadir features léxicas al ranking, no como verdad universal	Dataset y nicho distintos del nuestro	Correlación entre features y respuestas/likes reales

hushreply es la pieza más directamente reutilizable: su README documenta que el comentario se reclama una sola vez antes de actuar, que las respuestas públicas rotan entre variantes elegidas desde el comment_id, y que una reentrega de webhook no publica una segunda respuesta distinta.

Código tal cual para reutilizar
1. Regla con variantes rotatorias e idempotencia conceptual

Este fragmento es el modelo de configuración que conviene adaptar al esquema interno de Facebook: variantes públicas, coincidencia por palabra clave y respuesta asociada.

json
// Fuente exacta: https://github.com/lakpriya1s/hushreply/blob/main/README.md
{
  "id": "link",
  "keyword": "LINK",
  "dm": "Hey {{name}}! Here's the link you asked for 👇\n\nhttps://example.com",
  "publicReply": ["Just sent it to your DMs 📬", "Check your DMs {{name}} 📬"]
}

Adaptación propuesta para nuestro sistema: sustituir publicReply por comment_candidates, cada uno con metadatos de tono, longitud, emoji y perfil (pagina_autora o grupo_lectores). La elección debe hacerla el ranking, no una rotación ciega.

2. Prompt base a ampliar

Este es el prompt original del repo de Selenium; sirve como semilla, pero hay que sustituirlo por una versión con contexto del post, hilo, perfil de voz y restricciones de español.

text
# Fuente exacta: https://github.com/thanhduy1706/ai-comment-bot/blob/main/README.md
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_PROMPT=Generate a friendly, specific, and engaging Facebook comment.
POST_URL=https://www.facebook.com/your_post_url_here

Versión mejorada para nuestro adaptador:

text
Escribe un comentario en español de España para Facebook.

Contexto:
- Tipo de cuenta: {pagina_autora | grupo_lectores}
- Post: {texto_post}
- Comentario padre, si existe: {comentario_padre}
- Detalles relevantes: {trope, personaje, portada, escena, duda}
- Tema: fantasía juvenil, romantasy, lectura, escritura

Reglas:
- 1–3 frases en página; 2–5 en grupo.
- Menciona al menos un detalle concreto del post.
- Tono humano, cálido y natural; nada corporativo.
- Máximo 1 emoji, solo si refuerza la emoción.
- No repitas conectores usados en los últimos comentarios.
- Si añades pregunta, que sea abierta y breve.
- Devuelve solo el comentario, sin comillas ni explicaciones.
3. Pseudocódigo de selección determinista

Basado en el mecanismo descrito por hushreply: el comentario se reclama antes de responder y la variante se deriva del identificador, evitando respuestas distintas ante reentregas.

python
# Adaptación propia del patrón de:
# https://github.com/lakpriya1s/hushreply/blob/main/README.md

import hashlib

def elegir_variante(comment_id: str, candidatos: list[str]) -> str:
    if not candidatos:
        raise ValueError("No hay candidatos de comentario")
    digest = hashlib.sha256(comment_id.encode("utf-8")).hexdigest()
    indice = int(digest, 16) % len(candidatos)
    return candidatos[indice]

def puede_responder(comment_id: str, store, ahora) -> bool:
    if store.exists(f"respondido:{comment_id}"):
        return False
    store.set(f"respondido:{comment_id}", ahora, ttl=7 * 24 * 3600)
    return True
Qué quitar del informe anterior

pruthvikurada/Facebook-Comment-Auto-Reply: eliminado como recomendación; es de 2017 y no aporta controles modernos de idempotencia, variantes ni evaluación.

Scrapers como componente de ejecución: kevinzg/facebook-scraper, mohdtalal3/facebook_post_comment_scraper y similares se relegan a referencia de esquema de datos; no deben convertirse en la vía principal de obtención de comentarios.
github
+1

langchain-ai/social-media-agent: eliminado como dependencia; su valor es la orquestación de posts con revisión humana, no la generación conversacional de comentarios.

Rotación ciega de respuestas: se sustituye por selección asistida por ranking; la rotación determinista se reserva para evitar duplicados ante reentregas.

Recomendación

Implementar un Facebook Spanish Comment Voice Pack con tres perfiles:

Perfil	Tono	Longitud	Emojis	Pregunta
Página de autora	Cálida, cercana, con voz editorial	1–3 frases	0–1	Opcional
Grupo de lectores	Espontáneo, afín, coloquial	2–5 frases	0–2	Frecuente, no obligatoria
Respuesta a comentario	Reconocimiento + microaporte	1–2 frases	0–1	Solo si abre conversación

Reglas duras:

Rechazar comentarios sin referencia concreta al post.

Prohibir aperturas genéricas tipo “¡Qué buen post!”.

Limitar emojis y evitar más de uno por frase.

Alternar estructura entre candidatos: reacción + detalle, pregunta + opinión, anécdota + cierre.

Registrar qué variante se publicó, para evitar repetición y medir rendimiento.

Plan de implementación en PR pequeñas
PR 1 — Especificación de voz

Crear docs/facebook/comment_voice_es.md con perfiles de página y grupo, límites de longitud, catálogo de conectores, ejemplos positivos/negativos y reglas de emojis. Debe partir de research/perplexity-comentarios-humanos-es.

PR 2 — Esquema de candidato

Definir el objeto interno:

json
{
  "network": "facebook",
  "surface": "page|group",
  "post_id": "string",
  "parent_comment_id": "string|null",
  "context": {
    "post_text": "string",
    "thread": [],
    "entities": ["trope", "personaje", "portada"]
  },
  "candidates": [
    {
      "text": "string",
      "voice_profile": "pagina_autora|grupo_lectores",
      "length_class": "short|medium",
      "has_question": true,
      "emoji_count": 1,
      "specificity_score": 0.82
    }
  ]
}
PR 3 — Generador de variantes

Añadir un generador que produzca 3–5 candidatos por oportunidad usando el contexto nativo ya disponible. Debe alimentarse de research/native-context-evidence-adapters y entregar candidatos al selector de research/reply-candidate-selection-wiring-9nets.

PR 4 — Evaluador de naturalidad

Implementar filtros y puntuaciones:

Longitud dentro del rango del perfil.

Presencia de al menos una entidad o detalle del post.

Variedad léxica frente a los últimos N comentarios.

Español correcto, con especial atención a tildes e inflexiones; aprovechar research/spanish-orthography-inflection-regressions.

Penalización de plantillas, exceso de emojis y preguntas cerradas.

PR 5 — Idempotencia y cooldown

Portar a Python el patrón de claim por comment_id, cooldown por persona y guardia de autocomentario documentado en hushreply.

PR 6 — Ranking específico

Extender el ranking con señales propias de Facebook: superficie página/grupo, profundidad del hilo, especificidad, novedad, tono adecuado y rendimiento histórico. No sustituir el ranking global.

Aplicación a las demás redes

El núcleo —contexto nativo, variantes, evaluador, idempotencia y ranking— es común. Solo cambian los parámetros:

X y Threads: 1–2 frases, menos emojis, más gancho.

Bluesky y Mastodon: tono comunitario, contexto de hilo y menos orientación comercial.

Instagram y TikTok: más emoción, emojis moderados y referencia visual o de vídeo.

Pinterest: comentario útil, descriptivo y orientado a guardado.

Reddit: utilidad, experiencia concreta y respeto al contexto del subreddit.

Facebook: mayor longitud tolerada, grupos como espacio de conversación y preguntas más naturales.

Fuentes

Repositorio espejo davidpd89/ci-sandbox-tmp, rama main y ramas de investigación relevantes: https://github.com/davidpd89/ci-sandbox-tmp

lakpriya1s/hushreply: 
https://github.com/lakpriya1s/hushreply

thanhduy1706/ai-comment-bot: 
https://github.com/thanhduy1706/ai-comment-bot

MasuRii/FBScrapeIdeas: 
https://github.com/MasuRii/FBScrapeIdeas
github

disrex-group/FB-Comments-Exporter-User-script: 
https://github.com/disrex-group/FB-Comments-Exporter-User-script

kevinzg/facebook-scraper: 
https://github.com/kevinzg/facebook-scraper
github

LivXue/SoMe: 
https://github.com/LivXue/SoMe

Social-Media-Capstone/Social-Media-Engagement-Forecasting: 
https://github.com/Social-Media-Capstone/Social-Media-Engagement-Forecasting
github

Guía de comentarios naturales en español: 
https://spanishstep.com/archives/24071

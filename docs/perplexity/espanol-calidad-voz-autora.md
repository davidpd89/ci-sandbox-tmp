# Calidad del español y voz de autora

Fuente: informe de Perplexity (https://www.perplexity.ai/search/c9ef5db4-40a4-40f1-b390-6148969021e7), generado 10/10/2026.

Informe: calidad del español, voz de autora y detección de IA
Resumen

Para el sistema de crecimiento multired conviene montar una capa editorial común en Python: LanguageTool para ortografía, tildes y gramática; PUCP-Metrix + spaCy español para registro, variedad léxica y legibilidad; pystylometry + embeddings multilingües para medir cercanía a la voz de David Porto; y GLTR/Binoculars como señales de tics de IA, siempre con revisión humana. La recomendación central es no usar un detector como veredicto, sino convertir sus métricas en un score editorial accionable antes de publicar en X, Threads, Facebook, Pinterest, Reddit, Bluesky, Mastodon, TikTok e Instagram.
arxiv
+3

Hallazgos
Área	Repo / recurso	Licencia	Qué reutilizar	Integración en el sistema	Riesgos técnicos
Ortografía, tildes, gramática y estilo	
languagetool-org/languagetool
	LGPL-2.1 o posterior	Motor de corrección con soporte explícito de español; reglas gramaticales, ortográficas y de estilo; servidor local/API	Servicio quality-es: recibe texto y red social, devuelve errores por categoría, sugerencias y texto corregido propuesto	Requiere JVM; algunas reglas o límites pueden depender de la edición/servicio; conviene aislarlo tras una API propia
Corrector local alternativo	
languagetool Docker
	Según imagen/proyecto	Despliegue contenedorizado del corrector	Ejecutar LanguageTool como servicio interno en Windows vía Docker Desktop o WSL2	Añade infraestructura; vigilar memoria y versiones de Java
Análisis lingüístico español	
iapucp/pucp-metrix
	CC BY-NC-SA 4.0	182 métricas: diversidad léxica, densidad de categorías, cohesión, complejidad sintáctica/semántica, psicología y legibilidad	Generar perfil por post: riqueza léxica, longitud, cohesión, registro y legibilidad; comparar con corpus propio	Licencia no comercial: usar como dependencia de análisis interno requiere revisar el alcance de uso; no copiar su código en un producto comercial sin asesoría
NLP español base	
explosion/spacy-models
, modelo es_core_news_lg	Modelo documentado como MIT/BSD-3 en empaquetado conda; spaCy es MIT	Tokenización, lematización, POS, dependencias, NER y frases en español	Preprocesador común para métricas, extracción de entidades, detección de hashtags/menciones y normalización	Los modelos consumen RAM; validar versiones de spaCy/modelo en Python 3.11
Estilometría y atribución	craigtrim/pystylometry	MIT	Burrows’ Delta, Cosine Delta, Zeta, chi-cuadrado, NCD y más de 50 métricas; incluye módulo de detección de generación	Crear “huella de voz” a partir de novelas, newsletters, hilos y comentarios aprobados; puntuar cada borrador contra esa huella	Necesita corpus limpio y suficientemente amplio; los resultados deben calibrarse por tipo de pieza
Estilometría ligera	
riadmaouchi/stylometry-python
	MIT	Biblioteca ligera para estilo, atribución y cambios estilísticos introducidos por LLM	Alternativa rápida si PUCP-Metrix resulta pesada; útil para comparaciones por red	Proyecto pequeño y con pocas estrellas; tratarlo como complemento, no como núcleo
Similitud semántica y paráfrasis	
huggingface/sentence-transformers
	Apache-2.0	Embeddings multilingües, similitud semántica, clustering y minería de paráfrasis	Medir si un post mantiene el significado tras reescritura; agrupar comentarios por tema; evitar duplicados entre redes	La calidad depende del modelo elegido; embeddings no capturan por sí solos ritmo, humor o voz
Transferencia de estilo few-shot	
zacharyhorvitz/TinyStyler
	MIT	Transferencia de estilo con pocos ejemplos mediante representaciones de autoría; conserva significado	Prototipo de “adaptador de voz”: convertir un borrador neutro en versión más cercana al registro de David Porto	Modelo de 800M parámetros; español no es su caso de evaluación principal; usar solo como propuesta, nunca publicación automática
Transferencia por paráfrasis	
martiansideofthemoon/style-transfer-paraphrase
	Revisar licencia y datos en el repo	Código y datos para reformular transferencia de estilo como generación de paráfrasis	Base conceptual para un flujo “borrador → paráfrasis controlada → validación de voz”	Investigación de 2020; requiere adaptación fuerte y modelos en inglés; no prioritario frente a TinyStyler
Detección de IA, enfoque GLTR	
luciayn/AI-generated-Text-Detection-with-GLTR-based-approach
	MIT	Implementación GLTR evaluada también en español dentro de IberLEF-AuTexTification 2023	Señal de predictibilidad por token — detectar prosa excesivamente predecible, repetitiva o “plana”	GLTR original se apoya en GPT-2; requiere calibración con textos humanos del nicho
Detección de IA zero-shot	
ahans30/Binoculars
	BSD-3-Clause	Método sin entrenamiento, basado en perplejidad cruzada de dos modelos	Puntuar borradores antes de publicar; marcar solo outliers para revisión humana	Los autores advierten expresamente contra uso sin supervisión humana; rendimiento multilingüe debe validarse con corpus español propio
Detección estadística simple	
bancaditalia/gen-text-detect
	Revisar licencia en el repo	Enfoques ingenuos y reproducibles para separar texto humano y generado	Baseline barato: longitud, repetición, diversidad, frecuencia de palabras y cohesión	Menos preciso que métodos modernos; útil como control y explicabilidad
GLTR original	
GLTR
 y detecting-fake-text	Revisar licencia del repo original	Herramienta forense visual de tokens según probabilidad predictiva	Referencia para construir un panel de revisión editorial, no para automatizar decisiones	Orientado a GPT-2/inglés; no debe usarse como detector español definitivo

LanguageTool es la base más sólida para la capa de calidad: su núcleo es LGPL-2.1+, incluye español y puede ejecutarse como servidor propio. PUCP-Metrix es el hallazgo más específico para español: ofrece 182 métricas y ha sido evaluado tanto para legibilidad como para detección de texto generado. Para imitar voz, la combinación más práctica es una huella estilométrica propia más embeddings semánticos; TinyStyler puede explorarse después como generador asistido, no como sustituto de la revisión humana.
arxiv
+6

Recomendación

Implementar una arquitectura de tres capas, común a todas las redes:

Capa de corrección: LanguageTool local para tildes, concordancia, puntuación y errores groseros.

Capa de voz y registro: perfil estilométrico de David Porto + PUCP-Metrix + embeddings de sentence-transformers.

Capa de señales de IA: GLTR español, Binoculars y métricas propias de repetición, previsibilidad y cohesión.

El objetivo no es “parecer humano” de forma engañosa, sino elevar la calidad editorial: conservar la voz real del autor, variar léxico, ajustar registro por red y eliminar patrones mecánicos. Binoculars y GLTR deben alimentar una cola de revisión, no bloquear publicaciones automáticamente.
github
+1

Perfil de voz propio

El corpus debe separarse por tipo de texto:

Novela y prosa de fantasía/romantasy.

Sinopsis, newsletter y blog.

Comentarios sociales aprobados manualmente.

Hilos, captions y respuestas por red.

Cada perfil guarda: longitud media de frase, proporción de adjetivos/adverbios, diversidad léxica, conectores frecuentes, metáforas recurrentes, ritmo de párrafo, entidades del canon y similitud semántica con textos de referencia. Así se puede exigir, por ejemplo, más tensión y menos explicación en un gancho de TikTok, y más contexto cálido en Facebook.

Plan de implementación en PR pequeñas
PR 1 — Contrato de calidad editorial

Crear src/quality_es/schemas.py con QualityReport, Issue, VoiceScore y AIDetectionSignal.

Definir umbrales por red: X/Threads más breves; Pinterest más visual-descriptivo; Reddit más conversacional; Facebook más narrativo.

Tests con textos correctos, con tildes ausentes, con repeticiones y con registro inadecuado.

PR 2 — Corrector español con LanguageTool

Añadir servicio language_tool local o contenedor.

Implementar cliente con reintentos, timeout y normalización de resultados.

Guardar correcciones sugeridas sin aplicarlas automáticamente.

Tests: “espanol” → “español”; concordancia básica; puntuación duplicada; texto vacío.

PR 3 — Métricas de español y registro

Integrar spaCy + es_core_news_lg.

Integrar PUCP-Metrix como dependencia de análisis, respetando su licencia CC BY-NC-SA.

Calcular: TTR, densidad de adjetivos/adverbios, longitud de frase, legibilidad adaptada al español, cohesión y repetición.

Emitir recomendaciones: “reduce adjetivos”, “varía conectores”, “acorta párrafo”, “añade concreción sensorial”.

PR 4 — Huella de voz de David Porto

Crear corpus/voz_david/ con textos etiquetados por tipo y red.

Implementar voice_profile.py con pystylometry: Delta, Cosine Delta, Zeta y métricas de diversidad.

Calcular similitud semántica con sentence-transformers.

Generar un informe: voice_distance, semantic_drift, lexical_richness, sentence_rhythm.

Tests de regresión: un texto claramente ajeno al corpus debe puntuar peor que un fragmento propio.

PR 5 — Señales de IA y tics

Integrar GLTR español y Binoculars como analizadores opcionales.

Crear señales interpretables: baja entropía léxica, alta predictibilidad, frases de longitud casi idéntica, conectores repetidos, exceso de adjetivos genéricos y cohesión artificialmente uniforme.

Establecer tres bandas: ok, revisar, reescribir.

Nunca publicar automáticamente por debajo de ok; en reescribir, proponer cambios concretos.

PR 6 — Adaptadores por red
Red	Adaptación principal
X	Frases cortas, gancho inicial, cero relleno, control de longitud
Threads	Tono cercano, ritmo conversacional, pregunta final natural
Facebook	Más narrativa, contexto emocional, CTA suave
Pinterest	Descripción visual, palabras clave de fantasía, títulos evocadores
Reddit	Registro comunitario, menos promoción, más utilidad y especificidad
Bluesky	Brevedad, voz personal, humor o imagen vívida
Mastodon	Tono genuino, contexto, menos fórmulas publicitarias
TikTok	Gancho en 1-2 segundos, oralidad, ritmo y CTA corto
Instagram	Caption evocador, primera línea fuerte, hashtags relevantes y CTA claro
PR 7 — Panel y aprendizaje

Guardar cada texto con: red, score de calidad, score de voz, señales de IA, interacciones y resultado editorial.

Comparar variantes A/B por red.

Ajustar umbrales con datos reales: qué longitud, registro y densidad léxica generan más guardados, respuestas, clics o seguidores.

Fuentes

LanguageTool, núcleo LGPL-2.1+ y soporte de español: 
https://github.com/languagetool-org/languagetool
github

Detalle de licencia y recursos españoles de LanguageTool: 
https://github.com/languagetool-org/languagetool/blob/master/languagetool-standalone/README.md
github

PUCP-Metrix, 182 métricas para español: 
https://github.com/iapucp/pucp-metrix
arxiv

Artículo de PUCP-Metrix y licencia CC BY-NC-SA: 
https://arxiv.org/html/2511.17402v2
arxiv

Modelos spaCy: 
https://github.com/explosion/spacy-models
github

pystylometry, MIT y métricas de autoría: 
https://pypi.org/project/pystylometry/
pypi

sentence-transformers, Apache-2.0 y similitud semántica: 
https://github.com/huggingface/sentence-transformers
github

TinyStyler, MIT y transferencia few-shot: 
https://github.com/zacharyhorvitz/TinyStyler
github

GLTR en español, MIT: 
https://github.com/luciayn/AI-generated-Text-Detection-with-GLTR-based-approach
github

Binoculars, BSD-3-Clause y advertencia de supervisión humana: 
https://github.com/ahans30/Binoculars
github

GLTR original: http://gltr.io/
gltr

Detección estadística de texto generado: 
https://github.com/bancaditalia/gen-text-detect
github

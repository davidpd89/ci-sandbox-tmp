# Comentarios humanos y variados en X (Twitter)

Fuente: informe de Perplexity (https://www.perplexity.ai/search/88be557a-9632-42a2-b34c-7298ac55aa13), generado 10/10/2026.

Informe mejorado: comentarios y respuestas naturales en X para lectores y autores
Resumen

He revisado el espejo davidpd89/ci-sandbox-tmp en la rama research/perplexity-comentarios-humanos-es. El sistema ya contiene documentación de diversidad de respuestas (docs/research/reply-candidate-diversity-114.md), ramas de descubrimiento, ranking, adaptadores por red, memoria de contexto, calidad de voz en español e idempotencia; por tanto, la mejora correcta no es crear otro bot de publicación, sino añadir una capa de generación, validación, diversificación y ranking de candidatos de respuesta.

He retirado del informe anterior las afirmaciones no verificables o poco aplicables: los rangos exactos de caracteres “óptimos”, la prioridad automática de respuestas sobre otros tipos de acción y la idea de que los emojis deban regirse por una política rígida global. En su lugar, propongo reglas configurables por red, medibles con experimentos y compatibles con el pipeline existente.

Nota importante sobre el código: el conector de GitHub confirmó la descarga de los archivos, pero en esta sesión no expuso el contenido textual de los ficheros. Por coherencia con tu petición de “código tal cual”, no voy a inventar fragmentos ni presentarlos como copias literales. Abajo dejo las URL exactas de los archivos, su licencia y qué extraer de cada uno; los bloques Python que sí incluyo son código original de integración para nuestro repo, no copias de terceros.

Hallazgos verificados
Hallazgo	Fuente / repo	Licencia	Actividad y aplicabilidad	Qué reutilizar	Integración propuesta
Existen bots de respuesta a menciones con LLM, pero la mayoría resuelven transporte y API, no calidad conversacional.	gkamradt/twitter-reply-bot	No aparece licencia en los metadatos consultados	Último push: 31/05/2023; 66 estrellas; Python. Útil como referencia de flujo, no como dependencia.	Separación entre detección de mención, construcción de prompt, generación y publicación.	Inspirar ReplyCandidatePipeline, sin copiar código por ausencia de licencia verificada.
Un bot antiguo pero conceptualmente útil separa respuestas preparadas por intención/tema y evita repetir la misma respuesta.	analog-nico/twitter-reply-bot	ISC	Archivado; último push 24/07/2019; 41 estrellas; JavaScript. No reutilizar como runtime.	Modelo de carpetas responses/ por tema y selección no repetitiva.	Adaptar a YAML/JSON de plantillas en español con metadatos: ángulo, tono, red, tropo y nivel de formalidad.
La validación estructurada de salidas LLM es un patrón maduro: contrato, validación, reintento y registro de fallos.	labrat-akhona/semantix-ai	MIT	Último push: 16/09/2026; Python; 5 estrellas. Proyecto pequeño, pero activo y directamente aplicable.	Validadores semánticos y contratos de salida; no conviene depender del paquete entero.	Crear ReplyContract con Pydantic: texto, ángulo, pregunta opcional, emojis, red, motivo de selección y puntuaciones.
Los guardrails de salida deben validar tanto formato como intención; varios proyectos recientes lo confirman, aunque muchos son pequeños o sin licencia clara.	MANIGAAA27/agentguard	Sin licencia clara (NOASSERTION)	Python 3.11+, FastAPI; último push 22/03/2026.	Patrón de validación de entrada/salida, no código.	Añadir validadores previos a publicación: longitud, idioma, una pregunta máxima, emojis, prohibición de fórmulas.
Para español, los recursos públicos de PlanTL son más fiables que crear tokenización, normalización o evaluación lingüística desde cero.	PlanTL-GOB-ES/lm-spanish	Apache-2.0	Proyecto institucional; recursos en español.	Evaluación lingüística ligera y normalización; no es necesario ejecutar un LLM grande en CI.	Fase SpanishQualityGate tras generación y antes del ranking.
La interacción lectora en Twitter se asocia más con reacciones originales y participación activa que con repetir extractos; un estudio con 18.962 tweets encontró predominio de citas frente a reacciones propias.	Estudio de lectura social en Twitter	No aplica	Publicado en 2022; revisado por pares.	Criterio de originalidad: penalizar respuestas que solo repiten o parafrasean el post.	OriginalityScorer con similitud frente al post y frente a candidatos previos.
Las preguntas concretas y una sola por respuesta son el patrón más defendible para abrir conversación; las guías coinciden en evitar preguntas cerradas genéricas.	Supabird: Twitter engagement tips	No aplica	Artículo actualizado en 2026.	Banco de preguntas con disyuntiva real, experiencia o matiz narrativo.	QuestionBuilder con plantillas parametrizadas por tropo, arco, mundo y lectura actual.
La relación entre longitud y engagement no es lineal; no existe un número universal “óptimo” aplicable a todas las cuentas y formatos.	Limitora: longitud y engagement	No aplica	Análisis de 2025; útil como hipótesis, no como regla fija.	Rango inicial configurable, no límite duro.	length_profile por red y experimento A/B: 60–120, 120–180 y 180–240 caracteres.
Repos menos obvios y su valor real
Repo	Licencia	Estado	Por qué importa	Decisión
gkamradt/twitter-reply-bot	Sin licencia visible en metadatos	Inactivo desde 2023	Muestra el flujo completo de respuesta automática con LLM.	Solo referencia arquitectónica; no copiar código.
analog-nico/twitter-reply-bot/blob/master/server.js	ISC	Archivado	Demuestra respuestas preparadas, búsqueda por términos y selección de respuesta.	Reutilizar el concepto de banco de respuestas y anti-repetición.
labrat-akhona/semantix-ai/blob/master/examples.py	MIT	Activo en 2026	Ejemplos de validación semántica de salidas de LLM en Python.	Candidato a dependencia opcional o referencia directa para ReplyContract.
BeaEsparcia/spanish-text-classification-bert	MIT	Último push 15/07/2025	Clasificador de intención en español: petición de información, queja o recomendación.	Referencia para detectar intención del post antes de elegir el ángulo de respuesta.
SebaB29/criticas-peliculas	MIT	Archivado; último push 03/06/2026	Normalización y análisis de reseñas en español.	Útil para normalizar texto y detectar polaridad en comentarios de lectores.
PlanTL-GOB-ES/lm-spanish	Apache-2.0	Mantenido institucionalmente	Recursos y modelos de lenguaje en español.	Base para evaluación de calidad lingüística; evitar modelos pesados en CI.
Piezas reutilizables y URLs exactas
1. Flujo de respuesta con LLM

Archivo: gkamradt/twitter-reply-bot/blob/main/twitter-reply-bot.py
Licencia: no verificada en los metadatos del repositorio; por ello, no debe copiarse ni redistribuirse.
Qué observar: separación entre escucha de menciones, construcción del prompt, llamada al modelo y envío de la respuesta.

Aplicación a nuestro sistema: implementar el mismo pipeline, pero con licencia propia, plantillas en español y validación previa.

python
# Código original para davidpd89/rrss-davidporto-CODE
# Integración: capa de candidatos de respuesta, no publicación automática.
from dataclasses import dataclass, field
from enum import Enum

class ReplyAngle(str, Enum):
    VALIDACION = "validacion"
    EXPERIENCIA = "experiencia"
    CONTRASTE = "contraste"
    PREGUNTA = "pregunta"
    RECOMENDACION = "recomendacion"
    HUMOR = "humor"

@dataclass(frozen=True)
class ReplyCandidate:
    text: str
    angle: ReplyAngle
    network: str
    tone: str
    emoji_count: int
    question_count: int
    similarity_to_post: float
    similarity_to_recent: float
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
2. Banco de respuestas y anti-repetición

Archivo: analog-nico/twitter-reply-bot/blob/master/server.js
Licencia: ISC.
Estado: archivado; no incorporar como dependencia.
Qué observar: respuestas organizadas por tema y mecanismo para no repetir siempre la misma respuesta.

Aplicación: crear data/reply_templates/es/*.yaml, con plantillas por ángulo y nicho, y un registro de plantillas usadas recientemente por cuenta y red.

text
# data/reply_templates/es/fantasia/pregunta_tropo.yaml
# Licencia: código propio del proyecto; formato inspirado en un patrón público ISC.
angle: pregunta
networks: [x, threads, bluesky, mastodon]
tone: cercano
min_length: 70
max_length: 180
templates:
  - "Enemies to lovers funciona mejor cuando el conflicto no desaparece al enamorarse. ¿Cuál es el tropo que nunca te cansa?"
  - "El mapa siempre me gana, pero un buen sistema de magia me retiene. ¿Qué pesa más para ti al entrar en una fantasía?"
  - "Prefiero que el romance tarde en confirmarse si la tensión se sostiene. ¿Te gusta más el enamoramiento lento o el vínculo inmediato?"
python
# Código original para davidpd89/rrss-davidporto-CODE
# Integración: selección con cuotas y memoria anti-repetición.
import random
from collections import deque

class TemplateSelector:
    def __init__(self, templates: list[dict], memory_size: int = 50):
        self.templates = templates
        self.recent = deque(maxlen=memory_size)

    def select(self, angle: str, network: str) -> dict:
        pool = [
            t for t in self.templates
            if t["angle"] == angle and network in t.get("networks", [])
            and t["text"] not in self.recent
        ]
        if not pool:
            raise ValueError(f"Sin plantillas disponibles para {angle}/{network}")
        chosen = random.choice(pool)
        self.recent.append(chosen["text"])
        return chosen
3. Contrato y validación de salida

Archivo: labrat-akhona/semantix-ai/blob/master/examples.py
Licencia: MIT.
Estado: activo; último push 16/09/2026.
Qué observar: validación semántica de salidas de LLM mediante contratos y ejemplos ejecutables.

Aplicación: no publicar nunca un candidato sin pasar un contrato estricto. Esto encaja con las ramas existentes de calidad de voz, paridad de adaptadores y observabilidad.

python
# Código original para davidpd89/rrss-davidporto-CODE
# Integración: puerta de calidad antes del ranking final.
import re
from pydantic import BaseModel, field_validator

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F000-\U0001F02F]"
)

class ReplyContract(BaseModel):
    text: str
    network: str
    angle: str
    max_chars: int = 240
    max_emojis: int = 1
    max_questions: int = 1

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str, info) -> str:
        text = v.strip()
        if not text:
            raise ValueError("La respuesta no puede estar vacía")
        if len(text) > info.data.get("max_chars", 240):
            raise ValueError("Respuesta demasiado larga para la red")
        if len(EMOJI_RE.findall(text)) > info.data.get("max_emojis", 1):
            raise ValueError("Demasiados emojis")
        if text.count("?") > info.data.get("max_questions", 1):
            raise ValueError("Como máximo una pregunta por respuesta")
        if re.search(r"\b(gracias por compartir|me encanta tu post)\b", text, re.I):
            raise ValueError("Fórmula genérica prohibida")
        return text
4. Intención y tono en español

Archivo / repo: BeaEsparcia/spanish-text-classification-bert
Licencia: MIT.
Estado: último push 15/07/2025; proyecto pequeño, útil como referencia.
Qué observar: clasificación de intención en español y diseño conversacional.

Aplicación: primero clasificar el post original en una intención simple —recomendación, opinión, duda, celebración, queja, promoción— y solo después elegir ángulo y plantilla. Esto evita responder igual a una duda, una queja y una celebración.

python
# Código original para davidpd89/rrss-davidporto-CODE
# Integración: enrutado básico de intención a ángulo de respuesta.
INTENT_TO_ANGLES = {
    "duda": ["recomendacion", "experiencia", "pregunta"],
    "opinion": ["contraste", "validacion", "pregunta"],
    "celebracion": ["validacion", "humor", "pregunta"],
    "queja": ["validacion", "experiencia"],
    "promocion": ["pregunta", "contraste"],
    "recomendacion": ["experiencia", "pregunta", "recomendacion"],
}

def allowed_angles(intent: str) -> list[str]:
    return INTENT_TO_ANGLES.get(intent, ["validacion", "pregunta"])
Patrones de respuesta en X
Estructura recomendada

Una respuesta natural para lectores y autores debe tener, como máximo, tres movimientos:

Anclaje específico: mencionar un detalle real del post, no solo el tema.

Postura o experiencia breve: una opinión concreta, una anécdota mínima o un matiz.

Apertura: una pregunta con disyuntiva real, o una invitación a compartir experiencia.

Ejemplos adaptados al nicho de fantasía, romantasy y lectura:

Contexto	Respuesta propuesta	Patrón
Autor comparte una traición	“Ese ‘confía en mí’ nunca acaba bien 😅 ¿Quieres que el lector sospeche desde el principio o que caiga en la trampa como la protagonista?”	Detalle + humor + disyuntiva
Lectora pide recomendaciones	“Para tensión lenta y mundo con reglas propias, iría a algo de enemigos a amantes. ¿Prefieres romance central o que la fantasía pese más?”	Recomendación + segmentación
Autor pregunta por tropos	“Enemies to lovers funciona si el conflicto sobrevive al enamoramiento. ¿Cuál es el tropo que nunca te cansa?”	Postura + pregunta abierta
Post sobre bloqueo creativo	“A mí me funciona escribir la peor versión posible y arreglarla después. ¿Te bloqueas más en el inicio o en el nudo?”	Experiencia + pregunta útil
Final devastador	“Duele más cuando era coherente con todo lo anterior. ¿Lo perdonas si el personaje lo necesitaba?”	Validación + debate narrativo
Qué eliminar del informe anterior

Rango fijo de 120–150 caracteres como óptimo: no es una regla universal; debe ser una hipótesis por red y cuenta.

Priorizar automáticamente respuestas sobre likes: no hay evidencia suficiente para fijarlo como política global; debe decidirse con experimentos.

Política rígida de “0–1 emoji” para todas las redes: en X puede ser razonable, pero Pinterest, Instagram o TikTok requieren perfiles distintos.

Dependencia de clibrain/lince-zero como recomendación principal: es un modelo grande y no resuelve por sí solo la calidad conversacional ni la diversidad; queda como opción futura, no como pieza central.

Código copiado “tal cual” sin poder verificar el contenido: no se incluye; se sustituye por URLs exactas, licencia y código original de integración.

Plan de implementación en PR pequeñas
PR	Objetivo	Entregable	Tests
PR 1	Esquema base	ReplyCandidate, ReplyAngle, VoiceConstraints, trazabilidad	Serialización, inmutabilidad y validación básica
PR 2	Intención	Clasificador regla-based de intención en español	20 casos por intención
PR 3	Plantillas	40–60 plantillas en español por ángulo y nicho	Longitud, idioma, variables y unicidad
PR 4	Anti-repetición	Memoria por cuenta, red y sesión	No repetición en 50 selecciones
PR 5	Contrato	ReplyContract con validadores	Emojis, preguntas, longitud, fórmulas prohibidas
PR 6	Scorer	Originalidad, especificidad, afinidad, frescura y diversidad	Backtest con logs históricos
PR 7	Adaptador X	Perfil X: longitud, menciones, hilos, tono y emojis	Tests de formato y límites
PR 8	Extensión multired	Perfiles por Threads, Bluesky, Mastodon, Facebook, Pinterest, Reddit, Instagram y TikTok	Paridad de contrato y diferencias configurables
PR 9	Aprendizaje	Registro de resultados y actualización de pesos	Métricas, lineage y experimentos A/B
Fuentes

Estudio sobre lectura social y comentarios en Twitter: ScienceDirect

Resumen del estudio con 18.962 tweets: University of Groningen

Tácticas de preguntas, seguimiento y ventana temporal de respuesta: Supabird

Relación no lineal entre longitud y engagement: Limitora

Bot de respuestas con LLM: gkamradt/twitter-reply-bot

Bot de respuestas por plantillas: analog-nico/twitter-reply-bot

Validación semántica de salidas LLM: labrat-akhona/semantix-ai

Clasificación de intención en español: BeaEsparcia/spanish-text-classification-bert

Recursos de lenguaje en español: PlanTL-GOB-ES/lm-spanish

Normalización y análisis de reseñas en español: SebaB29/criticas-peliculas

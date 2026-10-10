# Comentarios humanos y variados en Mastodon

Fuente: informe de Perplexity (https://www.perplexity.ai/search/b64665ed-46d3-412e-a2ea-47b1865d5571), generado 10/10/2026.

Informe mejorado: comentarios naturales en Mastodon para lectores y autores

He revisado el informe anterior y eliminado o degradado lo que no aporta directamente al sistema: BLEURT queda como opción opcional —no como pieza central—, el autorespondedor antiguo solo sirve como referencia de escucha y no como modelo de conversación, y los corpus de prensa se usan únicamente para calibrar métricas de registro, no para generar frases. La base técnica correcta es Mastodon.py, que sigue siendo una librería Python mantenida para la API REST y de streaming de Mastodon y servicios compatibles.
joss.theoj
+1

Resumen

Para que una cuenta de autora o lectora comente de forma natural en Mastodon, el sistema debe responder al hilo real, no al post aislado: recuperar OP, respuestas previas y descendientes, identificar un detalle concreto y redactar una intervención breve, específica y conversacional. La API ofrece GET /api/v1/statuses/:id/context, que devuelve ancestors y descendants; Mastodon.py expone ese contexto y permite publicar con in_reply_to_id.
mastodonpy

La mejora recomendada es un Mastodon Conversational Reply Layer: contexto de hilo, arquetipos de respuesta en español, guardián de estilo, ranking de variantes y publicación idempotente. No propongo un bot que responda automáticamente a todo: el sistema debe seleccionar pocas oportunidades prometedoras y aprender de sus respuestas, boosts y favoritos.

Hallazgos verificados
Hallazgo	Recurso público	Estado comprobado	Qué reutilizar	Aplicación al sistema
Cliente Python maduro para API de Mastodon	halcy/Mastodon.py	Activo; documentación estable 2.2.2 y artículo JOSS reciente. 
joss.theoj
+1
	status_context, status_post, gestión de rate limits.	Base del adaptador Mastodon; no duplicar cliente HTTP propio.
Publicación como respuesta	halcy/Mastodon.py	El método admite in_reply_to_id, visibilidad, idioma y clave de idempotencia.	Firma y parámetros de status_post.	Publicar la respuesta elegida vinculada al status_id correcto.
Lectura de hilos	
mastodon/mastodon
 y documentación oficial	Endpoint context devuelve ancestros y descendientes; límite público de 40 ancestros y 60 descendientes. 
github
	Estructura ancestors / descendants.	ContextBuilder para alimentar el generador con el hilo real.
Bot modular de Mastodon	
slashtechno/pystodon
	Repositorio público activo, con funciones de recordatorios, clima y datos temporales. 
github
	Arquitectura modular de comandos/configuración.	Inspiración para separar listener, estrategias y publicador; no copiar funciones ajenas al nicho.
Bot Python con moderación colectiva	DocTocToc/doctoctocbot	Último push: 21 de enero de 2025; Python, MPL-2.0, 9 estrellas, no archivado.	Patrón de Quick Replies/DM y moderación de cuentas.	Útil como referencia de cola, reglas y auditoría; no copiar su lógica de retweet.
Envoltorio de respuesta	Shura0/mastaj	Código público con status_post y in_reply_to_id.	Patrón mínimo de wrapper.	Referencia para MastodonPublisher, con manejo de errores propio.
Detector multilingüe de toxicidad	
textdetox
	Incluye español; modelos actualizados en diciembre de 2025. 
huggingface
	Clasificador de toxicidad y explicación.	Filtro previo para descartar respuestas agresivas, sarcasmo dañino o contenido inadecuado.
Alternativa ligera de toxicidad	unitary/detoxify	Variante multilingüe que cubre español. 
ai-tldr
	Clasificación de toxicidad, insultos y amenazas.	Segundo filtro opcional si textdetox resulta demasiado pesado para CI.
Corpus conversacional español	
mariagrandury/SpanishCasualChat
	Dataset público de diálogos en español con contexto.	Muestras de registro casual.	Calibrar tono cercano, longitud y naturalidad; no copiar respuestas literales.
Corpus de comentarios españoles	
DETESTS-Dis
	Comentarios de medios y foros españoles, incluidos ABC, elDiario.es, El Mundo, NIUS y Menéame.	Distribuciones de longitud, interrogaciones y emojis.	Calibrar register_fit; excluir comentarios polémicos u ofensivos.
Métrica semántica	
Tiiiger/bert_score
	Proyecto público de evaluación de generación textual.	Comparación candidato-referencia.	Ranking interno de variantes frente a resúmenes del hilo.
Clasificador de emojis	
prithivi-007-AI/Classify-emoji-classifier-
	Extrae emojis, los mapea a estados emocionales y genera etiqueta global. 
github
	Lógica de extracción y mapeo.	Validador de coherencia emoji-texto; mantener presupuesto de 0–1 emoji.
Qué eliminar del informe anterior

BLEURT como evaluador principal: es válido, pero añade dependencias pesadas y no resuelve el problema central, que es contextualidad y estilo. Se conserva solo como experimento posterior.

sipb/mastodon-bot-autoresponder como referencia de conversación: su valor es mínimo; responde con contenido predefinido y puede inducir un patrón mecánico. Solo sirve, como mucho, para inspirar deduplicación de menciones.

“Emojis funcionales” como regla universal: en Mastodon literario, el valor por defecto debe ser cero emojis; uno solo cuando el post tenga emoción, humor o celebración evidente.

“Preguntas siempre”: una pregunta solo debe aparecer si el OP invita explícitamente a opinión o si el hilo ya está en modo conversación. En un comentario inicial sobre una reseña, una afirmación específica suele ser más natural.

Corpus de prensa como fuente de estilo directo: sirve para estadística de registro, no como fuente de ejemplos para imitar.

Código reutilizable tal cual
Publicación contextual en Mastodon.py

Este es el fragmento directamente aprovechable de Mastodon.py: demuestra que la publicación contextual es una capacidad nativa de la librería, incluida la clave de idempotencia.

python
# https://github.com/halcy/Mastodon.py/blob/master/mastodon/statuses.py
    @api_version("1.0.0", "4.5.0")
    def status_post(self, status: str, in_reply_to_id: Optional[Union[Status, IdType]] = None, media_ids: Optional[List[Union[MediaAttachment, IdType]]] = None,
                    sensitive: bool = False, visibility: Optional[str] = None, spoiler_text: Optional[str] = None, language: Optional[str] = None, 
                    idempotency_key: Optional[str] = None, content_type: Optional[str] = None, scheduled_at: Optional[datetime] = None, 
                    poll: Optional[Union[Poll, IdType]] = None, quote_id: Optional[Union[Status, IdType]] = None, strict_content_type: bool = False,

Uso en el sistema: llamar a status_post con in_reply_to_id=thread.target_status_id, language="es" y una idempotency_key derivada de hash(status_id + account_id + fecha). Así se evita duplicar una respuesta si el job se reinicia.

Patrón mínimo de envoltorio de respuesta

Este fragmento de mastaj es útil como referencia de integración mínima, no como implementación final: nuestro adaptador debe añadir reintentos, trazabilidad y deduplicación.

python
# https://github.com/Shura0/mastaj/blob/master/mastodon_listener.py
    def status_post(self, status, visibility='public', in_reply_to_id=None):
        try:
            res = self.mastodon.status_post(
                status=status,

Uso en el sistema: encapsular esta llamada en MastodonPublisher.publish_reply(), pero con idempotency_key, language="es", registro de status_id devuelto y modo dry_run.

Código propuesto para el PR

Este bloque es código nuevo para nuestro repositorio, diseñado para convivir con SISTEMA_DIARIO_MASTODON/growth_config.json y no duplicar la capa de publicación existente.

python
# Nuevo archivo: SISTEMA_DIARIO_MASTODON/context_builder.py
# Basado en la API oficial: https://docs.joinmastodon.org/methods/statuses/#get-parent-and-child-statuses-in-context
from dataclasses import dataclass, field


@dataclass
class ThreadContext:
    target_status_id: str
    op_text: str
    op_account: str
    language: str
    ancestors: list[str] = field(default_factory=list)
    descendants: list[str] = field(default_factory=list)

    def conversation_digest(self) -> str:
        parts = [f"OP ({self.op_account}): {self.op_text}"]
        if self.ancestors:
            parts.append("Contexto previo:\n- " + "\n- ".join(self.ancestors[-3:]))
        if self.descendants:
            parts.append("Respuestas posteriores:\n- " + "\n- ".join(self.descendants[:3]))
        return "\n\n".join(parts)


class MastodonContextBuilder:
    def __init__(self, mastodon_client):
        self.client = mastodon_client

    def build(self, status_id: str) -> ThreadContext:
        status = self.client.status(status_id)
        context = self.client.status_context(status_id)

        return ThreadContext(
            target_status_id=status_id,
            op_text=self._plain_text(status["content"]),
            op_account=status["account"]["acct"],
            language=status.get("language") or "es",
            ancestors=[self._plain_text(s) for s in context["ancestors"]],
            descendants=[self._plain_text(s) for s in context["descendants"]],
        )

    @staticmethod
    def _plain_text(html: str) -> str:
        # Mastodon devuelve HTML; para el prompt basta con una versión plana.
        return (
            html.replace("<br />", "\n")
            .replace("<br>", "\n")
            .replace("</p>", "\n")
            .replace("<p>", "")
        )
python
# Nuevo archivo: SISTEMA_DIARIO_MASTODON/reply_strategy.py
# Estilo basado en conversación comunitaria de Mastodon; no copia frases de usuarios.
import hashlib
import json
import random
from dataclasses import dataclass


@dataclass
class ReplyCandidate:
    archetype: str
    text: str
    includes_question: bool


class ReplyStrategist:
    ARCHETYPES = ["emocion", "personaje", "escena", "tema", "recomendacion"]

    def __init__(self, config: dict, seed: int | None = None):
        self.config = config
        self.random = random.Random(seed)

    def candidates(self, thread_digest: str, extracted_entities: list[str]) -> list[ReplyCandidate]:
        entity = extracted_entities[0] if extracted_entities else "esa escena"
        base = [
            ReplyCandidate(
                "emocion",
                f"Me quedé con {entity}: tiene una carga emocional muy bien construida.",
                False,
            ),
            ReplyCandidate(
                "personaje",
                f"{entity} funciona especialmente bien porque se nota que tiene contradicciones propias.",
                False,
            ),
            ReplyCandidate(
                "escena",
                f"Esa parte con {entity} deja una imagen muy clara; se siente tensa sin explicar demasiado.",
                False,
            ),
            ReplyCandidate(
                "tema",
                f"Me interesa cómo encaja {entity} con el tipo de fantasía que buscas contar.",
                True,
            ),
        ]

        allowed = self.config.get("reply_style", {}).get("allowed_archetypes", self.ARCHETYPES)
        return [c for c in base if c.archetype in allowed]

    def select(self, candidates: list[ReplyCandidate], scores: dict[str, float]) -> ReplyCandidate:
        if not candidates:
            raise ValueError("No hay candidatas válidas")
        return max(candidates, key=lambda c: scores.get(c.archetype, 0.0))

    def idempotency_key(self, status_id: str, account_id: str) -> str:
        raw = f"{status_id}:{account_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
python
# Nuevo archivo: SISTEMA_DIARIO_MASTODON/style_guard.py
# Reglas propias del sistema; no reutiliza código de terceros.
import re

GENERIC_PHRASES = [
    r"^¡qué buen post!",
    r"^me encanta tu contenido",
    r"^sígueme para más",
    r"^gracias por compartir$",
    r"^totalmente de acuerdo$",
]


class SpanishStyleGuard:
    def __init__(self, max_chars: int = 280, max_emojis: int = 1, max_questions: int = 1):
        self.max_chars = max_chars
        self.max_emojis = max_emojis
        self.max_questions = max_questions

    def validate(self, text: str) -> tuple[bool, str]:
        if not text.strip():
            return False, "Respuesta vacía"

        if len(text) > self.max_chars:
            return False, "Demasiado larga para Mastodon"

        if sum(ch in "?!¡¿" for ch in text if ch in "?!") > self.max_questions:
            return False, "Más de una pregunta"

        emoji_count = sum(1 for ch in text if ord(ch) > 0x1F000)
        if emoji_count > self.max_emojis:
            return False, "Demasiados emojis"

        lowered = text.strip().lower()
        if any(re.search(pattern, lowered) for pattern in GENERIC_PHRASES):
            return False, "Fórmula genérica de crecimiento"

        return True, "OK"
Configuración recomendada

Añadir este bloque a SISTEMA_DIARIO_MASTODON/growth_config.json, sin eliminar las claves actuales:

json
{
  "reply_style": {
    "language": "es",
    "max_chars": 280,
    "max_sentences": 2,
    "max_emojis": 1,
    "default_emojis": 0,
    "max_questions": 1,
    "question_probability": 0.25,
    "allowed_archetypes": [
      "emocion",
      "personaje",
      "escena",
      "tema",
      "recomendacion"
    ],
    "forbidden_patterns": [
      "¡qué buen post!",
      "me encanta tu contenido",
      "sígueme para más",
      "gracias por compartir"
    ]
  },
  "thread_context": {
    "max_ancestors": 3,
    "max_descendants": 3,
    "require_op": true,
    "skip_if_already_replied": true
  },
  "ranking": {
    "candidates_per_post": 4,
    "weights": {
      "specificity": 0.35,
      "semantic_fit": 0.25,
      "diversity": 0.20,
      "fluency": 0.10,
      "safety": 0.10
    }
  }
}
Plan de PR pequeñas
PR	Entregable	Motivo	Criterio de aceptación
PR 1	context_builder.py y tests	Evita responder a ciegas	Reconstruye OP, ancestros y descendientes; ignora hilos vacíos.
PR 2	reply_archetypes.json y ReplyStrategist	Estructura variable, no frases fijas	Cada arquetipo exige una entidad del post.
PR 3	SpanishStyleGuard	Evita respuestas robóticas o genéricas	Rechaza fórmulas, exceso de emojis y preguntas múltiples.
PR 4	ranking.py con BERTScore opcional	Elige la mejor variante medida	Salida determinista con semilla y candidatas auditables.
PR 5	MastodonPublisher con idempotency_key	Publicación segura y trazable	Dry-run sin publicación; un solo comentario por status_id.
PR 6	Filtro textdetox opcional	Evita respuestas inadecuadas	Bloquea toxicidad alta; registra motivo.
PR 7	Métricas de registro con DETESTS-Dis	Calibra longitud, interrogaciones y emojis	La salida queda dentro de los percentiles definidos.
PR 8	Adaptador genérico multirred	Reutiliza el núcleo en todas las redes	Cambia solo extractor de contexto y límites de estilo.
Aplicación multirred

El núcleo —contexto, arquetipos, guardián y ranking— debe ser común. Solo cambian estos parámetros:

Red	Contexto prioritario	Longitud	Emojis	Preguntas
Mastodon	Hilo completo, comunidad e instancias	80–280 caracteres	0–1	Opcionales
Bluesky	Post y respuestas visibles	60–220 caracteres	0–1	Opcionales
X	Post, autor y conversación	40–180 caracteres	0–1	Raras
Threads	Post, autor y hilo	60–220 caracteres	0–2	Ocasionales
Facebook	Post, grupo y comentarios previos	120–400 caracteres	0–2	Ocasionales
Pinterest	Pin, tablero y descripción	80–240 caracteres	0–1	Raras
Reddit	Post, reglas del subreddit e hilos	150–600 caracteres	0	Solo si aportan
TikTok	Caption, comentarios y nicho	40–160 caracteres	0–2	Frecuentes
Instagram	Caption, imagen y comentarios	60–220 caracteres	0–2	Ocasionales
Fuentes

API de estados y contexto de Mastodon: 
https://docs.joinmastodon.org/methods/statuses/

Entidad Context: 
https://docs.joinmastodon.org/entities/Context/

Límites de la API de Mastodon: 
https://docs.joinmastodon.org/api/rate-limits/
github

Mastodon.py, documentación y gestión de rate limits: 
https://mastodonpy.readthedocs.io/en/stable/01_general.html
mastodonpy

Artículo científico de Mastodon.py: 
https://joss.theoj.org/papers/10.21105/joss.08946.pdf
joss.theoj

Repositorio halcy/Mastodon.py: https://github.com/halcy/Mastodon.py

Archivo original de status_post: https://github.com/halcy/Mastodon.py/blob/master/mastodon/statuses.py

Repositorio Shura0/mastaj: https://github.com/Shura0/mastaj/blob/master/mastodon_listener.py

Repositorio slashtechno/pystodon: 
https://github.com/slashtechno/pystodon
github

Repositorio DocTocToc/doctoctocbot: https://github.com/DocTocToc/doctoctocbot

textdetox, toxicidad y español: 
https://huggingface.co/textdetox
huggingface

Detoxify, clasificación multilingüe: 
https://ai-tldr.dev/tools/detoxify/
ai-tldr

SpanishCasualChat: 
https://huggingface.co/datasets/mariagrandury/SpanishCasualChat

Corpus DETESTS-Dis: 
https://detests-dis.github.io/corpus/

BERTScore: 
https://github.com/Tiiiger/bert_score

Clasificador de emojis: 
https://github.com/prithivi-007-AI/Classify-emoji-classifier-
github

Issue sobre el límite de contexto no autenticado: 
 mastodon/mastodon#25892
github

# Comentarios humanos y variados en Threads

Fuente: informe de Perplexity (https://www.perplexity.ai/search/fe6e35c8-3b19-4f6d-9313-f8ea45be08b1), generado 10/10/2026.

Informe mejorado: comentarios naturales y contextuales en Threads (ES)
Resumen

Tras revisar el repo davidpd89/ci-sandbox-tmp, la conclusión se mantiene pero se acota: no conviene añadir otro generador de comentarios paralelo. El sistema ya dispone de threads_api.py, threads_interact.py, threads_reply_queue.py, reply_writer.py, conversation_followups.py, conversation_turn_policy.py, check_language_variety.py, check_duplicate_phrase.py, reply_corpus_lint.py y action_ledger.py; la mejora correcta es una capa de estilo, contexto y evaluación específica para Threads en español, conectada a esos módulos existentes.

He retirado del informe anterior dos afirmaciones que no eran suficientemente aplicables: el uso directo de PolyAI-LDN/conversational-datasets —útil como referencia metodológica, pero basado en Reddit y no en Threads— y cualquier sugerencia de copiar código de scraping no oficial de Threads. También he verificado la actividad de los repos propuestos y separado claramente el código verificado del código de integración propio.

Limitación importante: en esta sesión el conector GitHub confirmó la existencia, licencia y actividad de los archivos, pero no devolvió el contenido textual de pythreads/threads.py ni de responsive_image_comment (1).py. Por rigor, no incluyo como “copiado tal cual” fragmentos que no he podido leer íntegramente; en su lugar dejo las URL exactas de origen y el código de integración listo para adaptar.

Hallazgos verificados
Repositorio / fuente	Estado y licencia	Qué aporta	Uso en ci-sandbox-tmp	Veredicto
marclove/pythreads	Python, MIT; 72 estrellas; último push 2025-09-09; no archivado	Cliente Python limpio para la API oficial de Meta Threads; módulos api.py y threads.py	Referencia para revisar contratos, paginación, tokens y publicación de respuestas; no sustituye a threads_api.py	Reutilizar como referencia, no como dependencia
josefr1/comment_generation_model	Python; creado/actualizado en 2025; repo pequeño, sin releases ni tests visibles	Pipeline de comentario contextual: descripción de imagen + comentario previo + prompt para LLM	Inspiración para context_extractor y prompt de generación; adaptar a español y nicho literario	Copiar idea y contrato, no el pipeline completo
dancolta/subscope	Python, MIT; 28 estrellas; último push 2026-08-12; activo	Detección y puntuación de señales en hilos de Reddit; motor con CLI, tests y prompts	Patrón útil para intent_classifier, scoring de oportunidades y cola priorizada	Reutilizar patrón de scoring, no el dominio Reddit
NFeruch/reddit2text	Python, Apache-2.0; 124 estrellas; último push 2026-03-01	Conversión de hilos y comentarios de Reddit en texto estructurado	Referencia para normalizar hilos, autores y respuestas en un corpus interno	Opcional, solo si se construye corpus de entrenamiento propio

Threads API oficial
	Documentación Meta	Publicación, lectura, respuestas, moderación e insights	Base obligatoria para threads_api.py y ejecución	Fuente canónica
Threads Reply Management	Documentación Meta	Gestión de respuestas, ocultación y aprobaciones	Útil para moderación y control de conversaciones propias	Fuente canónica

pythreads es la referencia más sólida para la capa API: es MIT, está escrito específicamente para la API oficial de Threads y su último push es de septiembre de 2025; no está archivado. [GitHub: resultado de búsqueda y listado de src/pythreads]

subscope es el hallazgo menos obvio más útil: aunque está orientado a Reddit, su valor es el patrón de puntuación de hilos por señales, directamente trasladable a decidir qué posts de Threads merecen respuesta. Su último push es de agosto de 2026 y tiene licencia MIT. [GitHub: listado raíz y engine/subscope]

Qué eliminar del informe anterior

PolyAI-LDN/conversational-datasets como recurso de copia: sus pares provienen de Reddit y su escala no encaja con un corpus pequeño, español y literario. Se conserva solo como referencia de evaluación contexto-respuesta.

pysentimiento/spanish-tweets como fuente principal de estilo: los tweets no representan el registro de Threads ni el nicho de fantasía. Puede servir para análisis auxiliar, pero no para definir plantillas.

Cualquier wrapper no oficial o reverse-engineered de Threads: por ejemplo, dmytrostriletskyi/threads-net tiene 424 estrellas, pero su último push es de octubre de 2023 y se declara para fines académicos; no encaja con un sistema de producción.

La idea de generar siempre una pregunta: en Threads una pregunta solo tiene sentido si el post la invita o si añade una dimensión nueva. En portadas, memes y opiniones cerradas, una pregunta puede sonar forzada.

Estilo real observado

Los ejemplos públicos del nicho confirman cuatro rasgos:

Pregunta lectora directa: “¿Cuáles son los últimos libros de fantasía que has leído y que más te han gustado?”
threads

Opinión con matiz, no solo entusiasmo: el debate sobre si un libro escrito por una autora y dirigido a lectoras es automáticamente romantasy.

Presentación de autora con elementos concretos: elfos, conflictos políticos, dragones, guerras y romance +18.
threads

Autoidentificación por subgénero: fantasía oscura, romance fantasy y dark romance.

La regla práctica es: reacción breve + un detalle extraído del post + opcionalmente una pregunta que abra una vía nueva. El comentario debe demostrar que se leyó el post; el elogio genérico es la principal señal de automatización.

Código de integración propio

El siguiente módulo es código nuevo para ci-sandbox-tmp, diseñado para enchufarse a reply_writer.py, threads_reply_queue.py y action_ledger.py. No duplica la ejecución de la API: solo decide intención, estilo, longitud, emojis y si procede preguntar.

python
# Fuente de inspiración / contrato:
# https://github.com/josefr1/comment_generation_model/blob/834623f643c0fa275110169d5514d829d68d2e90/responsive_image_comment%20(1).py
# https://github.com/dancolta/subscope/blob/cf45ffd8956d0d24bbaaf4eaa5d7f0ecc293cb27/engine/subscope/cli.py
# Integración prevista: tools/threads_comment_style.py

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Literal


Intent = Literal[
    "opinion", "recomendacion", "portada", "lectura_actual",
    "lanzamiento", "debate", "meme", "desconocido",
]


TROPOS = [
    "enemigos a amantes", "amigos a amantes", "romance lento",
    "enemies to lovers", "friends to lovers", "slow burn",
    "dragones", "elfos", "magia", "vampiros", "fae",
    "alta fantasía", "fantasía oscura", "grimdark", "romantasy",
    "dark romance", "romance fantasy", "enemistad", "traición",
    "elegido", "profecía", "academia", "rebeldes", "guerra",
]

GENERIC_OPENERS = {
    "qué bueno", "qué bonito", "me encanta", "increíble",
    "muy interesante", "buen post", "totalmente de acuerdo",
}


@dataclass(frozen=True)
class ThreadContext:
    text: str
    author_is_writer: bool = False
    has_image: bool = False
    has_question: bool = False


@dataclass(frozen=True)
class StyleDecision:
    intent: Intent
    max_words: int
    allow_emoji: bool
    allow_question: bool
    tone: Literal["calido", "analitico", "entusiasta", "prudente"]
    detected: list[str] = field(default_factory=list)


def classify_intent(ctx: ThreadContext) -> Intent:
    text = ctx.text.lower()

    if any(word in text for word in ("recomienda", "recomendación", "qué leo", "que leo")):
        return "recomendacion"
    if any(word in text for word in ("portada", "cubierta", "ilustración", "estética")):
        return "portada"
    if any(word in text for word in ("estoy leyendo", "lectura actual", "empecé", "empece")):
        return "lectura_actual"
    if any(word in text for word in ("lanzado", "publicado", "sale hoy", "ya disponible", "estreno")):
        return "lanzamiento"
    if any(word in text for word in ("opinión", "creo que", "no entiendo", "polémica", "debatir")):
        return "debate"
    if ctx.has_image and not ctx.has_question:
        return "portada"
    if ctx.has_question:
        return "recomendacion"
    return "opinion"


def detect_context(text: str) -> list[str]:
    lowered = text.lower()
    return [trope for trope in TROPOS if trope in lowered]


def decide_style(ctx: ThreadContext) -> StyleDecision:
    intent = classify_intent(ctx)
    detected = detect_context(ctx.text)

    rules = {
        "opinion": (18, True, ctx.has_question, "analitico"),
        "recomendacion": (22, True, True, "calido"),
        "portada": (14, True, False, "entusiasta"),
        "lectura_actual": (24, True, False, "calido"),
        "lanzamiento": (24, True, ctx.author_is_writer, "calido"),
        "debate": (32, False, ctx.has_question, "prudente"),
        "meme": (12, True, False, "entusiasta"),
        "desconocido": (16, False, False, "prudente"),
    }

    max_words, allow_emoji, allow_question, tone = rules[intent]
    return StyleDecision(
        intent=intent,
        max_words=max_words,
        allow_emoji=allow_emoji,
        allow_question=allow_question,
        tone=tone,
        detected=detected,
    )


def is_generic(text: str) -> bool:
    lowered = re.sub(r"[¡!¿?.,]", "", text.lower()).strip()
    return any(opener in lowered for opener in GENERIC_OPENERS)


def has_contextual_anchor(text: str, detected: list[str]) -> bool:
    lowered = text.lower()
    return any(anchor in lowered for anchor in detected)


def score_candidate(
    candidate: str,
    decision: StyleDecision,
    seen_openers: set[str],
) -> float:
    words = len(candidate.split())
    score = 0.0

    if 8 <= words <= decision.max_words:
        score += 3.0
    elif words > decision.max_words:
        score -= min(3.0, (words - decision.max_words) / 10)

    if has_contextual_anchor(candidate, decision.detected):
        score += 4.0
    else:
        score -= 2.0

    if is_generic(candidate):
        score -= 5.0

    emoji_count = len(re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", candidate))
    if emoji_count == 0:
        score += 1.0
    elif emoji_count == 1 and decision.allow_emoji:
        score += 0.5
    else:
        score -= 2.0

    questions = candidate.count("¿") + candidate.count("?")
    if questions == 0:
        score += 0.5
    elif questions == 1 and decision.allow_question:
        score += 1.5
    else:
        score -= 3.0

    first_words = " ".join(candidate.lower().split()[:3])
    if first_words in seen_openers:
        score -= 4.0

    return score


def pick_best(
    candidates: list[str],
    ctx: ThreadContext,
    seen_openers: set[str] | None = None,
) -> tuple[str, float, StyleDecision]:
    decision = decide_style(ctx)
    seen_openers = seen_openers or set()

    scored = [
        (score_candidate(candidate, decision, seen_openers), candidate)
        for candidate in candidates
        if candidate.strip()
    ]
    if not scored:
        raise ValueError("No hay candidatos válidos")

    best_score, best = max(scored, key=lambda item: item[0])
    return best, best_score, decision
Ejemplo de uso
python
# Uso previsto desde reply_writer.py o threads_reply_queue.py
from tools.threads_comment_style import ThreadContext, pick_best

ctx = ThreadContext(
    text="¿Vosotras preferís enemigos a amantes o amigos a amantes?",
    has_question=True,
)

candidates = [
    "Amigos a amantes, pero solo cuando la confianza se ha construido durante años.",
    "Enemigos a amantes si hay tensión real; si no, se vuelve previsible.",
    "Me gusta más amigos a amantes porque el vínculo previo hace que importe más.",
]

best, score, decision = pick_best(candidates, ctx)
print(decision.intent, score, best)
Código de evaluación de naturalidad

Este evaluador es complementario, no sustituto, de check_language_variety.py, check_duplicate_phrase.py, spellcheck_es.py y reply_corpus_lint.py. Su función es impedir que entre en cola un comentario genérico, demasiado largo, con exceso de emojis o sin anclaje contextual.

python
# Fuente de patrón de scoring:
# https://github.com/dancolta/subscope/blob/cf45ffd8956d0d24bbaaf4eaa5d7f0ecc293cb27/engine/subscope/cli.py
# Integración prevista: tools/comment_naturalness_evaluator.py

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class NaturalnessReport:
    score: float
    passes: bool
    reasons: list[str]


GENERIC_PHRASES = (
    "qué bueno", "qué bonito", "me encanta", "increíble",
    "muy interesante", "buen post", "totalmente de acuerdo",
    "gracias por compartir", "qué gran libro",
)

EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def evaluate_comment(
    comment: str,
    context_anchors: list[str],
    *,
    max_words: int = 32,
    min_words: int = 8,
    max_emojis: int = 1,
    allow_question: bool = True,
    min_score: float = 6.0,
) -> NaturalnessReport:
    reasons: list[str] = []
    score = 10.0
    words = len(comment.split())
    lowered = comment.lower()

    if words < min_words:
        score -= 3.0
        reasons.append(f"Demasiado corto: {words} palabras")

    if words > max_words:
        score -= min(4.0, (words - max_words) / 8)
        reasons.append(f"Demasiado largo: {words} palabras")

    if not any(anchor.lower() in lowered for anchor in context_anchors):
        score -= 4.0
        reasons.append("Sin anclaje contextual detectable")

    if any(phrase in lowered for phrase in GENERIC_PHRASES):
        score -= 5.0
        reasons.append("Contiene fórmula genérica")

    emojis = len(EMOJI_RE.findall(comment))
    if emojis > max_emojis:
        score -= 2.0
        reasons.append(f"Exceso de emojis: {emojis}")

    questions = comment.count("¿") + comment.count("?")
    if questions > 1 or (questions == 1 and not allow_question):
        score -= 2.5
        reasons.append("Pregunta no justificada por el contexto")

    if re.search(r"\b(jajaja+|lol|xd)\b", lowered):
        score -= 1.0
        reasons.append("Registro demasiado informal para autoría")

    return NaturalnessReport(
        score=round(score, 2),
        passes=score >= min_score,
        reasons=reasons,
    )
Ejemplo de evaluación
python
from tools.comment_naturalness_evaluator import evaluate_comment

report = evaluate_comment(
    comment="Los conflictos políticos y los dragones ya me han llamado la atención.",
    context_anchors=["conflictos políticos", "dragones"],
    allow_question=False,
)

print(report)
# NaturalnessReport(score=10.0, passes=True, reasons=[])
Integración con el repo actual
Contrato con reply_writer.py

reply_writer.py debe recibir un objeto de decisión, no solo el texto final:

python
# Integración prevista en tools/reply_writer.py
from tools.threads_comment_style import ThreadContext, pick_best
from tools.comment_naturalness_evaluator import evaluate_comment


def build_threads_reply(
    post_text: str,
    candidates: list[str],
    *,
    author_is_writer: bool = False,
    has_image: bool = False,
    seen_openers: set[str] | None = None,
) -> dict:
    ctx = ThreadContext(
        text=post_text,
        author_is_writer=author_is_writer,
        has_image=has_image,
        has_question="?" in post_text or "¿" in post_text,
    )

    best, style_score, decision = pick_best(
        candidates=candidates,
        ctx=ctx,
        seen_openers=seen_openers,
    )

    report = evaluate_comment(
        comment=best,
        context_anchors=decision.detected,
        max_words=decision.max_words,
        allow_question=decision.allow_question,
    )

    return {
        "text": best,
        "intent": decision.intent,
        "style_score": style_score,
        "naturalness": report.score,
        "passes": report.passes,
        "reasons": report.reasons,
        "detected": decision.detected,
    }
Regla de publicación

En threads_execute.py, ninguna respuesta debe enviarse si:

falta reply_to_id;

passes es False;

el comentario no tiene anclaje contextual;

la misma apertura aparece más de una vez en la misma tanda;

el comentario contiene una pregunta cuando la intención no la permite.

La API oficial de Threads contempla publicación, lectura y gestión de respuestas; el flujo correcto es responder al post padre mediante su identificador, no crear un hilo nuevo.

Plan de PR pequeñas
PR 1 — threads_comment_style.py

Añadir clasificador de intención, detector de tropos y decisión de estilo.

No conectar todavía a ejecución.

Añadir tests con posts de opinión, portada, recomendación, lanzamiento y debate.

Criterio de aceptación: un post de portada no genera pregunta; un post de recomendación sí; un debate no usa emojis.

PR 2 — comment_naturalness_evaluator.py

Añadir puntuación de naturalidad y motivos de rechazo.

Integrar con check_duplicate_phrase.py y check_language_variety.py.

Definir umbral inicial: min_score = 6.0.

Criterio de aceptación: “¡Qué buen libro!” queda rechazado; “Los conflictos políticos y los dragones ya me han llamado la atención” queda aprobado cuando el post menciona esos elementos.

PR 3 — Conexión con reply_writer.py

Añadir función build_threads_reply().

Generar tres candidatos por post: reacción breve, matiz analítico y pregunta contextual.

Registrar intención, puntuaciones y plantilla en action_ledger.py.

Criterio de aceptación: cada respuesta guardada incluye intent, style_score, naturalness, detected y reply_to_id.

PR 4 — Cola priorizada estilo subscope

Crear threads_opportunity_score.py.

Puntuar posts por: relevancia de nicho, pregunta explícita, actividad reciente, autor/a escritor, posibilidad de conversación y ausencia de respuesta propia previa.

Ordenar la cola antes de llamar a threads_reply_queue.py.

Criterio de aceptación: los posts con pregunta, tropo detectado y autor/a del nicho se sitúan por encima de posts genéricos.

PR 5 — Aprendizaje por resultados

Ampliar growth_attribution.py y reciprocity_stats.py.

Medir por plantilla e intención: respuestas recibidas, me gusta, réplicas, nuevos seguidores y respuestas propias necesarias.

Publicar un ranking semanal y desactivar plantillas con rendimiento bajo.

Criterio de aceptación: cada plantilla tiene métricas comparables y puede desactivarse sin tocar el resto del sistema.

Aplicación multired
Red	Adaptación del núcleo
Threads	Conversación breve, cálida, con matiz y contexto literario
Bluesky	Casi idéntico a Threads; algo más nicho y menos promocional
Mastodon	Más contextual y comunitario; evitar tono de crecimiento
X	Más seco, una idea por respuesta, casi sin emojis
Facebook	Más cálido, frases más largas y preguntas de experiencia
Instagram	Anclado a imagen, portada, reel o estética
TikTok	Muy breve, reactivo y vinculado al vídeo
Pinterest	Comentario mínimo; prioridad en descripción, tablero y guardado
Reddit	Más argumentado, sin fórmulas de redes y con aporte real
Fuentes

Repo espejo revisado: davidpd89/ci-sandbox-tmp, especialmente tools/threads_api.py, tools/threads_interact.py, tools/threads_reply_queue.py, tools/reply_writer.py, tools/conversation_followups.py, tools/check_language_variety.py, tools/check_duplicate_phrase.py y tools/action_ledger.py.

marclove/pythreads — cliente MIT para la API oficial de Threads; archivo principal: src/pythreads/threads.py.

josefr1/comment_generation_model — pipeline de generación contextual de comentarios; archivo: responsive_image_comment (1).py.

dancolta/subscope — motor de detección y puntuación de oportunidades en hilos; archivo principal: engine/subscope/cli.py.

NFeruch/reddit2text — normalización de hilos y comentarios en texto estructurado.

Threads API oficial

Threads Reply Management

Ejemplo de pregunta lectora en Threads: 
@thebee_ofbooks
threads

Ejemplo de debate de nicho sobre romantasy: 
@casiunafantasia

Ejemplo de autora de alta fantasía y romance: 
@cynthiaparrenoperez
threads

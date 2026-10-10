# Comentarios humanos y variados en Bluesky

Fuente: informe de Perplexity (https://www.perplexity.ai/search/22aaaabd-c99f-4282-9719-e4a13340cec2), generado 10/10/2026.

Informe mejorado: comentarios naturales en Bluesky para lectores y autores
Resumen

La conclusión anterior era correcta en lo esencial, pero incluía repos poco accionables y no distinguía entre código directamente copiable y referencias de arquitectura. Esta versión se centra en piezas verificadas y activas: el SDK MarshalX/atproto para publicar respuestas, langchain-ai/social-media-agent para prompts y validación de contenido, y eliasdabbas/llm-content-evaluation para evaluación con criterios explícitos.
atproto
+2

He revisado el espejo davidpd89/ci-sandbox-tmp: ya existe SISTEMA_DIARIO_BLUESKY/ con README.md, ESTADO.md y growth_config.json; por tanto, todo lo propuesto debe encajar como extensión de ese módulo, no como un sistema paralelo. El repositorio también tiene carpetas equivalentes para Mastodon, X, Threads, Facebook, Pinterest, Reddit, Instagram y TikTok, lo que permite diseñar un núcleo común de generación y evaluación de réplicas.

Correcciones al informe anterior

Eliminado apiverve/commentgenerator-api: es un envoltorio de API comercial y no aporta código suficientemente útil ni controlable para un sistema propio.

Eliminado kanishkkatara/omniwrite: apareció solo como resultado de un topic; no lo he podido verificar como dependencia madura ni como referencia superior a LangChain.

Eliminado FujitsuResearch/atproto-python: es un fork/variante del SDK; para producción conviene usar el SDK comunitario referenciado por ATProto, MarshalX/atproto.
atproto

Eliminado polybot: está archivado, aunque su idea de framework multired es válida como inspiración; no debe copiarse como dependencia.

Corregido el enfoque de “generar y publicar”: en Bluesky una respuesta es un post normal con reply_to, que exige dos referencias fuertes: root y parent. No existe un método send_reply() independiente.
atproto

Añadida verificación de actividad: MarshalX/atproto figura como SDK Python comunitario en la documentación oficial de ATProto; social-media-agent y llm-content-evaluation tienen rutas y documentación públicas consultables hoy.
github
+2

Hallazgos verificados
Repositorio / fuente	Estado	Qué copiar	Integración en ci-sandbox-tmp	Por qué es el mejor encaje

MarshalX/atproto
	Activo; SDK Python comunitario listado por ATProto. 
atproto
	examples/send_reply.py, examples/send_post.py y examples/send_rich_text.py. 
atproto
+1
	SISTEMA_DIARIO_BLUESKY/bluesky_reply_client.py	Es la vía más directa para leer, responder y mantener hilos en Bluesky desde Python.

langchain-ai/social-media-agent
	Activo; contiene prompts y reglas de generación en src/agents/generate-post/prompts/. 
github
	Separación entre contexto de negocio, ejemplos, reglas de estructura y prompt de validación. 
github
	SISTEMA_DIARIO_BLUESKY/replies/prompts.py y replies/validator.py	Su patrón de generar → condensar → validar es directamente adaptable a réplicas en español.

eliasdabbas/llm-content-evaluation
	Activo; README público con enfoque de evaluación mediante LLM y criterios. 
github
	Idea de rúbrica externa y evaluación por lotes; no copiar sus criterios de artículos sin adaptarlos.	SISTEMA_DIARIO_BLUESKY/replies/evaluate.py	Permite puntuar naturalidad, especificidad, coherencia y tono antes de publicar.
sneezeparty/soupy	Activo; actualizado en octubre de 2026; integración Bluesky y panel FastAPI.	Patrón de configuración en caliente y memoria/RAG para coherencia de voz.	Opcional: config/voice_profile.json y memoria de interacciones previas.	Útil para evitar que el bot repita fórmulas y para mantener una voz estable.
molly/paywall-bot	Actualizado en 2025; bot Bluesky en Python.	Patrón de bot sencillo, ciclo de ejecución y manejo de publicaciones.	Referencia para el job diario; no copiar su dominio.	Es un ejemplo pequeño y legible de automatización Bluesky.
ianklatzco/bsky-telegram-bot	Actualizado en septiembre de 2025.	Integración externa → Bluesky y manejo básico de credenciales.	Referencia para un panel interno o alertas de aprobación.	Menos obvio, pero útil si se quiere revisar candidatas desde Telegram antes de publicar.
Código directamente reutilizable
1. Responder correctamente en Bluesky

Este es el patrón exacto que debe usar el cliente de respuestas: root es el primer post del hilo y parent es el mensaje al que se contesta.
atproto

python
# Fuente exacta: https://github.com/MarshalX/atproto/blob/main/examples/send_reply.py
from atproto import Client, models


def main() -> None:
    client = Client()
    client.login('my-handle', 'my-password')

    root_post_ref = models.create_strong_ref(client.send_post('Post from Python SDK'))

    # Reply to the root post.
    # We need to pass ReplyRef with root and parent
    reply_to_root = models.create_strong_ref(
        client.send_post(
            text='Reply to the root post',
            reply_to=models.AppBskyFeedPost.ReplyRef(parent=root_post_ref, root=root_post_ref),
        )
    )

    # To reply on reply, we need to change the "parent" field.
    # Let's reply to our previous reply
    client.send_post(
        text='Reply to the parent reply',
        reply_to=models.AppBskyFeedPost.ReplyRef(parent=reply_to_root, root=root_post_ref),
    )


if __name__ == '__main__':
    main()

Adaptación para el sistema: en lugar de crear el post raíz, el sistema recibirá root_uri, root_cid, parent_uri y parent_cid del post descubierto. La función de publicación debe aceptar esos cuatro valores y nunca asumir que el post original es siempre la raíz.

2. Publicación básica y referencia de post
python
# Fuente exacta: https://github.com/MarshalX/atproto/blob/main/examples/send_post.py
from atproto import Client


def main() -> None:
    client = Client()
    client.login('my-handle', 'my-password')

    client.send_post(text='Hello World from Python SDK!')


if __name__ == '__main__':
    main()

Esta pieza sirve para el smoke test de conexión, pero en producción debe ejecutarse solo contra una cuenta de pruebas o tras aprobación manual.
pypi
+1

3. Texto enriquecido, si se enlaza a la web o a una novela
python
# Fuente exacta: https://github.com/MarshalX/atproto/blob/main/examples/send_rich_text.py
from atproto import Client, client_utils


def main() -> None:
    client = Client()
    client.login('my-handle', 'my-password')

    text_builder = client_utils.TextBuilder()
    text_builder.text('Hello World from Python SDK! ')
    text_builder.link('Python SDK', 'https://atproto.blue/')

    # You can pass instance of TextBuilder instead of str to the "text" argument.
    client.send_post(text_builder)  # same with send_image method


if __name__ == '__main__':
    main()

Para comentarios de crecimiento, los enlaces deben ser excepcionales: solo cuando el autor pregunta explícitamente por la web, la novela o un recurso. El SDK permite construir el enlace como faceta correcta en lugar de dejar una URL plana.
github

Código nuevo recomendado para el repo
SISTEMA_DIARIO_BLUESKY/replies/reply_prompt.py
python
# Archivo nuevo propuesto para davidpd89/ci-sandbox-tmp
# Ruta: SISTEMA_DIARIO_BLUESKY/replies/reply_prompt.py
from dataclasses import dataclass


@dataclass
class ReplyCandidate:
    text: str
    intent: str
    tone: str
    word_count: int
    emoji_count: int
    has_question: bool
    score: float = 0.0


BLUESKY_REPLY_SYSTEM_PROMPT = """Eres la voz de David Porto, autor español de fantasía juvenil y romantasy.

Escribe una respuesta breve para Bluesky a partir del post original.

Reglas obligatorias:
- Español de España, natural y cercano.
- Entre 20 y 45 palabras.
- Máximo 2 emojis; preferiblemente 0 o 1.
- Máximo 1 pregunta, y solo si el post invita a conversación.
- Demuestra que has leído el post: menciona un detalle concreto.
- Nunca suenes promocional ni uses fórmulas genéricas.
- No repitas literalmente frases del post original.
- No inventes datos sobre la obra, el autor o la persona.
- Devuelve solo el texto de la respuesta, sin comillas ni explicaciones.
"""

BLUESKY_REPLY_USER_PROMPT = """Post original:
{post_text}

Autor del post: {author_display_name}
Tipo de post: {post_type}
Tema detectado: {topic}
Intención deseada: {intent}
Tono deseado: {tone}

Escribe una única respuesta candidata."""
SISTEMA_DIARIO_BLUESKY/replies/reply_validator.py
python
# Archivo nuevo propuesto para davidpd89/ci-sandbox-tmp
# Ruta: SISTEMA_DIARIO_BLUESKY/replies/reply_validator.py
import re
import unicodedata

MIN_WORDS = 20
MAX_WORDS = 45
MAX_EMOJIS = 2
BANNED_PATTERNS = [
    r"\bgran contenido\b",
    r"\bme encanta tu perfil\b",
    r"\bsigue así\b",
    r"\bno te lo pierdas\b",
    r"\bdisponible en mi web\b",
    r"\bcompra mi libro\b",
]


def _count_words(text: str) -> int:
    return len(re.findall(r"\b[\wáéíóúüñÁÉÍÓÚÜÑ]+\b", text, flags=re.UNICODE))


def _count_emojis(text: str) -> int:
    return sum(1 for char in text if unicodedata.category(char) == "So")


def validate_reply(text: str) -> tuple[bool, list[str]]:
    errors = []

    if not text or not text.strip():
        errors.append("empty_reply")

    words = _count_words(text)
    if words < MIN_WORDS:
        errors.append(f"too_short:{words}")
    if words > MAX_WORDS:
        errors.append(f"too_long:{words}")

    emojis = _count_emojis(text)
    if emojis > MAX_EMOJIS:
        errors.append(f"too_many_emojis:{emojis}")

    lowered = text.lower()
    for pattern in BANNED_PATTERNS:
        if re.search(pattern, lowered):
            errors.append(f"banned_phrase:{pattern}")

    if text.count("?") > 1:
        errors.append("too_many_questions")

    return not errors, errors
SISTEMA_DIARIO_BLUESKY/replies/bluesky_reply_client.py
python
# Archivo nuevo propuesto para davidpd89/ci-sandbox-tmp
# Ruta: SISTEMA_DIARIO_BLUESKY/replies/bluesky_reply_client.py
from dataclasses import dataclass

from atproto import Client, models


@dataclass
class BlueskyThreadRefs:
    root_uri: str
    root_cid: str
    parent_uri: str
    parent_cid: str


def send_reply(
    client: Client,
    text: str,
    refs: BlueskyThreadRefs,
    langs: list[str] | None = None,
):
    return client.send_post(
        text=text,
        reply_to=models.AppBskyFeedPost.ReplyRef(
            root=models.ComAtprotoRepoStrongRef.Main(
                uri=refs.root_uri,
                cid=refs.root_cid,
            ),
            parent=models.ComAtprotoRepoStrongRef.Main(
                uri=refs.parent_uri,
                cid=refs.parent_cid,
            ),
        ),
        langs=langs or ["es"],
    )

La clave es que root y parent son objetos independientes: si se responde a una respuesta, parent cambia, pero root sigue apuntando al primer post del hilo.
atproto
+1

Estilo de réplica: reglas operativas
Tono y estructura

Tono: cercano, curioso y lector; nunca corporativo ni excesivamente efusivo.

Longitud: 20–45 palabras; máximo 60.

Estructura: detalle observado + matiz, experiencia breve o pregunta concreta.

Emojis: 0–2; preferir 📚, ✨, 🐉, 🖤, ☕ y 🔥.

Preguntas: máximo una por réplica y solo en torno al 30–40% de los casos.

Promoción: prohibida en la primera réplica; un enlace solo si surge de forma natural y el post lo invita.

Ejemplos de calidad

Post: “Llevo semanas atascada con la escena en la que la protagonista descubre la traición.”

Buena:
“Ese momento es complicado porque tiene que doler sin explicar demasiado. ¿Lo descubre por una prueba concreta o por algo que ya había notado? 📚”

Buena y más corta:
“Me da curiosidad cómo vas a equilibrar su rabia y su miedo; esas escenas funcionan mejor cuando ninguna de las dos gana del todo.”

Mala:
“¡Qué interesante! Tu historia suena increíble. ¡Sigue así! 🔥🔥🔥”

Mala:
“Como autora de fantasía, te recomiendo leer mi última novela, disponible en mi web.”

Plan de implementación en PR pequeñas
PR 1 — Especificación y golden set

Crear SISTEMA_DIARIO_BLUESKY/replies/REPLY_STYLE.md.

Añadir replies/golden_set_es.jsonl con 50 ejemplos anotados.

Campos: post_context, reply, intent, tone, word_count, emoji_count, has_question, quality_score.

No se publica nada.

PR 2 — Generador de candidatas

Crear replies/reply_prompt.py.

Generar tres candidatas por post: empática, analítica y curiosa.

Guardar en replies/candidates.jsonl con post, refs, candidata, prompt, modelo y timestamp.

PR 3 — Validador determinista

Crear replies/reply_validator.py.

Validar idioma, longitud, emojis, preguntas, frases prohibidas y duplicados recientes.

Añadir tests con casos buenos, cortos, largos, promocionales y con exceso de emojis.

PR 4 — Cliente de respuesta

Crear replies/bluesky_reply_client.py con el patrón exacto de send_reply.py.
atproto

Exigir root_uri, root_cid, parent_uri y parent_cid.

Tests con mocks; ninguna publicación real en CI.

PR 5 — Evaluación LLM y cola de aprobación

Crear replies/evaluate.py inspirado en la evaluación por criterios de llm-content-evaluation.
github

Puntuar: especificidad, naturalidad, coherencia, tono, riesgo promocional y probabilidad de respuesta.

Crear replies/review_queue.jsonl; solo se publica lo aprobado.

PR 6 — Métricas y aprendizaje

Crear metrics/reply_results.jsonl.

Registrar: impresiones, likes en la réplica, respuestas recibidas, reposts, continuación del hilo y seguidores nuevos atribuibles.

Ranking inicial: respuesta recibida > continuación del hilo > like en réplica > impresiones.

Aplicación a las demás redes

El núcleo context_extractor + reply_prompt + reply_validator debe ser común. Solo cambian el adaptador y las restricciones:

Red	Adaptación principal
Bluesky	Hilos con root/parent; 20–45 palabras; tono lector-autor. 
atproto

Mastodon	Respuestas públicas o limitadas según visibilidad; tono algo más reflexivo.
Threads	Más visual y casual; preguntas muy cortas.
X	Máxima brevedad; evitar hilos innecesarios.
Facebook	Grupos y páginas requieren más contexto; tono comunitario.
Reddit	Prioridad absoluta a aportar valor; nada promocional.
Pinterest	Comentarios poco relevantes; priorizar guardados y descripciones.
Instagram	Comentarios breves, visuales y emocionales.
TikTok	Comentarios muy cortos, gancho o pregunta directa.
Fuentes

ATProto SDK — guía de publicación y respuestas
 — confirma que una respuesta exige ReplyRef con root y parent.
atproto

ATProto SDK — ejemplos básicos
 — contiene el ejemplo send_reply.py verificado.
github

MarshalX/atproto — ejemplo de respuesta — código fuente exacto reutilizable.
atproto

MarshalX/atproto — ejemplo de texto enriquecido
 — construcción de enlaces como facetas.
github

ATProto — SDKs oficiales y comunitarios
 — valida atproto como SDK Python comunitario.
atproto

langchain-ai/social-media-agent — prompts
 — patrón de contexto, ejemplos, reglas y validación.
github

eliasdabbas/llm-content-evaluation
 — evaluación de contenido mediante LLM y criterios explícitos.
github

sneezeparty/soupy — bot activo con integración Bluesky, memoria/RAG y panel FastAPI.

molly/paywall-bot — bot Bluesky en Python, útil como referencia de automatización sencilla.

ianklatzco/bsky-telegram-bot — integración externa hacia Bluesky, útil para aprobaciones humanas.

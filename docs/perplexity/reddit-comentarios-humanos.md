# Comentarios humanos y variados en Reddit

Fuente: informe de Perplexity (https://www.perplexity.ai/search/f39e9777-df2e-4993-a1fd-e4e54ad7d403), generado 10/10/2026.

Informe mejorado: comentarios naturales de lectores y autores en Reddit (español)
Resumen

Tras revisar el repo espejo, la recomendación se mantiene pero queda más acotada: no crear un generador paralelo, sino añadir a tools/reddit_comments.py y tools/reply_writer.py una capa de estilo Reddit en español, alimentada por el corpus español de diálogos de Reddit y controlada por los lint existentes. También elimino afirmaciones que no se pueden sostener con evidencia directa —por ejemplo, atribuir a las preguntas un efecto uniformemente positivo— y sustituyo referencias poco útiles por repos verificados y más recientes.

Correcciones al informe anterior
Punto anterior	Decisión	Motivo
Incluir feder-cr/reddit_karma_farmer_auto_commentator_with_AI	Eliminado	Su valor es automatización de navegador, no estilo ni calidad de comentario; no aporta nada reutilizable para nuestro objetivo.
Presentar beeCuiet/reddit-llm-comment-bot como referencia principal	Degradado	Es un script mínimo; existen alternativas más recientes con separación entre servicio LLM, contexto de Reddit y ejecución.
Afirmar que “las preguntas ayudan”	Matizado	La evidencia encontrada indica que más interrogantes no mejoran necesariamente la probabilidad de respuesta; la pregunta debe ser opcional, concreta y contextual.
Sugerir un “humanity score” como filtro fuerte	Convertido en advertencia	Los detectores de texto IA tienen falsos positivos; debe marcar para revisión, no bloquear automáticamente.
Corpus español de 2019 como única fuente	Conservado, con advertencia	Sigue siendo el recurso más directo para español, pero su último push es de 2021; sirve para estilo y ejemplos, no para tendencias actuales.
Estado del repo espejo

El sistema ya dispone de las piezas necesarias para integrar esta mejora sin duplicar arquitectura:

tools/reddit_comments.py — lógica específica de comentarios Reddit.

tools/reddit_interact.py y tools/reddit_execute.py — interacción y ejecución.

tools/reply_writer.py y tools/api_comment_writer.py — redacción de respuestas.

tools/check_language_variety.py, check_duplicate_phrase.py y reply_corpus_lint.py — control de variedad, duplicados y calidad del corpus.

tools/conversation_followups.py y conversation_turn_policy.py — política de continuación conversacional.

tools/action_ledger.py y growth_attribution.py — registro y atribución de resultados.

La carpeta publicaciones Reddit GPT/2026-10-20 confirma que Reddit ya es un canal operativo del sistema, por lo que cualquier cambio debe respetar el contrato actual de generación, cola, auditoría y publicación.

Hallazgos verificados
Hallazgo	Fuente / estado	Qué aprovechar	Integración	Riesgo	Test
Corpus español de diálogos Reddit con pares contexto→respuesta	
sunnweiwei/spanish-reddit-dialogues-corpus
; Python; último push 2021-07-18; no archivado.	filter_by_subreddit.py, filter_by_lang.py y get_context_and_build.py para construir ejemplos reales en español.	Nuevo tools/reddit_style_corpus.py que genere data/reddit_style_examples_es.jsonl.	Corpus antiguo y con ruido; requiere filtrado por subreddit, longitud y toxicidad.	Esquema JSONL; idioma español; longitud; ausencia de duplicados.
La longitud influye en la conversación, con rendimientos decrecientes	Estudio sobre estructura de conversaciones en Reddit.	Perfiles de longitud: 1 frase, 2–3 frases y 4–6 frases.	Parámetro length_profile en reddit_comments.py.	Longitud fija = patrón robótico.	Distribución de longitud; variedad entre comentarios consecutivos.
Más signos de interrogación no garantizan más réplicas	Estudio de dinámica de discusión en Reddit, 2026.	Máximo una pregunta por comentario, ligada a una entidad concreta del post.	Regla en conversation_followups.py.	Preguntas genéricas tipo “¿Qué opinas?”.	Lint de ?; test de relevancia semántica básica.
Los emojis son útiles sólo como matiz contextual	Discusiones de usuarios sobre emojis y tono.	Lista corta: 😅, 😭, 🥹, 👀, 🔥, 📚.	Política en check_language_variety.py: 0–1 emoji.	Uso sistemático = señal de bot.	Frecuencia máxima; variedad; prohibición en comentarios técnicos.
Los detectores de comentarios IA son un campo activo	trentmkelly/reddit-llm-comment-detector; extensión entrenada con texto estilo Reddit.	Señales de uniformidad, cortesía excesiva y frases genéricas.	tools/reddit_humanity_score.py como aviso previo.	Falsos positivos.	Precisión sobre conjunto interno aprobado/rechazado.
Existen agentes Reddit LLM recientes con arquitectura separada	rajrounak21/reddit-ai-agent; MIT; creado y actualizado en septiembre de 2026.	Separación entre reddit_service.py, llm_service.py y main.py; generación contextual de respuestas.	Referencia arquitectónica; no copiar su flujo de publicación.	Proyecto muy nuevo, con poco uso comunitario.	Test de contrato de entrada/salida.
Existe un bot Reddit con revisión humana y campañas	Seeking-Leverage/reddit-comment-bot; MIT; junio de 2026.	Estructura de playbooks, borradores IA, revisión humana y seguimiento de campañas.	Inspiración para reply_hold.py y daily_review.py; no duplicar su web/FastAPI.	Complejidad mayor de la necesaria.	Test de que ningún comentario se publica sin estado de revisión.
Corpus masivo Reddit en BigQuery	
PolyAI-LDN/conversational-datasets
. 
github
	Conversión de hilos Reddit en dataset conversacional; útil si se necesita más volumen multilingüe.	Opcional, fase 2; no imprescindible para empezar.	Coste/permisos de BigQuery y volumen.	Test de muestreo y filtrado por idioma.
Código reutilizable

Los bloques siguientes son adaptaciones listas para copiar, no transcripciones literales de los repos origen. Cada uno conserva la URL exacta del archivo del que parte la idea o la estructura.

1. Construir pares contexto→respuesta en español

Basado en la lógica de emparejar respuestas con su comentario padre del corpus español.

python
# Fuente: https://github.com/sunnweiwei/spanish-reddit-dialogues-corpus/blob/main/get_context_and_build.py
# Adaptación para el sistema: convierte comentarios Reddit en pares contexto/respuesta filtrados.

import json
from pathlib import Path

def build_pairs(rows: list[dict], min_len: int = 20, max_len: int = 900) -> list[dict]:
    by_id = {r["id"]: r for r in rows if r.get("id")}
    pairs = []

    for reply in rows:
        parent_id = reply.get("parent_id", "").replace("t1_", "")
        parent = by_id.get(parent_id)

        if not parent:
            continue

        context = (parent.get("body") or "").strip()
        response = (reply.get("body") or "").strip()

        if not context or not response:
            continue
        if not (min_len <= len(context) <= max_len):
            continue
        if not (min_len <= len(response) <= max_len):
            continue
        if "[deleted]" in context.lower() or "[removed]" in context.lower():
            continue

        pairs.append({
            "subreddit": reply.get("subreddit"),
            "context": context,
            "response": response,
            "context_chars": len(context),
            "response_chars": len(response),
        })

    return pairs

def save_jsonl(pairs: list[dict], path: str = "data/reddit_style_examples_es.jsonl"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

Integración: ejecutarlo tras descargar el corpus, filtrar por subreddits literarios y volcar el resultado a data/reddit_style_examples_es.jsonl. reply_writer.py podrá seleccionar 3–5 ejemplos como few-shot.

2. Filtrar por subreddits del nicho

Basado en el filtro por subreddit del corpus.

python
# Fuente: https://github.com/sunnweiwei/spanish-reddit-dialogues-corpus/blob/main/filter_by_subreddit.py
# Adaptación: filtra el corpus por subreddits útiles para fantasía, lectura y escritura.

import json
from pathlib import Path

ALLOWED = {
    "fantasy", "books", "suggestmeabook", "yAlit", "printsf",
    "fantasywriters", "writing", "selfpublish", "espanol",
    "libros", "lectura", "fantasia", "escribir",
}

def filter_subreddits(input_path: str, output_path: str) -> int:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    kept = 0

    with open(input_path, encoding="utf-8") as src, open(output_path, "w", encoding="utf-8") as dst:
        for line in src:
            row = json.loads(line)
            subreddit = (row.get("subreddit") or "").strip().lower()

            if subreddit in ALLOWED:
                dst.write(json.dumps(row, ensure_ascii=False) + "\n")
                kept += 1

    return kept

Integración: añadir los subreddits definitivos a config/reddit_style_profile.json, no dejarlos hard-coded en producción.

3. Perfil de estilo Reddit en español

Nuevo archivo propuesto: config/reddit_style_profile.json.

json
{
  "language": "es",
  "register": "conversacional",
  "archetypes": [
    "lector_entusiasta",
    "lector_critico",
    "recomendador",
    "autor_craft",
    "vecino_subreddit"
  ],
  "length_profiles": {
    "reaction": {"sentences": [1, 1], "chars": [40, 180]},
    "opinion": {"sentences": [2, 3], "chars": [120, 420]},
    "recommendation": {"sentences": [3, 6], "chars": [220, 800]}
  },
  "emoji_policy": {
    "max_per_comment": 1,
    "allowed": ["😅", "😭", "🥹", "👀", "🔥", "📚"],
    "forbidden_contexts": ["correccion", "debate_tecnico", "queja"]
  },
  "question_policy": {
    "max_per_comment": 1,
    "required_when": ["recomendacion", "opinion"],
    "forbidden_when": ["post_pide_recomendacion_cerrada"]
  },
  "banned_patterns": [
    "¡Claro!",
    "¡Por supuesto!",
    "Como modelo de lenguaje",
    "Espero que esto te ayude",
    "En resumen,"
  ]
}

Integración: cargarlo desde reddit_comments.py; no modificar la firma pública de reply_writer.py hasta que el perfil esté validado.

4. Validador previo de naturalidad

Nuevo archivo propuesto: tools/reddit_humanity_score.py.

python
# Fuente conceptual: https://github.com/trentmkelly/reddit-llm-comment-detector
# Adaptación: filtro ligero de señales de texto artificial; devuelve avisos, no bloqueos.

import re
from dataclasses import dataclass

AI_PHRASES = [
    "¡Claro!", "¡Por supuesto!", "Espero que esto te ayude",
    "En resumen,", "Como modelo de lenguaje", "No dudes en",
]

@dataclass
class HumanityResult:
    score: float
    warnings: list[str]

def score_comment(text: str) -> HumanityResult:
    warnings = []
    score = 1.0

    lowered = text.lower()

    for phrase in AI_PHRASES:
        if phrase.lower() in lowered:
            warnings.append(f"frase_generica:{phrase}")
            score -= 0.2

    if text.count("?") > 1:
        warnings.append("demasiadas_preguntas")
        score -= 0.15

    if len(re.findall(r"[\U0001F300-\U0001FAFF]", text)) > 1:
        warnings.append("demasiados_emojis")
        score -= 0.15

    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    if len(sentences) >= 3:
        starts = [s.strip().split()[0].lower() for s in sentences if s.strip().split()]
        if len(set(starts)) < len(starts) * 0.7:
            warnings.append("estructura_repetitiva")
            score -= 0.2

    return HumanityResult(score=max(0.0, score), warnings=warnings)

Integración: llamarlo antes de insertar el comentario en reply_queue.py. Si score < 0.6, enviar a revisión humana mediante reply_hold.py; no descartar automáticamente.

5. Selección variada de few-shots

Nuevo archivo propuesto: tools/reddit_style_examples.py.

python
# Fuente de datos: https://github.com/sunnweiwei/spanish-reddit-dialogues-corpus
# Adaptación: selecciona ejemplos variados por longitud y presencia de pregunta.

import json
import random
from pathlib import Path

def load_examples(path: str = "data/reddit_style_examples_es.jsonl") -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def pick_examples(examples: list[dict], k: int = 4, seed: int | None = None) -> list[dict]:
    rng = random.Random(seed)

    short = [e for e in examples if e["response_chars"] <= 180]
    medium = [e for e in examples if 180 < e["response_chars"] <= 420]
    long = [e for e in examples if e["response_chars"] > 420]
    questions = [e for e in examples if "?" in e["response"]]

    buckets = [short, medium, long, questions]
    chosen: list[dict] = []

    for bucket in buckets:
        if bucket and len(chosen) < k:
            chosen.append(rng.choice(bucket))

    while len(chosen) < k and examples:
        candidate = rng.choice(examples)
        if candidate not in chosen:
            chosen.append(candidate)

    return chosen[:k]

Integración: reply_writer.py llamará a pick_examples() con una semilla distinta por comentario, garantizando variación sin perder coherencia de estilo.

Ejemplos de patrón para prompts

Estos ejemplos son patrones de redacción, no comentarios para publicar literalmente.

Reacción breve

Uf, sí. A mí el último tercio me dejó con la sensación de que faltaba una escena para cerrar el arco de la protagonista. ¿Lo viste precipitado o como final abierto?

Recomendación

Si buscas fantasía con romance lento, El nombre del viento tiene mucha tensión, aunque el romance no es el centro. Para algo más directo, Fourth Wing funciona mejor. ¿Prefieres mundo oscuro o algo más ligero?

Autor comentando craft

Me gusta cómo planteas la duda del personaje antes de la acción: le da más peso a la escena. ¿La tensión viene de que no sabe si puede confiar en él, o de que sabe que no debería?

Plan de implementación en PR pequeñas
PR 1 — Perfil de estilo

Añadir config/reddit_style_profile.json.

Definir arquetipos, longitudes, emojis y política de preguntas.

No tocar todavía la generación.

Tests: validación JSON; carga en Python 3.11; test en Windows.

PR 2 — Minería del corpus español

Añadir tools/reddit_style_corpus.py y tools/reddit_style_examples.py.

Filtrar por subreddit, longitud, idioma y calidad.

Generar data/reddit_style_examples_es.jsonl.

Tests: mínimo de ejemplos válidos; idioma; duplicados; distribución de longitud.

PR 3 — Integración en reply_writer.py

Añadir style_profile="reddit_reader_es".

Inyectar few-shots variables y reglas de longitud/pregunta/emoji.

Mantener el contrato de salida actual.

Tests: snapshot de prompt; una pregunta como máximo; longitud válida; sin patrones prohibidos.

PR 4 — Lint de humanidad

Añadir tools/reddit_humanity_score.py.

Integrarlo como advertencia en audit_lote.py o daily_review.py.

Enviar a reply_hold.py los comentarios con puntuación baja.

Tests: comentarios IA-like detectados; comentarios humanos válidos no bloqueados; umbral configurable.

PR 5 — Ranking y aprendizaje

Ampliar action_ledger.py / growth_attribution.py con métricas Reddit: respuestas recibidas, upvotes, profundidad de hilo y respuesta del autor original.

Agrupar por arquetipo, longitud, emoji y pregunta.

Generar informe semanal para ajustar pesos.

Tests: agregación con datos simulados; atribución por comentario; informe reproducible.

Aplicación multired

X / Threads: 1–2 frases; pregunta directa; emoji casi siempre fuera.

Bluesky / Mastodon: tono cercano, más contexto cultural, menos fórmulas de engagement.

Facebook: 2–4 frases; experiencia personal y grupos de lectura.

Instagram / TikTok: comentarios muy cortos, referencia visual o de escena.

Pinterest: comentarios en pines y tableros; nada de réplicas largas.

Reddit: es la red donde más conviene variar longitud, opinión matizada y pregunta contextual.

Fuentes

Estudio de dinámica de discusión en Reddit: 
https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0344782

Estructura de conversaciones en Reddit: 
https://arxiv.org/html/2209.14836v2

Corpus español de diálogos Reddit: 
https://github.com/sunnweiwei/spanish-reddit-dialogues-corpus

Detector de comentarios LLM: 
https://github.com/trentmkelly/reddit-llm-comment-detector

Agente Reddit LLM reciente: https://github.com/rajrounak21/reddit-ai-agent

Bot Reddit con revisión humana: https://github.com/Seeking-Leverage/reddit-comment-bot

Corpus conversacional Reddit en BigQuery: 
https://github.com/PolyAI-LDN/conversational-datasets/blob/master/reddit/README.md
github

Discusiones sobre emojis y tono: 
https://www.reddit.com/r/SpicyAutism/comments/11qgpfq/do_emojis_in_text_help_you_understand_tone_make/
 y 
https://www.reddit.com/r/linguistics/comments/5bcphq/perspectives_on_emojis/

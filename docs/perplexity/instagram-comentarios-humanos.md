# Comentarios humanos y variados en Instagram

Fuente: informe de Perplexity (https://www.perplexity.ai/search/10283bbe-ae42-4cea-8e84-604a140882fb), generado 10/10/2026.

Informe mejorado: comentarios naturales en Instagram para el sistema multired
Resumen

Tu sistema ya resuelve la parte más difícil: no usa bancos de frases y exige que cada comentario tenga procedencia de ChatGPT, pase validaciones de forma y respete memoria, cooldown por autor y contexto. La carencia real es que reply_writer.py solo está conectado a X, Threads y Facebook; Instagram tiene ejecución y exploración, pero no generación de comentarios integrada.
arxiv
+1

La recomendación revisada es más conservadora que el informe anterior: extender el módulo existente a Instagram, añadir un perfil de estilo por red y un auditor de variedad; no copiar bots públicos de comentarios ni añadir un segundo generador. También elimino afirmaciones que no pude verificar como aplicables a comentarios —especialmente las estadísticas de emojis, que medían posts, no respuestas—.
quintly

Hallazgos
Hallazgo	Repositorio / fuente	Estado	Qué aprovechar	Qué no aprovechar
Generación contextual con estilo imitado	bobtech-IIT/reply-genie — TypeScript, 2 estrellas, actualizado el 19/07/2026.	Activo, pero poco maduro y en TypeScript	La idea de producto: generar varias respuestas contextuales y permitir imitar un estilo definido.	Su implementación web/PWA y su proveedor de IA; no encaja con tu pipeline Python/Edge.
Respuestas por plataforma y URL	Noob-Developer-Real/ClarityReply — Python/Django, 2 estrellas, actualizado el 25/06/2026.	Activo, tamaño pequeño	Separación entre extracción de contexto y servicio de respuesta (core/services/reply.py).	Su dependencia de Django, scraping y proveedor externo; tu sistema ya tiene instagram_interact.py.
Generador humano contextual multiplataforma	vvmmm/Human_like_social_media_reply_generator_using_AI — Python/FastAPI, actualizado el 23/05/2025.	Poco activo	Patrón de API: post + plataforma + historial -> respuesta.	Su uso de Gemini, MongoDB y frontend Streamlit; añadiría dependencias innecesarias.
Acceso estructurado a comentarios e insights	thenavidm/instagram-mcp — Python, actualizado el 03/10/2026.	Activo	Modelo de capacidades: comentarios, insights, investigación de hashtags y análisis de competencia.	Usarlo como servidor MCP o API no oficial; tu repo ya tiene capa propia de navegador y instagram_api.py.
Corpus de comentarios con respuestas	
AMINE1921/instacomments
 — actualizado el 08/08/2025.	Moderadamente activo	Esquema de exportación: comentario padre, respuesta, autor, likes y fecha.	Su scraper directo; conviene aislar cualquier lectura detrás de tu capa existente.
Sentimiento en español	chat-crm-suite/chat-crm-ia — Python/FastAPI, actualizado el 06/10/2026; usa pysentimiento.	Activo	pysentimiento como dependencia opcional para clasificar tono de comentarios recibidos y respuestas candidatas.	Su servicio FastAPI completo; solo interesa la función de análisis.
Sentimiento español ligero	
sentiment-analysis-spanish/sentiment-spanish
 — Python, 2020.	Estable, pero antiguo	Alternativa sin GPU para una primera clasificación gruesa.	Como árbitro de naturalidad: mide polaridad, no si un comentario suena humano.
Evaluación con LLM	
llm-as-a-judge/Awesome-LLM-as-a-judge
 — recopilación activa de métodos y bibliotecas.	Activo	Rúbrica de juez con motivo explicado, como segundo filtro tras reglas duras.	Delegar en el juez la decisión final sin reglas deterministas previas.

Descartes respecto al informe anterior:

Las cifras de “emojis aumentan interacciones” proceden de análisis sobre posts, no comentarios; no las uso como justificación de política de emojis.
quintly

No incluyo “ejemplos reales” de comentarios de Instagram: no he podido verificar comentarios concretos, autores ni fechas desde las herramientas disponibles. Los ejemplos que siguen son plantillas de forma derivadas de tu propio prompt aprobado, no citas de terceros.
arxiv

No recomiendo drjeff-ai/instagram-commenter ni otros repos de automatización de comentarios: resuelven el envío, no la calidad contextual, y duplicarían tu instagram_interact.py.
github

Código reutilizable tal cual

El único código que puedo garantizar como copia literal y verificada es el de tu propio espejo. Estas son las piezas que conviene reutilizar en el PR de Instagram.

1. Límites por red: añadir Instagram

Fuente exacta: tools/reply_writer.py.
arxiv

python
# https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/reply_writer.py
MAX_CHARS = {"reddit_micro": 62, "pinterest": 110, "x": 200, "threads": 230, "facebook": 230, "bluesky": 200, "mastodon": 230, "tiktok": 90, "reddit": 170}
MAX_WORDS = {"reddit_micro": 9, "pinterest": 16, "x": 32, "threads": 36, "facebook": 36, "bluesky": 32, "mastodon": 36, "tiktok": 14, "reddit": 28}

Cambio propuesto:

python
MAX_CHARS = {"reddit_micro": 62, "pinterest": 110, "x": 200, "threads": 230, "facebook": 230, "bluesky": 200, "mastodon": 230, "tiktok": 90, "reddit": 170, "instagram": 120}
MAX_WORDS = {"reddit_micro": 9, "pinterest": 16, "x": 32, "threads": 36, "facebook": 36, "bluesky": 32, "mastodon": 36, "tiktok": 14, "reddit": 28, "instagram": 20}
2. Registro de procedencia: evitar texto sin ChatGPT

Fuente exacta: tools/reply_writer.py.
arxiv

python
# https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/reply_writer.py
def require_gpt(plan, network="", log=print, path=None):
    """Guardia común para textos externos: inválidos o sin procedencia se omiten.

    Un texto ausente/blank antes escapaba al `if item.get("text")` y hacía que
    el preflight del ejecutor rechazase el lote entero. Las acciones sanas siguen.
    La excepción `authored=manual` no permite publicar un texto vacío.
    """
    if os.environ.get("RRSS_ALLOW_UNMARKED_TEXT") == "1":
        return list(plan)  # Exclusivamente tests offline existentes.
    kept, dropped_empty, dropped_provenance = [], 0, 0
    for index, item in enumerate(plan, start=1):
        if item.get("kind") in TEXT_KINDS:
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                dropped_empty += 1
                log(f"[{network or 'ejecutor'}] GUARDIA_TEXTO elemento {index}: texto_vacio; se omite solo este elemento")
                continue
            if item.get("authored") != "manual" and not is_gpt(text, path):
                dropped_provenance += 1
                continue
        kept.append(item)
    if dropped_provenance:
        log(f"[{network or 'ejecutor'}] {dropped_provenance} comentarios/respuestas SIN texto de ChatGPT quitados del plan (nunca se publica texto de banco)")
    if dropped_empty:
        log(f"[{network or 'ejecutor'}] {dropped_empty} comentarios/respuestas sin texto omitidos, resto del lote conservado")
    return kept

Esta función debe invocarse también desde instagram_execute.py antes de publicar cualquier comment.

3. Validación de forma: reutilizar, no duplicar

Fuente exacta: tools/reply_writer.py.
arxiv

python
# https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/reply_writer.py
def valid_reply(text, network, recent=(), *, allow_question=True):
    """(True, '') o (False, motivo). Reglas de forma: no se juzga el fondo, eso lo decide la propia consulta."""
    raw = (text or "").strip()
    if not raw:
        return False, "vacio"
    words = re.findall(r"[^\W_]+", raw)
    if len(words) < 2 or len(words) > MAX_WORDS.get(network, 30):      # 08/10: micro-reacciones de 2 palabras («Jaja, totalmente») valen (GUIA_VOZ_REPLIES)
        return False, f"{len(words)} palabras"
    if len(raw) > MAX_CHARS.get(network, 270) or "\n" in raw:
        return False, "longitud/lineas"
    if BANNED.search(raw):
        return False, "frase o contenido prohibido"
    if STYLE.search(raw):
        return False, "punto y coma o guion largo"
    if raw.count("?") > 1 or (not allow_question and "?" in raw):
        return False, "preguntas"
    try:
        import x_interact as x
        x._check_spanish_orthography(raw.replace("¿", "").replace("?", ""))
    except ValueError as exc:
        return False, str(exc)[:60]
    except Exception:
        pass
    start = _start(raw)
    if start and any(_start(old) == start for old in recent):
        return False, "arranque repetido"
    return True, ""

Con "instagram" añadido a los diccionarios de límites, esta función valida Instagram sin cambios adicionales.

4. Cooldown por autor: impedir comentarios repetidos

Fuente exacta: tools/reply_writer.py.
arxiv

python
# https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/reply_writer.py
AUTHOR_COOLDOWN_DAYS = 30        # a quien ya le hemos comentado no se le vuelve a comentar de nuestra iniciativa (David, 07/10: «ahi no se comenta mas»)
python
# https://github.com/davidpd89/ci-sandbox-tmp/blob/main/tools/reply_writer.py
def new_authors_only(items, network, log=print):
    """Quita los posts de autores a los que ya hemos comentado (salvo que sea ELLOS quienes nos comentan: `reply_to_us`)."""
    cache, kept = {}, []
    for item in items:
        net = item.get("network") or network
        if net not in cache:
            cache[net] = replied_authors(net)
        import relationship_policy as rp
        if not item.get("reply_to_us") and rp.norm(item.get("author")) in cache[net]:
            log(f"[reply_writer] {item['id']} omitido: ya comentamos a {item.get('author')} en {net}")
            continue
        kept.append(item)
    return kept
Perfil de estilo para Instagram

Añadiría esta sección a 00_OPERATIVO/respuestas_memoria.json, dentro de estilo_por_red:

json
{
  "estilo_por_red": {
    "instagram": "Comentario muy corto, cercano y visual. Primero un detalle concreto del post: portada, tropo, frase, libro, ambientación o situación. Una o dos frases, normalmente menos de 12 palabras. Pregunta solo si es fácil y útil. Cero o un emoji, solo si hay celebración, humor o cariño evidente. Sin autopromoción, sin hashtags, sin menciones y sin frases de IA."
  }
}
Plantillas de forma

No son ejemplos reales ni frases para publicar; son los cinco formatos que el generador debe repartir:

Reacción corta: “Uf, qué portada”.

Pregunta concreta: “¿Es la primera parte de la saga?”.

Observación breve: “Ese tropo siempre me gana”.

Observación + pregunta: “Ese final suena intenso. ¿Ya sabes qué leerás ahora?”.

Recomendación: dos títulos reales, dos frases cortas, sin pregunta final.

Tu prompt ya establece que ningún formato supere el 40% del lote y que haya al menos tres formatos distintos; esa regla debe aplicarse también a Instagram.
arxiv

Mejora principal: auditor de estilo multired

En vez de un “juez de naturalidad” como primer filtro, propongo un auditor determinista que mida lo que tu prompt ya exige. Es más barato, explicable y testeable.

python
# tools/comment_style_audit.py — adaptación nueva para el sistema; no es copia literal de un repo externo.
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

FORMATOS = ("reaccion", "pregunta", "observacion", "observacion_pregunta", "recomendacion")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")

def clasificar(texto: str) -> str:
    t = texto.strip()
    if "?" in t:
        return "observacion_pregunta" if len(t.split()) > 6 else "pregunta"
    if re.search(r"\b(prueba|prueba a|te recomiendo|échale un ojo|pruébate)\b", t, re.I):
        return "recomendacion"
    if len(t.split()) <= 6:
        return "reaccion"
    return "observacion"

def auditar(filas: list[dict], red: str, max_formato: float = 0.40) -> dict:
    textos = [f["texto"] for f in filas if f.get("texto")]
    formatos = Counter(clasificar(t) for t in textos)
    total = len(textos) or 1
    emojis = sum(len(EMOJI.findall(t)) for t in textos)
    arranques = Counter(" ".join(re.findall(r"[^\W_]+", t.lower())[:2]) for t in textos)
    return {
        "red": red,
        "total": len(textos),
        "formatos": dict(formatos),
        "formato_dominante": formatos.most_common(1)[0][0] if formatos else "",
        "formato_dominante_pct": round(formatos.most_common(1)[0][1] / total, 3) if formatos else 0,
        "preguntas_pct": round(formatos.get("pregunta", 0) / total + formatos.get("observacion_pregunta", 0) / total, 3),
        "emoji_total": emojis,
        "emoji_por_comentario": round(emojis / total, 3),
        "arranques_repetidos": sum(v - 1 for v in arranques.values() if v > 1),
        "valido": formatos.most_common(1)[0][1] / total <= max_formato if formatos else False,
    }

def escribir_informe(resultados: list[dict], ruta: str | Path) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(resultados[0].keys()))
        writer.writeheader()
        writer.writerows(resultados)

Reglas de aprobación iniciales:

Ningún formato por encima del 40%.

Al menos tres formatos por lote.

Máximo un emoji por comentario.

Máximo 20% del lote con emoji.

Ningún arranque de dos palabras repetido.

Ninguna respuesta sin procedencia ChatGPT, salvo authored: manual.

Plan de implementación en PR pequeñas
PR 1 — Instagram en reply_writer.py

Añadir instagram a PLAN_FILES, MAX_CHARS y MAX_WORDS.

Añadir instagram a rewrite_plan() y strip_bank().

Conectar instagram_execute.py con require_gpt().

Mantener el comportamiento de fallback: si ChatGPT no responde, la acción pasa a like.

Tests: texto válido se publica; texto de banco se convierte en like; texto sin procedencia se descarta; fallo de ChatGPT no interrumpe la ronda.

PR 2 — Perfil de estilo Instagram

Añadir estilo_por_red.instagram a la memoria.

Extender el prompt con las plantillas de formato y la política de emoji.

Prohibir el patrón de “sugerencia automática”: elogio genérico, pregunta obvia o emoji sin contenido.

Tests: lote de 10 respuestas con al menos tres formatos; ningún formato superior al 40%; máximo un emoji por respuesta.

PR 3 — comment_style_audit.py

Crear el auditor multired mostrado arriba.

Ejecutarlo después de write_replies() y antes de instagram_execute.py.

Guardar informe_estilo.csv por fecha y red.

Reutilizar check_duplicate_phrase.py y check_language_variety.py; no duplicar sus comprobaciones.

Tests: lote correcto pasa; lote con 60% de preguntas falla; lote con arranques repetidos falla; lote con dos emojis por comentario falla.

PR 4 — Corpus de resultados

Crear 00_OPERATIVO/corpus_comentarios_instagram.csv.

Campos: fecha, post_url, post_texto, autor, respuesta, formato, resultado, respuesta_recibida, nota_calidad.

Alimentar respuestas_memoria.json solo con ejemplos aprobados por David y errores reales anotados.

Tests: esquema CSV, deduplicación por post_url + autor + fecha, y trazabilidad desde respuesta publicada a resultado.

PR 5 — Juez LLM opcional

Crear tools/comment_quality_judge.py.

Rúbrica: especificidad, naturalidad, tono, utilidad y riesgo de repetición.

Interviene solo después de valid_reply() y comment_style_audit.py.

Si falla, no bloquea: degrada la acción a like.

Tests: respuestas malas conocidas reciben puntuación baja; fallo del juez devuelve None; la decisión queda registrada.

Aplicación a las demás redes
Red	Adaptación
X	Reacción o pregunta de 4–12 palabras; emoji prácticamente fuera.
Threads	Conversacional y cálido; pregunta concreta funciona bien; sin hashtags.
Facebook	Permite una frase algo más completa; mantener cercanía sin formalidad.
Pinterest	Comentario mínimo y visual; evitar preguntas salvo que el pin las invite.
Reddit	Contexto del hilo primero; nada de elogio genérico; aportar dato, matiz o pregunta sustantiva.
Bluesky	Tono comunitario; bienvenida y recomendación funcionan bien.
Mastodon	Conversación sustantiva; evitar cualquier patrón automatizado perceptible.
TikTok	Una frase muy corta, humor o gancho; mantener el límite actual de 90 caracteres y 14 palabras. 
arxiv
Fuentes

Código existente: davidpd89/ci-sandbox-tmp — tools/reply_writer.py.
arxiv

Código existente: davidpd89/ci-sandbox-tmp — tools/instagram_interact.py.
socialmediatoday

bobtech-IIT/reply-genie: generación contextual e imitación de estilo.

Noob-Developer-Real/ClarityReply: separación entre contexto y respuesta por plataforma.

vvmmm/Human_like_social_media_reply_generator_using_AI: patrón de generación contextual multiplataforma.

thenavidm/instagram-mcp: capacidades de comentarios, insights y hashtags.

AMINE1921/instacomments
: extracción y exportación de comentarios.

chat-crm-suite/chat-crm-ia: análisis de sentimiento en español con pysentimiento.

sentiment-analysis-spanish/sentiment-spanish
: clasificación de sentimiento en español.

llm-as-a-judge/Awesome-LLM-as-a-judge
: evaluación de generaciones con LLM.

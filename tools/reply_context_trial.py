"""PR #74: constructor de entradas y variante H1 para evaluación OFFLINE.

No lo importa ningún ejecutor, planificador ni trabajador. No consulta GPT, no
publica y no sustituye al evaluador ciego de la PR #90.
"""
from __future__ import annotations

from collections.abc import Mapping
import re

import reply_writer as rw

NETWORKS = frozenset(
    ("bluesky", "mastodon", "x", "threads", "facebook", "pinterest", "reddit", "reddit_micro", "tiktok")
)
CONTEXT_STATES = frozenset(("complete", "partial", "visual_unverified"))

H1_POLICY = """DECISIÓN CONVERSACIONAL PARA CADA PUBLICACIÓN
Antes de responder, determina qué pretende la persona: preguntar, celebrar,
compartir una dificultad, bromear, continuar nuestro diálogo o cerrarlo.
Responde solo si puedes aportar una reacción pertinente a un hecho observable
del post o a un turno anterior que conste explícitamente. Si no, escribe null.
No presupongas haber leído un libro ni haber visto un vídeo, una imagen,
un GIF o una portada sin evidencia textual o visual verificada.
No repitas el mensaje ajeno como una paráfrasis vacía.
Una pregunta solo encaja si nace de lo que la persona ha dicho y le resulta
razonable contestarla. Un cierre ya completo puede quedarse en null.
No repartas formatos, preguntas, interjecciones ni signos por porcentajes.
Elige la extensión que requiera la idea, dentro de los límites de la red.

"""

# Cambios mínimos adicionales para evitar instrucciones contradictorias con H1.
_REPLACEMENTS = (
    (
        "- Cortas: la mayoría por debajo de 12 palabras. Mejor poco y claro que mucho.",
        "- Brevedad proporcional: usa únicamente las palabras necesarias para responder al contenido.",
    ),
    (
        "- Cercana y con calidez. Si alguien cuenta un problema (bloqueo, cansancio, dudas), termina con ánimo y con ganas de saber cómo evoluciona («Ánimo, cuéntanos cómo va», «Seguro que sale, ya nos dirás»). Siempre motivadora, participativa, que genere confianza y apoyo.",
        "- Cercana, pero sin ánimo ni petición de novedades por defecto. Ante una dificultad, reconoce el hecho concreto sin dar consejos ni exigir que vuelva a contarlo.",
    ),
    (
        "- Cambia el gesto según el caso (bienvenida, ánimo, felicitación, recomendación, curiosidad, humor suave, agradecimiento, «me lo apunto»). Que dos respuestas no empiecen igual ni tengan la misma forma ni la misma longitud.",
        "- Escoge el gesto conversacional por el contenido, no por la necesidad de diferenciarlo de los demás.",
    ),
)


def _clean(value: object, limit: int) -> str:
    """Texto humano, no repr de dict/list/None; conserva ñ, tildes y Unicode."""
    if not isinstance(value, str):
        return ""
    collapsed = " ".join(value.split())
    return collapsed[:limit]


def _conversation(value: object) -> str:
    """Orden dado por el llamador; nunca reconstruir padres inexistentes."""
    if isinstance(value, str):
        return _clean(value, 900)
    if not isinstance(value, list):
        return ""
    parts = []
    for turn in value[-8:]:
        if isinstance(turn, str):
            item = _clean(turn, 200)
        elif isinstance(turn, Mapping):
            role = _clean(turn.get("role"), 40)
            body = _clean(turn.get("text"), 200)
            item = f"{role}: {body}" if role and body else body
        else:
            item = ""
        if item:
            parts.append(item)
    return " | ".join(parts)[:900]


def prepare_items(items: object) -> list[dict]:
    """Normaliza una muestra idéntica para baseline y H1; sin efectos remotos.

    El adaptador debe aportar datos comprobables. 'visual_verified' es una
    declaración de procedencia del curador, NO un clasificador de imágenes.
    """
    if not isinstance(items, list):
        raise ValueError("items debe ser una lista")
    seen = set()
    prepared = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("cada entrada debe ser un objeto")
        item_id = _clean(item.get("id"), 100)
        network = _clean(item.get("network"), 30).casefold()
        if not item_id or item_id in seen or network not in NETWORKS:
            raise ValueError("id duplicado/vacío o red desconocida")
        seen.add(item_id)

        raw_text = _clean(item.get("text"), 600)
        body = _clean(item.get("post_body"), 450)
        if body:
            raw_text = (_clean(raw_text, 135) + ". Texto del post: " + body)[:600]
        context = _clean(item.get("context"), 450)
        thread = _conversation(item.get("conversation_context"))
        sections = [context] if context else []
        if thread:
            sections.append("Historial disponible, en orden cronológico: " + thread)

        state = item.get("context_status", "partial")
        if not isinstance(state, str) or state not in CONTEXT_STATES:
            raise ValueError("context_status desconocido")
        if state == "partial":
            sections.append("Contexto parcial: no dar por conocidos otros turnos.")
        media = _clean(item.get("media_context"), 400)
        if item.get("visual_verified") is True and media:
            sections.append("Medio interpretado y acreditado: " + media)
        elif state == "visual_unverified" or item.get("has_media"):
            sections.append("Medio NO interpretado: no atribuirle contenido visual.")
        if not raw_text:
            sections.append("No hay texto de post verificable: responder null.")

        prepared.append({
            "id": item_id,
            "network": network,
            "author": _clean(item.get("author"), 100),
            "text": raw_text,
            "context": " ".join(sections)[:1700],
            "reply_to_us": item.get("reply_to_us") is True,
        })
    return prepared


def build_pair(items: object, *, recent=(), memoria: str = "") -> dict[str, str]:
    """Un solo render del baseline: H1 hereda exactamente posts/contexto/estilo.

    Falla expresamente si la plantilla productiva cambia. Nunca hacer un
    reemplazo silencioso ni interpretar estas cadenas como salidas del modelo.
    """
    prepared = prepare_items(items)
    if not prepared:
        raise ValueError("muestra vacía")
    baseline = rw.build_prompt(prepared, prepared[0]["network"],
                               recent=recent, memoria=memoria)
    start = baseline.find("MEZCLA DE FORMATOS (")
    end = baseline.find("CÓMO SUENA UNA RESPUESTA BUENA", start + 1)
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError("plantilla del prompt modificada; revisar H1 antes de evaluar")
    h1 = baseline[:start] + H1_POLICY + baseline[end:]
    for old, new in _REPLACEMENTS:
        if h1.count(old) != 1:
            raise RuntimeError("plantilla de prompt incompatible con H1")
        h1 = h1.replace(old, new, 1)
    return {"baseline": baseline, "H1": h1}

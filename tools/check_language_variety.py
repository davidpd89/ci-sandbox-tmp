"""Preflight anti-repetición estructural para respuestas/comentarios de Autora Demo.

No reescribe ni "humaniza" texto con sinónimos. Detecta si un candidato cae
otra vez en las mismas estructuras recientes: apertura repetida, modo
analítico encadenado, pregunta final automática, inciso con raya usado en
serie o frases típicas de asistente.

Uso:
    python tools/check_language_variety.py "texto candidato"
    python tools/check_language_variety.py --json "texto candidato"

Lee los registro_interacciones.csv de las redes y compara con textos realmente
usados. Ese historial sirve para detectar repetición; NO demuestra voz personal de
David. Es una ayuda editorial: una advertencia pide reescritura
con criterio, nunca sustituye hechos por experiencias inventadas de David.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher

ROOT = os.path.join(os.path.dirname(__file__), "..")
REGISTROS = {
    "X": "SISTEMA_DIARIO_X/registro_interacciones.csv",
    "Threads": "SISTEMA_DIARIO_THREADS/registro_interacciones.csv",
    "Bluesky": "SISTEMA_DIARIO_BLUESKY/registro_interacciones.csv",
    "Mastodon": "SISTEMA_DIARIO_MASTODON/registro_interacciones.csv",
    "Reddit": "SISTEMA_DIARIO_REDDIT/registro_interacciones.csv",
    "Instagram": "SISTEMA_DIARIO_INSTAGRAM/registro_interacciones.csv",
    "Facebook": "SISTEMA_DIARIO_FACEBOOK/registro_interacciones.csv",
}
TEXT_FIELDS = ("texto_usado", "texto", "text", "comentario", "respuesta")
CONVERSATION_TYPES = {
    "reply", "respuesta", "comment", "comentario", "quote", "cita",
}
CONFIRMED_RESULTS = {"confirmado", "publicado", "publicado y fijado"}
NOT_USED_RESULT_PREFIXES = (
    "fallo", "pendiente", "no_intentado", "saltado", "parada", "invalido",
    "incierto", "revisar", "descartado", "ya_", "already", "no_",
)

ASSISTANT_PATTERNS = (
    r"^totalmente de acuerdo(?:[.,!]|$)",
    r"^qu[eé] buena (?:reflexi[oó]n|pregunta)(?:[.,!]|$)",
    r"^muy interesante(?:[.,!]|$)",
    r"^gracias por compartir(?:[.,!]|$)",
    r"^sin duda(?:[.,!]|$)",
    r"^me encanta c[oó]mo\b",
)

ANALYTIC_OPENERS = (
    "lo interesante", "lo curioso", "lo raro", "la clave", "el problema",
    "ese es", "esa es", "esto funciona", "tiene sentido", "al final",
)
MODE_ORDER = (
    "reaccion_corta",
    "pregunta_directa",
    "humor_seco",
    "mini_desacuerdo",
    "recomendacion_concreta",
    "imagen_concreta",
    "oficio_especifico",
    "analitico",
)


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )


def _norm(text: str) -> str:
    text = " ".join((text or "").split()).casefold()
    return _strip_accents(text)


def _first_text(row: dict) -> str:
    for field in TEXT_FIELDS:
        value = (row.get(field) or "").strip()
        if value:
            return value
    return ""



def _is_conversation_kind(raw: str) -> bool:
    """Reconocer replies/comentarios incluso en variantes combinadas o externas."""
    kind = _norm(raw or "").replace("-", "_")
    if not kind:
        return False
    parts = [part.strip() for part in re.split(r"[+|/]", kind) if part.strip()]
    for part in parts:
        if part in CONVERSATION_TYPES:
            return True
        if any(part.startswith(prefix + "_") for prefix in CONVERSATION_TYPES):
            return True
    return False


def _is_conversation_row(row: dict) -> bool:
    """Usar para anti-repetición solo acciones donde realmente se escribió a otra persona.

    Se falla cerrado ante filas sin tipo: un texto sin semántica de acción no debe
    convertirse por accidente en ejemplo de historial conversacional.
    """
    return _is_conversation_kind(row.get("tipo") or "")


def _usage_state(row: dict) -> str:
    """Clasificar el resultado sin convertir estados desconocidos en confirmación."""
    if "resultado" not in row:
        return "unknown"
    result = _norm(row.get("resultado") or "")
    if not result:
        return "unknown"
    if result in CONFIRMED_RESULTS:
        return "used"
    if any(result.startswith(prefix) for prefix in NOT_USED_RESULT_PREFIXES):
        return "not_used"
    return "unknown"


def _was_actually_used(row: dict) -> bool:
    """Solo estados explícitamente confirmados/publicados cuentan como texto usado."""
    return _usage_state(row) == "used"


def _is_iso_date(value: str) -> bool:
    try:
        datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


def _select_recent_rows(rows: list[dict], limit: int) -> list[dict]:
    """No cortar a mitad de un día cuando no existe hora para ordenar redes."""
    if limit <= 0 or not rows:
        return []
    if len(rows) <= limit:
        return rows
    cutoff = rows[-limit]["date"]
    return [row for row in rows if row["date"] >= cutoff]


def load_recent(limit: int = 30, *, with_issues: bool = False):
    rows = []
    issues = []
    seq = 0
    for network, rel_path in REGISTROS.items():
        path = os.path.join(ROOT, rel_path)
        if not os.path.exists(path):
            issues.append(f"{network}: falta {rel_path}")
            continue
        try:
            with open(path, encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                fields = set(reader.fieldnames or [])
                required = {"fecha", "tipo", "resultado"}
                if not required.issubset(fields) or not any(field in fields for field in TEXT_FIELDS):
                    issues.append(
                        f"{network}: esquema inesperado en {rel_path} "
                        f"(faltan columnas requeridas o campo de texto)"
                    )
                    continue
                for row in reader:
                    if not _is_conversation_row(row):
                        continue
                    text = _first_text(row)
                    if not text:
                        continue
                    usage = _usage_state(row)
                    if usage == "not_used":
                        continue
                    if usage == "unknown":
                        issues.append(
                            f"{network}: resultado conversacional no reconocido "
                            f"«{(row.get('resultado') or '').strip()}»; fila excluida"
                        )
                        continue
                    date = (row.get("fecha") or "").strip()
                    if not _is_iso_date(date):
                        issues.append(
                            f"{network}: fecha no ISO «{date}» en fila conversacional; fila excluida"
                        )
                        continue
                    seq += 1
                    rows.append({
                        "network": network,
                        "date": date,
                        "text": text,
                        "_seq": seq,
                    })
        except (OSError, csv.Error, UnicodeError) as exc:
            issues.append(f"{network}: no se pudo leer {rel_path}: {type(exc).__name__}")
    # Solo conocemos el día, no el orden real entre redes. Ordenar por fecha
    # sirve para recencia agregada, pero NO para inferir secuencias exactas.
    rows.sort(key=lambda item: (item["date"], item["network"], item["_seq"]))
    selected = _select_recent_rows(rows, limit)
    return (selected, issues) if with_issues else selected


def opening_signature(text: str, words: int = 2) -> str:
    tokens = re.findall(r"[a-záéíóúüñ0-9]+", (text or "").casefold())
    return " ".join(tokens[:words])


def classify(text: str) -> str:
    raw = " ".join((text or "").split())
    norm = _norm(raw)
    words = re.findall(r"\w+", norm, re.UNICODE)

    if raw.lstrip().startswith("¿"):
        return "pregunta_directa"
    if re.search(r"(?:😂|😅|jaj+a|jej+e|me hizo gracia|me hace gracia)", raw, re.I):
        return "humor_seco"
    if re.search(r"^(?:prueba|te recomiendo|si quieres algo|yo empezaria|yo empezaría)\b", norm):
        return "recomendacion_concreta"
    if re.search(r"\b(?:yo diria|yo diría|no lo veo|mas que|más que|discrepo|pero ahi|pero ahí)\b", raw, re.I):
        return "mini_desacuerdo"
    # La forma discursiva manda sobre el tema. "La clave está en el personaje"
    # sigue siendo un gesto analítico aunque contenga vocabulario de oficio.
    if any(norm.startswith(_norm(prefix)) for prefix in ANALYTIC_OPENERS):
        return "analitico"
    if re.search(r"\b(?:escena|capitulo|capítulo|ritmo|borrador|punto de vista|dialogo|diálogo|worldbuilding|personaje)\b", raw, re.I):
        return "oficio_especifico"
    if re.search(r"\b(?:puerta|reloj|estanteria|estantería|mesa|margen|madriguera|mapa|mano|pasillo|libreria|librería)\b", raw, re.I):
        return "imagen_concreta"
    if len(words) <= 12:
        return "reaccion_corta"
    return "observacion"


def opening_shape(text: str) -> str:
    norm = _norm(text)
    if (text or "").lstrip().startswith("¿"):
        return "pregunta"
    if re.match(r"^(?:ese|esa|eso|este|esta|esto)\b", norm):
        return "demostrativo"
    if re.match(r"^(?:el|la|los|las|un|una|unos|unas)\b", norm):
        return "articulo"
    if re.match(r"^(?:yo|a mi|para mi)\b", norm):
        return "primera_persona"
    if re.match(r"^que\b", norm):
        return "que_subordinada"
    return "otro"


def cadence_signature(text: str) -> str:
    """Forma de fraseo: nº de frases + cubos de longitud + cierre pregunta."""
    raw = " ".join((text or "").split())
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", raw) if p.strip()]
    if not parts:
        return "0"
    buckets = []
    for part in parts:
        count = len(re.findall(r"\w+", part, re.UNICODE))
        buckets.append("S" if count <= 8 else "M" if count <= 18 else "L")
    tail = "?" if raw.endswith("?") else "."
    return f"{len(parts)}:" + "-".join(buckets) + tail




def _has_symmetric_dash_inciso(text: str) -> bool:
    """Detecta — x —, – x – y el muy repetido ' - x - '."""
    raw = text or ""
    return bool(re.search(
        r"(?:—|–|\s-\s)[^—–\n]{3,90}(?:—|–|\s-\s)",
        raw,
    ))


def _near_similarity(a: str, b: str) -> float:
    """Parecido global sin dependencias: evita reescribir casi la misma respuesta."""
    left, right = _norm(a), _norm(b)
    if min(len(left.split()), len(right.split())) < 8:
        return 0.0
    return SequenceMatcher(None, left, right, autojunk=False).ratio()



def scaffold_signature(text: str) -> str:
    """Andamios sintácticos muy reconocibles; no se penalizan una sola vez."""
    norm = _norm(text)
    if re.search(r"\bno\b[^.!?]{1,70}\bsino\b", norm):
        return "no_x_sino_y"
    if re.search(r"\bno es\b[^.!?]{1,70}[,;:]\s*(?:es|sino)\b", norm):
        return "no_es_x_es_y"
    if re.search(r"\bmas que\b[^.!?]{1,70}[,;:]", norm):
        return "mas_que_x_y"
    if _has_symmetric_dash_inciso(text):
        return "inciso_rayas"
    return ""



def _features(text: str) -> dict:
    raw = " ".join((text or "").split())
    return {
        "opening": opening_signature(raw),
        "opening_shape": opening_shape(raw),
        "cadence": cadence_signature(raw),
        "scaffold": scaffold_signature(raw),
        "mode": classify(raw),
        "question": "?" in raw or "¿" in raw,
        "ends_question": raw.rstrip().endswith("?"),
        "dash_inciso": _has_symmetric_dash_inciso(raw),
        "em_dash": "—" in raw,
        "words": len(re.findall(r"\w+", raw, re.UNICODE)),
    }


def recommend_modes(history: list[dict], n: int = 3) -> list[str]:
    # No cortar a mitad de un día: entre redes no conocemos el orden intradía.
    recent = _select_recent_rows(history, 12)
    recent_modes = Counter(classify(item["text"]) for item in recent)
    ranked = sorted(MODE_ORDER, key=lambda mode: (recent_modes[mode], MODE_ORDER.index(mode)))
    return ranked[:n]



VARIATION_PLANS = {
    "reaccion_corta": "1 frase breve; sin explicación añadida ni pregunta final.",
    "pregunta_directa": "Abrir con una pregunta concreta y dejar que ella haga el trabajo.",
    "humor_seco": "Una observación con ironía ligera; sin explicar después el chiste.",
    "mini_desacuerdo": "Matiz o desacuerdo concreto + una razón; sin validar primero al autor.",
    "recomendacion_concreta": "Una recomendación concreta con un porqué; sin convertirla en lista.",
    "imagen_concreta": "Anclar la respuesta en un objeto, gesto o imagen material del post.",
    "oficio_especifico": "Señalar un detalle de oficio (ritmo, escena, diálogo, POV) con un ejemplo.",
    "analitico": "Analizar una sola idea; cortar antes del resumen y no cerrar por sistema con pregunta.",
}


def variation_plans(history: list[dict], n: int = 3) -> list[str]:
    return [VARIATION_PLANS[mode] for mode in recommend_modes(history, n=n)]



def analyze(candidate: str, history: list[dict] | None = None) -> dict:
    candidate = (candidate or "").strip()
    history = list(load_recent() if history is None else history)
    warnings = []
    features = _features(candidate)

    if not candidate:
        return {
            "ok": False,
            "mode": "vacio",
            "warnings": ["texto vacío"],
            "recommended_modes": recommend_modes(history),
            "variation_plans": variation_plans(history),
        }

    norm = _norm(candidate)
    for pattern in ASSISTANT_PATTERNS:
        if re.search(pattern, norm, re.I):
            warnings.append("frase de asistente/validación genérica")
            break

    # No existe un orden fiable entre redes dentro del mismo día. Mantener entero
    # el día de corte evita que una red quede sobrerrepresentada por orden alfabético.
    recent = _select_recent_rows(history, 12)
    recent_features = [_features(item["text"]) for item in recent]

    if recent:
        closest = max((_near_similarity(candidate, item["text"]), item["text"])
                      for item in recent)
        if closest[0] >= 0.80:
            warnings.append(
                f"texto demasiado parecido a una respuesta reciente "
                f"({closest[0]:.0%} de similitud aproximada)"
            )

    opening = features["opening"]
    if opening:
        opening_count = sum(f["opening"] == opening for f in recent_features)
        if opening_count >= 2:
            warnings.append(
                f"apertura repetida «{opening}» ({opening_count} veces en las últimas {len(recent)})"
            )

    # No sabemos cuál fue "la respuesta anterior" entre redes en un mismo
    # día. Medimos saturación agregada, no secuencias inventadas.
    mode_count = sum(f["mode"] == features["mode"] for f in recent_features)
    if features["mode"] == "analitico" and mode_count >= 3:
        warnings.append("modo analítico saturado en la muestra reciente")
    if len(recent_features) >= 6 and mode_count / len(recent_features) >= 0.40:
        warnings.append(
            f"modo «{features['mode']}» ocupa ≥40% de la muestra reciente"
        )
    shape = features["opening_shape"]
    shape_count = sum(f["opening_shape"] == shape for f in recent_features)
    if shape != "otro" and len(recent_features) >= 6 and shape_count / len(recent_features) >= 0.50:
        warnings.append(
            f"forma de apertura «{shape}» demasiado dominante en la muestra reciente"
        )

    cadence = features["cadence"]
    cadence_count = sum(f["cadence"] == cadence for f in recent_features)
    if cadence.startswith(("2:", "3:", "4:", "5:")) and cadence_count >= 2:
        warnings.append(
            f"cadencia «{cadence}» repetida {cadence_count} veces recientemente"
        )

    scaffold = features["scaffold"]
    if scaffold:
        scaffold_count = sum(f["scaffold"] == scaffold for f in recent_features)
        if scaffold_count >= 2:
            warnings.append(
                f"andamio «{scaffold}» repetido {scaffold_count} veces recientemente"
            )

    if features["dash_inciso"]:
        warnings.append("inciso simétrico «— x —» / «- x -»: variar estructura")
    elif features["em_dash"] and recent_features:
        dash_count = sum(f["em_dash"] for f in recent_features)
        if dash_count >= 2 and dash_count / len(recent_features) >= 0.30:
            warnings.append("raya larga demasiado frecuente en la muestra reciente")

    if features["ends_question"] and len(recent_features) >= 4:
        question_count = sum(f["ends_question"] for f in recent_features)
        if question_count >= 3 and question_count / len(recent_features) >= 0.50:
            warnings.append("pregunta final demasiado frecuente: no cerrar por inercia")

    if features["words"] > 55 and len(recent_features) >= 4:
        long_count = sum(f["words"] > 55 for f in recent_features)
        if long_count >= 2 and long_count / len(recent_features) >= 0.35:
            warnings.append("respuesta larga dentro de una muestra ya cargada de textos largos")

    return {
        "ok": not warnings,
        "mode": features["mode"],
        "opening": features["opening"],
        "warnings": warnings,
        "recommended_modes": recommend_modes(history),
        "variation_plans": variation_plans(history),
        "history_size": len(history),
    }


def _print_human(result: dict) -> None:
    status = "OK" if result["ok"] else "REVISAR"
    print(f"{status}: modo={result['mode']}")
    for warning in result["warnings"]:
        print(f"- {warning}")
    modes = ", ".join(result["recommended_modes"])
    print(f"Próximos registros infrautilizados: {modes}")
    for plan in result.get("variation_plans", []):
        print(f"  · {plan}")
    print(
        "No inventar una experiencia personal para forzar variedad; "
        "si no hay un ángulo real, un like/silencio también es una opción."
    )


def main(argv=None) -> int:
    import sys
    # Windows usa cp1252 por defecto y los avisos llevan caracteres como '>='/comillas: sin
    # esto el script moria al imprimir (visto el 03/10), asi que nadie lo usaba.
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--history", type=int, default=30)
    parser.add_argument(
        "--strict", action="store_true",
        help="devuelve código 2 también ante avisos editoriales; por defecto solo informa",
    )
    args = parser.parse_args(argv)

    history, load_issues = load_recent(limit=max(args.history, 1), with_issues=True)
    result = analyze(args.text, history)
    if load_issues:
        result["warnings"].extend(load_issues)
        result["ok"] = False
        result["data_issues"] = load_issues
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)
    if load_issues or not args.text.strip():
        return 2
    return 2 if args.strict and not result["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

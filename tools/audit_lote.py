from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path


def load_index(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            if isinstance(record, dict):
                rows.append(record)
        except json.JSONDecodeError:
            rows.append({"_error": f"invalid json line {line_no}", "raw": line})
    return rows


def field_values(text: str, field: str) -> list[str]:
    pattern = re.compile(rf"^\s*{re.escape(field)}\s*:\s*(.+?)\s*$", re.MULTILINE)
    return [m.group(1).strip().strip("'\"") for m in pattern.finditer(text) if m.group(1).strip()]


def repeated(values: list[str]) -> dict[str, int]:
    return {k: v for k, v in Counter(values).items() if v > 1 and k.lower() not in {"null", "none", "[]"}}


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s?]", "", text)
    return re.sub(r"\s+", " ", text)


def cta_family(cta: str) -> str:
    low = normalize_text(cta)
    if not low or low in {"null", "none"}:
        return "sin_cta"
    if "te leo" in low or "comenta" in low or "comentarios" in low:
        return "comentario_generico"
    if low.startswith("que ") or low.startswith("que?") or low.startswith("cual ") or low.startswith("cual?"):
        return "pregunta_directa"
    if "te ha pasado" in low or "te paso" in low:
        return "experiencia_personal"
    if "guarda" in low or "guardar" in low:
        return "guardado"
    if "comparte" in low:
        return "compartido"
    if "dime" in low:
        return "dime_respuesta"
    return re.sub(r"\b\w{1,3}\b", "", low).strip()[:48] or low[:48]


def parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    return None


def recent_counts(index: list[dict], field: str, days: int) -> dict[str, int]:
    cutoff = date.today() - timedelta(days=days)
    values: list[str] = []
    for row in index:
        when = parse_date(row.get("fecha_publicacion") or row.get("fecha_creacion"))
        if not when or when < cutoff:
            continue
        value = row.get(field)
        if isinstance(value, str) and value:
            values.append(value)
    return dict(Counter(values))


def high_overlap(a: str, b: str) -> bool:
    words_a = {w for w in re.findall(r"\w+", normalize_text(a)) if len(w) > 3}
    words_b = {w for w in re.findall(r"\w+", normalize_text(b)) if len(w) > 3}
    if not words_a or not words_b:
        return False
    return len(words_a & words_b) / max(1, min(len(words_a), len(words_b))) >= 0.7


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a RRSS batch/lote")
    parser.add_argument("lote", help="markdown/yaml/json file with proposed batch")
    parser.add_argument("--index", default="content_index.jsonl")
    parser.add_argument("--assets", default="assets_registry.csv")
    args = parser.parse_args()

    lote_path = Path(args.lote)
    text = lote_path.read_text(encoding="utf-8", errors="replace")
    index = load_index(Path(args.index))
    warnings: list[str] = []
    blockers: list[str] = []

    if not index:
        warnings.append("content_index missing or empty; 7d/30d repetition cannot be trusted")
    if not Path(args.assets).exists() or Path(args.assets).stat().st_size == 0:
        warnings.append("assets_registry missing or empty; asset repetition cannot be trusted")

    temas = field_values(text, "tema")
    formatos = field_values(text, "formato")
    ctas = field_values(text, "cta")
    cta_families = [cta_family(cta) for cta in ctas]
    captions = field_values(text, "caption_base") + field_values(text, "caption")
    hooks = field_values(text, "gancho_1") + field_values(text, "hook")
    categories = field_values(text, "categoria_70_20_10")

    repeated_topics = repeated(temas)
    repeated_formats = repeated(formatos)
    repeated_ctas = repeated(ctas)
    repeated_cta_families = repeated(cta_families)
    if repeated_topics:
        warnings.append(f"repeated topics: {repeated_topics}")
    if len(formatos) >= 4 and repeated_formats:
        warnings.append(f"repeated formats: {repeated_formats}")
    if repeated_ctas:
        blockers.append(f"repeated CTA exact text: {repeated_ctas}")
    if repeated_cta_families and len(cta_families) >= 3:
        blockers.append(f"repeated CTA family: {repeated_cta_families}")

    category_counts = Counter(categories)
    total_categories = sum(category_counts.values())
    if total_categories >= 4:
        for category, count in category_counts.items():
            if count / total_categories > 0.7:
                blockers.append(f"70/20/10 imbalance: {category} is {count}/{total_categories}")

    for days in (7, 30):
        topic_counts = recent_counts(index, "tema", days)
        format_counts = recent_counts(index, "formato", days)
        topic_hits = {topic: topic_counts[topic] for topic in temas if topic in topic_counts}
        format_hits = {fmt: format_counts[fmt] for fmt in formatos if fmt in format_counts}
        if topic_hits:
            warnings.append(f"topics already used in last {days}d: {topic_hits}")
        if format_hits and days == 7:
            warnings.append(f"formats already used in last {days}d: {format_hits}")

    similar_hooks = []
    for idx, hook in enumerate(hooks):
        for other in hooks[idx + 1:]:
            if high_overlap(hook, other):
                similar_hooks.append((hook, other))

    if similar_hooks:
        blockers.append(f"similar hooks: {similar_hooks[:3]}")
    if len(captions) != len(set(captions)):
        blockers.append("duplicated captions")
    if "lista_para_programar" in text and ("QA_RESULT:" not in text or "status: pass" not in text):
        blockers.append("lista_para_programar without QA_RESULT: pass")
    if any("QA_RESULT:" in block and "status: pass" not in block for block in text.split("PIEZA:")[1:]):
        blockers.append("piece with QA_RESULT not pass")
    if any(cliche in text.lower() for cliche in ["no es solo", "descubre", "adentrate", "una historia que"]):
        blockers.append("AI/copywriting cliche detected")
    if "reel" in text.lower() and "MONTAGE_PRESET:" not in text:
        blockers.append("reel/video without MONTAGE_PRESET")

    status = "fail" if blockers else "pass"
    print("LOTE_AUDIT_RESULT:")
    print(f"  status: {status}")
    print("  rango_fechas: null")
    print(f"  piezas_revisadas: {text.count('PIEZA:')}")
    print(f"  equilibrio_70_20_10: {dict(category_counts)}")
    print(f"  repeticion_tema: {repeated_topics}")
    print(f"  repeticion_formato: {repeated_formats}")
    print("  repeticion_visual: {}")
    print(f"  repeticion_cta: {repeated_ctas}")
    print(f"  familias_cta_repetidas: {repeated_cta_families}")
    print(f"  captions_similares: {len(captions) != len(set(captions))}")
    print(f"  hooks_similares: {similar_hooks[:3]}")
    print(f"  saturacion_detectada: {warnings}")
    print("  metricool_ok: null")
    print(f"  bloqueantes: {blockers}")
    print(f"  avisos: {warnings}")
    print("  correcciones_requeridas: []")
    print(f"  hooks_revisados: {len(hooks)}")
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())

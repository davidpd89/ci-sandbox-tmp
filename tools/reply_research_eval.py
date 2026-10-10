"""#90: evaluación OFFLINE de experimentos de respuestas, sin publicar ni consultar GPT.

Uso: python tools/reply_research_eval.py casos.json
Entrada: {"cases": [{"case_id":"c1","network":"x","post":"...","variant":"baseline","reply":null|"texto"}]}
Salida: solo métricas agregadas JSON; NO imprime publicaciones, respuestas ni autores.
Los datos deben ser sintéticos, propios o autorizados. No inferir «naturalidad» de estos proxies.
"""
from __future__ import annotations

import collections
import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path

import reply_corpus_lint

NETWORKS = frozenset({
    "bluesky", "mastodon", "x", "threads", "facebook", "pinterest",
    "reddit", "tiktok", "reddit_micro",
})
TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def _words(text: str) -> list[str]:
    return [_fold(w) for w in TOKEN.findall(text)]


def validate_cases(cases: object) -> list[dict]:
    """Valida formato sin suponer licencias ni publicar texto ajeno."""
    if not isinstance(cases, list):
        raise ValueError("'cases' debe ser una lista")
    seen: set[tuple[str, str, str]] = set()
    source_by_case: dict[str, str] = {}
    valid = []
    for i, item in enumerate(cases):
        if not isinstance(item, dict):
            raise ValueError(f"caso {i}: debe ser objeto")
        cid = item.get("case_id")
        net = item.get("network")
        post = item.get("post")
        variant = item.get("variant", "baseline")
        if "reply" not in item:
            raise ValueError(f"caso {i}: falta reply; usar null explícito para abstención")
        reply = item["reply"]
        sample_id = item.get("sample_id", "1")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise ValueError(f"caso {i}: sample_id no válido")
        if not isinstance(cid, str) or not cid.strip():
            raise ValueError(f"caso {i}: falta case_id")
        if not isinstance(net, str) or net not in NETWORKS:
            raise ValueError(f"caso {i}: red no admitida")
        if not isinstance(post, str) or not post.strip():
            raise ValueError(f"caso {i}: falta texto del post")
        if not isinstance(variant, str) or not variant.strip():
            raise ValueError(f"caso {i}: variante no válida")
        if reply is not None and (not isinstance(reply, str) or not reply.strip()):
            raise ValueError(f"caso {i}: reply debe ser texto no vacío o null")
        key = (variant, cid, sample_id)
        if key in seen:
            raise ValueError(f"caso {i}: case_id/sample_id repetidos en una variante")
        seen.add(key)
        # En un A/B, la entrada debe ser idéntica entre variantes: no vale comparar
        # respuestas a posts/redes/hilos diferentes. No guardamos ni emitimos el texto.
        # Conservador: todo campo salvo los TRES de resultado/experimento debe
        # ser igual entre variantes. Así ni "author", "post_id" ni futuras
        # ampliaciones de contexto podrán cambiar en silencio.
        source = json.dumps({
            name: value for name, value in item.items()
            if name not in {"variant", "reply", "sample_id"}
        }, ensure_ascii=False, sort_keys=True)
        if cid in source_by_case and source_by_case[cid] != source:
            raise ValueError(f"caso {i}: mismo case_id con entradas diferentes")
        source_by_case[cid] = source
        valid.append(item)
    return valid


def _group_metrics(cases: list[dict]) -> dict:
    replies = [r["reply"].strip() for r in cases if isinstance(r.get("reply"), str)]
    answered = len(replies)
    n = len(cases)
    lengths = [len(_words(r)) for r in replies]
    folded = [_fold(" ".join(r.split())) for r in replies]
    repeated = sum(c - 1 for c in collections.Counter(folded).values() if c > 1)
    openings = collections.Counter(" ".join(_words(t)[:2]) for t in replies)
    corpus, warnings = reply_corpus_lint.lint(replies)
    # El lint preexistente devuelve la primera palabra más frecuente y puede
    # citarla en los avisos. La herramienta de investigación no expone texto
    # de terceros ni fragmentos de las respuestas en sus informes JSON.
    corpus = {key: value for key, value in corpus.items() if key != "opening_top"}
    corpus["opening_top_count"] = openings.most_common(1)[0][1] if openings else 0
    return {
        "cases": n, "answers": answered, "null": n - answered,
        "answer_share": round(answered / n, 3) if n else None,
        "median_words": statistics.median(lengths) if lengths else None,
        "questions_share": round(sum("?" in t or "¿" in t for t in replies) / answered, 3) if answered else None,
        "exact_repeated_extra": repeated,
        "opening_2word_top_share": round(max(openings.values()) / answered, 3) if answered else None,
        "corpus_lint": corpus, "corpus_warning_count": len(warnings),
    }


def summarize(cases: object) -> dict:
    rows = validate_cases(cases)
    groups: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    by_variant: dict[str, list[dict]] = collections.defaultdict(list)
    by_variant_keys: dict[str, set[tuple[str, str]]] = collections.defaultdict(set)
    for row in rows:
        variant = row.get("variant", "baseline")
        groups[(variant, row["network"])].append(row)
        by_variant[variant].append(row)
        by_variant_keys[variant].add((row["case_id"], row.get("sample_id", "1")))
    sets = list(by_variant_keys.values())
    common = set.intersection(*sets) if sets else set()
    paired = {
        "variants": sorted(by_variant_keys),
        "matched_case_samples": len(common) if len(sets) > 1 else 0,
        "all_variants_fully_matched": len(sets) > 1 and all(v == common for v in sets),
        "unpaired_case_samples_by_variant": {
            v: len(keys - common) if len(sets) > 1 else len(keys)
            for v, keys in sorted(by_variant_keys.items())
        },
    }
    return {
        "schema_version": 2,
        "pairing": paired,
        "warning": "Métricas descriptivas, NO miden pertinencia ni naturalidad. Comparar variantes solo con all_variants_fully_matched=true y revisión humana ciega.",
        "all": _group_metrics(rows),
        "variants": {v: _group_metrics(group) for v, group in sorted(by_variant.items())},
        "by_variant_network": {
            f"{variant}/{net}": _group_metrics(group)
            for (variant, net), group in sorted(groups.items())
        },
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("Uso: python tools/reply_research_eval.py casos.json", file=sys.stderr)
        return 2
    try:
        payload = json.loads(Path(argv[0]).read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("la raíz debe ser objeto con clave cases")
        result = summarize(payload.get("cases"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error en corpus: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

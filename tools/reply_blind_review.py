"""#90: comparación humana ciega A/B de respuestas guardadas, sin consultar ni publicar.

La hoja contiene texto de terceros: utilizar sólo material sintético, propio o autorizado.
La clave revela las variantes: NO compartirla con evaluadores ni subirla a GitHub.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import random
import unicodedata
from pathlib import Path

from reply_research_eval import validate_cases

CATEGORIES = ("pertinencia", "naturalidad", "concrecion", "no_inventa", "tono")
DISPLAY = ("review_id", "network", "interaction_type", "length_bucket", "context_status", "post", "thread",
           "media_context", "reply_left", "reply_right", "left_abstained", "right_abstained")
RATINGS = tuple(f"{category}_{side}" for side in ("left", "right") for category in CATEGORIES)
COLUMNS = DISPLAY + ("should_reply", "preference") + RATINGS + ("notes",)
PERMISSIONS = frozenset({"synthetic", "owned", "authorized"})
CONTEXT_STATES = frozenset({"complete", "partial", "visual_unverified"})
INTERACTIONS = frozenset({"new_post", "reply_to_us", "question", "humor", "feedback",
                           "sensitive", "visual", "other"})
PREFERENCES = frozenset({"left", "right", "tie", "neither"})


def _digest(row):
    data = {key: row[key] for key in DISPLAY}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _excel_safe(value):
    """Neutraliza fórmulas de hoja de cálculo en publicaciones de terceros."""
    if value and (value[0] in "\t\r\n" or
                  unicodedata.normalize("NFKC", value.lstrip()).startswith(("=", "+", "-", "@"))):
        return "'" + value
    return value


def _safe_value(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)


def _length_bucket(post):
    """Tramos descriptivos para auditar cobertura; no son objetivos de longitud."""
    count = len(post.split())
    return "short" if count <= 12 else ("medium" if count <= 40 else "long")


def prepare(cases, seed=90):
    """(filas ciegas, clave privada). No requiere navegador ni API."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed debe ser entero")
    rows = validate_cases(cases)
    variants = sorted({row.get("variant", "baseline") for row in rows})
    if len(variants) != 2:
        raise ValueError("el ensayo exige exactamente dos variantes")
    grouped = collections.defaultdict(dict)
    for row in rows:
        if row.get("source_permission") not in PERMISSIONS:
            raise ValueError("source_permission debe ser synthetic, owned o authorized")
        if row.get("context_status") not in CONTEXT_STATES:
            raise ValueError("context_status debe ser complete, partial o visual_unverified")
        if row.get("interaction_type") not in INTERACTIONS:
            raise ValueError("interaction_type no reconocido")
        if row.get("context_status") == "visual_unverified" and row.get("visual_verified") is True:
            raise ValueError("contradicción de verificación visual")
        if row.get("interaction_type") == "visual" and row.get("visual_verified") is not True and row.get("context_status") == "complete":
            raise ValueError("un post visual no verificado no tiene contexto complete")
        key = row["case_id"], row.get("sample_id", "1")
        grouped[key][row.get("variant", "baseline")] = row
    if not grouped or any(set(pair) != set(variants) for pair in grouped.values()):
        raise ValueError("se requieren los mismos case_id/sample_id en ambas variantes")
    keys = sorted(grouped)
    rng = random.Random(seed)
    rng.shuffle(keys)
    output, secret = [], {}
    for idx, pair_key in enumerate(keys):
        pair = grouped[pair_key]
        left, right = (variants if (idx + seed) % 2 == 0 else variants[::-1])
        base = pair[left]
        review_id = f"r{idx + 1:04d}"
        row = {
            "review_id": review_id,
            "network": base["network"],
            "interaction_type": base["interaction_type"],
            "length_bucket": _length_bucket(base["post"]),
            "context_status": base["context_status"],
            "post": _excel_safe(base["post"]),
            "thread": _excel_safe(_safe_value(base.get("thread", []))),
            "media_context": _excel_safe(_safe_value(base.get("media_context"))),
            "reply_left": _excel_safe(pair[left]["reply"] or ""),
            "reply_right": _excel_safe(pair[right]["reply"] or ""),
            "left_abstained": "yes" if pair[left]["reply"] is None else "no",
            "right_abstained": "yes" if pair[right]["reply"] is None else "no",
        }
        row.update({col: "" for col in COLUMNS if col not in row})
        secret[review_id] = {"case_id": pair_key[0], "sample_id": pair_key[1],
                             "left": left, "right": right, "digest": _digest(row)}
        output.append(row)
    return output, {"schema_version": 1, "variants": variants, "seed": seed, "rows": secret}


def grade(rows, key):
    """Informe de cobertura y juicios: nunca devuelve textos o identificadores de terceros."""
    if key.get("schema_version") != 1 or len(key.get("variants", [])) != 2:
        raise ValueError("clave ciega incompatible")
    expected = key.get("rows")
    if not isinstance(expected, dict) or not expected:
        raise ValueError("clave vacía")
    observed = set()
    totals = collections.Counter()
    wins = collections.Counter()
    scores = collections.defaultdict(list)
    by_network = collections.Counter()
    by_type = collections.Counter()
    by_length = collections.Counter()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(COLUMNS):
            raise ValueError("cabecera o fila incompleta, duplicada o con columnas extra")
        rid = row["review_id"]
        if rid not in expected or rid in observed:
            raise ValueError("identificador desconocido o duplicado")
        observed.add(rid)
        meta = expected[rid]
        if _digest(row) != meta["digest"]:
            raise ValueError("contenido del ensayo alterado: no se puede puntuar")
        if row["should_reply"] not in {"yes", "no", "uncertain"}:
            raise ValueError("should_reply: yes/no/uncertain obligatorio")
        if row["preference"] not in PREFERENCES:
            raise ValueError("preference: left/right/tie/neither obligatorio")
        if (row["reply_left"] == row["reply_right"] and
                row["left_abstained"] == row["right_abstained"] and
                row["preference"] in {"left", "right"}):
            raise ValueError("preferencia imposible: respuestas idénticas")
        for side in ("left", "right"):
            null = row[f"{side}_abstained"] == "yes"
            for category in CATEGORIES:
                val = row[f"{category}_{side}"]
                if (null and val != "") or (not null and val not in {"0", "1", "2"}):
                    raise ValueError("rúbrica: 0/1/2 por respuesta; vacío para abstención")
        totals["reviewed"] += 1
        by_network[row["network"]] += 1
        by_type[row["interaction_type"]] += 1
        by_length[row["length_bucket"]] += 1
        if row["context_status"] != "complete":
            totals["excluded_incomplete_context"] += 1
            continue
        totals["complete_context"] += 1
        pref = row["preference"]
        if pref in ("left", "right"):
            wins[meta[pref]] += 1
        else:
            totals[f"preference_{pref}"] += 1
        for side in ("left", "right"):
            variant = meta[side]
            null = row[f"{side}_abstained"] == "yes"
            if row["should_reply"] != "uncertain":
                correctness = "correct" if null == (row["should_reply"] == "no") else "incorrect"
                totals[f"decision_{variant}_{correctness}"] += 1
            if not null:
                for category in CATEGORIES:
                    scores[(variant, category)].append(int(row[f"{category}_{side}"]))
    if observed != set(expected):
        raise ValueError("faltan filas del ensayo; no emitir comparación parcial")
    return {
        "schema_version": 1,
        "warning": "Juicios humanos, no prueba de causalidad ni eficacia en producción. Sólo contexto completo cuenta para resultados.",
        "coverage": {"reviewed": totals["reviewed"], "complete_context": totals["complete_context"],
                     "excluded_incomplete_context": totals["excluded_incomplete_context"],
                     "by_network": dict(sorted(by_network.items())),
                     "by_interaction_type": dict(sorted(by_type.items())),
                     "by_length_bucket": dict(sorted(by_length.items()))},
        "preference": {"wins": {v: wins[v] for v in key["variants"]},
                       "tie": totals["preference_tie"], "neither": totals["preference_neither"]},
        "decision": {v: {"correct": totals[f"decision_{v}_correct"],
                         "incorrect": totals[f"decision_{v}_incorrect"]} for v in key["variants"]},
        "rubric": {v: {cat: {"count": len(scores[(v, cat)]),
                              "mean": round(sum(scores[(v, cat)]) / len(scores[(v, cat)]), 3)
                              if scores[(v, cat)] else None}
                       for cat in CATEGORIES} for v in key["variants"]},
    }


def _csv(rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\r\n", quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(rows)
    return "\ufeff" + buffer.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description="A/B ciego estrictamente offline")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_cmd = commands.add_parser("prepare")
    prepare_cmd.add_argument("input")
    prepare_cmd.add_argument("--sheet", required=True)
    prepare_cmd.add_argument("--key", required=True)
    prepare_cmd.add_argument("--seed", type=int, default=90)
    score_cmd = commands.add_parser("score")
    score_cmd.add_argument("sheet")
    score_cmd.add_argument("--key", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            if Path(args.sheet).resolve() == Path(args.key).resolve():
                raise ValueError("hoja y clave requieren rutas distintas")
            if Path(args.sheet).exists() or Path(args.key).exists():
                raise ValueError("no se sobrescriben archivos existentes")
            payload = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict):
                raise ValueError("la raíz debe ser objeto con 'cases'")
            sheet, key = prepare(payload.get("cases"), seed=args.seed)
            # Ambos son privados. Las rutas deben existir; nunca usar git add -A.
            with Path(args.key).open("x", encoding="utf-8") as f:
                f.write(json.dumps(key, ensure_ascii=False, indent=2))
            with Path(args.sheet).open("x", encoding="utf-8", newline="") as f:
                f.write(_csv(sheet))
            print(json.dumps({"prepared": len(sheet), "variants": len(key["variants"]),
                              "privacy": "HOJA Y CLAVE PRIVADAS; no subir a GitHub"}, ensure_ascii=False))
        else:
            key = json.loads(Path(args.key).read_text(encoding="utf-8-sig"))
            with Path(args.sheet).open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames != list(COLUMNS):
                    raise ValueError("cabecera CSV inesperada, duplicada o desordenada")
                rows = list(reader)
            print(json.dumps(grade(rows, key), ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError, csv.Error) as exc:
        parser.exit(2, f"Error de formato/archivo: {type(exc).__name__}. No se imprime contenido sensible.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

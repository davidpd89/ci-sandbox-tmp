"""Benchmark de avisos en pares sintéticos; no evalúa naturalidad."""
import argparse
import json
from pathlib import Path

from spanish_voice_blind import pack, score
from spanish_voice_quality import audit


def compare(pairs):
    pack(pairs, seed="validation-only")
    by_network = {}
    total = {"before": 0, "after": 0}
    for pair in pairs:
        counts = {}
        for variant in ("before", "after"):
            issues = audit(pair[variant], network=pair["network"], check_accents=False)
            counts[variant] = sum(issues["counts"].values())
            total[variant] += counts[variant]
        net = pair["network"]
        group = by_network.setdefault(net, {"before": 0, "after": 0, "cases": 0})
        group["cases"] += 1
        for variant in ("before", "after"):
            group[variant] += counts[variant]
    return {
        "synthetic_pairs": len(pairs), "rule_findings": total,
        "difference": total["before"] - total["after"],
        "by_network": dict(sorted(by_network.items())),
        "warning": "Solo avisos de reglas en corpus sintético; NO demuestra calidad humana.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pairs", type=Path)
    parser.add_argument("--blind-prefix", type=Path)
    parser.add_argument("--blind-key-dir", type=Path,
                        help="directorio PRIVADO diferente al de revisión")
    parser.add_argument("--seed", default="independent-reviewer")
    parser.add_argument("--score-review", type=Path)
    parser.add_argument("--score-key", type=Path)
    args = parser.parse_args()
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    if bool(args.blind_prefix) != bool(args.blind_key_dir):
        parser.error("--blind-prefix y --blind-key-dir son obligatorios juntos")
    if args.blind_prefix:
        review_path = args.blind_prefix.with_suffix(".review.json").resolve()
        key_dir = args.blind_key_dir.resolve()
        if key_dir == review_path.parent:
            parser.error("la clave debe guardarse en un directorio separado")
        if not review_path.parent.is_dir() or not key_dir.is_dir():
            parser.error("ambos directorios deben existir")
        root = Path(__file__).resolve().parents[1]
        if review_path.is_relative_to(root) or key_dir.is_relative_to(root):
            parser.error("no guardar revisiones ni claves dentro del repositorio")
        key_path = key_dir / (args.blind_prefix.stem + ".key.json")
        if review_path.exists() or key_path.exists():
            parser.error("no sobrescribir revisiones o claves existentes")
        review, key = pack(pairs, seed=args.seed)
        with review_path.open("x", encoding="utf-8") as writer:
            json.dump(review, writer, ensure_ascii=False, indent=2)
        with key_path.open("x", encoding="utf-8") as writer:
            json.dump(key, writer, ensure_ascii=False, indent=2)
    output = {"offline": compare(pairs)}
    if args.score_review and args.score_key:
        output["human"] = score(
            json.loads(args.score_review.read_text(encoding="utf-8")),
            json.loads(args.score_key.read_text(encoding="utf-8")),
        )
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

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
        by_network[pair["network"]] = counts
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
    parser.add_argument("--seed", default="independent-reviewer")
    parser.add_argument("--score-review", type=Path)
    parser.add_argument("--score-key", type=Path)
    args = parser.parse_args()
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    if args.blind_prefix:
        review, key = pack(pairs, seed=args.seed)
        args.blind_prefix.with_suffix(".review.json").write_text(
            json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
        args.blind_prefix.with_suffix(".key.json").write_text(
            json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    output = {"offline": compare(pairs)}
    if args.score_review and args.score_key:
        output["human"] = score(
            json.loads(args.score_review.read_text(encoding="utf-8")),
            json.loads(args.score_key.read_text(encoding="utf-8")),
        )
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

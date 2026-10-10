"""Detect exact, nontrivial function-body copies across network-specific modules.

Read-only AST parsing. The report contains metadata, never source or literals.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

NETWORKS = (
    "bluesky", "facebook", "instagram", "mastodon", "pinterest",
    "reddit", "threads", "tiktok", "x",
)
SUFFIXES = ("_build_plan.py", "_execute.py", "_interact.py", "_scan.py")


def _network(path: Path) -> str | None:
    return next((name for name in NETWORKS if path.name.startswith(name + "_")), None)


def _canonical_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Retain the existing baseline's conservative size threshold."""
    body = list(node.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body.pop(0)
    if len(body) < 3:
        return None
    dumped = ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False)
    if dumped.count("(") < 12:
        return None
    return dumped

def _qualified_functions(tree: ast.AST):
    """Yield functions with lexical scope, never just the bare method name.

    A class replacement cannot spend an allowance reserved for a method of
    another class. Top-level identities remain backward compatible.
    """
    def walk(node: ast.AST, scope: tuple[str, ...]):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node, ".".join((*scope, node.name))
            scope = (*scope, node.name)
        elif isinstance(node, ast.ClassDef):
            scope = (*scope, node.name)
        for child in ast.iter_child_nodes(node):
            yield from walk(child, scope)

    yield from walk(tree, ())


def _eligible_paths(tools_dir: Path) -> list[tuple[Path, str]]:
    if not tools_dir.is_dir():
        raise ValueError(f"Tools directory does not exist: {tools_dir}")
    paths = []
    for path in sorted(tools_dir.glob("*.py")):
        network = _network(path)
        if network is not None and path.name.endswith(SUFFIXES):
            paths.append((path, network))
    if not paths:
        raise ValueError(f"No network source modules found in: {tools_dir}")
    return paths


def collect(tools_dir: str | Path) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for path, network in _eligible_paths(Path(tools_dir)):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        except (SyntaxError, UnicodeError) as exc:
            # SyntaxError normally prints the source line into tracebacks.
            raise ValueError(
                f"Unable to parse {path.name} at line {getattr(exc, 'lineno', '?')}"
            ) from None
        for node, qualname in _qualified_functions(tree):
            body = _canonical_body(node)
            if body is None:
                continue
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
            grouped.setdefault(digest, []).append({
                "network": network,
                "file": path.name,
                "function": qualname,
                "line": node.lineno,
            })
    result = []
    for digest, occurrences in grouped.items():
        networks = sorted({item["network"] for item in occurrences})
        if len(networks) < 2:
            continue
        result.append({
            "fingerprint": digest,
            "networks": networks,
            "occurrences": sorted(
                occurrences,
                key=lambda item: (
                    item["network"], item["file"], item["function"], item["line"]
                ),
            ),
        })
    return sorted(result, key=lambda item: item["fingerprint"])


def _identity(occurrence: dict) -> tuple[str, str, str]:
    """Stable across line shifts, strict across network/file/function changes."""
    return occurrence["network"], occurrence["file"], occurrence["function"]

def _validate_baseline(baseline: list[dict]) -> None:
    """Refuse malformed allowances rather than silently skipping bad entries."""
    if not isinstance(baseline, list):
        raise ValueError("Malformed architecture baseline")
    fingerprints = set()
    for item in baseline:
        if not isinstance(item, dict):
            raise ValueError("Malformed architecture baseline")
        fingerprint = item.get("fingerprint")
        if not (isinstance(fingerprint, str) and len(fingerprint) == 16
                and all(char in "0123456789abcdef" for char in fingerprint)):
            raise ValueError("Malformed architecture baseline fingerprint")
        if fingerprint in fingerprints:
            raise ValueError("Duplicate fingerprint in architecture baseline")
        fingerprints.add(fingerprint)
        occurrences = item.get("occurrences")
        if not isinstance(occurrences, list) or len(occurrences) < 2:
            raise ValueError("Malformed architecture baseline occurrences")
        networks = set()
        locations = set()
        for occ in occurrences:
            if not isinstance(occ, dict):
                raise ValueError("Malformed architecture baseline occurrence")
            network = occ.get("network")
            filename = occ.get("file")
            function = occ.get("function")
            line = occ.get("line")
            if not (network in NETWORKS
                    and isinstance(filename, str)
                    and filename.startswith(network + "_")
                    and filename.endswith(SUFFIXES)
                    and isinstance(function, str) and bool(function)
                    and isinstance(line, int) and not isinstance(line, bool)
                    and line > 0):
                raise ValueError("Malformed architecture baseline occurrence")
            # Exact repeats cannot represent distinct AST nodes. Counting them
            # would silently mint extra copies for a lexical identity.
            location = (network, filename, function, line)
            if location in locations:
                raise ValueError("Duplicate occurrence in architecture baseline")
            locations.add(location)
            networks.add(network)
        if len(networks) < 2 or item.get("networks") != sorted(networks):
            raise ValueError("Malformed architecture baseline networks")


def regressions(current: list[dict], baseline: list[dict]) -> list[dict]:
    """Reject new locations even when they replace deleted copies.

    The same fingerprint is not a transferable allowance for other functions.
    Removing copies is always allowed.
    """
    _validate_baseline(baseline)
    allowances: dict[str, Counter] = {}
    for item in baseline:
        fingerprint = item["fingerprint"]
        allowances[fingerprint] = Counter(
            _identity(occ) for occ in item["occurrences"]
        )
    failures = []
    for item in current:
        budget = allowances.get(item["fingerprint"], Counter())
        seen: Counter = Counter()
        additions = []
        for occurrence in item["occurrences"]:
            key = _identity(occurrence)
            seen[key] += 1
            if seen[key] > budget[key]:
                additions.append(occurrence)
        if additions:
            failures.append({**item, "unbudgeted_occurrences": additions})
    return failures


def missing_modules(tools_dir: str | Path, expected: list[str]) -> list[str]:
    """Identify a vanished audited module even if its network is still present."""
    if (not isinstance(expected, list) or len(expected) != len(set(expected))
            or not all(isinstance(name, str)
                       and Path(name).name == name
                       and _network(Path(name)) is not None
                       and name.endswith(SUFFIXES) for name in expected)):
        raise ValueError("Malformed architecture module manifest")
    current = {path.name for path, _ in _eligible_paths(Path(tools_dir))}
    return sorted(set(expected) - current)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--baseline")
    parser.add_argument("--module-manifest", help="Required audited source filenames JSON")
    args = parser.parse_args(argv)
    report = collect(args.tools)
    if args.module_manifest:
        expected = json.loads(Path(args.module_manifest).read_text(encoding="utf-8"))
        missing = missing_modules(args.tools, expected)
        if missing:
            raise ValueError("Missing audited network modules: " + ", ".join(missing))
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        failures = regressions(report, baseline)
        if failures:
            print(
                f"Architecture duplication budget exceeded: {len(failures)} groups",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

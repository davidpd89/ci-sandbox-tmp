"""Matriz ejecutable de paridad: inspección offline del código, no acciones reales."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NETWORKS = ("bluesky", "facebook", "instagram", "mastodon", "pinterest", "reddit", "threads", "tiktok", "x")
FEATURES = ("discovery", "follow", "unfollow", "like", "comment", "repost", "loyalty")
STATES = frozenset(("wired", "present_not_wired", "missing", "unverifiable"))
SCANS = {
    "bluesky": "bluesky_growth_scan", "facebook": "facebook_scan",
    "instagram": "instagram_commenters_scan", "mastodon": "mastodon_growth_scan",
    "pinterest": "pinterest_growth", "reddit": "reddit_scan",
    "threads": "threads_scan", "tiktok": "tiktok_growth_scan", "x": "x_scan",
}
EXECUTORS = {
    "bluesky": "bluesky_execute", "facebook": "facebook_execute",
    "instagram": "instagram_execute", "mastodon": "mastodon_execute",
    "pinterest": "pinterest_growth", "reddit": "reddit_execute",
    "threads": "threads_execute", "tiktok": "tiktok_mobile_execute", "x": "x_execute",
}
# Un voto de Reddit y una reacción de Pinterest se exponen como variantes,
# sin atribuirles equivalencia semántica plena con un like.
KINDS = {
    "bluesky": {"follow": "follow", "like": "like", "comment": "reply", "repost": "repost"},
    "facebook": {"like": "like_external", "comment": "comment_external"},
    "instagram": {"follow": "follow", "like": "like", "comment": "comment"},
    "mastodon": {"follow": "follow", "like": "favourite", "comment": "reply", "repost": "boost"},
    "pinterest": {"follow": "follow", "like": "react", "comment": "comment"},
    "reddit": {"like": "vote", "comment": "comment"},
    "threads": {"follow": "follow", "like": "like", "comment": "reply"},
    "tiktok": {"follow": "follow", "like": "like", "comment": "comment"},
    "x": {"follow": "follow", "like": "like", "comment": "reply", "repost": "repost"},
}
# Indicios de cobertura previa, no pruebas de cada función individual.
TEST_HINTS = {
    "bluesky": "tests/test_bluesky_execute_preflight.py",
    "facebook": "tests/test_facebook_like_comments.py",
    "instagram": "tests/test_instagram_paused.py",
    "mastodon": "tests/test_mastodon_api_features.py",
    "pinterest": "tests/test_pinterest_growth.py",
    "reddit": "tests/test_reddit_comments.py",
    "threads": "tests/test_threads_execute_api.py",
    "tiktok": "tests/test_tiktok_mobile_execute.py",
    "x": "tests/test_x_execute_preflight.py",
}


def _parse(root: Path, module: str):
    path = root / "tools" / (module + ".py")
    if not path.is_file():
        return None
    try:
        return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError):
        return None


def _defs(tree):
    return {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _kind_branches(tree):
    """Sólo literales de comparaciones sobre kind; docstrings no prueban soporte."""
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or any(
            not isinstance(op, (ast.Eq, ast.In)) for op in node.ops
        ):
            continue
        expression = ast.unparse(node.left)
        if not (expression == "kind" or expression.endswith("['kind']") or expression.endswith(".get('kind')")):
            continue
        for comparator in node.comparators:
            for child in ast.walk(comparator):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    found.add(child.value)
    return found


def _script_steps(spec):
    """Lee argv de PIPELINES sin lanzar subprocess ni abrir sesiones."""
    for section in ("pre", "build", "execute", "post"):
        steps = spec.get(section) or ()
        if section in ("build", "execute") and steps and isinstance(steps[0], str):
            steps = (steps,)
        for argv in steps:
            if isinstance(argv, (list, tuple)):
                yield section, tuple(str(v).replace("\\", "/") for v in argv)


def _wiring(spec, module, network=None, *, required_args=()):
    """Comprueba un paso invocado con los argumentos operativos exigidos."""
    needle = f"tools/{module}.py"
    for section, argv in _script_steps(spec):
        if any(part == needle or part.endswith("/" + needle) for part in argv):
            if (network is None or network in argv) and all(arg in argv for arg in required_args):
                return section
    return None


def _registry_keys(tree, variable):
    if tree is None:
        return set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == variable for t in node.targets
        ) and isinstance(node.value, ast.Dict):
            return {
                k.value for k in node.value.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
    return set()


def build_matrix(*, root=ROOT, pipelines=None):
    """Genera celdas con referencia a fuente, tests, configuración y métricas."""
    root = Path(root)
    if pipelines is None:
        from mechanical_round import PIPELINES
        pipelines = PIPELINES
    cleanup = _registry_keys(_parse(root, "unfollow_cleanup"), "ADAPTERS")
    harvest = _registry_keys(_parse(root, "loyalty"), "HARVEST")
    out = {}
    for network in NETWORKS:
        spec = pipelines.get(network) or {}
        exe, scan = EXECUTORS[network], SCANS[network]
        exec_tree, scan_tree = _parse(root, exe), _parse(root, scan)
        executable = exec_tree is not None and bool(_defs(exec_tree) & {"run_plan", "main"})
        scan_entry = scan_tree is not None and bool(_defs(scan_tree) & {"scan", "run", "main"})
        executable_kinds = _kind_branches(exec_tree) if exec_tree else set()
        row = {}
        for feature in FEATURES:
            module, symbol, variant, stage, verified = None, None, None, None, False
            if feature == "discovery":
                module, symbol = scan, "scan|run|main"
                verified = scan_entry
                stage = _wiring(spec, scan)
            elif feature == "unfollow":
                module, symbol = "unfollow_cleanup", "ADAPTERS"
                verified = network in cleanup
                stage = _wiring(spec, module, network, required_args=("--apply",))
            elif feature == "loyalty":
                module, symbol = "loyalty", "HARVEST"
                verified = network in harvest
                stage = _wiring(spec, module, network)
            else:
                variant = KINDS[network].get(feature)
                module, symbol = exe, "run_plan|main"
                verified = bool(variant and executable and variant in executable_kinds)
                stage = _wiring(spec, exe)
            implementation = f"tools/{module}.py" if verified else None
            if verified:
                status = "wired" if stage else "present_not_wired"
            elif module and _parse(root, module) is None:
                status = "unverifiable"
            else:
                status = "missing"
            config = f"SISTEMA_DIARIO_{network.upper()}/growth_config.json"
            if not (root / config).is_file():
                config = None
            metrics_source = f"tools/{exe}.py" if exec_tree and any(
                isinstance(n, ast.Name) and n.id == "METRICAS_CSV" for n in ast.walk(exec_tree)
            ) else None
            hint = TEST_HINTS[network]
            row[feature] = {
                "status": status,
                "implementation": implementation,
                "symbol": symbol if verified else None,
                "variant": variant if verified else None,
                "pipeline_stage": stage if verified else None,
                "tests": [p for p in ("tests/test_executable_feature_parity.py", hint) if (root / p).is_file()],
                "config": config,
                "metrics_source": metrics_source,
            }
        out[network] = row
    return out


def problems(matrix):
    errors = []
    if set(matrix) != set(NETWORKS):
        errors.append("networks mismatch")
    for network, row in matrix.items():
        if set(row) != set(FEATURES):
            errors.append(f"{network}: feature mismatch")
        for feature, cell in row.items():
            if cell.get("status") not in STATES:
                errors.append(f"{network}/{feature}: bad status")
            if cell.get("status") == "wired" and not (cell.get("implementation") and cell.get("pipeline_stage")):
                errors.append(f"{network}/{feature}: unsupported wired assertion")
    return errors


def as_markdown(matrix):
    labels = {"wired": "W", "present_not_wired": "P", "missing": "—", "unverifiable": "?"}
    lines = ["| Red | " + " | ".join(FEATURES) + " |",
             "| --- | " + " | ".join("---" for _ in FEATURES) + " |"]
    for net, row in matrix.items():
        cols = []
        for cell in row.values():
            symbol = labels[cell["status"]]
            if cell["implementation"]:
                symbol = f"[{symbol}](../../{cell['implementation']})"
            cols.append(symbol)
        lines.append(f"| {net} | " + " | ".join(cols) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true", help="falla ante incoherencias, no ante carencias reales")
    parser.add_argument("--require", action="append", default=[], metavar="RED:ACCION", help="exige celda wired")
    args = parser.parse_args(argv)
    matrix = build_matrix()
    errors = problems(matrix)
    for requirement in args.require:
        net, sep, feat = requirement.partition(":")
        if not sep or matrix.get(net, {}).get(feat, {}).get("status") != "wired":
            errors.append(f"not wired: {requirement}")
    if args.json:
        print(json.dumps({"matrix": matrix, "problems": errors}, ensure_ascii=False, indent=2))
    elif args.markdown:
        print(as_markdown(matrix), end="")
    else:
        for net in NETWORKS:
            print(net, " ".join(f"{feat}={matrix[net][feat]['status']}" for feat in FEATURES))
        for error in errors:
            print("ERROR:", error)
    return 1 if errors and (args.strict or args.require) else 0


if __name__ == "__main__":
    raise SystemExit(main())

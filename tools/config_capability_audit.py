"""Auditoría offline de paridad declarativa, sin sesiones ni acciones en redes.

Los hallazgos de cobertura son evidencia de wiring, NO prueba de que una API funcione.
Los campos sin referencias literales son CANDIDATOS, no claves huérfanas probadas.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
from pathlib import Path

import growth_policy as gp
import network_capabilities as cap

ROOT = Path(__file__).resolve().parents[1]
SCANNERS = {
    "bluesky": "tools/bluesky_growth_scan.py",
    "mastodon": "tools/mastodon_growth_scan.py",
    "tiktok": "tools/tiktok_growth_scan.py",
}
CONFIG_PATHS = {
    "bluesky": "SISTEMA_DIARIO_BLUESKY/growth_config.json",
    "mastodon": "SISTEMA_DIARIO_MASTODON/growth_config.json",
    "tiktok": "SISTEMA_DIARIO_TIKTOK/growth_config.json",
}
# Comprobado en los scanners: en estas dos redes se llama a growth_policy.
POLICY_CONSUMERS = ("bluesky", "mastodon")
COMMON_KEYS = {
    "acquisition_age": ("like_max_age_acquisition_days", "favourite_max_age_acquisition_days"),
    "community_age": ("like_max_age_days", "favourite_max_age_days"),
    "follow_max_followers": ("follow_max_followers",),
}
COMMON_DEFAULTS = {
    "acquisition_age": gp.MAX_POST_AGE_DAYS["acquisition"],
    "community_age": gp.MAX_POST_AGE_DAYS["community"],
    "follow_max_followers": gp.FOLLOW_MAX_FOLLOWERS,
}


def _pairs_unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"clave JSON duplicada: {key}")
        out[key] = value
    return out


def _read_config(path):
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs_unique)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_config(config):
    """Errores de forma contrastables; no inventa schemas comunes entre plataformas."""
    issues = []
    if not isinstance(config, dict):
        return ["raíz: se esperaba objeto JSON"]
    if type(config.get("version")) is not int or config["version"] != 1:
        issues.append("version: se esperaba entero 1")
    budgets = config.get("budgets")
    if not isinstance(budgets, dict) or not budgets:
        issues.append("budgets: objeto no vacío requerido")
    else:
        for key, value in budgets.items():
            if not _number(value) or value < 0:
                issues.append(f"budgets.{key}: número finito no negativo requerido")
        for key in ("max_read_requests", "max_candidates", "max_posts_total"):
            if key in budgets and _number(budgets[key]) and budgets[key] <= 0:
                issues.append(f"budgets.{key}: debe ser mayor que cero")
    shortlist = config.get("shortlist", {})
    if not isinstance(shortlist, dict):
        issues.append("shortlist: se esperaba objeto")
    else:
        for aliases in COMMON_KEYS.values():
            defined = [(key, shortlist[key]) for key in aliases if key in shortlist]
            for key, value in defined:
                if not _number(value) or value <= 0:
                    issues.append(f"shortlist.{key}: número positivo requerido")
            if len(defined) == 2 and defined[0][1] != defined[1][1]:
                issues.append(f"shortlist: alias contradictorios {defined[0][0]} y {defined[1][0]}")
    for group in ("surfaces",):
        if group in config:
            value = config[group]
            if not isinstance(value, dict) or any(type(v) is not bool for v in value.values()):
                issues.append(f"{group}: se esperaba mapa de booleanos")
    coverage = config.get("coverage", {})
    if not isinstance(coverage, dict):
        issues.append("coverage: se esperaba objeto")
    else:
        required = coverage.get("required_surfaces", [])
        optional = coverage.get("optional_surfaces", [])
        for key, entries in (("required_surfaces", required), ("optional_surfaces", optional)):
            if not isinstance(entries, list) or any(not isinstance(v, str) or not v for v in entries):
                issues.append(f"coverage.{key}: lista de nombres no vacíos")
            elif len(set(entries)) != len(entries):
                issues.append(f"coverage.{key}: entradas duplicadas")
        if isinstance(required, list) and isinstance(optional, list):
            try:
                overlap = set(required) & set(optional)
                if overlap:
                    issues.append("coverage: required/optional comparten " + ",".join(sorted(overlap)))
            except TypeError:
                pass  # Los tipos inválidos ya generan su error anterior.
    return issues


def _effective(config):
    section = config.get("shortlist", {})
    result = {}
    for label, aliases in COMMON_KEYS.items():
        source = next((key for key in aliases if section.get(key) is not None), None)
        if label == "acquisition_age":
            value = gp.max_post_age_days(config, "acquisition")
        elif label == "community_age":
            value = gp.max_post_age_days(config, "community")
        else:
            value = gp.follow_max_followers(config)
        result[label] = {"value": value, "source": f"shortlist.{source}" if source else "growth_policy.default"}
    return result


def _source_literals(path):
    """AST estático: no importa ni ejecuta el scanner."""
    try:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeError):
        return set()
    return {node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)}


def _candidate_keys(root, network, config):
    scanner = root / SCANNERS[network]
    if not scanner.is_file():
        return []
    # Cobertura conservadora: también siguen vigentes los adaptadores comunes.
    files = (scanner, root / "tools/growth_policy.py", root / "tools/volume_ramp.py",
             root / "tools/tiktok_discovery.py", root / "tools/tiktok_growth_flow.py")
    literals = set().union(*(_source_literals(path) for path in files))
    candidates = []
    for section in ("budgets", "coverage", "shortlist", "scoring", "surfaces"):
        for key in (config.get(section) or {}):
            if key not in literals:
                candidates.append(f"{section}.{key}")
    return sorted(candidates)


def _pipeline_view(pipeline):
    if not pipeline:
        return {"primary_lane": None, "shape": None, "runs_per_day": None,
                "runs_source": "no_pipeline"}
    lane = "MOBILE" if pipeline.get("phone") else ("WEB" if pipeline.get("browser") else "API")
    return {
        "primary_lane": lane,
        "shape": pipeline.get("shape", True),
        "runs_per_day": pipeline.get("runs_per_day"),
        "runs_source": "pipeline" if "runs_per_day" in pipeline else "runtime_dynamic_or_default",
    }


def _env_declarations(root):
    """Solo nombres de variables; nunca extrae valores, secretos ni entorno real."""
    found = {}
    tools_dir = root / "tools"
    if not tools_dir.is_dir():
        return found
    for path in sorted(tools_dir.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in ("getenv", "get"):
                continue
            receiver = func.value
            is_getenv = (isinstance(receiver, ast.Name) and receiver.id == "os"
                         and func.attr == "getenv")
            is_environ = (isinstance(receiver, ast.Attribute) and
                          isinstance(receiver.value, ast.Name) and
                          receiver.value.id == "os" and receiver.attr == "environ"
                          and func.attr == "get")
            if not (is_getenv or is_environ):
                continue
            key = node.args[0]
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                found.setdefault(key.value, set()).add(path.name)
    return {key: sorted(files) for key, files in sorted(found.items())}


def audit(root=ROOT, *, pipelines=None, cleanup_adapters=None, harvesters=None):
    root = Path(root)
    if pipelines is None:
        from mechanical_round import PIPELINES
        pipelines = PIPELINES
    if cleanup_adapters is None:
        from unfollow_cleanup import ADAPTERS
        cleanup_adapters = ADAPTERS
    if harvesters is None:
        from loyalty import HARVEST
        harvesters = HARVEST

    matrix = cap.build_matrix(pipelines=pipelines, cleanup_adapters=cleanup_adapters,
                              harvesters=harvesters)
    result = {"schema": 1, "capabilities": matrix, "pipelines": {},
              "configurations": {}, "environment_names": _env_declarations(root),
              "findings": [], "errors": 0}
    for network in cap.NETWORKS:
        pipeline = pipelines.get(network) or {}
        result["pipelines"][network] = _pipeline_view(pipeline)
        if network not in CONFIG_PATHS:
            result["configurations"][network] = {"status": "not_declared", "path": None}
            continue
        relative = CONFIG_PATHS[network]
        path = root / relative
        if not path.is_file():
            result["configurations"][network] = {"status": "missing_in_checkout", "path": relative}
            result["findings"].append({"network": network, "kind": "missing_in_checkout",
                                       "detail": relative, "severity": "info"})
            continue
        try:
            config = _read_config(path)
        except (OSError, ValueError, UnicodeError) as exc:
            # No registrar contenido inválido (podría incluir información privada).
            result["errors"] += 1
            result["configurations"][network] = {"status": "invalid", "path": relative}
            result["findings"].append({"network": network, "kind": "invalid_json",
                                       "detail": type(exc).__name__, "severity": "error"})
            continue
        errors = validate_config(config)
        for detail in errors:
            result["findings"].append({"network": network, "kind": "invalid_config",
                                       "detail": detail, "severity": "error"})
        result["errors"] += len(errors)
        entry = {"status": "valid" if not errors else "invalid",
                 "path": relative, "section_names": sorted(config)}
        if network in POLICY_CONSUMERS and not errors:
            entry["effective_common_policy"] = _effective(config)
        entry["disabled_surfaces"] = sorted(
            key for key, enabled in (config.get("surfaces") or {}).items()
            if enabled is False
        ) if isinstance(config.get("surfaces", {}), dict) else []
        candidates = _candidate_keys(root, network, config)
        entry["unverified_literal_references"] = candidates
        if candidates:
            result["findings"].append({"network": network, "kind": "review_key_references",
                                       "detail": f"{len(candidates)} candidatas, NO huérfanas confirmadas",
                                       "severity": "info"})
        result["configurations"][network] = entry
    # Divergencia efectiva no equivale a error: puede ser un override legítimo.
    for name in COMMON_KEYS:
        observed = {
            network: result["configurations"].get(network, {})
                .get("effective_common_policy", {}).get(name, {}).get("value")
            for network in POLICY_CONSUMERS
        }
        observed = {key: value for key, value in observed.items() if value is not None}
        if len(set(observed.values())) > 1:
            result["findings"].append({"network": "*", "kind": "policy_divergence",
                                       "detail": {name: observed}, "severity": "info"})
    # Capacidad no implementada, o implementada pero sin wiring: estados separados.
    result["wiring"] = {}
    for network, data in matrix.items():
        result["wiring"][network] = {
            "unfollow": ("wired" if data["unfollow_scheduled"] else
                         "available_not_wired" if data["unfollow_adapter"] else "missing"),
            "loyalty": ("wired" if data["loyalty_scheduled"] else
                        "available_not_wired" if data["inbound_harvest"] else "missing"),
            "gpt_writer": "wired" if data["gpt_writer_scheduled"] else "not_observed_in_pre",
        }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="checkout a inspeccionar")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = audit(args.root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        for network in cap.NETWORKS:
            cfg = report["configurations"][network]
            pipe = report["pipelines"][network]
            print(f"{network:10} {pipe['primary_lane'] or '-':6} {cfg['status']:20} {report['wiring'][network]}")
        print(f"Hallazgos: {len(report['findings'])}; errores: {report['errors']}")
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

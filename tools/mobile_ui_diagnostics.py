"""Read-only, privacy-preserving Android accessibility-tree diagnostics.

Does not store raw UI text, images, account identifiers or coordinates.
Contract: structural features + fixed navigation landmarks only; schema 1.
No device, network, credentials or social actions. Python 3.11 stdlib.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from typing import Any

MAX_NODES = 3000
MAX_DEPTH = 32
MAX_INPUT_BYTES = 1_000_000
ROLES = frozenset({
    "textview", "button", "imagebutton", "edittext", "recyclerview",
    "view", "viewgroup", "imageview", "framelayout", "linearlayout",
    "scrollview", "checkbox", "switch", "textinputlayout",
})
LANDMARKS = frozenset({
    "inicio", "home", "para ti", "for you", "siguiendo", "following",
    "seguir", "follow", "perfil", "profile", "usuarios", "users",
    "videos", "vídeos", "comentarios", "comments", "buscar", "search",
    "me gusta", "like", "compartir", "share", "amigos", "friends",
    "mensajes", "messages",
})
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


def _walk_bounded(tree: Any) -> list[dict[str, Any]]:
    if not isinstance(tree, (dict, list)):
        raise ValueError("invalid UI tree")
    stack = [(tree, 0)]
    nodes: list[dict[str, Any]] = []
    visited = 0
    while stack:
        node, depth = stack.pop()
        visited += 1
        if visited > MAX_NODES:
            raise ValueError("UI tree exceeds node limit")
        if depth > MAX_DEPTH:
            raise ValueError("UI tree exceeds depth limit")
        if isinstance(node, list):
            stack.extend((child, depth + 1) for child in reversed(node))
        elif isinstance(node, dict):
            if isinstance(node.get("rect"), dict):
                nodes.append(node)
            children = node.get("children")
            if isinstance(children, list):
                stack.append((children, depth + 1))
            else:
                for key in ("roots", "root", "elements"):
                    if key in node:
                        stack.append((node[key], depth + 1))
        elif node is not None:
            raise ValueError("invalid UI child")
    return nodes


def _role(element: dict[str, Any]) -> str:
    value = element.get("type") or element.get("className") or ""
    if not isinstance(value, str) or len(value) > 128:
        return "other"
    value = value.rsplit(".", 1)[-1].lower()
    return value if value in ROLES else "other"


def _landmark(element: dict[str, Any]) -> str:
    for key in ("text", "label", "name", "value", "placeholder", "contentDescription"):
        value = element.get(key)
        if not isinstance(value, str) or len(value) > 64:
            continue
        label = unicodedata.normalize("NFKC", value).strip().casefold()
        label = " ".join(label.split())
        if label in LANDMARKS:
            return label.replace(" ", "_")
    return "none"


def _geometry(element: dict[str, Any]) -> tuple[float, float] | None:
    rect = element["rect"]
    try:
        x, y = float(rect["x"]), float(rect["y"])
        width, h = float(rect["width"]), float(rect["height"])
    except (TypeError, ValueError, KeyError, OverflowError):
        return None
    if not (all(map(math.isfinite, (x, y, width, h)))
            and y >= 0 and width > 0 and h > 0):
        return None
    center, bottom = y + h / 2, y + h
    if not (math.isfinite(center) and math.isfinite(bottom)):
        return None
    return center, bottom


def diagnose(tree: Any) -> dict[str, Any]:
    """Return only approved feature names and aggregates, never raw labels."""
    elements = _walk_bounded(tree)
    valid = [(element, _geometry(element)) for element in elements]
    valid = [(element, pos) for element, pos in valid if pos is not None]
    if not valid:
        raise ValueError("UI tree has no valid geometry")
    bottom = max(pos[1] for _, pos in valid)
    if bottom <= 0:
        raise ValueError("UI viewport is empty")
    features: Counter[str] = Counter()
    for element, (center, _) in valid:
        region = min(3, int(4 * (center / bottom)))
        features[f"{_role(element)}:{region}:{_landmark(element)}"] += 1
    ordered = dict(sorted(features.items()))
    payload = json.dumps(ordered, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return {
        "schema": 1,
        "fingerprint": hashlib.sha256(payload.encode("ascii")).hexdigest(),
        "elements": len(valid),
        "features": ordered,
    }


def _validated(snapshot: dict[str, Any]) -> dict[str, int]:
    if not isinstance(snapshot, dict) or type(snapshot.get("schema")) is not int or snapshot["schema"] != 1:
        raise ValueError("unsupported snapshot schema")
    if not isinstance(snapshot.get("fingerprint"), str) or not FINGERPRINT_RE.fullmatch(snapshot["fingerprint"]):
        raise ValueError("invalid fingerprint")
    features = snapshot.get("features")
    if not isinstance(features, dict) or len(features) > MAX_NODES:
        raise ValueError("invalid feature map")
    allowed_labels = {label.replace(" ", "_") for label in LANDMARKS} | {"none"}
    for key, count in features.items():
        if not isinstance(key, str) or len(key) > 90:
            raise ValueError("invalid feature key")
        parts = key.split(":")
        if len(parts) != 3 or parts[0] not in ROLES | {"other"} or parts[1] not in {"0", "1", "2", "3"} or parts[2] not in allowed_labels:
            raise ValueError("unknown feature key")
        if type(count) is not int or count <= 0 or count > MAX_NODES:
            raise ValueError("invalid feature count")
    encoded = json.dumps(features, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    if hashlib.sha256(encoded.encode("ascii")).hexdigest() != snapshot["fingerprint"]:
        raise ValueError("snapshot fingerprint mismatch")
    if type(snapshot.get("elements")) is not int or snapshot["elements"] != sum(features.values()) or snapshot["elements"] > MAX_NODES:
        raise ValueError("snapshot element count mismatch")
    return features


def compare(reference: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Weighted Jaccard similarity; 1 means equivalent structural features."""
    left, right = _validated(reference), _validated(current)
    keys = left.keys() | right.keys()
    union = sum(max(left.get(k, 0), right.get(k, 0)) for k in keys)
    overlap = sum(min(left.get(k, 0), right.get(k, 0)) for k in keys)
    return {
        "same_fingerprint": reference["fingerprint"] == current["fingerprint"],
        "similarity": round(overlap / union, 4) if union else 1.0,
        "added_elements": sum(max(0, right.get(k, 0) - left.get(k, 0)) for k in keys),
        "removed_elements": sum(max(0, left.get(k, 0) - right.get(k, 0)) for k in keys),
    }


def _read_json(path: Path) -> Any:
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("input exceeds size limit")
    with path.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds size limit")
    return json.loads(raw.decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline mobile UI structural diagnostics")
    parser.add_argument("snapshot", type=Path, help="synthetic UI tree JSON (never real user data)")
    parser.add_argument("--reference", type=Path, help="another synthetic UI tree JSON")
    args = parser.parse_args(argv)
    current = diagnose(_read_json(args.snapshot))
    result = {"current": current}
    if args.reference:
        result["comparison"] = compare(diagnose(_read_json(args.reference)), current)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

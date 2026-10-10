"""Contrato de lectura offline de planes nativos para las nueve redes.

Inspiración arquitectónica: soxoj/AdsLibrary @ 1ead5b3 (SourceCapabilities).
Implementación original: no copia código ajeno. No importa ejecutores, realiza
acciones sociales ni sustituye los preflights de las plataformas.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit

NETWORKS = (
    "x", "bluesky", "mastodon", "reddit", "threads",
    "instagram", "tiktok", "pinterest", "facebook",
)


@dataclass(frozen=True)
class NativeKind:
    kind: str
    family: str
    target_fields: tuple[str, ...]
    required_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlatformCapabilities:
    """Sintaxis local soportada, no permisos reales de una API."""
    network: str
    native_kinds: frozenset[str]
    source: str


@dataclass(frozen=True)
class CanonicalAction:
    network: str
    kind: str
    family: str
    target_scope: str
    target: str
    target_portable: bool
    source_index: int
    has_text: bool


@dataclass(frozen=True)
class ProjectionIssue:
    source_index: int
    code: str


@dataclass(frozen=True)
class Projection:
    actions: tuple[CanonicalAction, ...]
    issues: tuple[ProjectionIssue, ...]


@dataclass(frozen=True)
class ActionOutcome:
    network: str
    kind: str
    status: str
    retryable: bool | None


class ReadOnlyAdapter(Protocol):
    network: str
    capabilities: PlatformCapabilities

    def project(self, plan: object) -> Projection: ...
    def observe(self, record: Mapping[str, Any]) -> ActionOutcome: ...


NATIVE: dict[str, tuple[NativeKind, ...]] = {
    "bluesky": (
        NativeKind("follow", "relationship", ("handle",)),
        NativeKind("unfollow", "relationship", ("handle",)),
        NativeKind("like", "reaction", ("url",)),
        NativeKind("repost", "amplification", ("url",)),
        NativeKind("quote", "amplification", ("url",), ("text",)),
        NativeKind("reply", "conversation", ("url",), ("text",)),
    ),
    "mastodon": (
        NativeKind("follow", "relationship", ("handle",)),
        NativeKind("favourite", "reaction", ("url", "status_id")),
        NativeKind("boost", "amplification", ("url", "status_id")),
        NativeKind("reply", "conversation", ("url", "status_id"), ("text",)),
    ),
    "x": (
        NativeKind("follow", "relationship", ("handle",)),
        NativeKind("like_latest", "reaction", ("handle",)),
        NativeKind("like", "reaction", ("url",)),
        NativeKind("repost", "amplification", ("url",)),
        NativeKind("quote", "amplification", ("url",), ("text",)),
        NativeKind("reply", "conversation", ("url",), ("text",)),
    ),
    "threads": (
        NativeKind("follow", "relationship", ("handle",)),
        NativeKind("like_latest", "reaction", ("handle",)),
        NativeKind("like", "reaction", ("permalink", "text_fragment"), ("handle",)),
        NativeKind("reply", "conversation", ("reply_to_id", "permalink", "text_fragment"), ("handle", "text")),
    ),
    "facebook": (
        NativeKind("like", "reaction", ("index",)),
        NativeKind("comment", "conversation", ("index",), ("text",)),
        NativeKind("like_external", "reaction", ("permalink",)),
        NativeKind("comment_external", "conversation", ("permalink",), ("text",)),
    ),
    "instagram": (
        NativeKind("follow", "relationship", ("handle",)),
        NativeKind("like", "reaction", ("permalink",), ("handle",)),
        NativeKind("comment", "conversation", ("permalink",), ("handle", "text")),
    ),
    "pinterest": (
        NativeKind("follow", "relationship", ("handle",)),
        NativeKind("react", "reaction", ("url",)),
        NativeKind("save", "curation", ("url",), ("board",)),
        NativeKind("comment", "conversation", ("url",), ("text",)),
    ),
    "reddit": (
        NativeKind("vote", "vote", ("url",), ("subreddit",)),
        NativeKind("comment", "conversation", ("url",), ("subreddit", "text")),
    ),
    "tiktok": (
        NativeKind("follow", "relationship", ("handle",)),
        NativeKind("like", "reaction", ("url",), ("handle",)),
        NativeKind("comment", "conversation", ("url",), ("handle", "text")),
    ),
}

SOURCES = {
    "bluesky": "tools/bluesky_execute.py",
    "mastodon": "tools/mastodon_execute.py",
    "x": "tools/x_execute.py",
    "threads": "tools/threads_execute.py",
    "facebook": "tools/facebook_execute.py",
    "instagram": "tools/instagram_execute.py",
    "pinterest": "tools/pinterest_growth.py",
    "reddit": "tools/reddit_execute.py",
    "tiktok": "tools/tiktok_mobile_execute.py",
}

NONPORTABLE = {"text_fragment", "index", "handle", "status_id", "reply_to_id"}
HOSTS = {
    "bluesky": ("bsky.app",),
    "x": ("x.com", "twitter.com"),
    "reddit": ("reddit.com", "redd.it"),
    "threads": ("threads.com", "threads.net"),
    "instagram": ("instagram.com",),
    "tiktok": ("tiktok.com",),
    "pinterest": ("pinterest.com", "pin.it"),
    "facebook": ("facebook.com", "fb.com"),
    # Mastodon federado: sus instancias no tienen un único dominio.
}


def _portable_target(network: str, field: str, value: str) -> bool:
    if field in NONPORTABLE or field not in {"url", "permalink"}:
        return False
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            return False
    except ValueError:
        return False
    domains = HOSTS.get(network)
    return domains is None or any(host == name or host.endswith("." + name) for name in domains)


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


class PlanAdapter:
    def __init__(self, network: str, rules: tuple[NativeKind, ...], source: str):
        if network not in NETWORKS or not rules:
            raise ValueError("red o contrato no admitido")
        names = [r.kind for r in rules]
        if len(names) != len(set(names)):
            raise ValueError("kinds duplicados")
        self.network = network
        self._rules = {r.kind: r for r in rules}
        self.capabilities = PlatformCapabilities(network, frozenset(names), source)

    def project(self, plan: object) -> Projection:
        """Convierte planes finales (listas) sin ejecutar ni alterar acciones."""
        if not isinstance(plan, list):
            raise ValueError("se exige una lista JSON de plan final")
        actions: list[CanonicalAction] = []
        issues: list[ProjectionIssue] = []
        for i, item in enumerate(plan):
            if not isinstance(item, dict):
                issues.append(ProjectionIssue(i, "not_object"))
                continue
            kind = item.get("kind")
            if not isinstance(kind, str) or kind not in self._rules:
                issues.append(ProjectionIssue(i, "unsupported_kind"))
                continue
            rule = self._rules[kind]
            if any(not _nonempty(item.get(field)) for field in rule.required_fields):
                issues.append(ProjectionIssue(i, "missing_required_field"))
                continue
            key = value = None
            for field in rule.target_fields:
                candidate = item.get(field, 0) if field == "index" else item.get(field)
                if field == "index":
                    if type(candidate) is int and candidate >= 0:
                        key, value = field, str(candidate)
                        break
                elif _nonempty(candidate):
                    key, value = field, candidate.strip()
                    break
            if key is None or value is None:
                issues.append(ProjectionIssue(i, "missing_target"))
                continue
            actions.append(CanonicalAction(
                self.network, kind, rule.family, key, value,
                _portable_target(self.network, key, value),
                i, _nonempty(item.get("text")),
            ))
        return Projection(tuple(actions), tuple(issues))

    def observe(self, record: Mapping[str, Any]) -> ActionOutcome:
        """No declara éxito sin confirmación explícita y exacta del ejecutor."""
        kind, raw = record.get("kind"), record.get("resultado")
        if not isinstance(kind, str) or kind not in self._rules or not isinstance(raw, str):
            return ActionOutcome(self.network, str(kind), "unknown", None)
        if raw in {"confirmado", "publicado"}:
            status = "confirmed"
        elif raw == "ya_hecho" or raw.startswith(("saltado_", "omitido_")):
            status = "skipped"
        elif raw.startswith("rechazado_"):
            status = "rejected"
        elif raw.startswith(("fallo_", "error_")):
            status = "failed"
        else:
            status = "unknown"
        # Sin señales tipadas del ejecutor no se puede afirmar retryable.
        return ActionOutcome(self.network, kind, status, None)


class AdapterRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ReadOnlyAdapter] = {}

    def register(self, adapter: ReadOnlyAdapter) -> None:
        if adapter.network not in NETWORKS or adapter.network != adapter.capabilities.network:
            raise ValueError("identidad/capacidades inconsistentes")
        if adapter.network in self._items:
            raise ValueError("adaptador duplicado")
        self._items[adapter.network] = adapter

    def get(self, network: str) -> ReadOnlyAdapter:
        return self._items[network]

    def by_kind(self, kind: str) -> tuple[ReadOnlyAdapter, ...]:
        return tuple(a for a in self._items.values() if kind in a.capabilities.native_kinds)

    def by_family(self, family: str) -> tuple[ReadOnlyAdapter, ...]:
        if family not in {"relationship", "reaction", "conversation", "amplification", "curation", "vote"}:
            raise ValueError("familia desconocida")
        return tuple(a for a in self._items.values()
                     if any(r.family == family for r in NATIVE[a.network]))

    def all(self) -> tuple[ReadOnlyAdapter, ...]:
        return tuple(self._items.values())


def builtins() -> AdapterRegistry:
    registry = AdapterRegistry()
    for network in NETWORKS:
        registry.register(PlanAdapter(network, NATIVE[network], SOURCES[network]))
    return registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("network", choices=NETWORKS)
    parser.add_argument("plan", type=Path, help="JSON local; solo lectura")
    args = parser.parse_args(argv)
    try:
        with args.plan.open("r", encoding="utf-8") as stream:
            projection = builtins().get(args.network).project(json.load(stream))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"error de entrada: {type(exc).__name__}\n")
    counts: dict[str, int] = {}
    for action in projection.actions:
        counts[action.kind] = counts.get(action.kind, 0) + 1
    # Ningún texto, destino ni perfil se imprime.
    print(json.dumps({
        "schema": 1, "network": args.network, "accepted": len(projection.actions),
        "issues": len(projection.issues), "by_native_kind": counts,
        "unresolved_identity": sum(not a.target_portable for a in projection.actions),
    }, ensure_ascii=False, sort_keys=True))
    return 1 if projection.issues else 0


if __name__ == "__main__":
    raise SystemExit(main())

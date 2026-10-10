"""Offline projection of *attested* follower/following observations.

Capture belongs inside an authorised collector, AFTER it has parsed a real
relationship response. This module cannot verify that external observation.
No IO, traversal, ranking, or write actions are performed here.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping
from urllib.parse import urlsplit

NETWORKS = ("bluesky", "mastodon", "x", "threads", "facebook",
            "pinterest", "reddit", "tiktok")
GRAPH_RELATIONS = {
    "bluesky": frozenset({"followers", "follows"}),
    "mastodon": frozenset({"followers", "following"}),
}
_VERSION = 1
_KEY_MIN_BYTES = 16
_MAX_OBSERVATIONS = 100_000
_TOKEN_PATTERN = re.compile(r"[0-9a-f]{24}\Z")
_PROOF_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_DID_PATTERN = re.compile(r"did:(?:plc:[a-z2-7]{24}|web:[A-Za-z0-9.-]+)\Z", re.ASCII)
_ID_PATTERN = re.compile(r"[0-9]+\Z", re.ASCII)


def _key_ok(key):
    return isinstance(key, bytes) and len(key) >= _KEY_MIN_BYTES


def _observed_at(value):
    if not isinstance(value, str) or not value or len(value) > 64 or "T" not in value:
        return None
    try:
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.utcoffset() is not None else None


def _actor_id(network, actor, api_origin):
    """Canonical actor IDs, not handles/posts; Mastodon IDs scoped to API host.

    A Mastodon remote actor may have distinct local numeric IDs on two servers.
    Thus tokens deliberately do not merge across API origins.
    """
    if not isinstance(actor, str) or not actor:
        raise ValueError("actor ID ausente")
    if network == "bluesky":
        # ATProto DIDs are case-sensitive; do not casefold the identifier.
        if len(actor) > 2048 or not _DID_PATTERN.fullmatch(actor):
            raise ValueError("se exige DID de Bluesky, no handle")
        return actor
    if network == "mastodon":
        if not _ID_PATTERN.fullmatch(actor):
            raise ValueError("se exige account_id de Mastodon")
        if not isinstance(api_origin, str):
            raise ValueError("falta servidor API de Mastodon")
        parsed = urlsplit(api_origin)
        if (parsed.scheme != "https" or not parsed.hostname
                or any(ch.isspace() for ch in parsed.netloc) or parsed.username
                or parsed.password or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment):
            raise ValueError("origen de API no valido")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("puerto de API no valido") from exc
        host = parsed.hostname.lower()
        if ":" in host:  # IPv6 URL host: keep brackets in the scope.
            host = "[" + host + "]"
        origin_scope = host + (":" + str(port) if port not in (None, 443) else "")
        return origin_scope + "/" + (actor.lstrip("0") or "0")
    raise ValueError("sin adaptador de grafo autorizado")


def _mac(key, domain, payload):
    return hmac.new(key, (domain + "\0" + payload).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _proof_fields(row):
    return "\0".join(str(row[k]) for k in (
        "version", "network", "relation", "seed_actor", "candidate_actor",
        "source", "observed_at"))


def capture_relation(*, network, relation, seed_actor_id, candidate_actor_id,
                     source, observed_at, hmac_key, api_origin=None):
    """Construct a signed, pseudonymous observation from verified API actors.

    The caller MUST check the response's target, permission, relation direction,
    and completeness, and MUST NOT call this for inferred/search relations.
    Signing detects mutation after capture; it does not establish API truth.
    """
    if not _key_ok(hmac_key):
        raise ValueError("clave HMAC ausente o insuficiente")
    if (not isinstance(network, str) or network not in GRAPH_RELATIONS
            or not isinstance(relation, str) or relation not in GRAPH_RELATIONS[network]):
        raise ValueError("relacion/red sin contrato")
    seed = _actor_id(network, seed_actor_id, api_origin)
    candidate = _actor_id(network, candidate_actor_id, api_origin)
    if seed == candidate:
        raise ValueError("cuenta relacionada consigo misma")
    if not isinstance(source, str) or not source.strip() or len(source) > 1024:
        raise ValueError("procedencia ausente o excesiva")
    if _observed_at(observed_at) is None:
        raise ValueError("fecha sin zona o no valida")
    # Same namespace + Unicode normalization as discovery_attribution._token
    # for *source keys* (#49). Actor tokens remain graph-specific.
    normalized_source = " ".join(unicodedata.normalize("NFKC", source).casefold().split())
    row = {
        "version": _VERSION,
        "network": network,
        "relation": relation,
        # SAME domain for both graph endpoints, unlike #49 audit fields.
        "seed_actor": _mac(hmac_key, network + "/graph_actor", seed)[:24],
        "candidate_actor": _mac(hmac_key, network + "/graph_actor", candidate)[:24],
        "source": _mac(hmac_key, network + "/source", normalized_source)[:24],
        "observed_at": observed_at,
    }
    row["proof"] = _mac(hmac_key, "discovery_graph/observation/v1", _proof_fields(row))
    return row


def _verified(row, key):
    if not isinstance(row, Mapping) or type(row.get("version")) is not int:
        return False
    if row["version"] != _VERSION:
        return False
    network = row.get("network")
    if not isinstance(network, str) or network not in GRAPH_RELATIONS:
        return False
    relation = row.get("relation")
    if not isinstance(relation, str) or relation not in GRAPH_RELATIONS[network]:
        return False
    if _observed_at(row.get("observed_at")) is None:
        return False
    for field in ("seed_actor", "candidate_actor", "source"):
        value = row.get(field)
        if not isinstance(value, str) or not _TOKEN_PATTERN.fullmatch(value):
            return False
    if row["seed_actor"] == row["candidate_actor"]:
        return False
    proof = row.get("proof")
    if not isinstance(proof, str) or not _PROOF_PATTERN.fullmatch(proof):
        return False
    expected = _mac(key, "discovery_graph/observation/v1", _proof_fields(row))
    return hmac.compare_digest(proof, expected)


def summarize_graph(observations, *, hmac_key):
    """Return historical graph facts, never current relationships or conversion.

    Unsupported networks and unverified input do not contribute candidates.
    Without the key evidence is unverifiable (counts are NULL, not zero).
    """
    coverage = {n: "contract_only" if n in GRAPH_RELATIONS else "unsupported"
                for n in NETWORKS}
    if not _key_ok(hmac_key):
        return {"capability": coverage, "status": "key_unavailable",
                "observations_seen": None, "observations_rejected": None,
                "unique_edges": None, "unique_candidates": None,
                "candidates": []}
    if not isinstance(observations, (list, tuple)):
        raise TypeError("observations debe ser una secuencia")
    if len(observations) > _MAX_OBSERVATIONS:
        raise ValueError("demasiadas observaciones para una proyeccion")
    edges = defaultdict(set)
    rejected = 0
    for row in observations:
        if not _verified(row, hmac_key):
            rejected += 1
            continue
        identity = (row["network"], row["relation"], row["seed_actor"],
                    row["candidate_actor"])
        edges[identity].add(row["source"])
    candidates = defaultdict(lambda: {"seeds": set(), "sources": set(), "relations": set()})
    for (network, relation, seed, candidate), record in edges.items():
        view = candidates[(network, candidate)]
        view["seeds"].add(seed)
        view["sources"].update(record)
        view["relations"].add(relation)
    return {
        "capability": coverage, "status": "historical_only",
        "observations_seen": len(observations), "observations_rejected": rejected,
        "unique_edges": len(edges), "unique_candidates": len(candidates),
        "candidates": [
            {"network": net, "candidate_id": actor,
             "seeds": sorted(entry["seeds"]), "sources": sorted(entry["sources"]),
             "relations": sorted(entry["relations"])}
            for (net, actor), entry in sorted(candidates.items())],
    }

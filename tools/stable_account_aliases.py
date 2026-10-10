"""Offline stable account alias ledger; never touches networks or operational state.

Verified remote IDs are distinct from handles and from #85 entity_snapshot_id.
"""
from __future__ import annotations
from bisect import bisect_left, bisect_right
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Mapping
from urllib.parse import urlsplit
import re

NETWORKS = frozenset({"x", "threads", "facebook", "pinterest", "reddit",
                      "bluesky", "mastodon", "tiktok", "instagram"})
QUEUES = frozenset({"WEB", "API", "MOBILE"})
_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:~-]{0,319}\Z", re.ASCII)
_DID = re.compile(r"did:(?:plc:[a-z2-7]{24}|web:[A-Za-z0-9._:%-]+)\Z", re.ASCII)


class AliasError(ValueError):
    """Diagnostic error for invalid or conflicting evidence."""


def _when(value: str) -> datetime:
    if not isinstance(value, str):
        raise AliasError("timestamp_required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AliasError("timestamp_invalid") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise AliasError("timestamp_timezone_required")
    return dt.astimezone(timezone.utc)


def _stamp(dt: datetime) -> str:
    return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")


def account_key(network: str, handle: str) -> str:
    """Local-key adapter for #85; prefer its account_key via key_builder after merge."""
    if network not in NETWORKS or not isinstance(handle, str):
        raise AliasError("account_invalid")
    h = handle.strip().lstrip("@").casefold()
    if not h or len(h) > 256 or any(c.isspace() or c in "|/:?#\\" for c in h):
        raise AliasError("handle_invalid")
    if network == "mastodon":
        parts = h.split("@")
        if (len(parts) != 2 or not re.fullmatch(r"[a-z0-9_][a-z0-9_.-]*", parts[0])
                or not re.fullmatch(r"[a-z0-9.-]+", parts[1]) or "." not in parts[1]):
            raise AliasError("mastodon_fully_qualified_acct_required")
    elif "@" in h or not re.fullmatch(r"[\w.-]+", h, re.UNICODE):
        raise AliasError("handle_invalid")
    return network + "|" + h


def stable_key(network: str, value: str, verification: str) -> str:
    """Accept only native remote identity pre-verified by a source adapter."""
    if network not in NETWORKS or not isinstance(value, str) or not value:
        raise AliasError("stable_id_invalid")
    if network == "bluesky":
        if verification != "did_bidirectional" or not _DID.fullmatch(value):
            raise AliasError("bluesky_did_not_bidirectionally_verified")
        return network + "|" + value
    if network == "mastodon":
        if verification != "actor_uri_confirmed":
            raise AliasError("mastodon_actor_uri_required")
        try:
            u = urlsplit(value)
            host = u.hostname
            if (u.scheme != "https" or not host or u.username or u.password or u.port is not None
                    or u.query or u.fragment or not u.path or any(x.isspace() for x in value)
                    or len(value) > 2048):
                raise ValueError("bad actor URI")
            host = host.encode("idna").decode("ascii").lower()
        except (ValueError, UnicodeError) as exc:
            raise AliasError("actor_uri_invalid") from exc
        return network + "|https://" + host + u.path.rstrip("/")
    if verification != "provider_account_id" or not _ID_PATTERN.fullmatch(value):
        raise AliasError("provider_id_unverified")
    return network + "|" + value


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    account: str
    stable: str
    observed_at: str
    queue: str
    source: str
    proof: str
    verification: str


class AliasTimeline:
    """In-memory replay of verified temporal claims; reversible without rekeying.

    resolve() distinguishes observed exact facts from interval extrapolation.
    project_events() requires explicit identity evidence for each event.
    """

    def __init__(self, *, key_builder=None):
        self.key_builder = key_builder or account_key
        self.evidence: dict[str, Evidence] = {}
        self.actions: list[dict[str, str]] = []
        self._inactive: set[str] = set()
        self._epoch = 0
        self._indexed_epoch = -1

    def observe(self, *, evidence_id: str, network: str, handle: str, stable_id: str,
                observed_at: str, queue: str, source: str, proof: str,
                verification: str) -> str:
        if not isinstance(evidence_id, str) or not _ID_PATTERN.fullmatch(evidence_id):
            raise AliasError("evidence_id_invalid")
        if queue not in QUEUES or not all(isinstance(x, str) and 0 < len(x.strip()) <= 300
                                          for x in (source, proof)):
            raise AliasError("provenance_required")
        key = self.key_builder(network, handle)
        stable = stable_key(network, stable_id, verification)
        at = _stamp(_when(observed_at))
        record = Evidence(evidence_id, key, stable, at, queue, source.strip(), proof.strip(), verification)
        prior = self.evidence.get(evidence_id)
        if prior is not None:
            if record != prior:
                raise AliasError("evidence_id_collision")
            return evidence_id
        self.evidence[evidence_id] = record
        self._epoch += 1
        return evidence_id

    def _audit(self, verb: str, evidence_id: str, reason: str) -> None:
        if evidence_id not in self.evidence:
            raise AliasError("unknown_evidence")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise AliasError("review_reason_required")
        active = evidence_id not in self._inactive
        if verb == "revoke" and not active or verb == "restore" and active:
            return
        if verb == "revoke":
            self._inactive.add(evidence_id)
        else:
            self._inactive.remove(evidence_id)
        self.actions.append({"action": verb, "evidence_id": evidence_id, "reason": reason.strip()})
        self._epoch += 1

    def revoke(self, evidence_id: str, *, reason: str) -> None:
        self._audit("revoke", evidence_id, reason)

    def restore(self, evidence_id: str, *, reason: str) -> None:
        self._audit("restore", evidence_id, reason)

    def _active(self) -> list[Evidence]:
        return [r for k, r in self.evidence.items() if k not in self._inactive]

    def _ensure_index(self) -> None:
        """Rebuild sorted indexes lazily after mutations, not for every event."""
        if self._indexed_epoch == self._epoch:
            return
        by_account, by_stable = {}, {}
        for row in self._active():
            by_account.setdefault(row.account, []).append(row)
            by_stable.setdefault(row.stable, []).append(row)

        def pack(groups):
            result = {}
            for key, records in groups.items():
                ordered = sorted(records, key=lambda r: (r.observed_at, r.evidence_id))
                result[key] = ([r.observed_at for r in ordered], ordered)
            return result

        self._account_index = pack(by_account)
        self._stable_index = pack(by_stable)
        self._indexed_epoch = self._epoch

    def _claims(self, account: str, moment: str) -> list[Evidence]:
        self._ensure_index()
        pair = self._account_index.get(account)
        if pair is None:
            return []
        times, rows = pair
        pos = bisect_right(times, moment)
        if pos == 0:
            return []
        first = bisect_left(times, times[pos - 1])
        return rows[first:pos]

    def resolve(self, network: str, handle: str, as_of: str) -> dict:
        account = self.key_builder(network, handle)
        moment = _stamp(_when(as_of))
        rows = self._claims(account, moment)
        if not rows:
            return {"account": account, "status": "unknown", "stable_key": None, "evidence_ids": []}
        owners = {r.stable for r in rows}
        if len(owners) > 1:
            return {"account": account, "status": "conflict_handle_recycled_same_time",
                    "stable_key": None, "evidence_ids": [r.evidence_id for r in rows]}
        stable = next(iter(owners))
        times, records = self._stable_index[stable]
        pos = bisect_right(times, moment)
        first = bisect_left(times, times[pos - 1])
        current = {r.account for r in records[first:pos]}
        if len(current) > 1:
            status, stable_out = "conflict_stable_multiple_handles", None
        elif account not in current:
            status, stable_out = "superseded_alias", stable
        else:
            status = "verified_at_observation" if rows[0].observed_at == moment else "inferred_interval"
            stable_out = stable
        return {"account": account, "status": status, "stable_key": stable_out,
                "evidence_ids": [r.evidence_id for r in rows]}

    def link(self, first_evidence_id: str, second_evidence_id: str) -> str:
        """Read-only link if both active observations contain the identical native ID."""
        a, b = self.evidence.get(first_evidence_id), self.evidence.get(second_evidence_id)
        if not a or not b or a.evidence_id in self._inactive or b.evidence_id in self._inactive:
            raise AliasError("link_evidence_missing_or_revoked")
        if a.stable != b.stable:
            raise AliasError("stable_identity_conflict")
        if a.account != b.account and a.observed_at == b.observed_at:
            raise AliasError("simultaneous_handles_conflict")
        # A third claim at either endpoint can invalidate an otherwise matching
        # pair. Never confirm a link whose observations are individually ambiguous.
        for record in (a, b):
            network, handle = record.account.split("|", 1)
            current = self.resolve(network, handle, record.observed_at)
            if (current["stable_key"] != record.stable
                    or current["status"] != "verified_at_observation"):
                raise AliasError("link_evidence_ambiguous")
        return a.stable

    def history(self, stable: str) -> list[dict]:
        return [{**asdict(r), "active": r.evidence_id not in self._inactive}
                for r in sorted(self.evidence.values(), key=lambda r: (r.observed_at, r.evidence_id))
                if r.stable == stable]

    def project_events(self, events: list[Mapping]) -> dict:
        """Strict join, deduplicated across WEB/API/MOBILE on (network, kind, event_id)."""
        prepared: dict[tuple[str, str, str], list[dict]] = {}
        for raw in events:
            if not isinstance(raw, Mapping):
                raise AliasError("event_invalid")
            network, kind, event_id, handle, at = (raw.get(x) for x in ("network", "kind", "event_id", "handle", "observed_at"))
            account = self.key_builder(network, handle)
            if not isinstance(kind, str) or not kind.strip() or len(kind) > 100:
                raise AliasError("event_kind_invalid")
            if not isinstance(event_id, str) or not event_id or len(event_id) > 512:
                raise AliasError("event_id_invalid")
            if raw.get("queue") not in QUEUES:
                raise AliasError("queue_invalid")
            at = _stamp(_when(at))
            proof_id = raw.get("evidence_id")
            if proof_id is not None and not isinstance(proof_id, str):
                raise AliasError("event_proof_invalid")
            key = (network, kind, event_id)
            prepared.setdefault(key, []).append({"account": account, "at": at, "proof": proof_id})
        linked, unresolved = [], []
        for (network, kind, event_id), versions in sorted(prepared.items()):
            shapes = {(row["account"], row["at"], row["proof"]) for row in versions}
            if len(shapes) > 1:
                unresolved.append({"network": network, "kind": kind, "event_id": event_id,
                                   "reason": "event_observation_conflict"})
                continue
            account, at, proof_id = next(iter(shapes))
            proof = self.evidence.get(proof_id) if proof_id else None
            if proof is None or proof_id in self._inactive or proof.account != account:
                unresolved.append({"network": network, "kind": kind, "event_id": event_id,
                                   "reason": "missing_verified_proof"})
                continue
            if _when(at) < _when(proof.observed_at):
                unresolved.append({"network": network, "kind": kind, "event_id": event_id,
                                   "reason": "proof_is_newer_than_event"})
                continue
            current = self.resolve(*account.split("|", 1), as_of=at)
            if current["stable_key"] != proof.stable or current["status"] not in {"verified_at_observation", "inferred_interval"}:
                unresolved.append({"network": network, "kind": kind, "event_id": event_id,
                                   "reason": "alias_no_longer_owned_or_conflicted"})
                continue
            linked.append({"network": network, "kind": kind, "event_id": event_id, "account": account,
                           "stable_key": proof.stable, "as_of": at})
        return {"linked": linked, "unresolved": unresolved}

    def to_document(self) -> dict:
        return {"schema_version": 1,
                "evidence": [asdict(self.evidence[k]) for k in sorted(self.evidence)],
                "actions": [dict(a) for a in self.actions]}

    @classmethod
    def from_document(cls, document: dict, *, key_builder=None) -> "AliasTimeline":
        if (not isinstance(document, dict) or document.get("schema_version") != 1
                or not isinstance(document.get("evidence"), list)
                or not isinstance(document.get("actions"), list)):
            raise AliasError("unsupported_schema")
        timeline = cls(key_builder=key_builder)
        for item in document["evidence"]:
            if not isinstance(item, dict) or set(item) != set(Evidence.__dataclass_fields__):
                raise AliasError("evidence_schema_invalid")
            network, sep, handle = item["account"].partition("|")
            if not sep:
                raise AliasError("account_invalid")
            sid = item["stable"].removeprefix(network + "|")
            timeline.observe(evidence_id=item["evidence_id"], network=network, handle=handle,
                             stable_id=sid, observed_at=item["observed_at"], queue=item["queue"],
                             source=item["source"], proof=item["proof"], verification=item["verification"])
            if asdict(timeline.evidence[item["evidence_id"]]) != item:
                raise AliasError("evidence_tampered")
        if len(timeline.evidence) != len(document["evidence"]):
            raise AliasError("duplicate_evidence")
        for action in document["actions"]:
            if not isinstance(action, dict) or set(action) != {"action", "evidence_id", "reason"}:
                raise AliasError("action_schema_invalid")
            if action["action"] not in {"revoke", "restore"}:
                raise AliasError("action_invalid")
            before = len(timeline.actions)
            timeline._audit(action["action"], action["evidence_id"], action["reason"])
            if len(timeline.actions) == before:
                raise AliasError("action_replay_not_a_transition")
        return timeline

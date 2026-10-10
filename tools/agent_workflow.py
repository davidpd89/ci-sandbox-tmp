"""Offline, side-effect-free skill workflow and event checkpoint contract.

No model/tool calls, social actions, network access or persistence occur here.
Consumers must keep the existing WEB/API/MOBILE queues and execution preflights.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Mapping

VERSION = 1
NETWORKS = frozenset({"x", "threads", "facebook", "pinterest", "reddit", "bluesky", "mastodon", "tiktok", "instagram"})
QUEUES = frozenset({"WEB", "API", "MOBILE"})
STAGES = ("research", "plan", "write", "validate", "approval", "dispatch", "verify")
HEX = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}\Z")


class WorkflowError(ValueError):
    """Invalid stage, stale approval, malformed checkpoint or conflicting replay."""


def digest(value: str) -> str:
    """Fingerprint content in memory; never store it in the checkpoint."""
    if not isinstance(value, str):
        raise WorkflowError("digest input must be a string")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _check_id(value: str, what: str) -> None:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise WorkflowError(f"invalid {what}")


def _check_digest(value: str, what: str) -> None:
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise WorkflowError(f"invalid {what}: expected SHA-256 hex fingerprint")


@dataclass(frozen=True)
class Event:
    event_id: str
    stage: str
    evidence: str
    revision: str = ""
    actor: str = ""
    outcome: str = ""
    tool_id: str = ""  # Opaque provenance of the tool/skill, not prompt or output

    def __post_init__(self) -> None:
        _check_id(self.event_id, "event_id")
        if self.stage not in STAGES:
            raise WorkflowError("unknown stage")
        _check_digest(self.evidence, "evidence")
        if self.revision:
            _check_digest(self.revision, "revision")
        if self.actor:
            _check_id(self.actor, "actor")
        if self.tool_id:
            _check_id(self.tool_id, "tool_id")
        if self.outcome and self.outcome not in {"confirmed", "failed", "unknown"}:
            raise WorkflowError("unsupported acknowledgement")

    def to_dict(self) -> dict[str, str]:
        return {k: getattr(self, k) for k in ("event_id", "stage", "evidence", "revision", "actor", "outcome", "tool_id")}


@dataclass(frozen=True)
class Workflow:
    run_id: str
    network: str
    queue: str
    events: tuple[Event, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _check_id(self.run_id, "run_id")
        if self.network not in NETWORKS or self.queue not in QUEUES:
            raise WorkflowError("unknown network or queue")
        if not isinstance(self.events, tuple):
            raise WorkflowError("events must be a tuple")
        # Replaying checks the entire chain, including externally loaded snapshots.
        self._replay()

    def _replay(self) -> tuple[str, str, str]:
        expected = STAGES[0]
        written = ""
        validated = ""
        seen: set[str] = set()
        for event in self.events:
            if not isinstance(event, Event):
                raise WorkflowError("events must contain Event values")
            if event.event_id in seen:
                raise WorkflowError("duplicate event id in checkpoint")
            seen.add(event.event_id)
            if event.stage != expected:
                raise WorkflowError(f"invalid transition: expected {expected}")
            if expected in {"research", "plan", "write"}:
                if event.revision or event.actor or event.outcome:
                    raise WorkflowError("unexpected stage fields")
                if expected == "write":
                    written = event.evidence
            elif expected == "validate":
                if event.revision != written or event.actor or event.outcome:
                    raise WorkflowError("validation must reference current draft")
                validated = event.evidence
            elif expected == "approval":
                if event.revision != written or not validated or not event.actor.startswith("human:") or event.outcome:
                    raise WorkflowError("approval needs validated revision and human attestation")
            elif expected == "dispatch":
                if event.revision != written or event.evidence != self.intent_key() or event.actor or event.outcome:
                    raise WorkflowError("dispatch must record matching idempotency key")
            elif expected == "verify":
                if event.revision != written or event.actor or event.outcome not in {"confirmed", "failed", "unknown"}:
                    raise WorkflowError("verify requires explicit acknowledgement outcome")
            expected = ({"confirmed": "complete", "failed": "failed", "unknown": "uncertain"}[event.outcome]
                        if expected == "verify" else STAGES[STAGES.index(expected) + 1])
        return expected, written, validated

    @property
    def stage(self) -> str:
        return self._replay()[0]

    @property
    def result(self) -> str:
        return self.events[-1].outcome if self.stage in {"complete", "failed", "uncertain"} else "pending"

    def intent_key(self) -> str:
        # Computed from the draft, not from run-specific execution attempt or time.
        written = next((e.evidence for e in self.events if e.stage == "write"), "")
        if not written:
            raise WorkflowError("draft not available")
        return digest(_canonical([VERSION, self.run_id, self.network, self.queue, written]))

    def handoff(self) -> dict[str, str]:
        """A pure data envelope; NEVER calls a publisher or executor."""
        if self.stage != "dispatch":
            raise WorkflowError("only approved workflows can be handed off")
        return {"run_id": self.run_id, "network": self.network, "queue": self.queue,
                "idempotency_key": self.intent_key(), "revision": self._replay()[1]}

    def append(self, event: Event) -> Workflow:
        existing = next((e for e in self.events if e.event_id == event.event_id), None)
        if existing is not None:
            if existing == event:
                return self  # Exact event delivery may be retried by a checkpoint caller.
            raise WorkflowError("conflicting replay of event id")
        return Workflow(self.run_id, self.network, self.queue, self.events + (event,))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"version": VERSION, "run_id": self.run_id,
            "network": self.network, "queue": self.queue,
            "events": [e.to_dict() for e in self.events]}
        data["checksum"] = digest(_canonical(data))
        return data

    def to_json(self) -> str:
        return _canonical(self.to_dict())

    @classmethod
    def from_json(cls, text: str) -> Workflow:
        try:
            def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                output: dict[str, Any] = {}
                for key, value in pairs:
                    if key in output:
                        raise WorkflowError("duplicate checkpoint field")
                    output[key] = value
                return output
            data = json.loads(text, object_pairs_hook=no_duplicate_keys)
            if not isinstance(data, dict) or set(data) != {"version", "run_id", "network", "queue", "events", "checksum"}:
                raise WorkflowError("invalid checkpoint fields")
            if type(data["version"]) is not int or data["version"] != VERSION:
                raise WorkflowError("unsupported version")
            checksum = data.pop("checksum")
            _check_digest(checksum, "checkpoint checksum")
            if digest(_canonical(data)) != checksum:
                raise WorkflowError("checkpoint checksum mismatch")
            if not isinstance(data["events"], list):
                raise WorkflowError("invalid event list")
            fields = set(Event.__dataclass_fields__)
            events = []
            for row in data["events"]:
                if not isinstance(row, dict) or set(row) != fields:
                    raise WorkflowError("unexpected event fields")
                events.append(Event(**row))
            return cls(data["run_id"], data["network"], data["queue"], tuple(events))
        except (json.JSONDecodeError, TypeError, KeyError, OverflowError) as exc:
            raise WorkflowError("malformed checkpoint") from exc


def inspect_pipeline(network: str, pipelines: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Read-only adapter for mechanical_round.PIPELINES; no calls to commands.

    Returns only stage names and command *file basenames*, never arguments which
    can contain private handles or user-provided text. The classification is
    informational: it does not authorize a production action.
    """
    if network not in NETWORKS or network not in pipelines:
        raise WorkflowError("unknown or unsupported pipeline")
    spec = pipelines[network]
    queue = "MOBILE" if spec.get("phone") or network == "tiktok" else "WEB" if spec.get("browser") else "API"
    def names(commands: Any) -> list[str]:
        if commands is None:
            return []
        if not isinstance(commands, (list, tuple)):
            raise WorkflowError("invalid pipeline commands")
        result = []
        for cmd in commands:
            if not isinstance(cmd, (list, tuple)) or len(cmd) < 2 or not isinstance(cmd[1], str):
                raise WorkflowError("invalid command")
            result.append(cmd[1].replace("\\", "/").rsplit("/", 1)[-1])
        return result
    return {"network": network, "queue": queue,
            "steps": {"prepare": names(spec.get("pre", [])),
                      "plan": names([spec["build"]]) if spec.get("build") else [],
                      "execute": names([spec["execute"]]) if spec.get("execute") else [],
                      "post": names(spec.get("post", []))}}


def main(argv: list[str] | None = None) -> int:
    """Only the --inspect option exists; no live run or approval CLI."""
    import argparse
    parser = argparse.ArgumentParser(description="Read-only workflow skill inventory")
    parser.add_argument("--inspect", choices=sorted(NETWORKS), required=True)
    args = parser.parse_args(argv)
    from mechanical_round import PIPELINES  # imported only after explicit inspect
    if args.inspect not in PIPELINES:
        print(_canonical({"network": args.inspect, "status": "not-managed-by-mechanical_round"}))
        return 0
    print(_canonical(inspect_pipeline(args.inspect, PIPELINES)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

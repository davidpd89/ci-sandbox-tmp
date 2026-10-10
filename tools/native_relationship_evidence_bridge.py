"""Puentes de solo lectura: resultados nativos -> contrato RelationshipLedger (#84).

No importa ejecutores, no llama a redes, no altera el ActionLedger operativo.
El productor entrega un export INMUTABLE con IDs de fila estables.
"""
from __future__ import annotations

from collections.abc import Iterable
import json
from dataclasses import dataclass
from typing import Protocol

NETWORK_QUEUES = {
    "x": {"x_execute.run_plan": ("WEB",)},
    "threads": {"threads_execute.run_plan": ("WEB",), "threads_api.publish_reply": ("API",)},
    "facebook": {"facebook_execute.run_plan": ("WEB",)},
    "pinterest": {"pinterest_growth.cmd_run": ("WEB",), "pinterest_loyalty_observations": ("API",)},
    "reddit": {"reddit_execute.run_plan": ("WEB",)},
    "bluesky": {"bluesky_execute.run_plan": ("API",)},
    "mastodon": {"mastodon_execute.run_plan": ("API",)},
    "tiktok": {"tiktok_mobile_execute.run_plan": ("MOBILE",)},
    "instagram": {"instagram_execute.run_plan": ("WEB", "MOBILE")},
}
KINDS = {"follow": "follow", "unfollow": "unfollow", "like": "like",
         "like_latest": "like", "like_external": "like", "vote": "like", "favourite": "like",
         "favorite": "like", "comment": "comment", "comment_external": "comment",
         "reply": "reply", "boost": "repost", "quote": "repost",
         "repost": "repost", "visit": "visit"}
BASIS = {"WEB": {"ui_state"}, "API": {"api_response"},
         "MOBILE": {"mobile_observed"}}
# No se codifican alias dependientes del idioma para otros estados.
SUCCESSES = frozenset(("confirmado", "publicado"))


class LedgerSink(Protocol):
    def append_many(self, events: Iterable[dict]) -> dict: ...
    def reconcile_followers(self, **kwargs) -> dict: ...


@dataclass(frozen=True)
class Batch:
    network: str
    queue: str
    producer: str
    export_id: str

    def validate(self) -> None:
        if self.network not in NETWORK_QUEUES:
            raise ValueError("network desconocida")
        queues = NETWORK_QUEUES[self.network].get(self.producer)
        if not queues or self.queue not in queues:
            raise ValueError("productor/cola sin evidencia auditada")
        _id(self.export_id, "export_id")


def _id(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError(name + " ausente/inválido")
    if any(ord(char) < 32 for char in value):
        raise ValueError(name + " contiene controles")
    return value.strip()


def _target(item: dict, kind: str) -> tuple[str | None, str | None]:
    # Para acciones en posts se conserva la cuenta si se conoce. Si no,
    # la URI del destino es el sujeto; no se inventa una cuenta autora.
    handle = item.get("handle") or item.get("cuenta")
    post = item.get("url") or item.get("permalink") or item.get("post_url")
    target = handle if kind in ("follow", "unfollow", "followback") else post
    subject = handle or post
    if not isinstance(subject, str) or not subject.strip():
        return None, None
    if not isinstance(target, str) or not target.strip():
        return None, None
    return subject.strip(), target.strip()


def _outcome(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().casefold()
    if raw in SUCCESSES:
        return "confirmed"
    if raw.startswith("saltado_ya_"):
        return "observed"
    if raw.startswith(("saltado_", "omitido", "no_intentado", "listo_para_")):
        return "skipped"
    if raw.startswith(("pendiente_", "incierto", "parada:", "parada_")):
        return "uncertain"
    if raw.startswith(("fallo", "error", "rechazado_", "invalido:")):
        return "failed"
    return None


def _ack(item: dict, kind: str, target: str, queue: str) -> str | None:
    ack = item.get("ack")
    if not isinstance(ack, dict):
        return None
    try:
        ack_id = _id(ack.get("id"), "ack.id")
        ack_kind = KINDS.get(ack.get("kind"))
        ack_target = _id(ack.get("target"), "ack.target")
    except (TypeError, ValueError):
        return None
    if (ack_kind != kind or ack_target != target
            or ack.get("basis") not in BASIS[queue]):
        return None
    return ack_id


def bridge_results(ledger: LedgerSink, batch: Batch, records: Iterable[dict]) -> dict:
    """Normaliza solo registros con identidad, tiempo y resultado propios.

    El ID export_id/record_id representa una versión inmutable. Un ACK posterior
    es otro hecho append-only; no sobrescribe un 'unverified' anterior.
    """
    batch.validate()
    events, unknown, downgraded = [], {}, 0
    for index, item in enumerate(records):
        reason = None
        if not isinstance(item, dict):
            reason = "not_mapping"
        else:
            kind = KINDS.get(item.get("kind"))
            outcome = _outcome(item.get("resultado"))
            subject, target = _target(item, kind) if kind else (None, None)
            try:
                record_id = _id(item.get("record_id") or item.get("_intent_id"),
                                "record_id")
                if not isinstance(item.get("occurred_at"), str):
                    raise ValueError("occurred_at")
            except (ValueError, TypeError):
                record_id = None
            if not kind:
                reason = "kind"
            elif outcome is None:
                reason = "outcome"
            elif not subject or not target:
                reason = "identity"
            elif record_id is None:
                reason = "provenance_or_time"
            else:
                ack_id = _ack(item, kind, target, batch.queue) if outcome == "confirmed" else None
                if outcome == "confirmed" and ack_id is None:
                    outcome, downgraded = "unverified", downgraded + 1
                reservation = item.get("reservation_id")
                if reservation is not None:
                    reservation = _id(reservation, "reservation_id")
                correlation = ("reserve:" + reservation if reservation else "")
                if ack_id:
                    correlation += ("|" if correlation else "") + "ack:" + ack_id
                source_id = json.dumps([batch.export_id, record_id, "ack" if ack_id else "result", ack_id], ensure_ascii=False, separators=(",", ":"))
                events.append({
                    "network": batch.network, "queue": batch.queue,
                    "source": "native/" + batch.producer, "source_id": source_id,
                    "kind": kind, "outcome": outcome, "subject": subject,
                    "target_id": target, "occurred_at": item["occurred_at"],
                    "correlation_id": correlation or None,
                })
        if reason:
            unknown[reason] = unknown.get(reason, 0) + 1
    # append_many de #84 valida y confirma el lote atómicamente.
    stats = ledger.append_many(events)
    return {**stats, "unknown": sum(unknown.values()),
            "unknown_reasons": unknown, "downgraded_no_ack": downgraded}


def bridge_snapshot(ledger: LedgerSink, batch: Batch, snapshot: dict) -> dict:
    """Solo snapshots con identidades estables pueden crear observaciones.

    Sin paginación cerrada y ámbito acreditado nunca hay eventos 'absent'.
    Los contadores de Pinterest no permiten deducir identidades.
    """
    batch.validate()
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot inválido")
    coverage = snapshot.get("coverage")
    if not isinstance(coverage, dict) or coverage.get("identity_stable") is not True:
        return {"inserted": 0, "replayed": 0, "unknown": len(snapshot.get("tracked", [])),
                "reason": "identity_unverified"}
    tracked, followers = snapshot.get("tracked"), snapshot.get("followers")
    if (not isinstance(tracked, (list, tuple)) or
            not isinstance(followers, (list, tuple)) or
            any(not isinstance(x, str) or not x.strip() for x in tracked + followers)):
        raise ValueError("lista de identidades inválida")
    complete = (coverage.get("complete") is True and
                coverage.get("all_pages") is True and
                isinstance(coverage.get("account_scope"), str) and
                bool(coverage["account_scope"].strip()))
    snapshot_id = _id(snapshot.get("snapshot_id"), "snapshot_id")
    observed_at = _id(snapshot.get("observed_at"), "observed_at")
    # Pasar complete=False a #84 conserva positivos verificables y UNKNOWN.
    return ledger.reconcile_followers(
        network=batch.network, queue=batch.queue,
        snapshot_id=batch.export_id + "/" + snapshot_id,
        observed_at=observed_at, tracked=tracked, followers=followers,
        complete=complete, source="native/" + batch.producer + "/snapshot",
    )


def availability() -> list[dict]:
    """Matriz contractual; no declarar presencia en colas no auditadas."""
    return [{"network": network, "queue": queue, "producer": producer,
             "status": "source_identified_contract_only"}
            for network, producers in NETWORK_QUEUES.items()
            for producer, queues in producers.items() for queue in queues]

"""Contrato v2 de identidad de ensayos. Solo cálculo local, nunca acciones sociales.

Los hashes de manifests NO sustituyen una auditoría: TrustedRegistry debe
provenir de un registro local independiente, revisado por un controlador.
Nunca construirlo a partir del JSON agregado en producción.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re

VERSION = 2
DOMAIN = "rrss.cross-network-learning.verified-evidence.v2"
HASH = re.compile(r"^[0-9a-f]{64}$")
OPAQUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,63}$")
QUEUES = frozenset(("WEB", "API", "MOBILE"))
EVIDENCE_FIELDS = (
    "origin", "feature", "metric", "design", "outcome_link", "mature_days",
    "human_reviewed", "observed_on", "cohort_end",
    "baseline_nonfollowers_verified", "assignment_units_unique",
    "day14_snapshot_complete", "treatment", "control",
)
TARGET_FIELDS = ("queue", "capability", "permission", "implemented", "checked_on")
AUDIT_FIELDS = frozenset((
    "experiment_id", "design_sha256", "assignment_sha256", "assignment_count",
    "origin", "feature", "target", "queue",
))
REGISTRY_FIELDS = AUDIT_FIELDS | {"evidence_sha256"}


def _is_hash(value):
    return isinstance(value, str) and HASH.fullmatch(value) is not None


def audit_projection(row, target):
    """Campos que un auditor debe contrastar con un manifest de asignaciones."""
    if not isinstance(row, dict) or not isinstance(target, str):
        return None
    experiment = row.get("experiment")
    if (not isinstance(experiment, dict)
            or set(experiment) != {"id", "design_sha256", "assignment_sha256"}
            or not isinstance(experiment["id"], str)
            or OPAQUE.fullmatch(experiment["id"]) is None
            or not _is_hash(experiment["design_sha256"])
            or not _is_hash(experiment["assignment_sha256"])):
        return None
    targets = row.get("targets")
    if not isinstance(targets, dict):
        return None
    entry = targets.get(target)
    if not isinstance(entry, dict):
        return None
    queue = entry.get("queue")
    if not isinstance(queue, str) or queue not in QUEUES:
        return None
    a, b = row.get("treatment"), row.get("control")
    if not isinstance(a, dict) or not isinstance(b, dict):
        return None
    if type(a.get("n")) is not int or type(b.get("n")) is not int:
        return None
    count = a["n"] + b["n"]
    if not 0 < count <= 2_000_000:
        return None
    if not isinstance(row.get("origin"), str) or not isinstance(row.get("feature"), str):
        return None
    return {
        "experiment_id": experiment["id"],
        "design_sha256": experiment["design_sha256"],
        "assignment_sha256": experiment["assignment_sha256"],
        "assignment_count": count,
        "origin": row["origin"], "feature": row["feature"],
        "target": target, "queue": entry["queue"],
    }


def evidence_digest(row, target):
    """Compromiso SHA-256 por ensayo + procedencia + resultado + superficie.

    Dominio y versión explícitos; sin datos de usuarios en el informe.
    El hash solo liga bytes canónicos, no autentica el manifest por sí mismo.
    """
    audit = audit_projection(row, target)
    if audit is None:
        return None
    entry = row["targets"][target]
    content = {
        "domain": DOMAIN, "contract_schema": VERSION, "audit": audit,
        "evidence": {key: row.get(key) for key in EVIDENCE_FIELDS},
        "target_state": {key: entry.get(key) for key in TARGET_FIELDS},
    }
    try:
        raw = json.dumps(content, sort_keys=True, ensure_ascii=True,
                         separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError):
        return None
    if len(raw) > 16_384:
        return None
    return hashlib.sha256(raw).hexdigest()


class TrustedRegistry:
    """Snapshot de registros comprobados FUERA del JSON agregado.

    Es un límite de confianza del llamador, no un verificador criptográfico
    de autoría. No aceptar registros del mismo productor de agregados.
    """

    __slots__ = ("_entries",)

    def __init__(self, reviewed_records):
        if not isinstance(reviewed_records, (tuple, list)) or len(reviewed_records) > 200:
            raise ValueError("registro de auditoría inválido")
        records = {}
        assignments = {}
        for record in reviewed_records:
            if (not isinstance(record, dict) or set(record) != REGISTRY_FIELDS
                    or any(not isinstance(record[k], str)
                           for k in ("experiment_id", "origin", "feature", "target", "queue"))
                    or OPAQUE.fullmatch(record["experiment_id"]) is None
                    or record["queue"] not in QUEUES
                    or any(not _is_hash(record[k])
                           for k in ("design_sha256", "assignment_sha256", "evidence_sha256"))
                    or type(record["assignment_count"]) is not int
                    or not 0 < record["assignment_count"] <= 2_000_000):
                raise ValueError("registro de auditoría inválido")
            key = (record["experiment_id"], record["origin"], record["feature"],
                   record["target"], record["queue"])
            if key in records:
                raise ValueError("registro duplicado")
            manifest = record["assignment_sha256"]
            if manifest in assignments and assignments[manifest] != record["experiment_id"]:
                raise ValueError("manifest de asignaciones reutilizado entre ensayos")
            assignments[manifest] = record["experiment_id"]
            records[key] = dict(record)
        self._entries = records

    def approves(self, row, target):
        audit = audit_projection(row, target)
        if audit is None:
            return False
        key = (audit["experiment_id"], audit["origin"], audit["feature"],
               target, audit["queue"])
        record = self._entries.get(key)
        if record is None:
            return False
        digest = evidence_digest(row, target)
        return (digest is not None
                and all(record[k] == audit[k] for k in AUDIT_FIELDS)
                and hmac.compare_digest(record["evidence_sha256"], digest))

"""Read-only adapters for existing RRSS inbound/outbound and conversation rows.

Pass already loaded CSV rows; NO disk access, live account writes, or network I/O.
The original per-network policies keep their independent limits and recipients.
"""
from __future__ import annotations

from hashlib import sha256
from cross_network_identity import IdentityError, account_key

CONFIRMED = frozenset({"confirmado", "publicado"})
COMMENT_KINDS = frozenset({"reply", "comment", "comentario", "comment_external", "respuesta"})

def _normal_account(network, handle):
    return account_key(str(network or "").strip().casefold(), handle)

def adapt_inbound_rows(rows):
    """Adapt relationship_policy.log_inbound's fecha/red/handle/tipo schema.

    Its source ledger already coalesces one (day, network, handle, kind) record.
    Events therefore have that granularity, NOT raw per-interaction counts.
    """
    records, warnings = [], []
    for index, row in enumerate(rows):
        try:
            day, network, handle, kind = (row[k] for k in ("fecha", "red", "handle", "tipo"))
            account = _normal_account(network, handle)
            if not isinstance(day, str) or not day.strip() or not isinstance(kind, str) or not kind.strip():
                raise IdentityError("missing_inbound_fields")
            raw_id = "\x1f".join((day, network, account, kind))
            records.append({"account": account, "event_id": "in:" + sha256(raw_id.encode()).hexdigest(),
                            "direction": "inbound", "kind": kind})
        except (KeyError, TypeError, ValueError) as exc:
            warnings.append({"row": index, "reason": type(exc).__name__})
    return records, warnings

def adapt_outbound_rows(network, rows):
    """Adapt registro_interacciones.csv confirmed actions; preserve local scope.

    Row order is used only when no real unique event ID is recorded. In that
    case this is a per-file accounting view, NOT cross-run event deduplication.
    """
    records, warnings = [], []
    for index, row in enumerate(rows):
        try:
            if (row.get("resultado") or "").strip().casefold() not in CONFIRMED:
                continue
            handle, kind = row["cuenta"], row["tipo"]
            account = _normal_account(network, handle)
            if not isinstance(kind, str) or not kind.strip():
                raise IdentityError("missing_kind")
            event_id = row.get("event_id") or "row:" + str(index)
            if not isinstance(event_id, str):
                raise IdentityError("event_id_invalid")
            item = {"account": account, "event_id": "out:" + network + ":" + event_id,
                    "direction": "outbound", "kind": kind}
            ref = row.get("post_uri") or row.get("status_id") or row.get("url")
            if kind.strip().casefold() in COMMENT_KINDS and isinstance(ref, str) and ref:
                item["conversation_ref"] = ref
            records.append(item)
        except (KeyError, TypeError, ValueError) as exc:
            warnings.append({"row": index, "reason": type(exc).__name__})
    return records, warnings

def adapt_conversation_rows(network, rows):
    """Adapt verified conversation metadata; no message texts or reply synthesis."""
    records, warnings = [], []
    for index, row in enumerate(rows):
        try:
            account = _normal_account(network, row["handle"])
            ref = row["ref"]
            if not isinstance(ref, str) or not ref.strip():
                raise IdentityError("missing_ref")
            records.append({"account": account, "event_id": "conversation:" + network + ":" + ref,
                            "kind": "conversation", "direction": "inbound",
                            "conversation_ref": ref})
        except (KeyError, TypeError, ValueError) as exc:
            warnings.append({"row": index, "reason": type(exc).__name__})
    return records, warnings

def project_legacy(graph, account, *, inbound=(), outbound_by_network=None, conversations_by_network=None):
    """Combine synthetic/loaded rows only, retaining warnings for unresolved handles."""
    records, warnings = adapt_inbound_rows(inbound)
    for network, rows in (outbound_by_network or {}).items():
        extra, skipped = adapt_outbound_rows(network, rows)
        records.extend(extra)
        warnings.extend([{"source": network, **w} for w in skipped])
    for network, rows in (conversations_by_network or {}).items():
        extra, skipped = adapt_conversation_rows(network, rows)
        records.extend(extra)
        warnings.extend([{"source": network, **w} for w in skipped])
    return {"crm": graph.crm_view(account, records), "warnings": warnings}

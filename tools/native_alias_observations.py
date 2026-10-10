"""Strict read-only adapters for nine networks; no network, disk, or account I/O."""
from __future__ import annotations
from collections.abc import Iterable, Mapping
from stable_account_aliases import AliasTimeline, AliasError, NETWORKS

# Normalized provider evidence envelopes. Native producers must map their
# actual API/WEB/MOBILE fields to these names and verify IDs independently.
NATIVE_RULES = {
    "bluesky": ("handle", "did", "did_document_handle_verified", "did_bidirectional"),
    "mastodon": ("acct", "actor_uri", "actor_uri_confirmed", "actor_uri_confirmed"),
    **{n: ("handle", "remote_account_id", "remote_id_verified", "provider_account_id")
       for n in NETWORKS - {"bluesky", "mastodon"}},
}


def ingest_observations(network: str, rows: Iterable[Mapping],
                        *, timeline: AliasTimeline | None = None) -> dict:
    """Ingest synthetic/previously captured source rows, report redacted failures.

    An explicit boolean True is required; the string 'true' is NOT a proof.
    Returns in-memory timeline, accepted observation IDs, diagnostic reasons.
    """
    if network not in NATIVE_RULES:
        raise AliasError("network_invalid")
    if isinstance(rows, (str, bytes, Mapping)) or not isinstance(rows, Iterable):
        raise AliasError("rows_must_be_iterable_of_mappings")
    t = timeline if timeline is not None else AliasTimeline()
    if not isinstance(t, AliasTimeline):
        raise AliasError("timeline_invalid")
    handle_field, id_field, flag_field, verification = NATIVE_RULES[network]
    accepted, diagnostics = [], []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            diagnostics.append({"row": index, "reason": "row_invalid"})
            continue
        if "network" in row and row["network"] != network:
            diagnostics.append({"row": index, "reason": "network_mismatch"})
            continue
        if row.get(flag_field) is not True:
            diagnostics.append({"row": index, "reason": "native_identity_not_verified"})
            continue
        try:
            eid = t.observe(evidence_id=row["evidence_id"], network=network,
                            handle=row[handle_field], stable_id=row[id_field],
                            observed_at=row["observed_at"], queue=row["queue"],
                            source=row["source"], proof=row["proof"],
                            verification=verification)
        except KeyError:
            diagnostics.append({"row": index, "reason": "missing_required_field"})
        except AliasError as exc:
            diagnostics.append({"row": index, "reason": str(exc)})
        else:
            accepted.append(eid)
    return {"timeline": t, "accepted": accepted, "diagnostics": diagnostics}

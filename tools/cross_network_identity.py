"""Offline, read-only nine-network identity and CRM projection.

Identity groups NEVER replace per-network operational handles. API, browser and
mobile event IDs remain network-scoped; the snapshot ID is not a persistent CRM key.
"""
from __future__ import annotations

from hashlib import sha256
from identity_profiles import IdentityError, Profile, NETWORKS, account_key, canonical_url
from identity_graph import IdentityGraphBase, Match

class IdentityGraph(IdentityGraphBase):
    def crm_view(self, account: str, records: list[dict]) -> dict:
        """Project events from reciprocity/inbound logs and conversation references.

        Input mapping: account = network|handle, event_id = network-scoped remote
        event ID, kind = follow/comment/reply/etc., direction = inbound/outbound,
        optional conversation_ref = opaque per-network thread ID.
        Dedupe repeated observation by Web, API and Mobile using (account, event_id).
        Never writes to relationship_policy, loyalty or action_ledger.
        """
        group = self.cluster(account)
        unique, counts, conversations = set(), {}, set()
        for event in records:
            key = event.get("account")
            if key not in group:
                continue
            ident = event.get("event_id")
            kind, direction = event.get("kind"), event.get("direction")
            if (not isinstance(ident, str) or not ident or not isinstance(kind, str)
                    or not kind or direction not in {"inbound", "outbound"}):
                raise IdentityError("event_invalid")
            dedupe = (key, ident)
            if dedupe in unique:
                continue
            unique.add(dedupe)
            bucket = (key.split("|", 1)[0], direction, kind)
            counts[bucket] = counts.get(bucket, 0) + 1
            ref = event.get("conversation_ref")
            if ref:
                if not isinstance(ref, str):
                    raise IdentityError("conversation_ref_invalid")
                conversations.add((key, ref))
        return {
            "accounts": list(group),
            "entity_snapshot_id": "entity:" + sha256("\n".join(group).encode()).hexdigest()[:16],
            "events_by_network": [{"network": n, "direction": d, "kind": k, "count": v}
                                  for (n, d, k), v in sorted(counts.items())],
            "conversation_refs": [{"account": key, "ref": ref}
                                  for key, ref in sorted(conversations)],
        }

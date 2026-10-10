"""Reversible graph for cross-network links; purely in-memory."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from identity_profiles import IdentityError, Profile, valid_profile_url

@dataclass(frozen=True)
class Match:
    left: str
    right: str
    score: int
    status: str
    evidence: tuple[str, ...]

class IdentityGraphBase:
    def __init__(self):
        self.profiles: dict[str, Profile] = {}
        self.decisions: dict[tuple[str, str], tuple[str, str]] = {}

    def observe(self, profile: Profile) -> str:
        if not isinstance(profile, Profile):
            raise IdentityError("profile_required")
        if profile.key in self.profiles:
            old = self.profiles[profile.key]
            if old.stable_id and profile.stable_id and old.stable_id != profile.stable_id:
                raise IdentityError("stable_id_changed_requires_review")
        self.profiles[profile.key] = profile
        return profile.key

    def _pair(self, left: str, right: str) -> tuple[str, str]:
        if left not in self.profiles or right not in self.profiles or left == right:
            raise IdentityError("pair_invalid")
        return tuple(sorted((left, right)))

    def decide(self, left: str, right: str, *, same: bool, reason: str):
        pair = self._pair(left, right)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise IdentityError("review_reason_required")
        self.decisions[pair] = ("same" if same else "different", reason.strip())

    def revoke(self, left: str, right: str):
        self.decisions.pop(self._pair(left, right), None)

    def match(self, left: str, right: str) -> Match:
        pair = self._pair(left, right)
        a, b = (self.profiles[p] for p in pair)
        evidence = []
        a_points = b.profile_url and valid_profile_url(b) and b.profile_url in a.declared_links
        b_points = a.profile_url and valid_profile_url(a) and a.profile_url in b.declared_links
        if a_points and b_points and a.network != b.network and a.links_observed and b.links_observed:
            evidence.append("reciprocal_profile_links")
        elif a_points and b_points:
            evidence.append("unverified_reciprocal_links")
        elif a_points or b_points:
            evidence.append("one_way_profile_link")
        if a.website and b.website and a.website == b.website:
            evidence.append("shared_exact_website")
        if a.handle == b.handle:
            evidence.append("same_handle")
        if (a.display_name.strip() and b.display_name.strip() and
                min(SequenceMatcher(None, a.display_name.casefold(), b.display_name.casefold(), autojunk=False).ratio(),
                    SequenceMatcher(None, b.display_name.casefold(), a.display_name.casefold(), autojunk=False).ratio()) >= .92):
            evidence.append("similar_name")
        score = min(100, (100 if "reciprocal_profile_links" in evidence else 0) +
                    (55 if "one_way_profile_link" in evidence or "unverified_reciprocal_links" in evidence else 0) +
                    (15 if "shared_exact_website" in evidence else 0) +
                    (10 if "same_handle" in evidence else 0) +
                    (5 if "similar_name" in evidence else 0))
        decision = self.decisions.get(pair)
        status = ("confirmed" if decision[0] == "same" else "rejected") if decision else (
            "verified" if "reciprocal_profile_links" in evidence else
            "review" if score else "unrelated")
        return Match(*pair, score, status, tuple(evidence))

    def groups(self) -> list[tuple[str, ...]]:
        """Reject transitive grouping if any pair of members was marked different."""
        parent = {key: key for key in self.profiles}
        members = {key: {key} for key in self.profiles}
        denied = {pair for pair, (status, _) in self.decisions.items() if status == "different"}

        def root(x):
            while parent[x] != x:
                x = parent[x]
            return x

        edges = []
        keys = sorted(self.profiles)
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                m = self.match(a, b)
                if m.status in ("confirmed", "verified"):
                    edges.append((0 if m.status == "confirmed" else 1, -m.score, a, b))
        for _, _, a, b in sorted(edges):
            ra, rb = root(a), root(b)
            if ra == rb:
                continue
            if any(tuple(sorted((x, y))) in denied for x in members[ra] for y in members[rb]):
                continue
            parent[rb] = ra
            members[ra].update(members.pop(rb))
        return sorted(tuple(sorted(group)) for group in members.values())

    def conflicts(self) -> list[Match]:
        """Positive links omitted because of explicit negative evidence."""
        groups = self.groups()
        owner = {key: index for index, group in enumerate(groups) for key in group}
        keys = sorted(self.profiles)
        return [m for i, a in enumerate(keys) for b in keys[i + 1:]
                if (m := self.match(a, b)).status in {"confirmed", "verified"}
                and owner[a] != owner[b]]

    def cluster(self, account: str) -> tuple[str, ...]:
        if account not in self.profiles:
            raise IdentityError("unknown_account")
        return next(g for g in self.groups() if account in g)

    def candidates(self) -> list[Match]:
        keys = sorted(self.profiles)
        return sorted((m for i, a in enumerate(keys) for b in keys[i + 1:]
                       if (m := self.match(a, b)).status == "review"),
                      key=lambda m: (-m.score, m.left, m.right))

    def to_document(self) -> dict:
        return {"schema_version": 1,
                "profiles": [asdict(self.profiles[k]) for k in sorted(self.profiles)],
                "decisions": [{"left": a, "right": b, "status": status, "reason": reason}
                              for (a, b), (status, reason) in sorted(self.decisions.items())]}

    @classmethod
    def from_document(cls, data: dict):
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise IdentityError("unsupported_schema")
        graph = cls()
        for raw in data.get("profiles", []):
            profile = Profile(**raw)
            if profile.key in graph.profiles:
                raise IdentityError("duplicate_profile")
            graph.observe(profile)
        for raw in data.get("decisions", []):
            if raw["status"] not in ("same", "different"):
                raise IdentityError("invalid_decision")
            pair = graph._pair(raw["left"], raw["right"])
            if pair in graph.decisions:
                raise IdentityError("duplicate_decision")
            graph.decide(*pair, same=raw["status"] == "same", reason=raw["reason"])
        return graph

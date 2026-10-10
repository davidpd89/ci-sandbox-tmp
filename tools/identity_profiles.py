"""Normalized evidence profiles for nine social networks; no network requests."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlsplit, urlunsplit
import re

NETWORKS = frozenset({"x", "threads", "facebook", "pinterest", "reddit",
                      "bluesky", "mastodon", "tiktok", "instagram"})
DOMAINS = {
    "x": {"x.com", "twitter.com"}, "threads": {"threads.net", "threads.com"},
    "facebook": {"facebook.com", "www.facebook.com"},
    "pinterest": {"pinterest.com", "www.pinterest.com"},
    "reddit": {"reddit.com", "www.reddit.com"},
    "bluesky": {"bsky.app"}, "tiktok": {"tiktok.com", "www.tiktok.com"},
    "instagram": {"instagram.com", "www.instagram.com"},
}

class IdentityError(ValueError):
    pass

def canonical_url(value: str) -> str:
    """Conservative HTTPS normalization; does not follow redirects."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise IdentityError("url_invalid")
    try:
        u = urlsplit(value.strip())
        host = u.hostname
        if (u.scheme.lower() != "https" or not host or u.username or u.password
                or u.port is not None or u.query or u.fragment
                or any(c.isspace() for c in value)):
            raise IdentityError("url_invalid")
        host = host.encode("idna").decode("ascii").lower()
    except (ValueError, UnicodeError) as exc:
        raise IdentityError("url_invalid") from exc
    return urlunsplit(("https", host, u.path.rstrip("/"), "", ""))

def account_key(network: str, handle: str) -> str:
    if network not in NETWORKS or not isinstance(handle, str):
        raise IdentityError("network_or_handle_invalid")
    h = handle.strip().lstrip("@").casefold()
    if len(h) > 256 or not h or any(c.isspace() or c in "|/:?#\\" for c in h):
        raise IdentityError("handle_invalid")
    if network == "mastodon":
        parts = h.split("@")
        if len(parts) != 2 or not re.fullmatch(r"[a-z0-9_][a-z0-9_.-]*", parts[0]):
            raise IdentityError("mastodon_requires_fully_qualified_acct")
        if "." not in parts[1] or not re.fullmatch(r"[a-z0-9.-]+", parts[1]):
            raise IdentityError("mastodon_instance_invalid")
    elif "@" in h or not re.fullmatch(r"[\w.-]+", h, re.UNICODE):
        raise IdentityError("handle_invalid")
    return f"{network}|{h}"

@dataclass(frozen=True)
class Profile:
    network: str
    handle: str
    profile_url: str = ""
    display_name: str = ""
    website: str = ""
    declared_links: tuple[str, ...] = ()
    stable_id: str = ""
    links_observed: bool = False

    def __post_init__(self):
        key = account_key(self.network, self.handle)
        object.__setattr__(self, "handle", key.split("|", 1)[1])
        if self.profile_url:
            object.__setattr__(self, "profile_url", canonical_url(self.profile_url))
        if self.website:
            object.__setattr__(self, "website", canonical_url(self.website))
        if isinstance(self.declared_links, (str, bytes)):
            raise IdentityError("declared_links_must_be_sequence")
        links = tuple(sorted({canonical_url(link) for link in self.declared_links}))
        if len(links) > 100:
            raise IdentityError("too_many_links")
        object.__setattr__(self, "declared_links", links)
        if type(self.links_observed) is not bool:
            raise IdentityError("links_observed_must_be_bool")
        if not isinstance(self.display_name, str) or len(self.display_name) > 250:
            raise IdentityError("name_invalid")
        if not isinstance(self.stable_id, str) or len(self.stable_id) > 320:
            raise IdentityError("stable_id_invalid")

    @property
    def key(self) -> str:
        return account_key(self.network, self.handle)

def valid_profile_url(profile: Profile) -> bool:
    if not profile.profile_url:
        return False
    u = urlsplit(profile.profile_url)
    network, handle = profile.network, profile.handle
    if network == "mastodon":
        user, host = handle.split("@")
        return u.hostname == host and u.path == "/@" + user
    if u.hostname not in DOMAINS[network]:
        return False
    if network == "reddit":
        return u.path.casefold() == "/user/" + handle
    if network == "bluesky":
        return u.path.casefold() == "/profile/" + handle
    if network in {"tiktok", "threads"}:
        return u.path.casefold() == "/@" + handle
    return u.path.casefold() == "/" + handle

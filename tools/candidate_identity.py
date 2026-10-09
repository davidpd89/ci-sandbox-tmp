"""R1 / F11: identidad mínima explícita de candidatos, sin dependencias externas.

Solo se admiten dos esquemas verificados en el código del escáner API:
Mastodon (`acct`) y Bluesky (`handle`). Otras redes quedan fuera
hasta comprobar sus datos y conectarlas en sus propios ejecutores.
NO convierte un id de post, nombre o DID en un usuario/handle.
Los adaptadores deben llamar a resolve_author antes de tomar acciones sobre
una cuenta. Una identidad inválida se omite con alerta, nunca como None.
"""
from __future__ import annotations

from collections.abc import Mapping
import re

AUTHOR_FIELD = {
    "bluesky": "handle",  # bluesky_growth_scan.py _build_output: shortlist.append
    "mastodon": "acct",  # mastodon_growth_scan.py _build_output: shortlist.append
}

# IDs de posición que genera el scanner, NO IDs remotos de Mastodon.
_SCAN_ORDINAL = re.compile(r"^[GM][0-9]{3,}-P[0-9]+$", re.I)


def is_scan_ordinal(value):
    return isinstance(value, str) and _SCAN_ORDINAL.fullmatch(value) is not None


class CandidateIdentityError(ValueError):
    """No existe un identificador seguro de destinatario para la red."""


def resolve_author(network: str, candidate: Mapping) -> str:
    """Resuelve la identidad exacta de esta red, o falla con motivo legible.

    Sin fallback entre redes: un 'handle' auxiliar en Mastodon no sustituye
    a 'acct', y un 'acct' no sustituye al handle de Bluesky.
    Esta función no normaliza handles según convenciones de cada red.
    """
    if network not in AUTHOR_FIELD:
        raise CandidateIdentityError(f"red_no_admitida:{network}")
    if not isinstance(candidate, Mapping):
        raise CandidateIdentityError(f"{network}:candidato_no_es_mapa")
    field = AUTHOR_FIELD[network]
    value = candidate.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CandidateIdentityError(f"{network}:falta_{field}")
    author = value.strip()
    if "\n" in author or "\r" in author:
        raise CandidateIdentityError(f"{network}:{field}_contiene_salto_de_linea")
    if network == "bluesky":
        handle_pattern = r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?"
        if author.casefold() == "handle.invalid" or not re.fullmatch(handle_pattern, author.casefold()):
            raise CandidateIdentityError("bluesky:handle_invalido")
    elif not re.fullmatch(r"[a-z0-9_][a-z0-9_.-]*(?:@[a-z0-9.-]+)?", author.casefold()) or len(author) > 320:
        raise CandidateIdentityError("mastodon:acct_invalido")
    return author.casefold()


def resolve_post_ref(network, post):
    """Referencia remota estable, no el ID ordinal del scan."""
    if network not in AUTHOR_FIELD or not isinstance(post, Mapping):
        raise CandidateIdentityError("red_o_post_invalido")
    if network == "bluesky":
        uri = post.get("uri")
        if not isinstance(uri, str) or not re.fullmatch(r"at://did:[a-z0-9]+:[A-Za-z0-9._:%-]+/app\.bsky\.feed\.post/[A-Za-z0-9._~-]+", uri):
            raise CandidateIdentityError("bluesky:uri_post_invalida")
        return uri
    status_id = post.get("status_id")
    if isinstance(status_id, bool) or not isinstance(status_id, (str, int)) or not str(status_id).strip():
        raise CandidateIdentityError("mastodon:status_id_invalido")
    value = str(status_id)
    if len(value) > 256 or any(ch.isspace() for ch in value) or is_scan_ordinal(value):
        raise CandidateIdentityError("mastodon:status_id_invalido")
    return value


def resolve_stable_account(network, candidate):
    """Identidad auxiliar; no sustituye al acct/handle operativo."""
    if not isinstance(candidate, Mapping):
        return None
    if network == "bluesky":
        did = candidate.get("did")
        if isinstance(did, str) and did.startswith(("did:plc:", "did:web:")) and len(did) < 250 and not any(ch.isspace() for ch in did):
            return "bluesky:" + did
    elif network == "mastodon":
        account_id, instance = candidate.get("account_id"), candidate.get("instance")
        if isinstance(account_id, (str, int)) and not isinstance(account_id, bool) and isinstance(instance, str):
            account_id = str(account_id)
            if account_id and len(account_id) <= 256 and instance and "." in instance and all(ch.isalnum() or ch in ".-" for ch in instance):
                return f"mastodon:{instance.lower()}:{account_id}"
    return None

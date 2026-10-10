"""Controles puros de calidad de descubrimiento, reutilizables por otras redes.

No consultan cuentas ni publican. Una repetición solo es sospechosa si procede
de autores distintos y solicita algo; nunca se premian impresiones duplicadas.
"""
from __future__ import annotations

from collections import defaultdict
import re
import sqlite3
import unicodedata

_SOLICITATION = re.compile(
    r"\b(busco|buscamos|contrat\w*|empleo|trabaj\w*|presupuesto|salario|"
    r"pagamos|ofrezco|ofrecemos|escribeme|envia\w*|solicita\w*|gana dinero)\b"
)
_JOB = re.compile(r"\b(hablante\w*|nativ\w*|traductor\w*|traduccion\w*|espanol\w*|idioma\w*)\b")
_MONEY = re.compile(r"\b(presupuesto|pago\w*|pagamos|salario\w*|dolares|usd|eur\w*|moneda)\b")
_WORD = re.compile(r"[^a-z0-9 ]+")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def normalized(text):
    value = unicodedata.normalize("NFKD", str(text or "").casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"https?://\S+", " enlace ", value)
    value = value.replace("$", " moneda ").replace("€", " moneda ")
    value = _NUMBER.sub(" cifra ", value)
    return " ".join(_WORD.sub(" ", value).split())


def job_bait(text):
    """Rechazo conservador de ofertas de hablante nativo con presupuesto."""
    text = normalized(text)
    return bool(_SOLICITATION.search(text) and _JOB.search(text)
                and _MONEY.search(text))


def blocked_handles(rows, *, min_accounts=3):
    """Recibe dicts con handle/text o tuplas (handle, url, texto, fuente).

    Una campaña es >=3 autores con una petición sustantiva prácticamente
    idéntica; un mismo autor repetido 20 veces no cuenta como 20 autores.
    """
    groups = defaultdict(set)
    blocked = set()
    for row in rows:
        if isinstance(row, dict):
            handle, text = row.get("handle"), row.get("text")
        elif isinstance(row, (tuple, list)) and len(row) >= 3:
            handle, text = row[0], row[2]
        else:
            continue
        handle = str(handle or "").strip().lstrip("@").casefold()
        if not handle:
            continue
        body = normalized(text)
        if job_bait(text):
            blocked.add(handle)
        if len(body) >= 55 and len(body.split()) >= 10 and _SOLICITATION.search(body):
            groups[body].add(handle)
    for accounts in groups.values():
        if len(accounts) >= min_accounts:
            blocked.update(accounts)
    return blocked


def quarantined_pool_handles(db):
    """Consulta posts y perfiles históricos sin escribir ni alterar el estado.

    Incluye publicaciones ya actuadas: el mismo autor puede tener perfiles
    pendientes de follow aunque sus posts antiguos estén marcados como vistos.
    """
    posts = [(handle, None, text) for handle, text in db.execute(
        "SELECT handle, text FROM posts")]
    profiles = [(handle, None, f"{name or ''} {bio or ''}")
                for handle, name, bio in db.execute(
                    "SELECT handle, display, bio FROM accounts")]
    blocked = blocked_handles(posts + profiles)
    try:
        blocked.update(str(handle).lstrip("@").casefold() for (handle,) in db.execute(
            "SELECT handle FROM thread_discovery_quarantine"))
    except sqlite3.OperationalError as exc:
        # Compatibilidad con bases antiguas/fixtures, no ocultar otros SQL.
        if "no such table" not in str(exc).casefold():
            raise
    return blocked


def source_family(source):
    """Cohorte comparable, sin inventar permiso, visita o seguidor causal."""
    family = str(source or "").split(":", 1)[0].casefold()
    return family if family in {"feed", "search", "recent", "profiles",
                               "followers", "backfollow"} else "unknown"


def cohort_counts(rows, *, first_touch=None):
    """Solo primeras fuentes PERSISTIDAS; sin tabla no se inventa procedencia."""
    first_touch = first_touch or {}
    seen, counts = set(), defaultdict(int)
    known = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        handle = str(row.get("handle") or "").lstrip("@").casefold()
        if not handle or handle in seen:
            continue
        seen.add(handle)
        origin = first_touch.get(handle)
        if origin:
            known += 1
        counts[source_family(origin)] += 1
    return {"candidatos_unicos": dict(sorted(counts.items())),
            "origen_estable_verificado": known,
            "sin_origen_estable": len(seen) - known,
            "visitas_atribuidas": None, "seguidores_atribuidos": None}

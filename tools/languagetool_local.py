"""Auditoría editorial opcional vía servidor LanguageTool LOCAL (LGPL-2.1).

No inicia Java, no envía texto a Internet, no modifica borradores ni publica.
Solo se usa al invocar audit() con endpoint loopback explícito.
Implementación propia del contrato HTTP /v2/check; no se copia código ajeno.
"""
from __future__ import annotations

import argparse
import json
import re
from urllib import error, parse, request

NETWORKS = frozenset({
    "x", "threads", "facebook", "pinterest", "reddit",
    "bluesky", "mastodon", "tiktok", "instagram",
})
MAX_RESPONSE_BYTES = 1024 * 1024
PROTECTED = re.compile(
    r"```[\s\S]*?```|`[^`\n]*`|!?\[[^\]\n]+\]\([^\)\n]+\)|"
    r"https?://[^\s<>«»]+|www\.[^\s<>«»]+|"
    r"(?<!\w)@[\w.]+|(?<!\w)#[\wáéíóúüñÁÉÍÓÚÜÑ]+|"
    r"«[^»\n]*»|“[^”\n]*”|\"[^\"\n]*\"", re.UNICODE,
)


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _checked_endpoint(endpoint: str) -> str:
    """Solo /v2/check en loopback literal; rechaza proxies y redirecciones."""
    if not isinstance(endpoint, str):
        raise ValueError("endpoint debe ser texto")
    parts = parse.urlsplit(endpoint)
    if (parts.scheme != "http" or parts.username is not None or
            parts.password is not None or parts.path != "/v2/check" or
            parts.query or parts.fragment or not parts.hostname):
        raise ValueError("endpoint debe ser HTTP loopback /v2/check")
    try:
        if parts.hostname not in ("127.0.0.1", "::1") or parts.port is None:
            raise ValueError("endpoint remoto o sin puerto")
    except (ValueError, TypeError) as exc:
        raise ValueError("endpoint loopback/puerto inválido") from exc
    return endpoint


def _utf16_to_codepoint(text: str, index: int) -> int | None:
    """Traduce offsets UTF-16 Java a índices Python sin partir emojis."""
    if type(index) is not int or index < 0:
        return None
    units = 0
    for pos, char in enumerate(text):
        if units == index:
            return pos
        units += 2 if ord(char) > 0xFFFF else 1
        if units > index:
            return None
    return len(text) if units == index else None


def _inside_protected(text: str, start: int, end: int) -> bool:
    return any(start < match.end() and end > match.start()
               for match in PROTECTED.finditer(text))


def _safe_matches(payload: object, text: str) -> list[dict]:
    """Normaliza matches sin enviar a logs ni publicar datos originales."""
    if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
        raise ValueError("respuesta sin matches")
    findings = []
    for match in payload["matches"][:500]:
        if not isinstance(match, dict):
            continue
        offset, length = match.get("offset"), match.get("length")
        if type(offset) is not int or type(length) is not int or length <= 0 or offset < 0:
            continue
        start = _utf16_to_codepoint(text, offset)
        end = _utf16_to_codepoint(text, offset + length)
        if start is None or end is None or start >= end or _inside_protected(text, start, end):
            continue
        rule = match.get("rule") or {}
        if not isinstance(rule, dict):
            rule = {}
        category = rule.get("category") or {}
        if not isinstance(category, dict):
            category = {}
        replacements = match.get("replacements") or []
        suggestions = ([x["value"] for x in replacements[:3]
                        if isinstance(x, dict) and isinstance(x.get("value"), str)]
                       if isinstance(replacements, list) else [])
        findings.append({
            "start": start, "end": end,
            "rule_id": str(rule.get("id") or "unknown")[:100],
            "category": str(category.get("id") or "unknown")[:100],
            "suggestions": suggestions,
        })
    return sorted(findings, key=lambda x: (x["start"], x["end"], x["rule_id"]))


def audit(text: str, *, network: str, endpoint: str | None = None,
          timeout: float = 1.5, transport=None) -> dict:
    """Revisión no destructiva; por defecto no hay llamadas a red ni a Java.

    transport(req, timeout) se puede inyectar para tests offline.
    No se invoca desde los escritores ni desde los publicadores.
    """
    if not isinstance(text, str):
        raise TypeError("text debe ser str")
    if not isinstance(network, str) or network not in NETWORKS:
        raise ValueError("red desconocida")
    result = {"schema_version": 1, "network": network, "changed": False,
              "status": "disabled", "findings": []}
    if endpoint is None or not text.strip():
        return result
    endpoint = _checked_endpoint(endpoint)
    if not 0 < timeout <= 10:
        raise ValueError("timeout fuera de rango")
    data = parse.urlencode({"text": text, "language": "es-ES"}).encode("utf-8")
    req = request.Request(endpoint, data=data, method="POST",
                          headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                                   "Accept": "application/json"})
    opener = transport or request.build_opener(request.ProxyHandler({}), _NoRedirect()).open
    try:
        with opener(req, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("respuesta demasiado grande")
        result["findings"] = _safe_matches(json.loads(raw.decode("utf-8")), text)
        result["status"] = "ok"
    except (error.URLError, OSError, ValueError, UnicodeError, TypeError):
        result["status"] = "unavailable"
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Auditoría de español solo en servidor local")
    parser.add_argument("--network", required=True, choices=sorted(NETWORKS))
    parser.add_argument("--endpoint", help="http://127.0.0.1:8081/v2/check")
    parser.add_argument("--text", required=True, help="Solo texto propio/autorizado")
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.text, network=args.network, endpoint=args.endpoint),
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

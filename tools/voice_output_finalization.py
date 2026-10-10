"""Preflight de voz en el último punto propio anterior a enviar.

Consume EXCLUSIVAMENTE spanish_voice_quality.audit, ya incorporado a la
base sincronizada. No se corrige ni reescribe ninguna cadena; los hallazgos
editoriales son informativos, y un fallo técnico inesperado cancela el
preflight sin emitir acciones remotas.
"""
from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module
import re

NETWORKS = frozenset({
    "x", "threads", "facebook", "pinterest", "reddit",
    "bluesky", "mastodon", "tiktok", "instagram",
})
QUEUES = frozenset({"WEB", "API", "MOBILE"})
# Los códigos se registran sin contenido; rechazar IDs maliciosos o excesivos.
CODE_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
LEVELS = frozenset({"error", "warning", "hint"})


class VoicePreflightUnavailable(RuntimeError):
    """No se pudo obtener un diagnóstico válido; la salida no debe enviarse."""


def _valid_finding(finding: object, text_length: int) -> bool:
    """Validar offsets Unicode y esquema para que el logger no filtre texto."""
    if not isinstance(finding, dict):
        return False
    code, severity = finding.get("code"), finding.get("severity")
    start, end, advice = (finding.get("start"), finding.get("end"),
                          finding.get("advice"))
    return (isinstance(code, str) and CODE_NAME.fullmatch(code) is not None
            and isinstance(severity, str) and severity in LEVELS
            and type(start) is int and type(end) is int
            and 0 <= start <= end <= text_length
            and isinstance(advice, str))


def inspect(text: str, *, network: str, queue: str | None, log=print) -> list[dict]:
    """Una auditoría por campo. No devuelve ni registra texto original.

    Los findings no vetan publicaciones. Los errores del motor o un esquema
    inesperado sí impiden que el llamador pase al clic/API irreversible.
    """
    if not isinstance(text, str):
        raise TypeError("texto de salida no es str")
    if network not in NETWORKS or (queue is not None and queue not in QUEUES):
        raise ValueError("red/cola de salida desconocida")
    try:
        audit = import_module("spanish_voice_quality").audit
    except (ImportError, AttributeError) as exc:
        raise VoicePreflightUnavailable(
            "No está disponible la API spanish_voice_quality.audit"
        ) from exc
    try:
        outcome = audit(text, network=network, queue=queue)
    except Exception as exc:
        raise VoicePreflightUnavailable(
            "El auditor de voz no pudo ejecutarse: " + type(exc).__name__
        ) from exc
    if (not isinstance(outcome, dict) or outcome.get("schema_version") != 1 or outcome.get("network") != network
            or outcome.get("queue") != queue or outcome.get("changed") is not False
            or not isinstance(outcome.get("findings"), list)
            or any(not _valid_finding(f, len(text)) for f in outcome["findings"])):
        raise VoicePreflightUnavailable("Contrato inesperado del auditor de voz")
    findings = outcome["findings"]
    if findings:
        codes = ",".join(sorted({f["code"] for f in findings}))
        try:
            log("[voz] revision_es " + network + "/" + (queue or "MANUAL") + ": " + codes)
        except Exception:
            pass  # un fallo del logger no es un fallo del auditor
    return findings


def inspect_fields(fields: Mapping[str, str], *, network: str,
                   queue: str | None, log=print) -> dict[str, list[dict]]:
    """Campos independientes; no convertir ni recortar texto ni copiar findings."""
    if not isinstance(fields, Mapping):
        raise TypeError("campos de salida inválidos")
    # Evita un primer resultado/log válido seguido de un segundo campo de tipo
    # inválido. Un fallo del auditor más tarde sigue propagándose sin resultado.
    for field, text in fields.items():
        if not isinstance(field, str):
            raise TypeError("campo de salida inválido")
        if not isinstance(text, str):
            raise TypeError("texto de salida no es str")
    result = {}
    for field, text in fields.items():
        if text:  # La validación de obligatoriedad corresponde al publicador.
            result[field] = inspect(text, network=network, queue=queue, log=log)
    return result

"""Preflight de voz en el último punto propio anterior a enviar.

Consume EXCLUSIVAMENTE spanish_voice_quality.audit de la PR #79. El módulo
upstream se integrará antes de activar esta rama. No se corrige ni reescribe
ninguna cadena; los hallazgos editoriales son informativos, y un fallo técnico
inesperado cancela el preflight sin emitir acciones remotas.
"""
from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module

NETWORKS = frozenset({
    "x", "threads", "facebook", "pinterest", "reddit",
    "bluesky", "mastodon", "tiktok", "instagram",
})
QUEUES = frozenset({"WEB", "API", "MOBILE"})


class VoicePreflightUnavailable(RuntimeError):
    """No se pudo obtener un diagnóstico válido; la salida no debe enviarse."""


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
    except ImportError as exc:
        raise VoicePreflightUnavailable(
            "Falta dependencia de QA de voz: integrar PR #79 primero"
        ) from exc
    try:
        outcome = audit(text, network=network, queue=queue)
    except Exception as exc:
        raise VoicePreflightUnavailable(
            "El auditor de voz no pudo ejecutarse: " + type(exc).__name__
        ) from exc
    if (not isinstance(outcome, dict) or outcome.get("changed") is not False
            or not isinstance(outcome.get("findings"), list)
            or any(not isinstance(f, dict) or not isinstance(f.get("code"), str)
                   for f in outcome["findings"])):
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
    result = {}
    for field, text in fields.items():
        if not isinstance(field, str):
            raise TypeError("campo de salida inválido")
        if not isinstance(text, str):
            raise TypeError("texto de salida no es str")
        if text:  # ausente significa que no existe ese campo, no que sea inválido
            result[field] = inspect(text, network=network, queue=queue, log=log)
    return result

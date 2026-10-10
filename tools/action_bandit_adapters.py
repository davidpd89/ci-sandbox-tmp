"""Traducción de acciones nativas a un contrato común; sin llamadas a redes.

El adaptador NO supone que una función esté disponible: exige que el productor
certifique expresamente capacidad y elegibilidad en cada evento de entrada.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from action_bandit import Candidate, Observation, NETWORKS

# Nombres operativos locales; no es una declaración de capacidades reales.
ACTION_LABELS = {
    "x": {"follow": "follow", "reply": "reply", "retweet": "repost"},
    "threads": {"follow": "follow", "reply": "reply", "repost": "repost"},
    "facebook": {"follow": "follow", "comment": "reply", "share": "repost"},
    "pinterest": {"follow": "follow", "comment": "reply", "save": "repost"},
    "reddit": {"follow": "follow", "comment": "reply", "crosspost": "repost"},
    "bluesky": {"follow": "follow", "reply": "reply", "repost": "repost"},
    "mastodon": {"follow": "follow", "reply": "reply", "reblog": "repost"},
    "tiktok": {"follow": "follow", "comment": "reply", "repost": "repost"},
    "instagram": {"follow": "follow", "comment": "reply", "share": "repost"},
}
assert set(ACTION_LABELS) == NETWORKS


def canonical_action(network: str, local_action: str, *, capability_verified: bool) -> str:
    if type(capability_verified) is not bool or not capability_verified:
        raise ValueError("capacidad no verificada por el adaptador")
    if network not in NETWORKS:
        raise ValueError("red desconocida")
    try:
        return ACTION_LABELS[network][local_action]
    except (KeyError, TypeError):
        raise ValueError("acción nativa no cubierta por el adaptador") from None


def candidate_from_native(data: Mapping) -> Candidate:
    """No usa métricas inferidas: el productor aporta cada feature [0,1]."""
    if not isinstance(data, Mapping):
        raise ValueError("evento malformado")
    network = data.get('network')
    action = canonical_action(network, data.get('native_action'),
                              capability_verified=data.get('capability_verified'))
    return Candidate(candidate_id=data['candidate_id'], network=network, action=action,
                     affinity=data['affinity'], activity=data['activity'],
                     conversation=data['conversation'], source_quality=data['source_quality'],
                     eligible=data.get('eligible', False))


def observation_from_native(data: Mapping) -> Observation:
    """Solo traduce evidencia; no transforma silenciosamente ausencia en cero."""
    if not isinstance(data, Mapping):
        raise ValueError("observación malformada")
    network = data.get('network')
    action = canonical_action(network, data.get('native_action'),
                              capability_verified=data.get('capability_verified'))
    if any(type(data.get(name)) is not date for name in ('performed_on', 'observed_on')):
        raise ValueError("fechas locales explícitas obligatorias")
    return Observation(event_id=data['event_id'], network=network, action=action,
                       affinity=data['affinity'], activity=data['activity'],
                       conversation=data['conversation'], source_quality=data['source_quality'],
                       performed_on=data['performed_on'], observed_on=data['observed_on'],
                       window_days=data['window_days'], reciprocity=data.get('reciprocity'),
                       engagement=data.get('engagement'),
                       sustained_conversation=data.get('sustained_conversation'),
                       coverage=data['coverage'], provenance=data['provenance'],
                       confirmed_action=data.get('confirmed_action', False))

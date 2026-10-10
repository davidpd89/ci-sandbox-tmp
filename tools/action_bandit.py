"""Ranking experimental offline para nueve redes; no ejecuta ninguna acción.

Adaptación de MABWiser (Apache-2.0) por dependencia opcional, no copia de código.
El modelo nunca convierte falta de observación en fracaso ni modifica planes.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from math import isfinite

NETWORKS = frozenset((
    "bluesky", "mastodon", "x", "threads", "facebook", "pinterest",
    "reddit", "tiktok", "instagram",
))
ACTIONS = ("follow", "reply", "repost")
WINDOWS = frozenset((1, 3, 7))
MIN_EVENTS = 300
MIN_PER_ARM = 30
REWARD_WEIGHTS = (0.45, 0.35, 0.20)  # reciprocidad, engagement, conversación
ACTION_PRIORS = {"follow": 0.02, "reply": 0.04, "repost": 0.0}


@dataclass(frozen=True)
class Candidate:
    candidate_id: str   # opaco; no requiere ni publica handles ni texto
    network: str
    action: str
    affinity: float
    activity: float
    conversation: float
    source_quality: float
    eligible: bool = True  # veto externo: no se reinterpreta aquí


@dataclass(frozen=True)
class Observation:
    event_id: str
    network: str
    action: str
    affinity: float
    activity: float
    conversation: float
    source_quality: float
    performed_on: date
    observed_on: date
    window_days: int
    reciprocity: float | None
    engagement: float | None
    sustained_conversation: float | None
    coverage: str              # complete / partial / unavailable
    provenance: str            # audited_api / complete_snapshot / synthetic
    confirmed_action: bool = True


@dataclass(frozen=True)
class Ranking:
    candidate: Candidate
    score: float
    policy: str
    mature_events: int


def _unit(value: float) -> float:
    if type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= 1:
        raise ValueError("señal fuera de [0,1] o no finita")
    return float(value)


def _features(row: Candidate | Observation) -> list[float]:
    return [1.0, *(_unit(getattr(row, name)) for name in (
        "affinity", "activity", "conversation", "source_quality"))]


def _identity(network: str, action: str) -> None:
    if network not in NETWORKS or action not in ACTIONS:
        raise ValueError("red o acción no reconocida")


def validated_reward(item: Observation, *, as_of: date,
                     allow_synthetic: bool = False) -> float | None:
    """Solo recompensa D+7, madura y completa. None significa desconocido.

    Los snapshots sin cobertura total y D+1/D+3 no alimentan el modelo.
    La procedencia es una declaración del adaptador, NO prueba de confianza.
    """
    _identity(item.network, item.action)
    _features(item)
    if not isinstance(item.event_id, str) or not item.event_id.strip():
        raise ValueError("event_id vacío")
    if type(as_of) is not date or type(item.performed_on) is not date or type(item.observed_on) is not date:
        raise ValueError("fecha no válida: usar date local explícita")
    if type(item.window_days) is not int or item.window_days not in WINDOWS:
        raise ValueError("ventana no reconocida")
    if (item.observed_on - item.performed_on).days != item.window_days:
        raise ValueError("la fecha de observación no coincide con el hito")
    if item.performed_on > as_of:
        raise ValueError("acción posterior a fecha de corte")
    if item.coverage not in ("complete", "partial", "unavailable"):
        raise ValueError("cobertura desconocida")
    if item.provenance not in ("audited_api", "complete_snapshot", "synthetic"):
        raise ValueError("procedencia no reconocida")
    if type(item.confirmed_action) is not bool:
        raise ValueError("confirmación no booleana")
    for value in (item.reciprocity, item.engagement, item.sustained_conversation):
        if value is not None:
            _unit(value)
    if (item.observed_on > as_of or item.window_days != 7
            or item.coverage != "complete" or not item.confirmed_action
            or item.provenance == "synthetic" and not allow_synthetic
            or None in (item.reciprocity, item.engagement, item.sustained_conversation)):
        return None
    return sum(w * float(value) for w, value in zip(
        REWARD_WEIGHTS,
        (item.reciprocity, item.engagement, item.sustained_conversation),
    ))


def _prior(row: Candidate) -> float:
    return min(1.0, 0.55 * row.affinity + 0.20 * row.activity
               + 0.15 * row.conversation + 0.10 * row.source_quality
               + ACTION_PRIORS[row.action])


def _mabwiser_factory(seed: int):
    """Usa la implementación original de MABWiser 2.7.4, sin vendoring."""
    from mabwiser.mab import MAB, LearningPolicy
    return MAB(arms=list(ACTIONS),
               learning_policy=LearningPolicy.LinUCB(alpha=0.25, l2_lambda=1.0),
               seed=seed, n_jobs=1)


def rank_candidates(candidates: list[Candidate], observations: list[Observation],
                    *, as_of: date, seed: int = 116,
                    allow_synthetic: bool = False, model_factory=None) -> list[Ranking]:
    """Clasifica de forma reproducible sin seleccionar, registrar ni actuar.

    El modelo necesita >=300 observaciones D+7 verificadas por red, al menos
    30 por brazo. Hasta entonces se conserva el orden heurístico común.
    `model_factory` solo permite sustituir MABWiser en pruebas offline.
    """
    if type(as_of) is not date or type(seed) is not int or not isinstance(candidates, list) or not isinstance(observations, list):
        raise ValueError("parámetros inválidos")
    seen_candidates = set()
    networks = set()
    for row in candidates:
        if not isinstance(row, Candidate):
            raise ValueError("candidato inválido")
        _identity(row.network, row.action)
        _features(row)
        if not isinstance(row.candidate_id, str) or not row.candidate_id.strip() or type(row.eligible) is not bool:
            raise ValueError("identificador o elegibilidad inválido")
        key = (row.network, row.candidate_id, row.action)
        if key in seen_candidates:
            raise ValueError("candidato repetido")
        seen_candidates.add(key)
        networks.add(row.network)
    history: dict[str, list[tuple[Observation, float]]] = {net: [] for net in networks}
    seen_events = set()
    for event in observations:
        if not isinstance(event, Observation):
            raise ValueError("observación inválida")
        key = (event.network, event.event_id, event.window_days)
        if key in seen_events:
            raise ValueError("event_id duplicado en la misma ventana")
        seen_events.add(key)
        reward = validated_reward(event, as_of=as_of, allow_synthetic=allow_synthetic)
        if reward is not None and event.network in history:
            history[event.network].append((event, reward))
    models = {}
    for network, rows in history.items():
        counts = Counter(event.action for event, _ in rows)
        if len(rows) < MIN_EVENTS or any(counts[action] < MIN_PER_ARM for action in ACTIONS):
            continue
        try:
            model = model_factory(seed) if model_factory is not None else _mabwiser_factory(seed)
        except ImportError:
            continue  # dependencia opcional: no se simula un modelo entrenado
        model.fit([event.action for event, _ in rows],
                  [reward for _, reward in rows],
                  [_features(event) for event, _ in rows])
        models[network] = model
    output = []
    for row in candidates:
        if not row.eligible:
            continue  # ningún modelo puede reabrir un veto de candidato
        score, policy = _prior(row), "prior"
        model = models.get(row.network)
        if model is not None:
            prediction = model.predict_expectations([_features(row)])
            if isinstance(prediction, list):
                prediction = prediction[0] if len(prediction) == 1 else {}
            learned = prediction.get(row.action) if isinstance(prediction, dict) else None
            if type(learned) in (int, float) and isfinite(learned):
                score = 0.60 * score + 0.40 * max(0., min(1., learned))
                policy = "mabwiser_linucb"
        output.append(Ranking(row, round(score, 6), policy, len(history[row.network])))
    return sorted(output, key=lambda item: (-item.score, item.candidate.network,
                                            item.candidate.candidate_id, item.candidate.action))

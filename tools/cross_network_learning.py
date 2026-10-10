"""Solo evaluación offline de hipótesis entre redes. Nunca modifica cuentas ni colas.

Los agregados legacy de #49 son cobertura parcial, NO ensayos con control.
Ningún campo de un JSON de entrada acredita permisos reales por sí solo.
Cada permiso/capacidad de destino queda además ligado a UNA cola concreta.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import stat
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from discovery_attribution import NETWORKS as OBSERVABLE_NETWORKS, STATE_ADAPTERS
from growth_attribution import wilson
from experiment_evidence_lineage import TrustedRegistry

# No ampliar superficies por arrastre de otro módulo; Instagram sigue fuera.
NETWORKS = frozenset((
    "bluesky", "mastodon", "x", "threads", "facebook",
    "pinterest", "reddit", "tiktok",
)) & OBSERVABLE_NETWORKS
QUEUES = frozenset(("WEB", "API", "MOBILE"))

FEATURES = frozenset(("hashtag_search", "account_search", "community_hubs",
                      "reply_questions", "micro_replies"))
METRIC = "new_follower_day14"
# Suelo de política, no cálculo de potencia. La separación Wilson al 95 % y la
# revisión humana siguen siendo requisitos adicionales; ver informe de PR #3.
MIN_N = 40
FRESH_DAYS = 30
TARGET_TTL_DAYS = 30
MAX_INPUT_BYTES = 256_000


def _local_today():
    """Fecha civil de Madrid, independiente del huso horario del runner."""
    return dt.datetime.now(ZoneInfo("Europe/Madrid")).date()


def _date(value):
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        value_date = dt.date.fromisoformat(value)
        return value_date if value_date.isoformat() == value else None
    except ValueError:
        return None


def _valid_arm(arm):
    return (isinstance(arm, dict) and set(arm) == {"n", "successes"}
            and type(arm["n"]) is int and MIN_N <= arm["n"] <= 1_000_000
            and type(arm["successes"]) is int and 0 <= arm["successes"] <= arm["n"])


def _queue(entry):
    if not isinstance(entry, dict):
        return None
    value = entry.get("queue")
    return value if isinstance(value, str) and value in QUEUES else None


def _eligible_trial(row, today):
    if (not isinstance(row, dict)
            or not isinstance(row.get("feature"), str)
            or row["feature"] not in FEATURES
            or not isinstance(row.get("origin"), str)
            or row["origin"] not in NETWORKS
            or row.get("metric") != METRIC
            or row.get("design") != "randomized"
            or row.get("outcome_link") != "audited"
            or type(row.get("mature_days")) is not int
            or row["mature_days"] != 14
            or row.get("human_reviewed") is not True
            or row.get("baseline_nonfollowers_verified") is not True
            or row.get("assignment_units_unique") is not True
            or row.get("day14_snapshot_complete") is not True):
        return None
    cohort_end = _date(row.get("cohort_end"))
    observed = _date(row.get("observed_on"))
    if (cohort_end is None or observed is None
            or (observed - cohort_end).days < 14
            or not 0 <= (today - observed).days <= FRESH_DAYS):
        return None
    a, b = row.get("treatment"), row.get("control")
    if not _valid_arm(a) or not _valid_arm(b):
        return None
    return a, b


def _positive_effect(arms):
    """Efecto favorable, separado de la validez de un ensayo independiente."""
    if arms is None:
        return None
    a, b = arms
    lo_a, _ = wilson(a["successes"], a["n"], z=1.96)
    _, hi_b = wilson(b["successes"], b["n"], z=1.96)
    if lo_a <= hi_b:
        return None
    # Separación descriptiva de los extremos de Wilson, NO un IC válido
    # de la diferencia ni una inferencia causal o ajustada por múltiples tests.
    # No redondear: una separación estrictamente positiva puede ser <0.00005.
    # La precisión del efecto calculado debe conservarse en el informe v2.
    return {"wilson_interval_gap": lo_a - hi_b,
            "treatment_n": a["n"], "control_n": b["n"]}


def _positive(row, today):
    """Compatibilidad para consumidores existentes; NO usar como filtro de conflicto."""
    return _positive_effect(_eligible_trial(row, today))


def _targets_valid(targets, origin):
    """Contrato exacto de las redes instrumentadas, sin ocultar redes desconocidas."""
    return (isinstance(targets, dict)
            and 0 < len(targets) <= len(NETWORKS)
            and all(isinstance(target, str) and target in NETWORKS for target in targets)
            and any(target != origin for target in targets))


def _evidence_digest(row, target):
    """Hash interno del test y del permiso de destino, sin datos identificativos.

    Sirve únicamente para vincular una revisión independiente al agregado
    EXACTO; no prueba por sí mismo que los resultados sean auténticos.
    La cola forma parte del digest: una revisión API no acredita WEB/MOBILE.
    """
    entry = row["targets"][target]
    fields = {key: row.get(key) for key in (
        "origin", "feature", "metric", "design", "outcome_link", "mature_days",
        "human_reviewed", "observed_on", "cohort_end",
        "baseline_nonfollowers_verified", "assignment_units_unique",
        "day14_snapshot_complete", "treatment", "control")}
    fields["target"] = target
    fields["queue"] = entry.get("queue")
    fields["capability"] = entry.get("capability")
    fields["permission"] = entry.get("permission")
    fields["implemented"] = entry.get("implemented")
    fields["checked_on"] = entry.get("checked_on")
    raw = json.dumps(fields, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def review(data, *, today=None, trusted_verifications=None, trusted_registry=None):
    """Informe sin PII, sin escritura, sin inferencia de permisos ni cuotas.

    Campos del resultado controlados; no se devuelve ninguna URL, texto o ID
    de usuario que aparezca en la entrada, incluso si es arbitrario.
    """
    today = _local_today() if today is None else today
    # Quien inyecte tiempo debe pasar FECHA local explícita; un datetime
    # UTC a las 22:30 todavía puede ser mañana en Madrid.
    if isinstance(today, dt.datetime):
        raise ValueError("usar fecha de corte local, no instante")
    if not isinstance(today, dt.date):
        raise ValueError("fecha no válida")
    if not isinstance(data, dict) or type(data.get("schema")) is not int or data["schema"] not in (1, 2):
        raise ValueError("contrato de evidencias no compatible")
    schema = data["schema"]
    # Exigir la clase exacta evita que una subclase sustituya approves()
    # y presente aprobaciones sintéticas como si fueran un registro revisado.
    if trusted_registry is not None and type(trusted_registry) is not TrustedRegistry:
        raise ValueError("registro independiente inválido")
    items, history = data.get("observations"), data.get("history", [])
    if not isinstance(items, list) or len(items) > 100 or not isinstance(history, list) or len(history) > 500:
        raise ValueError("evidencias o histórico inválidos")
    # API histórica conservada para validación de argumentos, pero las
    # verificaciones v1 NUNCA autorizan promociones, ni en schema=1 ni v2.
    # Solo un TrustedRegistry independiente habilita v2; CLI no lo acepta.
    if trusted_verifications is None:
        trusted_verifications = frozenset()
    if not isinstance(trusted_verifications, (set, frozenset)):
        raise ValueError("verificaciones externas no válidas")
    if any(not isinstance(key, str) or len(key) != 64
           or any(ch not in "0123456789abcdef" for ch in key)
           for key in trusted_verifications):
        raise ValueError("formato de verificación inválido")
    suppressed = set()
    for h in history:
        if (isinstance(h, dict) and isinstance(h.get("origin"), str)
                and isinstance(h.get("feature"), str)
                and isinstance(h.get("target"), str)
                and h["origin"] in NETWORKS and h["feature"] in FEATURES
                and h["target"] in NETWORKS
                and h.get("decision") in ("implemented", "rejected", "under_review")):
            # Un histórico antiguo sin cola sigue siendo una decisión global;
            # un histórico nuevo solo suprime su propia cola.
            if "queue" in h and (not isinstance(h["queue"], str)
                                 or h["queue"] not in QUEUES):
                continue
            queue = h.get("queue")
            suppressed.add((h["origin"], h["feature"], h["target"], queue))

    # Conflictos no se resuelven por orden: una segunda evidencia en la
    # misma cola invalida ambas. Una cola desconocida es ambigua y bloquea
    # las verificaciones concretas de esa red/táctica hasta su reconciliación.
    # Una réplica negativa o inconclusa es evidencia CONTRADICTORIA aunque
    # no cumpla el umbral positivo; no permitir sesgo de selección de ensayos.
    # A la inversa, filas sin control o con estructura inválida no contaminan.
    arms = [_eligible_trial(row, today) for row in items]
    valid_targets = [
        _targets_valid(row.get("targets"), row.get("origin"))
        if isinstance(row, dict) else False
        for row in items
    ]
    effects = [_positive_effect(a) for a in arms]
    counts = Counter()
    for row, trial, targets_ok in zip(items, arms, valid_targets):
        if trial is None or not targets_ok:
            continue
        origin, feature, targets = row["origin"], row["feature"], row["targets"]
        for target, entry in targets.items():
            if target != origin:
                counts[(origin, feature, target, _queue(entry))] += 1

    report = {"schema": schema, "as_of": today.isoformat(),
              "identity_contract": "v2_external_registry" if schema == 2 else "legacy_read_only",
              "coverage": {n: ("partial" if n in STATE_ADAPTERS else "unverified")
                           for n in sorted(NETWORKS)}, "proposals": [],
              "invalid_or_unproven": 0, "non_positive_trials": 0,
              "suppressed": 0, "duplicate_evidence": 0, "writes": False}
    seen = set()
    for row, trial, targets_ok, effect in zip(items, arms, valid_targets, effects):
        if trial is None or not targets_ok:
            report["invalid_or_unproven"] += 1
            continue
        if effect is None:
            # Compatibilidad de schema=1: este contador incluía resultados
            # no demostrados, no solo entradas estructuralmente inválidas.
            report["invalid_or_unproven"] += 1
            # Desglose aditivo, útil para distinguir réplicas inconclusas.
            report["non_positive_trials"] += 1
            continue
        origin, feature = row["origin"], row["feature"]
        targets = row["targets"]
        for target in sorted(targets):
            if target not in NETWORKS or target == origin:
                continue
            entry = targets[target]
            queue = _queue(entry)
            key = (origin, feature, target, queue)
            legacy_key = (origin, feature, target, None)
            if counts[key] > 1 or (queue is not None and counts[legacy_key]):
                report["suppressed"] += 1
                report["duplicate_evidence"] += 1
                continue
            if key in seen or key in suppressed or legacy_key in suppressed:
                report["suppressed"] += 1
                continue
            seen.add(key)
            state = "investigar_equivalencia"
            # Capacidad, permiso e implementación solo tienen significado
            # operativo si vienen acotados a una de las tres colas reales.
            if isinstance(entry, dict) and queue is not None:
                capability = entry.get("capability")
                permission = entry.get("permission")
                date = _date(entry.get("checked_on"))
                fresh = date is not None and 0 <= (today - date).days <= TARGET_TTL_DAYS
                if fresh:
                    if capability == "unsupported" or permission == "denied":
                        state = "no_transferible"
                    elif entry.get("implemented") is True:
                        state = "ya_implementado"
                    elif (capability == "verified" and permission == "verified"
                          and entry.get("implemented") is False):
                        # Solo un manifest de asignaciones revisado externamente
                        # autoriza una promoción en schema=2.
                        state = ("proponer_ensayo_manual"
                                 if (schema == 2 and trusted_registry is not None
                                     and trusted_registry.approves(row, target))
                                 else "verificacion_externa_pendiente")
            externally_verified = state == "proponer_ensayo_manual"
            report["proposals"].append({"origin": origin, "target": target,
                                         "queue": queue,
                                         "feature": feature, "state": state,
                                         **effect, "metric": METRIC,
                                         "evidence_is_self_reported": True,
                                         "externally_verified": externally_verified,
                                         "needs_human_approval": True})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hipótesis entre redes (offline, solo lectura)")
    parser.add_argument("--input", required=True, help="JSON agregado y validado, nunca perfiles")
    parser.add_argument("--as-of", help="Fecha ISO para reproducibilidad")
    args = parser.parse_args(argv)
    path = Path(args.input)
    try:
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("se requiere fichero regular")
        if metadata.st_size > MAX_INPUT_BYTES:
            raise ValueError("JSON demasiado grande")
        # Acotar los bytes LEÍDOS, no solo stat(): evita ampliación entre
        # stat y read o una FIFO/dispositivo que no termine de crecer.
        with path.open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError("JSON demasiado grande")
        def _reject_constant(value):
            raise ValueError("constante JSON inválida: " + value)
        def _reject_duplicate_keys(pairs):
            obj = {}
            for key, value in pairs:
                if key in obj:
                    raise ValueError("clave JSON duplicada")
                obj[key] = value
            return obj
        data = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant,
                          object_pairs_hook=_reject_duplicate_keys)
        today = _date(args.as_of) if args.as_of is not None else _local_today()
        if today is None:
            raise ValueError("fecha de corte no válida")
        result = review(data, today=today)
    except (OSError, UnicodeError, ValueError, RecursionError,
            OverflowError, ZoneInfoNotFoundError):
        print("DATOS_NO_VALIDOS")
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

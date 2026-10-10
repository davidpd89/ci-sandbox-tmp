"""Análisis *offline* de dos cohortes preasignadas; nunca asigna ni actúa en redes.

Los flags de diseño son declaraciones externas, NO prueba de aleatorización.
El resultado nunca autoriza actuaciones automáticas ni combina redes/cohortes.
"""
from math import erfc, isfinite, sqrt
import re
from statistics import NormalDist


KNOWN_NETWORKS = frozenset({
    'bluesky', 'mastodon', 'threads', 'x', 'facebook',
    'pinterest', 'reddit', 'tiktok', 'instagram'
})


def _wilson(k, n, z):
    p = k / n
    d = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    span = z / d * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, mid - span), min(1.0, mid + span)


def analyze_experiment(records, *, design, min_per_arm=100, confidence=0.95,
                       expected_treatment_fraction=0.5, srm_cutoff=0.0005):
    """Diferencia de riesgos con IC Newcombe-Wilson, SRM y vetos de calidad.

    Cada fila: unit_id (seudónimo), network, cohort, arm, converted (bool),
    contaminated (bool), followup_days (int). Incluye TODOS los asignados.
    El registro de exposición y la fecha de medición deben auditarse fuera.
    """
    # El piso de privacidad no puede rebajarse desde un llamador externo.
    if type(min_per_arm) is not int or min_per_arm < 100:
        raise ValueError('min_per_arm inválido')
    # math.isfinite(int gigantesco) puede lanzar OverflowError al convertir
    # a float: tratamos esa entrada como inválida, nunca como error sin manejar.
    try:
        parameters_ok = all(type(x) in (int, float) and isfinite(x) for x in
                            (confidence, expected_treatment_fraction, srm_cutoff))
    except (OverflowError, ValueError):
        parameters_ok = False
    if not parameters_ok:
        raise ValueError('parámetro no finito')
    if not 0 < confidence < 1 or not 0 < expected_treatment_fraction < 1 or not 0 < srm_cutoff < 1:
        raise ValueError('confianza, asignación o umbral inválido')
    if not isinstance(design, dict):
        raise ValueError('faltan metadatos del diseño')
    horizon = design.get('window_days')
    if type(horizon) is not int or not 1 <= horizon <= 365:
        raise ValueError('ventana de observación inválida')
    flags = ('randomized_pre_exposure', 'complete_assignment_log',
             'fixed_outcome_window', 'no_interference', 'study_finished')
    if any(type(design.get(flag)) is not bool for flag in flags):
        raise ValueError('declaraciones de diseño incompletas')
    if not isinstance(records, (list, tuple)) or not records:
        raise ValueError('sin unidades asignadas')
    n = {'treatment': 0, 'control': 0}
    y = {'treatment': 0, 'control': 0}
    seen, scopes = set(), set()
    contaminated = 0
    for row in records:
        if not isinstance(row, dict):
            raise ValueError('unidad malformada')
        key, arm = row.get('unit_id'), row.get('arm')
        network, cohort = row.get('network'), row.get('cohort')
        # Las etiquetas se imprimen en JSON de salida: no aceptar saltos de
        # línea, URLs/handles ni cadenas arbitrarias en campos identificativos.
        if (not isinstance(key, str)
                or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}', key) is None
                or key in seen
                or not isinstance(arm, str) or arm not in n
                or not isinstance(network, str) or network not in KNOWN_NETWORKS
                or not isinstance(cohort, str)
                or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', cohort) is None
                or type(row.get('converted')) is not bool
                or type(row.get('contaminated')) is not bool
                or type(row.get('followup_days')) is not int):
            raise ValueError('duplicado, cohorte mezclada o fila inválida')
        seen.add(key)
        scopes.add((network, cohort))
        if row['followup_days'] != horizon:
            raise ValueError('ventanas de medición desiguales')
        n[arm] += 1
        y[arm] += int(row['converted'])
        contaminated += int(row['contaminated'])
    if len(scopes) != 1 or not all(n.values()):
        raise ValueError('mezcla de redes/cohortes o falta un brazo')
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    pt, pc = y['treatment'] / n['treatment'], y['control'] / n['control']
    lo_t, hi_t = _wilson(y['treatment'], n['treatment'], z)
    lo_c, hi_c = _wilson(y['control'], n['control'], z)
    delta = pt - pc
    # Newcombe score (método 10): límites asimétricos combinando Wilson.
    lo = delta - sqrt((pt - lo_t) ** 2 + (hi_c - pc) ** 2)
    hi = delta + sqrt((hi_t - pt) ** 2 + (pc - lo_c) ** 2)
    total = sum(n.values())
    expected_t = total * expected_treatment_fraction
    chi2 = ((n['treatment'] - expected_t) ** 2 / expected_t
            + (n['control'] - (total - expected_t)) ** 2 / (total - expected_t))
    srm_p = erfc(sqrt(chi2 / 2))
    reasons = [flag for flag in flags if not design[flag]]
    if contaminated:
        reasons.append('contamination_detected')
    if min(n.values()) < min_per_arm:
        reasons.append('insufficient_n')
    if srm_p < srm_cutoff:
        reasons.append('sample_ratio_mismatch')
    return {
        'network': next(iter(scopes))[0], 'cohort': next(iter(scopes))[1],
        # Evitar divulgación de resultados por brazo con celdas pequeñas.
        'treatment': {'n': n['treatment'],
                      'conversions': y['treatment'] if n['treatment'] >= min_per_arm else None,
                      'rate': pt if n['treatment'] >= min_per_arm else None},
        'control': {'n': n['control'],
                    'conversions': y['control'] if n['control'] >= min_per_arm else None,
                    'rate': pc if n['control'] >= min_per_arm else None},
        # Un experimento inválido no publica un uplift aparentemente causal.
        # Los conteos brutos y el SRM siguen disponibles para diagnóstico.
        'difference_pp': 100 * delta if not reasons else None,
        'ci_pp': ([100 * max(-1.0, lo), 100 * min(1.0, hi)]
                  if not reasons else None),
        'confidence': confidence, 'srm_p': srm_p,
        'contaminated_units': contaminated,
        'status': 'review_only' if not reasons else 'blocked',
        'reasons': reasons, 'causal_claim_approved': False,
        'note': 'Estimación declarativa; requiere auditoría externa del diseño y revisión humana.',
    }

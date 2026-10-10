"""Informe TikTok local y de solo lectura: no elige semillas ni ejecuta acciones.

Solo acepta el contrato de cohortes D+N; los contadores legacy, snapshots
parciales e identidades por handle NO certifican una conversión de fuente.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

WINDOWS = ('D+1', 'D+3', 'D+7')
FIELDS = ('eligible', 'converted', 'not_converted', 'unknown', 'censored',
          'pending', 'legacy_unverified', 'weak_identity')


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if type(successes) is not int or type(total) is not int or not (0 <= successes <= total and total > 0):
        raise ValueError('conteos inválidos')
    p = successes / total
    d = 1 + z * z / total
    mid = (p + z * z / (2 * total)) / d
    half = z / d * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return max(0., mid - half), min(1., mid + half)


def report(snapshot: dict, *, today: dt.date, window: str = 'D+7', min_sample: int = 100) -> dict:
    """Nunca produce ranking, semilla recomendada, yield operativo ni cambios de estado."""
    if type(today) is not dt.date or window not in WINDOWS or type(min_sample) is not int or min_sample < 100:
        raise ValueError('parámetros inválidos')
    if not isinstance(snapshot, dict):
        raise ValueError('instantánea inválida')
    try:
        day = dt.date.fromisoformat(snapshot['date'])
        cohort = snapshot['cohorts_v2']
        if (cohort['schema_version'] != 2 or cohort['timezone'] != 'Europe/Madrid' or
                cohort['definition'] != 'first_observed_positive_by_local_D+N'):
            raise ValueError('versión/semántica incompatibles')
        sources = cohort['windows'][window]
    except (KeyError, TypeError) as exc:
        raise ValueError('cohorte incompleta') from exc
    if not isinstance(sources, dict) or len(sources) > 10000:
        raise ValueError('fuentes malformadas')
    # Cobertura global: un parcial nunca autoriza recálculo. No inferir a partir
    # de días faltantes que una cuenta dejó de seguirnos.
    global_blockers = []
    dates = snapshot.get('complete_dates')
    if (snapshot.get('coverage_complete') is not True or not isinstance(dates, list)
            or any(type(value) is not str for value in dates)
            or day.isoformat() not in dates):
        global_blockers.append('snapshot_incomplete')
    if not 0 <= (today - day).days <= 3:
        global_blockers.append('snapshot_stale_or_future')
    results = []
    for index, (name, counts) in enumerate(sorted(sources.items()), 1):
        if not isinstance(name, str) or not name or len(name) > 200 or not isinstance(counts, dict):
            raise ValueError('fuente inválida')
        if any(type(counts.get(k)) is not int or counts[k] < 0 for k in FIELDS):
            raise ValueError('conteos faltantes o inválidos')
        n, successes, negatives = counts['eligible'], counts['converted'], counts['not_converted']
        if successes + negatives > n or counts['weak_identity'] > n or counts['legacy_unverified'] > n:
            raise ValueError('conteos inconsistentes')
        reasons = list(global_blockers)
        if n < min_sample:
            reasons.append('insufficient_sample')
        if counts['weak_identity']:
            reasons.append('weak_identity')
        if counts['legacy_unverified']:
            reasons.append('unverified_baseline')
        if (counts['unknown'] or counts['censored'] or counts['pending'] or
                successes + negatives != n or counts.get('coverage') != 'complete'):
            reasons.append('incomplete_outcomes')
        trusted = not reasons
        category = name.split(':', 1)[0]
        if category not in ('followers', 'mutual', 'auto', 'otros', 'followback'):
            category = 'otras'
        # No imprimir queries, handles ni fuentes originales por defecto.
        results.append({'code': f'S{index:03d}', 'category': category,
                        'n': n, 'status': 'observational_only' if trusted else 'blocked',
                        'reasons': reasons,
                        'rate': successes / n if trusted else None,
                        'wilson95': list(wilson(successes, n)) if trusted else None})
    return {'date': day.isoformat(), 'window': window, 'minimum_n': min_sample,
            'sources': results, 'global_blockers': global_blockers,
            'recommendations_enabled': False, 'causal_claim_approved': False,
            'note': 'Solo observación y revisión humana; no ordena ni cambia fuentes.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--window', choices=WINDOWS, default='D+7')
    args = parser.parse_args(argv)
    try:
        with args.snapshot.open('rb') as stream:
            raw = stream.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError('archivo demasiado grande')
        def unique_keys(pairs):
            parsed = {}
            for key, value in pairs:
                if key in parsed:
                    raise ValueError('clave duplicada')
                parsed[key] = value
            return parsed
        data = json.loads(raw, object_pairs_hook=unique_keys,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('JSON no estándar')))
        result = report(data, today=dt.datetime.now(ZoneInfo('Europe/Madrid')).date(), window=args.window)
    except (OSError, TypeError, ValueError, OverflowError, RecursionError):
        print('Datos de auditoría incompletos o inválidos: no hay priorización automática.')
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if any(x['status'] == 'observational_only' for x in result['sources']) else 3


if __name__ == '__main__':
    raise SystemExit(main())

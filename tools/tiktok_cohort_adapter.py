"""Adaptador únicamente lector de #33; no pide permisos ni toca Android.

Conserva D+N legacy como proyección incompatible con un KPI certificado.
El histórico previo no contiene fecha de evento real ni checkpoints negativos.
"""
from __future__ import annotations

import datetime
from cohort_metrics import FollowEvent, FollowerObservation, evaluate, legacy_projection


def project(follows, first_back_date, observed_since, today, *, complete_dates=(), deadlines=(1, 3, 7)):
    """(resultado v2, deadlines legacy). Identidad TikTok = handle débil."""
    start = datetime.date.fromisoformat(observed_since)
    events = []
    for handle, follow_iso, source in follows:
        try:
            day = datetime.date.fromisoformat(follow_iso)
        except (TypeError, ValueError):
            continue
        if day < start or day > today:
            continue
        events.append(FollowEvent(
            network="tiktok", subject_id=handle, occurred_at=day,
            source=source, identity="handle",
            baseline="preexisting" if source == "followback" else "legacy_unverified",
        ))
    complete = set()
    for iso in complete_dates:
        try:
            checkpoint = datetime.date.fromisoformat(iso)
            if start <= checkpoint <= today:
                complete.add(checkpoint)
        except (TypeError, ValueError):
            continue  # el registro previo puede carecer de fecha válida
    observations = []
    for event in events:
        first = first_back_date.get(event.subject_id)
        if first:
            try:
                day = datetime.date.fromisoformat(first)
            except (TypeError, ValueError):
                day = None
            if day is not None and start <= day <= today:
                observations.append(FollowerObservation(
                    network="tiktok", subject_id=event.subject_id,
                    captured_at=day, follows_back=True, coverage="partial",
                    capability="ui_snapshot", method="android_accessibility",
                    identity="handle",
                ))
        # Solo hay tres checkpoints posibles por episodio: O(follows * deadlines),
        # nunca un objeto por cada fecha histórica x seguidor.
        for n in dict.fromkeys(deadlines):
            checkpoint = event.occurred_at + datetime.timedelta(days=n)
            if checkpoint in complete:
                # Un positivo anterior no puede reetiquetarse como ausencia.
                seen_before = first is not None and day is not None and day <= checkpoint
                if not seen_before:
                    observations.append(FollowerObservation(
                        network="tiktok", subject_id=event.subject_id,
                        captured_at=checkpoint, follows_back=False,
                        coverage="complete", capability="ui_snapshot",
                        method="android_accessibility", identity="handle",
                    ))
    result = evaluate(events, observations, as_of=today, deadlines=deadlines)
    return result["networks"]["tiktok"], legacy_projection(result, "tiktok")

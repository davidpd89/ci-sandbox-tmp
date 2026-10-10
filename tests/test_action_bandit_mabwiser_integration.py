"""Integración opcional real con MABWiser 2.7.4; sin datos ni cuentas reales."""
from datetime import date, timedelta
from pathlib import Path
import sys
import pytest

pytest.importorskip("mabwiser.mab")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from action_bandit import Candidate, Observation, rank_candidates

NOW = date(2026, 10, 10)


def test_real_linucb_fit_predict():
    events = [
        Observation(event_id=f"synthetic-{i}", network="bluesky",
                    action=("follow", "reply", "repost")[i % 3],
                    affinity=(i % 10) / 10, activity=.7,
                    conversation=.5, source_quality=.8,
                    performed_on=NOW-timedelta(days=7), observed_on=NOW,
                    window_days=7, reciprocity=float(i % 2),
                    engagement=.4, sustained_conversation=.2,
                    coverage="complete", provenance="synthetic")
        for i in range(300)
    ]
    choices = [Candidate("synthetic-choice", "bluesky", "reply", .8, .7, .5, .8)]
    rows = rank_candidates(choices, events, as_of=NOW, allow_synthetic=True)
    assert len(rows) == 1
    assert rows[0].policy == "mabwiser_linucb"
    assert rows[0].mature_events == 300
    assert 0 <= rows[0].score <= 1
    assert rows == rank_candidates(choices, events, as_of=NOW, allow_synthetic=True)

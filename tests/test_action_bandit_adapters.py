"""Contrato común de nueve adaptadores con fixtures sintéticos."""
from datetime import date, timedelta
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from action_bandit import NETWORKS, rank_candidates
from action_bandit_adapters import ACTION_LABELS, candidate_from_native, observation_from_native

TODAY = date(2026, 10, 10)


@pytest.mark.parametrize('network', sorted(NETWORKS))
def test_native_adapter_each_network(network):
    for native_action, action in ACTION_LABELS[network].items():
        data = dict(network=network, native_action=native_action,
                    candidate_id='synthetic', affinity=.9, activity=.7,
                    conversation=.4, source_quality=.8,
                    capability_verified=True, eligible=True)
        cand = candidate_from_native(data)
        assert cand.action == action
        assert rank_candidates([cand], [], as_of=TODAY)[0].candidate.network == network
        evt = dict(data, event_id='synthetic-event',
                   performed_on=TODAY-timedelta(days=7), observed_on=TODAY,
                   window_days=7, reciprocity=1., engagement=.2,
                   sustained_conversation=.3, coverage='complete',
                   provenance='synthetic', confirmed_action=True)
        obs = observation_from_native(evt)
        assert obs.action == cand.action
        assert rank_candidates([cand], [obs], as_of=TODAY)[0].mature_events == 0


def test_no_implicit_capability_or_eligibility():
    data = dict(network='tiktok', native_action='comment', candidate_id='x',
                affinity=.8, activity=.7, conversation=.6, source_quality=.5)
    with pytest.raises(ValueError):
        candidate_from_native(data)
    row = candidate_from_native(dict(data, capability_verified=True))
    assert row.eligible is False
    assert rank_candidates([row], [], as_of=TODAY) == []


def test_no_zero_for_missing_outcome():
    data = dict(network='reddit', native_action='comment', event_id='e',
                affinity=.8, activity=.7, conversation=.6, source_quality=.5,
                capability_verified=True, performed_on=TODAY-timedelta(days=7),
                observed_on=TODAY, window_days=7, coverage='complete',
                provenance='audited_api', confirmed_action=True)
    obs = observation_from_native(data)
    assert obs.reciprocity is None
    assert rank_candidates([], [obs], as_of=TODAY) == []


def test_reject_wrong_native_action_and_unverified_capability():
    base = dict(network='pinterest', native_action='retweet', candidate_id='x',
                affinity=.8, activity=.7, conversation=.6, source_quality=.5,
                capability_verified=True)
    with pytest.raises(ValueError):
        candidate_from_native(base)
    with pytest.raises(ValueError):
        candidate_from_native(dict(base, native_action='save', capability_verified=False))

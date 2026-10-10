"""Fixtures completamente sintéticos; sin navegador, cuentas ni red."""
from dataclasses import replace
from datetime import date, timedelta
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from action_bandit import (ACTIONS, NETWORKS, Candidate, Observation,
                           rank_candidates, validated_reward)

TODAY = date(2026, 10, 10)


def candidate(net='bluesky', action='reply', key='one', **kwargs):
    return Candidate(key, net, action, .8, .7, .6, .9, **kwargs)


def observed(net='bluesky', action='reply', key='event', **kwargs):
    data = dict(event_id=key, network=net, action=action, affinity=.8,
                activity=.7, conversation=.6, source_quality=.9,
                performed_on=TODAY-timedelta(days=7), observed_on=TODAY,
                window_days=7, reciprocity=1.0, engagement=.5,
                sustained_conversation=.25, coverage='complete',
                provenance='audited_api', confirmed_action=True)
    data.update(kwargs)
    return Observation(**data)


def test_nine_networks_prior_and_determinism():
    rows = [candidate(net, key=net) for net in sorted(NETWORKS)]
    result = rank_candidates(rows, [], as_of=TODAY)
    assert len(result) == 9
    assert {row.candidate.network for row in result} == NETWORKS
    assert all(row.policy == 'prior' for row in result)
    assert result == rank_candidates(list(reversed(rows)), [], as_of=TODAY)


def test_no_model_and_no_network_side_effects():
    rows = rank_candidates([candidate()], [observed()], as_of=TODAY)
    assert rows[0].policy == 'prior'
    assert rows[0].mature_events == 1


def test_maturity_and_unknown_are_not_failures():
    assert validated_reward(observed(window_days=3, performed_on=TODAY-timedelta(days=3)), as_of=TODAY) is None
    assert validated_reward(observed(coverage='partial', reciprocity=0), as_of=TODAY) is None
    assert validated_reward(observed(engagement=None), as_of=TODAY) is None
    assert validated_reward(observed(provenance='synthetic'), as_of=TODAY) is None
    assert validated_reward(observed(confirmed_action=False), as_of=TODAY) is None
    assert validated_reward(observed(observed_on=TODAY+timedelta(days=1), performed_on=TODAY-timedelta(days=6)), as_of=TODAY) is None
    assert validated_reward(observed(reciprocity=0, engagement=0, sustained_conversation=0), as_of=TODAY) == 0


def test_reward_explicit_weights():
    assert validated_reward(observed(), as_of=TODAY) == pytest.approx(.45 + .35*.5 + .20*.25)


def test_invalid_dates_and_numbers():
    with pytest.raises(ValueError):
        validated_reward(observed(performed_on=TODAY), as_of=TODAY)
    with pytest.raises(ValueError):
        validated_reward(observed(reciprocity=float('nan')), as_of=TODAY)
    with pytest.raises(ValueError):
        rank_candidates([replace(candidate(), affinity=float('inf'))], [], as_of=TODAY)
    with pytest.raises(ValueError):
        rank_candidates([], [observed(provenance='crawler_guess')], as_of=TODAY)
    with pytest.raises(ValueError):
        validated_reward(observed(window_days=2), as_of=TODAY)


def test_duplicates_and_veto():
    with pytest.raises(ValueError, match='candidato repetido'):
        rank_candidates([candidate(), candidate()], [], as_of=TODAY)
    with pytest.raises(ValueError, match='event_id duplicado'):
        rank_candidates([candidate()], [observed(), observed()], as_of=TODAY)
    assert rank_candidates([candidate(eligible=False)], [], as_of=TODAY) == []
    assert len(rank_candidates([candidate(), candidate(action="follow")], [], as_of=TODAY)) == 2


def test_network_arms_require_threshold_and_isolation():
    class Recorder:
        def __init__(self):
            self.fitted = []
        def fit(self, arms, rewards, contexts):
            self.fitted.append((arms, rewards, contexts))
        def predict_expectations(self, contexts):
            return [{'follow': .1, 'reply': .9, 'repost': .2}]
    models = []
    def factory(seed):
        model = Recorder()
        models.append(model)
        return model
    history = [observed(action=ACTIONS[i % 3], key=f'event{i}') for i in range(300)]
    rows = rank_candidates([candidate(), candidate('mastodon', key='other')], history,
                           as_of=TODAY, model_factory=factory)
    scores = {r.candidate.network: r for r in rows}
    assert scores['bluesky'].policy == 'mabwiser_linucb'
    assert scores['mastodon'].policy == 'prior'
    assert scores['bluesky'].mature_events == 300
    assert len(models) == 1 and len(models[0].fitted[0][0]) == 300
    assert len(models[0].fitted[0][2][0]) == 5


def test_no_model_without_each_arm_minimum():
    models = []
    history = [observed(action='reply', key=f'event{i}') for i in range(300)]
    rows = rank_candidates([candidate()], history, as_of=TODAY,
                           model_factory=lambda _: models.append(1))
    assert rows[0].policy == 'prior'
    assert not models


def test_provenance_synthetic_opt_in():
    data = [observed(action=ACTIONS[i % 3], key=f'e{i}', provenance='synthetic')
            for i in range(300)]
    assert rank_candidates([candidate()], data, as_of=TODAY)[0].mature_events == 0
    assert rank_candidates([candidate()], data, as_of=TODAY, allow_synthetic=True,
                           model_factory=lambda _: FakeModel())[0].policy == 'mabwiser_linucb'


class FakeModel:
    def fit(self, *args):
        pass
    def predict_expectations(self, context):
        return [{'reply': 0.8}]


def test_bad_prediction_fails_to_prior():
    data = [observed(action=ACTIONS[i % 3], key=f'e{i}') for i in range(300)]
    class Wrong(FakeModel):
        def predict_expectations(self, context):
            return [{'reply': float('nan')}]
    result = rank_candidates([candidate()], data, as_of=TODAY, model_factory=lambda _: Wrong())
    assert result[0].policy == 'prior'


def test_nonexistent_import_not_silent_learning(monkeypatch):
    data = [observed(action=ACTIONS[i % 3], key=f'e{i}') for i in range(300)]
    import action_bandit
    def missing(_):
        raise ImportError('not installed')
    monkeypatch.setattr(action_bandit, '_mabwiser_factory', missing)
    result = rank_candidates([candidate()], data, as_of=TODAY)
    assert result[0].policy == 'prior'


def test_reject_other_network_or_action():
    with pytest.raises(ValueError):
        rank_candidates([candidate(net='unknown')], [], as_of=TODAY)
    with pytest.raises(ValueError):
        rank_candidates([candidate(action='like')], [], as_of=TODAY)


def test_invalid_model_factory_propagates_instead_of_silent_success():
    data = [observed(action=ACTIONS[i % 3], key=f'e{i}') for i in range(300)]
    class Broken:
        def fit(self, *_):
            raise RuntimeError('broken model')
    with pytest.raises(RuntimeError):
        rank_candidates([candidate()], data, as_of=TODAY,
                        model_factory=lambda _: Broken())


def test_multiple_windows_per_event_and_only_day7_trains():
    day1 = observed(key='shared', window_days=1,
                    performed_on=TODAY-timedelta(days=1))
    day3 = observed(key='shared', window_days=3,
                    performed_on=TODAY-timedelta(days=3))
    day7 = observed(key='shared')
    result = rank_candidates([candidate()], [day1, day3, day7], as_of=TODAY)
    assert result[0].mature_events == 1

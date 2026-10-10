"""Unit tests: all observations are synthetic; neither Android nor TikTok is touched."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import tiktok_loyalty_observe as m


def row(**kwargs):
    return {"source": "inbox:new_follower", "handle": "Lectora_123",
            "inbox_relation": "follows_me", "profile_relation": "follows_me",
            "navigation_provenance": "profile_opened_from_inbox_row", **kwargs}


def snapshot(rows=None, **updates):
    x = {"schema": 1, "observed_at": "2026-10-09T18:30:00+02:00",
         "owner_account_checked": True, "rows": [row()] if rows is None else rows}
    x.update(updates)
    return x


def test_no_event_or_reward_even_with_good_relationship():
    got = m.summarize(snapshot(), include_handles=True)
    assert got["relationships_observed"] == 1
    assert got["handles"] == ["lectora_123"]
    assert got["new_follow_events"] is None
    assert got["inbound_like_events"] is None
    assert got["inbound_comment_events"] is None
    assert got["eligible_for_auto_rewards"] is False
    assert got["eligible_for_inbound_ledger"] is False


def test_empty_rows_not_zero_activity_claim():
    got = m.summarize(snapshot([]))
    assert got["relationships_observed"] == 0
    assert got["new_follow_events"] is None


@pytest.mark.parametrize("failure,expected", [
    ({"source": "video_search:comment"}, "origen_no_acreditado"),
    ({"source": "user_search"}, "origen_no_acreditado"),
    ({"profile_relation": "not_following"}, "relacion_no_corroborrada"),
    ({"inbox_relation": "requested"}, "relacion_no_corroborrada"),
    ({"navigation_provenance": "search_result"}, "relacion_no_corroborrada"),
    ({"handle": ""}, "identidad_no_acreditada"),
    ({"handle": "a b"}, "identidad_no_acreditada"),
    ({"handle": "davidportoescritor"}, "identidad_no_acreditada"),
    ({"handle": "@a@b"}, "identidad_no_acreditada"),
])
def test_reject_unproven_evidence(failure, expected):
    given = row()
    given.update(failure)
    got = m.summarize(snapshot([given]))
    assert got["relationships_observed"] == 0
    assert got["rejected_by_reason"] == {expected: 1}


def test_owner_not_confirmed_fails_closed():
    got = m.summarize(snapshot(owner_account_checked=False))
    assert got["relationships_observed"] == 0
    assert got["rejected_by_reason"] == {"cuenta_no_comprobada": 1}


def test_repeat_same_handle_is_one_observed_relationship_not_events():
    r = row()
    got = m.summarize(snapshot([r, {**r, "handle": "@LECTORA_123"}]))
    assert got["relationships_observed"] == 1
    assert got["rejected_by_reason"] == {"duplicada_en_lectura": 1}


def test_unrelated_text_discarded_from_report():
    r = row()
    r.update({"comment_text": "privado", "email": "private@example.com", "caption": "secreto"})
    got = m.summarize(snapshot([r]))
    assert "privado" not in json.dumps(got)
    assert "secreto" not in json.dumps(got)


@pytest.mark.parametrize("observed_at", ["2026-10-09", "2026-10-09T18:30:00", "imposible", "2026-02-30T10:00:00Z", None])
def test_timestamp_requires_valid_timezone(observed_at):
    with pytest.raises(m.InvalidObservation):
        m.summarize(snapshot(observed_at=observed_at))


@pytest.mark.parametrize("bad", [{}, {"schema": 2}, {"schema": 1, "observed_at": "2026-10-09T13:00:00Z", "owner_account_checked": 1, "rows": []}])
def test_bad_contract_rejected(bad):
    with pytest.raises(m.InvalidObservation):
        m.summarize(bad)


def test_rows_must_be_bounded():
    with pytest.raises(m.InvalidObservation):
        m.summarize(snapshot([row()] * 201))


def test_invalid_rows_are_counted_but_never_trusted():
    got = m.summarize(snapshot([None, "invalid", row()]))
    assert got["relationships_observed"] == 1
    assert got["rejected_by_reason"] == {"fila_invalida": 2}


def test_readonly_and_no_identifiers_in_default_cli(tmp_path, capsys):
    file = tmp_path / "synthetic.json"
    file.write_text(json.dumps(snapshot()), encoding="utf-8")
    original = file.read_bytes()
    old_files = sorted(p.name for p in tmp_path.iterdir())
    assert m.main(["--input", str(file)]) == 0
    printed = capsys.readouterr().out
    assert "lectora_123" not in printed
    assert json.loads(printed)["relationships_observed"] == 1
    assert file.read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == old_files


def test_explicit_handles_requires_opt_in(tmp_path, capsys):
    file = tmp_path / "synthetic.json"
    file.write_text(json.dumps(snapshot()), encoding="utf-8")
    assert m.main(["--input", str(file), "--show-handles"]) == 0
    assert "lectora_123" in capsys.readouterr().out


def test_oversize_fail_closed(tmp_path):
    path = tmp_path / "huge.json"
    path.write_bytes(b" " * (m.MAX_INPUT_BYTES + 1))
    with pytest.raises(m.InvalidObservation, match="64 KiB"):
        m._read_json(path)


def test_utf8_bom_works(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(snapshot()).encode("utf-8"))
    assert m.summarize(m._read_json(path))["relationships_observed"] == 1


def test_later_observation_does_not_infer_second_event():
    first = m.summarize(snapshot())
    later = m.summarize(snapshot(observed_at="2026-11-08T18:30:00+01:00"))
    assert first["new_follow_events"] is later["new_follow_events"] is None


def test_no_input_file_is_created(tmp_path):
    with pytest.raises(m.InvalidObservation):
        m._read_json(tmp_path / "missing.json")
    assert list(tmp_path.iterdir()) == []


def test_another_network_cannot_be_counted_as_tiktok():
    bad = row()
    bad["source"] = "bluesky:notification"
    got = m.summarize(snapshot([bad]))
    assert got["relationships_observed"] == 0
    assert got["inbound_comment_events"] is None


def test_duplicate_json_keys_fail_closed(tmp_path):
    path = tmp_path / "duplicates.json"
    path.write_text('{"schema":1,"owner_account_checked":false,"owner_account_checked":true}', encoding="utf-8")
    with pytest.raises(m.InvalidObservation, match="duplicada"):
        m._read_json(path)


def test_nonfinite_json_rejected(tmp_path):
    path = tmp_path / "nonfinite.json"
    path.write_text('{"schema":1,"observed_at":NaN}', encoding="utf-8")
    with pytest.raises(m.InvalidObservation, match="finito"):
        m._read_json(path)

@pytest.mark.parametrize('schema_value', [True, 1.0, '1'])
def test_schema_must_be_exact_integer(schema_value):
    with pytest.raises(m.InvalidObservation, match='schema'):
        m.summarize(snapshot(schema=schema_value))


@pytest.mark.parametrize('stamp', [
    '2026-10-09 18:30:00+02:00',
    '2026-W41-5T18:30:00+02:00',
    '2026-10-09T18:30+02:00',
    '2026-10-09T18:30:00+0200',
    '2026-10-09T18:30:00.1234567+02:00',
])
def test_timestamp_rejects_noncanonical_iso(stamp):
    with pytest.raises(m.InvalidObservation, match='observed_at'):
        m.summarize(snapshot(observed_at=stamp))


def test_library_does_not_return_handles_without_explicit_opt_in():
    data = m.summarize(snapshot())
    assert 'handles' not in data
    assert 'lectora_123' not in json.dumps(data)
    assert m.summarize(snapshot(), include_handles=True)['handles'] == ['lectora_123']


def test_json_deeply_nested_fails_as_validation_error(tmp_path):
    path = tmp_path / 'nested.json'
    path.write_text('[' * 8000 + '0' + ']' * 8000, encoding='utf-8')
    with pytest.raises(m.InvalidObservation):
        m._read_json(path)

@pytest.mark.parametrize('spoofed', ['Kevin', 'ſusan'])
def test_unicode_casefold_confusables_are_not_accepted_as_ascii_handles(spoofed):
    observation = row()
    observation['handle'] = spoofed
    result = m.summarize(snapshot([observation]))
    assert result['relationships_observed'] == 0
    assert result['rejected_by_reason'] == {'identidad_no_acreditada': 1}

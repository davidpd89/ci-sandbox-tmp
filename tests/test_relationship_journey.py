"""Tests hermeticos del puente Retentioneering; no importa clientes sociales."""
import csv
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys
import types

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import relationship_journey as journey


def db(tmp_path):
    path = tmp_path / "relations.sqlite"
    with sqlite3.connect(path) as con:
        con.execute("""CREATE TABLE relationship_events(
            seq INTEGER PRIMARY KEY, event_id TEXT, network TEXT, queue TEXT,
            subject TEXT, kind TEXT, outcome TEXT, occurred_at TEXT,
            precision TEXT)""")
    return path


def add(path, net, kind, outcome, stamp="2026-09-01T12:00:00+00:00",
        subject="lectora", precision="instant", queue="API"):
    with sqlite3.connect(path) as con:
        con.execute("""INSERT INTO relationship_events
            (event_id, network, queue, subject, kind, outcome, occurred_at, precision)
            VALUES(?,?,?,?,?,?,?,?)""",
            (f"id-{net}-{kind}-{outcome}-{stamp}-{subject}-{precision}",
             net, queue, subject, kind, outcome, stamp, precision))


@pytest.mark.parametrize("network", sorted(journey.NETWORKS))
def test_nine_networks_share_one_contract(tmp_path, network):
    path = db(tmp_path)
    add(path, network, "follow", "confirmed")
    rows, omissions = journey.read_ledger(path)
    assert len(rows) == 1
    assert rows[0]["network"] == network
    assert rows[0]["event"] == "follow.confirmed"
    assert json.loads(rows[0]["user_id"]) == [network, "lectora"]
    assert omissions == {}


def test_no_cross_network_merge_without_identity_evidence(tmp_path):
    path = db(tmp_path)
    add(path, "x", "follow", "confirmed", subject="mismo")
    add(path, "threads", "follow", "confirmed", subject="mismo")
    rows, _ = journey.read_ledger(path)
    result = journey.summarize(rows, as_of=date(2026, 10, 10))
    assert result["paths"] == 2
    assert all(len(result["network_events"][n]) == 1 for n in ("x", "threads"))


def test_no_false_retention_from_unknown_or_daily_rows(tmp_path):
    path = db(tmp_path)
    add(path, "x", "follow", "confirmed")
    add(path, "x", "comment", "uncertain", stamp="2026-09-02T10:00:00Z")
    add(path, "x", "followback", "absent", stamp="2026-09-03T11:00:00Z")
    add(path, "x", "comment", "confirmed", stamp="2026-09-04T11:00:00Z", precision="day")
    rows, omitted = journey.read_ledger(path)
    assert [r["event"] for r in rows] == ["follow.confirmed"]
    assert omitted == {"not_positive_evidence": 2, "day_precision": 1}
    assert journey.summarize(rows, as_of=date(2026, 10, 10))["transitions_strict_time"] == []


def test_followback_snapshots_not_new_interactions(tmp_path):
    path = db(tmp_path)
    add(path, "bluesky", "follow", "confirmed")
    add(path, "bluesky", "followback", "present", stamp="2026-09-02T12:00:00Z")
    add(path, "bluesky", "followback", "present", stamp="2026-09-04T12:00:00Z")
    rows, omitted = journey.read_ledger(path)
    assert [r["event"] for r in rows] == ["follow.confirmed", "followback.present"]
    assert omitted["repeated_followback_snapshot"] == 1
    cohorts = journey.summarize(rows, as_of=date(2026, 10, 10))["followback_observed_lower_bound"]["bluesky"]
    assert cohorts["7"] == {"eligible": 1, "observed_followback": 1}
    assert cohorts["30"] == {"eligible": 1, "observed_followback": 1}


def test_censored_cohorts_never_claim_failure_without_evidence(tmp_path):
    path = db(tmp_path)
    add(path, "mastodon", "follow", "confirmed", stamp="2026-10-08T12:00:00Z")
    rows, _ = journey.read_ledger(path)
    cohorts = journey.summarize(rows, as_of=date(2026, 10, 10))["followback_observed_lower_bound"]["mastodon"]
    assert cohorts["7"] == {"eligible": 0, "observed_followback": 0}
    assert cohorts["30"] == {"eligible": 0, "observed_followback": 0}


def test_followback_before_follow_is_not_attributed(tmp_path):
    path = db(tmp_path)
    add(path, "reddit", "followback", "present", stamp="2026-09-01T12:00:00Z")
    add(path, "reddit", "follow", "confirmed", stamp="2026-09-03T12:00:00Z")
    rows, _ = journey.read_ledger(path)
    cohorts = journey.summarize(rows, as_of=date(2026, 10, 10))["followback_observed_lower_bound"]["reddit"]
    assert cohorts["7"]["eligible"] == 1
    assert cohorts["7"]["observed_followback"] == 0


def test_outcome_within_d7_but_not_after_d7(tmp_path):
    path = db(tmp_path)
    add(path, "instagram", "follow", "confirmed", stamp="2026-09-01T10:00:00Z")
    add(path, "instagram", "followback", "present", stamp="2026-09-15T10:00:00Z")
    rows, _ = journey.read_ledger(path)
    cohorts = journey.summarize(rows, as_of=date(2026, 10, 10))["followback_observed_lower_bound"]["instagram"]
    assert cohorts["7"]["observed_followback"] == 0
    assert cohorts["30"]["observed_followback"] == 1


def test_no_order_inferred_when_same_instant(tmp_path):
    path = db(tmp_path)
    add(path, "pinterest", "follow", "confirmed", stamp="2026-09-01T12:00:00Z")
    add(path, "pinterest", "reply", "confirmed", stamp="2026-09-01T12:00:00+00:00")
    rows, _ = journey.read_ledger(path)
    assert journey.summarize(rows, as_of=date(2026, 10, 10))["transitions_strict_time"] == []


def test_readonly_does_not_create_missing_path(tmp_path):
    missing = tmp_path / "never_created.sqlite"
    with pytest.raises(ValueError):
        journey.read_ledger(missing)
    assert not missing.exists()


def test_reject_action_ledger_and_invalid_timestamp(tmp_path):
    path = tmp_path / "actions.sqlite"
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE actions (kind TEXT)")
    with pytest.raises(ValueError, match="ledger relacional"):
        journey.read_ledger(path)
    path = db(tmp_path)
    add(path, "x", "follow", "confirmed", stamp="2026-09-01T12:00:00")
    with pytest.raises(ValueError, match="sin zona"):
        journey.read_ledger(path)


def test_reject_future_asof_and_unknown_network(tmp_path):
    path = db(tmp_path)
    add(path, "x", "follow", "confirmed")
    rows, _ = journey.read_ledger(path)
    with pytest.raises(ValueError, match="posterior"):
        journey.summarize(rows, as_of=date(2026, 8, 1))
    add(path, "fake", "follow", "confirmed")
    with pytest.raises(ValueError, match="incompatible"):
        journey.read_ledger(path)


def test_csv_export_is_opt_in_and_no_post_text(tmp_path):
    path = db(tmp_path)
    add(path, "tiktok", "like", "confirmed")
    rows, _ = journey.read_ledger(path)
    output = tmp_path / "journey.csv"
    assert not output.exists()
    journey.write_csv(rows, output)
    with output.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames) == journey.CSV_COLUMNS
        assert next(reader)["event"] == "like.confirmed"


def test_real_retentioneering_integration_interface_with_fake_modules(monkeypatch):
    """Smoke de interfaz; no instala la dependencia pesada en CI de ejecucion."""
    class FakeFrame:
        def __init__(self, rows, columns):
            self.rows, self.columns = rows, columns
        def __getitem__(self, key):
            return self.rows[0][key]
        def __setitem__(self, key, value):
            self.converted = (key, value)

    frame = types.SimpleNamespace(DataFrame=lambda rows, columns: FakeFrame(rows, columns),
                                  to_datetime=lambda value, utc: (value, utc))
    fake = types.SimpleNamespace(Eventstream=lambda df: ("eventstream", df))
    monkeypatch.setitem(sys.modules, "pandas", frame)
    monkeypatch.setitem(sys.modules, "retentioneering", fake)
    result = journey.to_eventstream([{"user_id": '["x","a"]', "event": "follow.confirmed",
                                      "timestamp": "2026-09-01T00:00:00+00:00"}])
    assert result[0] == "eventstream"
    assert result[1].columns == ("user_id", "event", "timestamp")
    assert result[1].converted[0] == "timestamp"

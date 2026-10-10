"""PR #45: ningún evento inventado ni doble captura, todo aislado."""
import sqlite3
from contextlib import closing
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import loyalty_events as e


def test_x_two_mentions_same_author_same_day_are_distinct(tmp_path):
    raw = {"includes": {"users": [{"id": "77", "username": "lectora"}]}, "data": [
        {"id": "1001", "author_id": "77", "created_at": "2026-10-09T09:00:00Z",
         "in_reply_to_user_id": "42"},
        {"id": "1002", "author_id": "77", "created_at": "2026-10-09T12:00:00Z"},
    ]}
    events = e.x_mentions(raw, "42")
    assert [row["kind"] for row in events] == ["comment", "mention"]
    db = tmp_path / "ledger.sqlite"
    assert e.record(events, path=db) == 2
    assert e.record(events, path=db) == 0
    with closing(sqlite3.connect(db)) as con:
        assert con.execute("SELECT count(*) FROM verified_inbound").fetchone()[0] == 2


def test_unresolved_x_author_or_id_fails_closed():
    raw = {"data": [
        {"id": "1", "author_id": "33", "created_at": "2026-10-09T10:00:00Z"},
        {"id": "not-id", "author_id": "1", "created_at": "2026-10-09T10:00:00Z"},
    ]}
    assert e.x_mentions(raw, "44") == []


def test_threads_replies_need_own_root_and_stable_id(tmp_path):
    events = e.threads_replies([
        {"id": "5", "username": "Lectora", "timestamp": "2026-10-09T12:00:00Z",
         "root_post": {"id": "42"}, "replied_to": {"id": "42"}},
        {"id": "6", "username": "david", "timestamp": "2026-10-09T12:00:00Z",
         "root_post": {"id": "42"}},
        {"id": "7", "username": "Otro", "timestamp": "2026-10-09T12:00:00Z",
         "root_post": {"id": "123"}},
        {"id": "", "username": "Otro", "timestamp": "2026-10-09T12:00:00Z",
         "root_post": {"id": "42"}},
    ], "david", "42")
    assert [x["event_id"] for x in events] == ["5"]
    assert e.record(events, path=tmp_path / "t.sqlite") == 1


def test_cross_network_ids_remain_separate(tmp_path):
    db = tmp_path / "shared.sqlite"
    x = {"network": "x", "event_id": "99", "author_id": "5",
         "handle": "a", "kind": "mention", "day": "2026-10-09",
         "source": "api:users_mentions", "target_id": "42"}
    t = {**x, "network": "threads", "kind": "comment",
         "source": "api:own_post_replies"}
    assert e.record([x,t], path=db) == 2
    assert e.record([t], path=db) == 0


def test_reject_unverified_event_before_database_created(tmp_path):
    db = tmp_path / "none.sqlite"
    bad = {"network": "x", "event_id": "", "author_id": "3",
           "handle": "a", "kind": "like", "day": "2026-10-09",
           "source": "browser:text_guess", "target_id": "42"}
    with pytest.raises(ValueError):
        e.record([bad], path=db)
    assert not db.exists()


def test_threads_api_mock_no_network_or_writes(tmp_path):
    requests = []
    def fake_api(path, token, **params):
        requests.append((path, params))
        if path == "me/threads":
            return {"data": [{"id": "42", "is_reply": False, "has_replies": True}]}
        assert path == "42/replies"
        return {"data": [{"id": "123", "username": "lectora",
                          "timestamp": "2026-10-09T15:00:00Z",
                          "replied_to": {"id": "42"}}]}
    result = e.read_threads_api(fake_api, "fake-token", "david")
    assert len(result) == 1 and result[0]["event_id"] == "123"
    assert len(requests) == 2
    assert not (tmp_path / "anything.sqlite").exists()



def test_threads_owned_posts_next_page_refused_before_reading_or_recording(tmp_path):
    calls = []
    def fake_api(path, token, **kwargs):
        calls.append(path)
        return {"data": [{"id": "42", "is_reply": False, "has_replies": True}],
                "paging": {"next": "https://graph.threads.net/me/threads?after=next",
                           "cursors": {"after": "next"}}}
    with pytest.raises(ValueError, match="más posts"):
        e.read_threads_api(fake_api, "fake-token", "david")
    assert calls == ["me/threads"]
    assert not list(tmp_path.glob("*.sqlite"))


def test_threads_owned_post_missing_is_reply_is_not_assumed_root():
    def fake_api(path, token, **kwargs):
        return {"data": [{"id": "42", "has_replies": True}]}
    with pytest.raises(ValueError, match="is_reply"):
        e.read_threads_api(fake_api, "fake-token", "david")


def test_threads_owned_post_missing_has_replies_not_silently_skipped():
    def fake_api(path, token, **kwargs):
        return {"data": [{"id": "42", "is_reply": False}]}
    with pytest.raises(ValueError, match="has_replies"):
        e.read_threads_api(fake_api, "fake-token", "david")


@pytest.mark.parametrize("limit", [0, -1, False, 101])
def test_threads_invalid_post_limit_denied_without_api_call(limit):
    def forbidden_api(*args, **kwargs):
        raise AssertionError("API no debe ejecutarse")
    with pytest.raises(ValueError, match="límites"):
        e.read_threads_api(forbidden_api, "no-token", "david", max_posts=limit)


def test_threads_zero_page_limit_denied_without_api_call():
    def forbidden_api(*args, **kwargs):
        raise AssertionError("API no debe ejecutarse")
    with pytest.raises(ValueError, match="límites"):
        e.read_threads_api(forbidden_api, "no-token", "david", max_pages=0)



def test_threads_api_permission_error_propagates():
    def denied(*args, **kwargs):
        raise PermissionError("threads_read_replies unavailable")
    with pytest.raises(PermissionError):
        e.read_threads_api(denied, "fake-token", "david")


def test_threads_api_unbounded_pagination_refused():
    def api(path, token, **kwargs):
        if path == "me/threads":
            return {"data": [{"id": "42", "is_reply": False, "has_replies": True}]}
        return {"data": [], "paging": {"next": "https://graph.threads.net/?after=x",
                                         "cursors": {"after": "same"}}}
    with pytest.raises(ValueError):
        e.read_threads_api(api, "fake-token", "david")


def test_legacy_inbound_feed_is_kept_until_verified_reader_is_connected():
    """Decision del revisor (09/10): no quitar la senal de reciprocidad de X/Threads sin sustituto conectado a INBOUND."""
    root = Path(__file__).resolve().parents[1] / "tools"
    for name in ("x_scan.py", "threads_scan.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "_rp.log_inbound(" in source



def test_duplicate_event_id_conflicting_target_rolls_back(tmp_path):
    db = tmp_path / "events.sqlite"
    item = {"network": "x", "event_id": "900", "author_id": "77",
            "handle": "lectora", "kind": "mention", "day": "2026-10-09",
            "source": "api:users_mentions", "target_id": "42"}
    assert e.record([item], path=db) == 1
    with pytest.raises(ValueError, match="colision"):
        e.record([{**item, "target_id": "84"}], path=db)
    with closing(sqlite3.connect(db)) as con:
        assert con.execute("SELECT target_id FROM verified_inbound").fetchone() == ("42",)


def test_no_false_thread_reply_from_somebody_elses_root():
    rows = [{"id": "555", "username": "lectora",
             "timestamp": "2026-10-09T10:00:00Z",
             "root_post": {"id": "external"}}]
    assert e.threads_replies(rows, "david", "42") == []
    nested = [{"id": "557", "username": "lectora",
               "timestamp": "2026-10-09T10:00:00Z",
               "root_post": {"id": "42"}, "replied_to": {"id": "556"}}]
    assert e.threads_replies(nested, "david", "42") == []


def test_incomplete_threads_page_never_persists(tmp_path):
    def api(path, token, **kwargs):
        if path == "me/threads":
            return {"data": [{"id": "42", "is_reply": False, "has_replies": True}]}
        raise PermissionError("429 / permiso insuficiente")
    with pytest.raises(PermissionError):
        e.read_threads_api(api, "unused", "david")
    assert not list(tmp_path.glob("*.sqlite"))


def test_invalid_source_network_is_denied(tmp_path):
    item = {"network": "threads", "event_id": "12", "author_id": "",
            "handle": "lectora", "kind": "comment", "day": "2026-10-09",
            "source": "api:users_mentions", "target_id": "42"}
    with pytest.raises(ValueError):
        e.record([item], path=tmp_path / "events.sqlite")

"""Pruebas unitarias del puente de investigación; solo fixtures, ninguna API."""
import datetime as dt
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import threads_research_bridge as bridge

NOW = dt.datetime(2026, 10, 10, 9, tzinfo=dt.timezone.utc)


def item(**updates):
    data = {"id": "101", "username": "lectora",
            "permalink": "https://www.threads.com/@lectora/post/xyz",
            "text": "He leído una novela de fantasía romántica que recomiendo.",
            "timestamp": "2026-10-10T08:00:00Z"}
    data.update(updates)
    return data


def test_nested_corpus_and_direct_jsonl(tmp_path):
    p = tmp_path / "export.json"
    p.write_text(json.dumps({"corpus": [{"post": {
        "author_username": "lectora", "url": item()["permalink"],
        "text": item()["text"], "published_at": item()["timestamp"]}}]}),
        encoding="utf-8")
    rows, stats = bridge.normalize("threads", bridge.read_export(p), now=NOW)
    assert stats["validos_unicos"] == 1 and rows[0][4] == 1
    p.write_text(json.dumps(item(), ensure_ascii=False) + "\n" +
                 json.dumps(item()), encoding="utf-8")
    rows, stats = bridge.normalize("threads", bridge.read_export(p), now=NOW)
    assert len(rows) == 1 and stats["duplicados_identicos"] == 1


def test_conflicts_rejected_and_nonfirst_winner():
    rows, stats = bridge.normalize("threads",
                                   [item(), item(text="Otro texto"), item()], now=NOW)
    assert rows == [] and stats["descartados"]["conflicto_duplicado"] == 1


def test_no_implicit_age_or_identity_or_website():
    rows, stats = bridge.normalize("threads", [
        item(timestamp=None), item(username="otra"),
        item(permalink="https://threads.com.evil.test/@lectora/post/xyz"),
        item(timestamp="2026-10-10T08:00:00"),
        item(timestamp="2026-10-11T08:00:00Z")], now=NOW)
    assert not rows and sum(stats["descartados"].values()) == 5


def test_other_networks_not_faked_and_fails_closed():
    try:
        bridge.normalize("x", [item()], now=NOW)
    except NotImplementedError:
        pass
    else:
        assert False, "no se puede simular cobertura de red"


def test_reject_oversize_and_structures(tmp_path):
    p = tmp_path / "invalid.json"
    p.write_text(json.dumps({"not_corpus": []}), encoding="utf-8")
    try:
        bridge.read_export(p)
    except ValueError:
        pass
    else:
        assert False
    p.write_bytes(b"a" * (bridge.MAX_BYTES + 1))
    try:
        bridge.read_export(p)
    except ValueError:
        pass
    else:
        assert False


def test_write_pool_only_explicit_db(tmp_path, monkeypatch):
    rows, _ = bridge.normalize("threads", [item()], now=NOW)
    path = tmp_path / "local.sqlite3"
    import types
    calls = []
    class Connection:
        def close(self):
            calls.append("close")
    def record(db, values):
        calls.append((db, values))
        return len(values)
    monkeypatch.setitem(sys.modules, "browser_pool", types.SimpleNamespace(
        connect=lambda path: Connection(), record_post_rows=record))
    assert bridge.ingest_rows(rows, db_path=path) == 1
    assert calls[0][1] == rows and calls[1] == "close"


def test_output_has_no_private_post_text(tmp_path, capsys):
    p = tmp_path / "export.json"
    p.write_text(json.dumps([item()], ensure_ascii=False), encoding="utf-8")
    assert bridge.main(["--input", str(p)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "dry_run"
    assert "He leído" not in json.dumps(report, ensure_ascii=False)
    assert not list(tmp_path.glob("*.sqlite*"))


def test_url_canonicalization_and_deduplication():
    rows, stats = bridge.normalize("threads", [
        item(permalink="https://threads.net/@lectora/post/xyz?utm_source=foo"),
        item()], now=NOW)
    assert len(rows) == 1
    assert rows[0][1] == "https://www.threads.com/@lectora/post/xyz"
    assert stats["duplicados_identicos"] == 1

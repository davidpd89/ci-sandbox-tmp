"""PR #48: clasificación sin I/O ni inferencias de identidad."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import discovery_terms as discovery


def test_unverified_sources_never_become_audience():
    rows = discovery.tag_seeds("x", [{"handle": "@Editorial", "source": "publisher:followers", "evidence": []}])
    assert rows[0]["roles"] == []
    assert rows[0]["status"] == "unverified"


def test_distinct_roles_require_distinct_evidence():
    entries = discovery.tag_seeds("bluesky", [{"handle": "@lector.bsky.social", "source": "post:42",
        "evidence": [
            {"kind": "conversation_post", "id": "at://did:plc:a/post/1"},
            {"kind": "reader_interaction", "id": "at://did:plc:a/post/2"},
            {"kind": "follow_graph", "id": "did:plc:b"},
        ]}])
    assert entries[0]["roles"] == ["audience_hub", "conversation_hub", "follow_hub"]
    assert len(entries[0]["evidence"]) == 3


def test_dedupe_by_origin_keeps_other_provenance():
    rows = discovery.tag_seeds("threads", [
        {"handle": "@LECTORA", "source": "Perfil:uno",
         "evidence": [{"kind": "conversation_post", "id": "post-1"}]},
        {"handle": "lectora", "source": "perfil:uno",
         "evidence": [{"kind": "conversation_post", "id": "post-1"},
                      {"kind": "conversation_post", "id": "post-2"}]},
        {"handle": "lectora", "source": "perfil:dos",
         "evidence": [{"kind": "reader_interaction", "id": "post-3"}]},
    ])
    assert len(rows) == 2
    assert [len(row["evidence"]) for row in rows] == [2, 1]
    assert rows[0]["roles"] == ["conversation_hub"]
    assert rows[1]["roles"] == ["audience_hub"]


def test_invalid_evidence_fails_closed():
    import pytest
    bad = [
        {"handle": "@a", "source": "r", "evidence": [{"kind": "like_count", "id": "99"}]},
        {"handle": "@a", "source": "r", "evidence": [{"kind": "follow_graph", "id": ""}]},
        {"handle": "", "source": "r", "evidence": []},
        {"handle": "a", "source": "", "evidence": []},
        {"handle": "a", "source": "r", "evidence": ["I think they read"]},
    ]
    for row in bad:
        with pytest.raises(ValueError):
            discovery.tag_seeds("x", [row])


def test_legacy_terms_api_unchanged_by_classification(tmp_path, monkeypatch):
    import json
    config = tmp_path / "discovery.json"
    config.write_text(json.dumps({"x": {"hubs": ["seed:followers", "large:audience_hub"]}}), encoding="utf-8")
    monkeypatch.setattr(discovery, "PATH", str(config))
    assert discovery.terms("x", "hubs") == ["seed:followers", "large:audience_hub"]
    assert discovery.tag_seeds("x", [{"handle": "reader", "source": "large:audience_hub"}])[0]["roles"] == []



def test_network_input_normalized_before_identity_and_dedupe():
    observations = [{"handle": "@LectorA", "source": "post:1",
                     "evidence": [{"kind": "conversation_post", "id": "post-99"}]},
                    {"handle": "lectora", "source": "post:1",
                     "evidence": [{"kind": "conversation_post", "id": "post-99"}]}]
    rows = discovery.tag_seeds(" X ", observations)
    assert len(rows) == 1
    assert rows[0]["network"] == "x"
    assert rows[0]["handle"] == "lectora"
    assert len(rows[0]["evidence"]) == 1



def test_mastodon_domains_not_collapsed():
    rows = discovery.tag_seeds("mastodon", [
        {"handle": "@reader@host1.social", "source": "directory", "evidence": []},
        {"handle": "@reader@host2.social", "source": "directory", "evidence": []},
    ])
    assert len(rows) == 2



def test_reject_unknown_network_or_control_characters():
    import pytest
    with pytest.raises(ValueError):
        discovery.tag_seeds("unknown-platform", [])
    with pytest.raises(ValueError):
        discovery.tag_seeds("x", [{"handle": "bad handle", "source": "seed", "evidence": []}])
    with pytest.raises(ValueError):
        discovery.tag_seeds("x", [{"handle": "a", "source": "seed\nprivate", "evidence": []}])
    with pytest.raises(ValueError):
        discovery.tag_seeds("x", [{"handle": "a", "source": "seed",
                                   "evidence": [{"kind": ["follow_graph"], "id": "42"}]}])

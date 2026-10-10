"""Pruebas offline: nueve redes, tres colas, estabilidad y segundas pasadas adversariales."""
import copy
import datetime as dt
import json
import subprocess
import sys

import pytest

from tools import relationship_priority as p

TODAY = dt.date(2026, 10, 10)
NETWORKS = ("x", "threads", "facebook", "pinterest", "reddit",
            "bluesky", "mastodon", "tiktok", "instagram")
LANES = ("WEB", "API", "MOBILE")


def row(network="bluesky", handle="lector", lane="API", **overrides):
    data = dict(network=network, handle=handle, lane=lane, affinity=0.75,
                inbound={"comment": 2, "like": 3, "follow": 1},
                last_inbound_at="2026-10-09", last_outbound_at="2026-09-20",
                latest_post_at="2026-10-09", reply_target_at="2026-10-09",
                reply_eligible=True, thread_verified=True, follow_eligible=True,
                reactivation_eligible=False, visit_eligible=True)
    data.update(overrides)
    return data


def rank(*rows, **kwargs):
    return p.rank_daily({"candidates": list(rows)}, today=TODAY, **kwargs)


@pytest.mark.parametrize("net", NETWORKS)
def test_nueve_redes_sin_excepciones(net):
    lane = "MOBILE" if net == "tiktok" else ("WEB" if net in ("x", "reddit") else "API")
    result = rank(row(net, lane=lane))
    assert result["queues"][lane][0]["network"] == net


@pytest.mark.parametrize("lane", LANES)
def test_tres_colas_separadas(lane):
    result = rank(row(lane=lane))
    assert [len(result["queues"][l]) for l in LANES] == [int(l == lane) for l in LANES]


def test_determinismo_y_orden_de_entrada():
    rows = [row(handle=f"lector{i}", affinity=i / 20) for i in range(10)]
    a = rank(*rows)
    b = rank(*reversed(rows))
    assert a["queues"] == b["queues"]


def test_replay_mismo_dia_mismo_resultado():
    assert rank(row()) == rank(row())


def test_relevancia_mas_alta_mejora_score():
    a = rank(row(affinity=0.2))["queues"]["API"][0]["score"]
    b = rank(row(affinity=0.8))["queues"]["API"][0]["score"]
    assert b > a


def test_fatiga_penaliza_sin_eliminar_candidato():
    a = rank(row(outbound_30d=0))["queues"]["API"][0]["score"]
    b = rank(row(outbound_30d=4))["queues"]["API"][0]["score"]
    assert b < a


def test_recencia_ponderada():
    a = rank(row(last_inbound_at="2026-10-10"))["queues"]["API"][0]["score"]
    b = rank(row(last_inbound_at="2026-09-20"))["queues"]["API"][0]["score"]
    assert a > b


def test_pregunta_sin_hilo_no_es_reply():
    r = rank(row(thread_verified=False))
    assert r["queues"]["API"][0]["action"] != "reply"
    assert any("contexto" in s for s in r["queues"]["API"][0]["notes"])


def test_reply_vencida_no_hay_necroposting():
    r = rank(row(reply_target_at="2026-09-20", latest_post_at="2026-10-09"))
    assert r["queues"]["API"][0]["action"] != "reply"
    assert any("antiguo" in s for s in r["queues"]["API"][0]["notes"])


def test_reply_fecha_futura_se_descarta_entero():
    r = rank(row(reply_target_at="2026-10-11"))
    assert r["summary"]["unique_eligible"] == 0
    assert "futura" in r["excluded"][0]["reason"]


def test_reply_edad_limite_inclusivo():
    r = rank(row(reply_target_at="2026-10-03"))
    assert r["queues"]["API"][0]["action"] == "reply"


def test_follow_no_sobre_ya_seguido():
    r = rank(row(reply_eligible=False, already_following=True))
    assert r["queues"]["API"][0]["action"] == "visit"


def test_reactivacion_exige_post_reciente_y_silencio():
    r = rank(row(reply_eligible=False, follow_eligible=False, reactivation_eligible=True))
    assert r["queues"]["API"][0]["action"] == "reactivate"
    old = rank(row(reply_eligible=False, follow_eligible=False,
                   reactivation_eligible=True, latest_post_at="2026-09-01"))
    assert old["queues"]["API"][0]["action"] == "visit"


@pytest.mark.parametrize("field", ["blocked", "self_account"])
def test_cuentas_excluidas(field):
    assert rank(row(**{field: True}))["summary"]["selected"] == 0


def test_sin_elegibilidad_no_inventa_accion():
    result = rank(row(reply_eligible=False, follow_eligible=False, visit_eligible=False))
    assert result["summary"]["selected"] == 0


def test_identidad_duplicada_en_dos_colas_un_solo_actor():
    result = rank(row(handle="Lector", lane="WEB", reply_eligible=False),
                  row(handle="@lector", lane="API"))
    assert result["summary"]["unique_eligible"] == 1
    assert result["queues"]["API"][0]["action"] == "reply"


def test_mismo_handle_diferentes_redes_no_se_mezcla():
    result = rank(row(network="bluesky"), row(network="mastodon"))
    assert result["summary"]["unique_eligible"] == 2


def test_ids_estables_distintos_no_se_mezclan():
    result = rank(row(handle="mismo", actor_id="did:plc:uno"),
                  row(handle="mismo", actor_id="did:plc:dos"))
    assert result["summary"]["unique_eligible"] == 2


def test_bonus_diversidad_blanda():
    rows = [row("bluesky", f"b{i}", affinity=0.8) for i in range(5)]
    rows += [row("mastodon", f"m{i}", affinity=0.8) for i in range(5)]
    q = rank(*rows, limits={"WEB": 0, "API": 4, "MOBILE": 0})["queues"]["API"]
    assert {r["network"] for r in q} == {"bluesky", "mastodon"}


def test_diversidad_no_cierra_volumen_de_una_sola_red():
    rows = [row(handle=f"cuenta{i}") for i in range(50)]
    q = rank(*rows, limits={"WEB": 0, "API": 50, "MOBILE": 0})["queues"]["API"]
    assert len(q) == 50


def test_limites_independientes():
    result = rank(row(handle="a", lane="WEB"),
                  row(handle="b", lane="API"),
                  row(handle="c", lane="MOBILE"),
                  limits={"WEB": 0, "API": 1, "MOBILE": 0})
    assert result["summary"]["selected"] == 1
    assert len(result["queues"]["API"]) == 1


@pytest.mark.parametrize("bad", [
    {"network": "discord"}, {"lane": "AUTO"}, {"handle": "cuenta|celda"},
    {"affinity": float("nan")}, {"reciprocity": 1.1},
    {"reply_eligible": "sí"}, {"inbound": {"comment": -1}},
    {"inbound": {"comment": 0.5}}, {"inbound": {"sorpresa": 3}},
    {"last_inbound_at": "2026-10-11"},
    {"latest_post_at": "2026-10-11"},
    {"outbound_30d": -5},
    {"actor_id": ""},
])
def test_entrada_erronea_aislada(bad):
    r = rank(row(**bad), row(handle="valida"))
    assert r["summary"]["selected"] == 1
    assert r["summary"]["candidates"] == 2
    assert r["excluded"][0]["index"] == 0


def test_inbound_con_conteos_requiere_fecha():
    r = rank(row(last_inbound_at=None))
    assert r["summary"]["selected"] == 0


def test_ausencia_de_observacion_no_inventa_recencia():
    r = rank(row(inbound={}, last_inbound_at=None))
    assert r["queues"]["API"][0]["features"]["recency"] == 0


def test_evaluacion_solo_labels_fixture_no_entran_score():
    first = row(handle="a", converted=True)
    second = row(handle="b", converted=False)
    snapshot = {"candidates": [first, second]}
    a = p.rank_daily(snapshot, today=TODAY)
    second["converted"], first["converted"] = True, False
    b = p.rank_daily(snapshot, today=TODAY)
    assert a == b
    metric = p.evaluate_synthetic(snapshot, b, k=2)
    assert metric["API"]["precision"] == 0.5


def test_evaluacion_sin_etiquetas_no_inventa_precision():
    r = rank(row())
    assert p.evaluate_synthetic({"candidates": [row()]}, r)["API"]["precision"] is None


def test_contradiccion_de_etiquetas_se_denuncia():
    r = rank(row())
    with pytest.raises(ValueError, match="contradictorias"):
        p.evaluate_synthetic({"candidates": [row(converted=True),
                                               row(converted=False)]}, r)


def test_markdown_vista_explica_puntuacion():
    text = p.markdown(rank(row()))
    assert "## API" in text and "niche:" in text and "Recomendaciones" in text
    assert "WEB" in text and "MOBILE" in text


def test_input_inmutable():
    snapshot = {"candidates": [row()]}
    original = copy.deepcopy(snapshot)
    p.rank_daily(snapshot, today=TODAY)
    assert snapshot == original


def test_cli_no_escribe_estado(tmp_path):
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps({"candidates": [row()]}), encoding="utf-8")
    before = set(tmp_path.iterdir())
    result = subprocess.run([sys.executable, "-m", "tools.relationship_priority",
                             "--input", str(path), "--today", "2026-10-10",
                             "--format", "json", "--evaluate-synthetic"],
                            capture_output=True, text=True, check=True)
    assert set(tmp_path.iterdir()) == before
    decoded = json.loads(result.stdout)
    assert decoded["summary"]["selected"] == 1
    assert decoded["synthetic_evaluation"]["API"]["precision"] is None


def test_limites_invalidos_se_rechazan():
    with pytest.raises(ValueError):
        rank(row(), limits={"API": 4, "WEB": 0})
    with pytest.raises(ValueError):
        rank(row(), limits={"API": -1, "WEB": 0, "MOBILE": 0})


def test_carga_sintetica_900_perfiles():
    rows = [row(net, f"lector{i}", lane=LANES[i % 3], affinity=(i % 10) / 10)
            for i, net in enumerate(NETWORKS * 100)]
    result = rank(*rows, limits={lane: 1000 for lane in LANES})
    assert result["summary"]["unique_eligible"] == 900
    assert result["summary"]["selected"] == 900


def test_unicode_handle_and_no_markdown_injection():
    result = rank(row(handle="lectór_ñ"))
    assert result["queues"]["API"][0]["handle"] == "lectór_ñ"
    assert "lectór_ñ" in p.markdown(result)


def test_actor_id_canonical_case_not_duplicated():
    result = rank(row(handle="ana", actor_id="DID:PLC:UNO"),
                  row(handle="otra_ana", actor_id="did:plc:uno"))
    assert result["summary"]["unique_eligible"] == 1


def test_date_compact_and_week_format_rejected():
    result = rank(row(last_inbound_at="20261009"),
                  row(handle="otro", last_inbound_at="2026-W41-5"))
    assert result["summary"]["selected"] == 0
    assert len(result["excluded"]) == 2


def test_evaluation_actor_id_casefold():
    candidate = row(actor_id="DID:PLC:ONE", converted=True)
    snapshot = {"candidates": [candidate]}
    ranked = p.rank_daily(snapshot, today=TODAY)
    assert p.evaluate_synthetic(snapshot, ranked)["API"]["precision"] == 1.0


def test_flag_unknown_missing_never_promotes_to_follow():
    result = rank(row(reply_eligible=False, follow_eligible=False, visit_eligible=True))
    assert result["queues"]["API"][0]["action"] == "visit"


@pytest.mark.parametrize("bad", [
    {"network": []}, {"network": {}}, {"network": 123},
    {"lane": []}, {"affinity": 10 ** 400},
    {"outbound_30d": 10 ** 400}, {"inbound": {"like": 10 ** 400}},
])
def test_adversarial_malformed_rows_do_not_crash_entire_batch(bad):
    result = rank(row(handle="mal", **bad), row(handle="sana"))
    assert result["summary"]["selected"] == 1
    assert result["excluded"][0]["index"] == 0


def test_boolean_age_limit_rejected():
    with pytest.raises(ValueError, match="max_target_age"):
        rank(row(), max_target_age=True)


def test_duplicate_tie_independent_of_source_order():
    a = row(handle="LectOr", actor_id="DID:PLC:UNICO")
    b = row(handle="lector", actor_id="did:plc:unico")
    forward = rank(a, b)["queues"]
    backward = rank(b, a)["queues"]
    assert forward == backward


def test_synthetic_evaluation_canonical_actor_id_with_whitespace():
    candidate = row(actor_id="  DID:PLC:ONE  ", converted=True)
    snapshot = {"candidates": [candidate]}
    ranked = p.rank_daily(snapshot, today=TODAY)
    assert p.evaluate_synthetic(snapshot, ranked)["API"]["precision"] == 1.0


# Tercera auditoria: fallos funcionales P1/P2 del controlador.
def test_lane_fallback_when_primary_budget_zero():
    limits = {"WEB": 1, "API": 0, "MOBILE": 0}
    result = rank(row(handle="actora", lane="API"),
                  row(handle="actora", lane="WEB", reply_eligible=False),
                  limits=limits)
    assert result["summary"]["unique_eligible"] == 1
    assert result["summary"]["selected"] == 1
    assert result["queues"]["WEB"][0]["handle"] == "actora"


def test_lane_fallback_when_primary_full_with_other_actor():
    limits = {"WEB": 1, "API": 1, "MOBILE": 0}
    result = rank(row(handle="ana", lane="API", affinity=0.8),
                  row(handle="ana", lane="WEB", affinity=0.8, reply_eligible=False),
                  row(handle="bea", lane="API", affinity=0.95),
                  limits=limits)
    assert result["summary"]["selected"] == 2
    assert {r["handle"] for lane in LANES for r in result["queues"][lane]} == {"ana", "bea"}


def test_augmented_matching_reassigns_high_scored_actor_for_coverage():
    # La asignacion codiciosa elegiria primero a Ana en API, despues dejaria
    # fuera a Bea, aunque Ana tiene alternativa WEB y Bea solo API.
    limits = {"WEB": 1, "API": 1, "MOBILE": 0}
    items = [row(handle="ana", lane="API", affinity=1),
             row(handle="ana", lane="WEB", affinity=1, reply_eligible=False),
             row(handle="bea", lane="API", affinity=0.9)]
    first = rank(*items, limits=limits)
    reverse = rank(*reversed(items), limits=limits)
    assert first["queues"] == reverse["queues"]
    assert first["summary"]["selected"] == 2
    assert first["queues"]["API"][0]["handle"] == "bea"
    assert first["queues"]["WEB"][0]["handle"] == "ana"


@pytest.mark.parametrize("flag", ["blocked", "self_account"])
@pytest.mark.parametrize("reverse", [False, True])
def test_cross_collector_veto_prevents_all_recommendations(flag, reverse):
    items = [row(handle="dos_alias", actor_id="did:plc:uno", lane="WEB",
                 reply_eligible=False, **{flag: True}),
             row(handle="otra_cuenta", actor_id="DID:PLC:UNO", lane="API")]
    if reverse:
        items.reverse()
    result = rank(*items)
    assert result["summary"]["selected"] == 0
    assert result["summary"]["unique_eligible"] == 0
    assert any("veto" in v["reason"] for v in result["excluded"])


def test_alias_with_and_without_actor_id_is_one_person():
    result = rank(row(handle="  inválida", lane="API"),
                  row(handle="@lectór", lane="API", actor_id="DID:PLC:UNO"),
                  row(handle="lectór", lane="WEB"))
    assert result["summary"]["candidates"] == 3
    assert result["summary"]["unique_eligible"] == 1
    assert result["summary"]["selected"] == 1


def test_ambiguous_unverified_handle_not_fused_with_two_ids():
    result = rank(row(handle="mismo", actor_id="did:plc:uno"),
                  row(handle="mismo", actor_id="did:plc:dos"),
                  row(handle="@mismo", lane="WEB"))
    assert result["summary"]["unique_eligible"] == 2
    assert result["summary"]["selected"] == 2
    assert any("ambigua" in v["reason"] for v in result["excluded"])


def test_ambiguous_blocked_handle_vetoes_all_conflicting_ids():
    result = rank(row(handle="mismo", actor_id="did:plc:uno"),
                  row(handle="mismo", actor_id="did:plc:dos"),
                  row(handle="@mismo", blocked=True))
    assert result["summary"]["selected"] == 0


def test_changed_handle_with_same_stable_id_is_single_actor():
    result = rank(row(handle="antiguo", actor_id="did:plc:uno", lane="WEB"),
                  row(handle="nuevo", actor_id="DID:PLC:UNO", lane="API"))
    assert result["summary"]["unique_eligible"] == 1
    assert result["summary"]["selected"] == 1


@pytest.mark.parametrize("network", NETWORKS)
def test_historical_engagement_decay_shared_across_networks(network):
    old = rank(row(network=network, handle="antigua", affinity=0.2,
                   inbound={"comment": 5, "follow": 1, "repost": 4, "like": 6},
                   last_inbound_at="2025-01-01"))
    recent = rank(row(network=network, handle="reciente", affinity=0.2,
                      inbound={"comment": 1}, last_inbound_at="2026-10-09"))
    old_features = old["queues"]["API"][0]["features"]
    new_features = recent["queues"]["API"][0]["features"]
    assert old_features["inbound"] < new_features["inbound"]
    assert old_features["depth"] < new_features["depth"]


def test_missing_inbound_observation_distinguished_from_verified_zero():
    unknown = rank(row(handle="desconocida", inbound=None))
    assert unknown["summary"]["selected"] == 0  # invalid contract, not imputed to zero
    r = row(handle="desconocida", last_inbound_at=None)
    del r["inbound"]
    result = rank(r)
    assert "inbound: observacion desconocida" in result["queues"]["API"][0]["notes"]
    assert result["queues"]["API"][0]["features"]["inbound"] == 0


def test_partial_synthetic_labels_do_not_claim_perfect_precision():
    candidates = [row(handle="a", converted=True), row(handle="b")]
    output = p.rank_daily({"candidates": candidates}, today=TODAY)
    result = p.evaluate_synthetic({"candidates": candidates}, output, k=2)["API"]
    assert result["observed"] == 1
    assert result["precision"] is None


def test_synthetic_evaluation_k_cannot_be_bool():
    snap = {"candidates": [row()]}
    with pytest.raises(ValueError, match="k debe"):
        p.evaluate_synthetic(snap, p.rank_daily(snap, today=TODAY), k=True)

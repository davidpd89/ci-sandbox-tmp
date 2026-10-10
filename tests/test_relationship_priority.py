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

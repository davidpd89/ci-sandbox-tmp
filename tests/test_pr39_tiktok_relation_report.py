"""Contratos offline de PR39: decisiones conservadoras, ninguna llamada a TikTok."""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import tiktok_relation_report as rr

TODAY = dt.date(2026, 10, 9)


def followed(h, date, result="confirmado"):
    return {"cuenta": "@" + h, "fecha": date, "tipo": "follow", "resultado": result}


def evidence(h, kind="comment", date="2026-10-08", result="confirmado"):
    return {"cuenta": "@" + h, "fecha": date, "tipo": kind, "resultado": result}


def audit(items, actions, inbound=(), observed="2026-10-09", protected=()):
    return rr.report(items, actions, list(inbound), today=TODAY,
                     observed_on=observed, protected=protected)


def one(result):
    return result["cuentas"][0]


def test_nothing_can_execute_unfollow():
    row = one(audit([{"handle": "reader1", "status": "Siguiendo"}],
                    [followed("reader1", "2026-09-18")]))
    assert row["categoria"] == "revision_21_mas" and row["accion"] == "ninguna"


@pytest.mark.parametrize("days,category", [
    (0, "espera"), (6, "espera"), (7, "revision_7_20"),
    (20, "revision_7_20"), (21, "revision_21_mas"), (30, "revision_21_mas"),
])
def test_date_boundaries(days, category):
    day = (TODAY - dt.timedelta(days=days)).isoformat()
    assert one(audit([{"handle": "reader1"}], [followed("reader1", day)]))["categoria"] == category


@pytest.mark.parametrize("date", ["no_date", "", "2026-10-10", "2026-02-30"])
def test_unknown_or_future_follow_never_counted_as_old(date):
    assert one(audit([{"handle": "reader1"}],
                     [followed("reader1", date)]))["categoria"] == "revision_incertidumbre"


def test_no_known_follow_date_means_unknown():
    assert one(audit([{"handle": "reader1"}], []))["edad_dias"] is None


def test_stale_or_unverified_snapshot_cannot_support_21_day_review():
    for observed in ["2026-10-01", "", "2026-11-01"]:
        x = audit([{"handle": "reader1"}],
                  [followed("reader1", "2026-08-01")], observed=observed)
        assert one(x)["categoria"] == "revision_incertidumbre"
        assert not x["snapshot_reciente"]


def test_mutual_safelist_and_interactions_override_review():
    entry = [{"handle": "reader1", "status": "Amigos"}]
    assert one(audit(entry, [followed("reader1", "2026-08-01")]))["categoria"] == "protegida"
    entry = [{"handle": "reader1"}]
    assert one(audit(entry, [followed("reader1", "2026-08-01"), evidence("reader1")]))["categoria"] == "protegida"
    incoming = {"fecha": "2026-10-08", "red": "tiktok", "handle": "reader1", "tipo": "like"}
    assert one(audit(entry, [followed("reader1", "2026-08-01")], [incoming]))["categoria"] == "protegida"
    assert one(audit(entry, [followed("reader1", "2026-08-01")],
                     protected=["@READER1"]))["categoria"] == "protegida"


def test_video_caption_is_not_authored_by_commenter():
    record = {"handle": "reader1", "video_caption": "Fantasía juvenil y libros"}
    assert one(audit([record], [followed("reader1", "2026-09-01")]))["categoria"] == "revision_21_mas"


def test_pending_ack_and_prior_unfollow_require_manual_check():
    entry = [{"handle": "reader1"}]
    pending = followed("reader1", "2026-10-08", "pendiente_verificacion")
    assert one(audit(entry, [followed("reader1", "2026-09-01"), pending]))["categoria"] == "revision_incertidumbre"
    stop = {"cuenta": "@reader1", "fecha": "2026-10-08",
            "tipo": "unfollow", "resultado": "confirmado"}
    assert one(audit(entry, [followed("reader1", "2026-10-07"), stop]))["categoria"] == "revision_incertidumbre"


def test_duplicate_handles_have_one_uncertain_result():
    x = audit([{"handle": "READER1"}, {"handle": "reader1"}],
              [followed("reader1", "2026-09-01")])
    assert x["totales"] == {"revision_incertidumbre": 1}
    assert x["cobertura"] == "parcial_o_desconocida"


def test_missing_mutual_label_does_not_prove_nonreciprocity():
    assert "reciprocidad no acreditada" in one(audit(
        [{"handle": "reader1"}], [followed("reader1", "2026-08-01")]
    ))["motivo"]


def test_bad_input_and_csv_fail_closed(tmp_path):
    with pytest.raises(ValueError):
        rr.report({}, [], [], today=TODAY)
    with pytest.raises(ValueError):
        rr.report([], [], [], today="2026-10-09")
    path = tmp_path / "registro.csv"
    path.write_text("fecha,cuenta,tipo\n2026-10-09,@x,follow\n", encoding="utf-8")
    with pytest.raises(ValueError):
        rr.read_csv(path, {"fecha", "cuenta", "tipo", "resultado"})
    path.write_text("fecha,cuenta,tipo,resultado\n2026-10-09,@x,follow\n", encoding="utf-8")
    with pytest.raises(ValueError):
        rr.read_csv(path, {"fecha", "cuenta", "tipo", "resultado"})


def test_normalizer_does_not_accept_url_as_handle():
    assert rr.normalize("@READER_name.11") == "reader_name.11"
    assert rr.normalize("https://example.org/name") is None


def test_no_network_or_account_writes(monkeypatch):
    import urllib.request
    def deny(*args, **kwargs):
        raise AssertionError("el informe no debe consultar red")
    monkeypatch.setattr(urllib.request, "urlopen", deny)
    x = audit([{"handle": "reader1"}], [followed("reader1", "2026-09-01")])
    assert x["acciones_remotas"] == 0

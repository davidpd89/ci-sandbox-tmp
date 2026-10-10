"""Pruebas puras de atribución, sin red ni ficheros operativos."""
import csv
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pinterest_funnel as pf


def fixture(tmp_path, columns, values):
    path = tmp_path / "fixture.csv"
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(columns)
        writer.writerows(values)
    return path


def pin(impressions="100", board="Libros", pin_id="123", *, level="pin", period="diario"):
    return ["2026-10-09", board, pin_id, "pinterest_analytics", period, level, impressions, "8", "4", "2"]


def ga4(scope="sesion", value="3"):
    if scope == "sesion":
        return ["2026-10-09", "lecturas", "pinterest", "organic", "sesion", "ultimo_clic_sesion", "-", value, ""]
    return ["2026-10-09", "lecturas", "pinterest", "organic", "evento", "basado_en_datos", "contacto", "", value]


def test_no_sources_never_mean_zero():
    result = pf.build_report("2026-10-09")
    assert result["pinterest"]["totales"]["impresiones"] is None
    assert result["web_ga4"]["totales"]["eventos_clave"] is None


def test_clicks_not_web_conversions(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin()])
    result = pf.build_report("2026-10-09", pins=path)
    assert result["pinterest"]["totales"]["clics_salientes"] == 2
    assert result["web_ga4"]["totales"]["eventos_clave"] is None


def test_independent_ga4_scopes(tmp_path):
    path = fixture(tmp_path, pf.WEB_FIELDS, [ga4(), ga4("evento", "1.5")])
    result = pf.build_report("2026-10-09", web=path)["web_ga4"]
    assert result["totales"]["sesiones"] == 3
    assert str(result["totales"]["eventos_clave"]) == "1.5"
    assert result["campanas"]["lecturas"]["modelo_eventos"] == "basado_en_datos"


@pytest.mark.parametrize("bad", ["-1", "nan", "1,4", "1e2", "2.5"])
def test_invalid_counts(tmp_path, bad):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin(impressions=bad)])
    with pytest.raises(pf.InvalidMetrics):
        pf.build_report("2026-10-09", pins=path)


def test_unknown_total_on_partial_board(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin(), pin("", "Otro", "456")])
    assert pf.build_report("2026-10-09", pins=path)["pinterest"]["totales"]["impresiones"] is None


def test_duplicate_pin_across_boards_fails(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin(), pin(board="Otro")])
    with pytest.raises(pf.InvalidMetrics, match="duplicado"):
        pf.build_report("2026-10-09", pins=path)


def test_wrong_source_fails(tmp_path):
    row = ga4()
    row[2] = "facebook"
    path = fixture(tmp_path, pf.WEB_FIELDS, [row])
    with pytest.raises(pf.InvalidMetrics):
        pf.build_report("2026-10-09", web=path)


def test_no_mutation_and_missing_day(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin()])
    prior = path.read_bytes()
    report = pf.build_report("2026-10-08", pins=path)
    assert report["pinterest"]["estado"] == "sin_filas_fecha"
    assert path.read_bytes() == prior


def test_two_distinct_pin_ids_are_not_safe_to_add(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin(), pin("300", "Libros", "456")])
    result = pf.build_report("2026-10-09", pins=path)["pinterest"]
    assert result["tableros"]["Libros"]["impresiones"] is None
    assert result["totales"]["impresiones"] is None
    assert result["motivo_totales"] == "solapamiento_no_descartado"
    assert result["tableros"]["Libros"]["detalle"]["123"]["impresiones"] == 100


def test_distinct_board_aggregates_are_not_safe_as_account_total(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin(board="Libros", pin_id="-", level="tablero"),
                                             pin(board="Escritura", pin_id="-", level="tablero")])
    result = pf.build_report("2026-10-09", pins=path)["pinterest"]
    assert result["tableros"]["Libros"]["impresiones"] == 100
    assert result["tableros"]["Escritura"]["impresiones"] == 100
    assert result["totales"]["impresiones"] is None


@pytest.mark.parametrize("field", ["acumulado", "ultimos_30_dias", ""])
def test_lifetime_or_multi_day_periods_rejected(tmp_path, field):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin(period=field)])
    with pytest.raises(pf.InvalidMetrics, match="día"):
        pf.build_report("2026-10-09", pins=path)


def test_mixed_pin_and_board_scope_rejected(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin(), pin(board="Otro", pin_id="-", level="tablero")])
    with pytest.raises(pf.InvalidMetrics, match="mezclar"):
        pf.build_report("2026-10-09", pins=path)


def test_wrong_board_level_id_rejected(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin(level="tablero")])
    with pytest.raises(pf.InvalidMetrics):
        pf.build_report("2026-10-09", pins=path)


def test_web_aggregate_event_name_must_be_ga4_event_id(tmp_path):
    row = ga4("evento", "1")
    row[6] = "All events"
    path = fixture(tmp_path, pf.WEB_FIELDS, [row])
    with pytest.raises(pf.InvalidMetrics, match="evento GA4"):
        pf.build_report("2026-10-09", web=path)


def test_web_campaign_cannot_blend_paid_and_organic(tmp_path):
    event = ga4("evento", "1")
    event[3] = "cpc"
    path = fixture(tmp_path, pf.WEB_FIELDS, [ga4(), event])
    with pytest.raises(pf.InvalidMetrics, match="fuentes/medios"):
        pf.build_report("2026-10-09", web=path)


def test_model_switch_within_campaign_rejected(tmp_path):
    event1 = ga4("evento", "1")
    event2 = ga4("evento", "1")
    event2[6], event2[5] = "purchase", "ultimo_clic"
    path = fixture(tmp_path, pf.WEB_FIELDS, [event1, event2])
    with pytest.raises(pf.InvalidMetrics, match="modelos"):
        pf.build_report("2026-10-09", web=path)


def test_oversized_input_closed(tmp_path, monkeypatch):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin()])
    monkeypatch.setattr(pf, "MAX_FILE_BYTES", 10)
    with pytest.raises(pf.InvalidMetrics, match="grande"):
        pf.build_report("2026-10-09", pins=path)


def test_invalid_date_fails_closed(tmp_path):
    row = pin()
    row[0] = "2026-02-30"
    path = fixture(tmp_path, pf.PIN_FIELDS, [row])
    with pytest.raises(pf.InvalidMetrics, match="fecha"):
        pf.build_report("2026-10-09", pins=path)


def test_explicit_zero_is_observed_and_not_unknown(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin(impressions="0")])
    result = pf.build_report("2026-10-09", pins=path)["pinterest"]
    assert result["estado"] == "observado"
    assert result["totales"]["impresiones"] == 0


def test_multiline_or_control_character_label_rejected(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin(board="Mal\x00tablero")])
    with pytest.raises(pf.InvalidMetrics):
        pf.build_report("2026-10-09", pins=path)


def test_pin_id_must_be_canonical_and_numeric(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin(pin_id="https://pinterest.com/pin/123")])
    with pytest.raises(pf.InvalidMetrics, match="numérico"):
        pf.build_report("2026-10-09", pins=path)


def test_truncated_csv_rejected(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin()[:-1]])
    with pytest.raises(pf.InvalidMetrics, match="truncada"):
        pf.build_report("2026-10-09", pins=path)


def test_utf8_bom_supported(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS, [pin()])
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert pf.build_report("2026-10-09", pins=path)["pinterest"]["totales"]["impresiones"] == 100


def test_incorrect_or_legacy_header_rejected(tmp_path):
    path = fixture(tmp_path, pf.PIN_FIELDS[:-1], [])
    with pytest.raises(pf.InvalidMetrics, match="cabecera"):
        pf.build_report("2026-10-09", pins=path)


def test_rows_without_any_metric_not_reported_as_observed(tmp_path):
    row = pin(impressions="")
    row[-3:] = ["", "", ""]
    path = fixture(tmp_path, pf.PIN_FIELDS, [row])
    assert pf.build_report("2026-10-09", pins=path)["pinterest"]["estado"] == "sin_metricas_fecha"


def test_ga4_rows_without_any_metric_not_reported_as_observed(tmp_path):
    row = ga4()
    row[7] = ""
    path = fixture(tmp_path, pf.WEB_FIELDS, [row])
    assert pf.build_report("2026-10-09", web=path)["web_ga4"]["estado"] == "sin_metricas_fecha"

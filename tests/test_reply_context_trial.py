"""PR #74: pruebas exclusivamente offline para contexto e hipótesis H1.

No se abre Edge, no se ejecuta la cola y no se escribe en datos operativos.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import reply_context_trial as trial
import reply_writer as rw

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "reply_74_context_synthetic.json"


@pytest.fixture(autouse=True)
def no_operational_style_files(monkeypatch):
    monkeypatch.setattr(rw, "estilo_red_texto", lambda networks, path=None: "")


def sample(**extra):
    return {
        "id": "p1", "network": "reddit", "author": "lectora",
        "text": "¿Qué novela corta me sugerís para volver a leer?",
        "context_status": "complete", **extra,
    }


def test_16_synthetic_cases_cover_eight_networks_and_varied_interactions():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    assert len(cases) == 16
    assert {row["network"] for row in cases} == trial.NETWORKS - {"reddit_micro"}
    assert all(row["source_permission"] == "synthetic" for row in cases)
    assert all(row["case_id"] and row["interaction_type"] for row in cases)
    assert len({row["case_id"] for row in cases}) == len(cases)
    assert {n: sum(row["network"] == n for row in cases)
            for n in trial.NETWORKS - {"reddit_micro"}} == {
                n: 2 for n in trial.NETWORKS - {"reddit_micro"}
            }
    for row in cases:
        assert trial.prepare_items([{"id": row["case_id"], **row}])[0]["network"] == row["network"]


def test_baseline_and_h1_have_exactly_identical_serialized_posts_and_context():
    item = sample(
        conversation_context=["David: ¿Cómo llevas el borrador?",
                              "Lectora: He terminado el segundo capítulo."],
        reply_to_us=True,
    )
    pair = trial.build_pair([item], memoria="")
    assert pair.keys() == {"baseline", "H1"}
    assert pair["baseline"].split("Publicaciones:\n", 1)[1] == pair["H1"].split("Publicaciones:\n", 1)[1]
    assert "He terminado el segundo capítulo" in pair["baseline"]
    assert "He terminado el segundo capítulo" in pair["H1"]
    assert "comentario que esta persona nos ha hecho" in pair["H1"]


def test_both_arms_are_given_same_concrete_question():
    pair = trial.build_pair([sample(text="¿Tapa dura o edición de bolsillo para viajar?")])
    assert "edición de bolsillo" in pair["baseline"]
    assert "edición de bolsillo" in pair["H1"]


def test_h1_removes_batch_quota_but_keeps_safety_and_json_contract():
    pair = trial.build_pair([sample()])
    assert "NINGUNO pase del 40 %" in pair["baseline"]
    assert "NINGUNO pase del 40 %" not in pair["H1"]
    assert "1 de cada 4" not in pair["H1"]
    assert "Siempre motivadora" not in pair["H1"]
    assert "Escribe UNA respuesta" in pair["H1"]
    assert '"reply": null' in pair["H1"]
    assert "NO confiable" in pair["H1"]
    assert "DECISIÓN CONVERSACIONAL" in pair["H1"]


def test_reddit_body_changes_interpretation_of_generic_title_without_invention():
    result = trial.prepare_items([sample(
        text="Audiolibros",
        post_body="Busco narradores en español que no hagan voces infantiles.",
    )])[0]
    assert result["text"].startswith("Audiolibros.")
    assert "no hagan voces infantiles" in result["text"]


def test_non_textual_reddit_post_does_not_gain_imaginary_description():
    result = trial.prepare_items([sample(
        text="Una portada", context_status="visual_unverified",
        media_context="Un dragón rojo delante de un castillo",
        visual_verified=False, has_media=True,
    )])[0]
    assert "NO interpretado" in result["context"]
    assert "dragón rojo" not in result["context"]


def test_visual_verified_requires_explicit_provenance_true():
    valid = trial.prepare_items([sample(
        visual_verified=True, media_context="En la imagen aparece una dedicatoria manuscrita",
    )])[0]
    invalid = trial.prepare_items([sample(
        visual_verified="true", media_context="En la imagen aparece una dedicatoria manuscrita",
        has_media=True,
    )])[0]
    assert "dedicatoria manuscrita" in valid["context"]
    assert "dedicatoria manuscrita" not in invalid["context"]


def test_partial_thread_is_not_reported_as_complete():
    result = trial.prepare_items([sample(
        context_status="partial", conversation_context=["Solo veo la última réplica"],
    )])[0]
    assert "Contexto parcial" in result["context"]
    assert "Solo veo la última réplica" in result["context"]


def test_thread_list_keeps_chronological_order_and_ignores_invalid_elements():
    result = trial.prepare_items([sample(
        conversation_context=[
            {"role": "David", "text": "¿Terminaste la saga?"},
            5, None,
            {"role": "Otra persona", "text": "Solo el primer libro."},
        ],
    )])[0]["context"]
    assert result.index("¿Terminaste") < result.index("primer libro")
    assert "None" not in result


def test_unicode_accents_and_enye_survive():
    result = trial.prepare_items([sample(
        text="Óscar, ¿qué título añadirías al año de la montaña?",
        conversation_context="Niñas leyendo ciencia ficción",
    )])[0]
    assert "Óscar" in result["text"] and "añadirías" in result["text"]
    assert "Niñas" in result["context"]
    assert "Óscar" in trial.build_pair([sample(text=result["text"])])["H1"]


@pytest.mark.parametrize("network", sorted(trial.NETWORKS))
def test_all_eight_networks_and_reddit_micro_mode_render(network):
    pair = trial.build_pair([sample(network=network)])
    assert f"[red: {network}]" in pair["baseline"]
    assert f"[red: {network}]" in pair["H1"]


@pytest.mark.parametrize("bad", [None, {}, "hello", 2, [None], [1]])
def test_invalid_input_rejected_without_side_effects(bad):
    with pytest.raises(ValueError):
        trial.prepare_items(bad)


@pytest.mark.parametrize("state", [None, [], {}, "unverified", True])
def test_unknown_state_rejected(state):
    with pytest.raises(ValueError):
        trial.prepare_items([sample(context_status=state)])


def test_duplicate_ids_rejected_even_when_network_differs():
    with pytest.raises(ValueError):
        trial.prepare_items([sample(), sample(network="tiktok")])


def test_empty_text_causes_explicit_abstention_instruction():
    row = trial.prepare_items([sample(text=None)])[0]
    assert row["text"] == ""
    assert "responder null" in row["context"]


def test_input_is_not_mutated():
    original = sample(conversation_context=["Primera respuesta"])
    before = json.dumps(original, ensure_ascii=False, sort_keys=True)
    trial.build_pair([original])
    assert json.dumps(original, ensure_ascii=False, sort_keys=True) == before


def test_long_body_and_long_thread_are_bounded():
    row = trial.prepare_items([sample(
        text="t" * 10000, post_body="b" * 10000,
        conversation_context=["h" * 1000] * 100,
    )])[0]
    assert len(row["text"]) <= 600
    assert len(row["context"]) <= 1700


def test_template_drift_fails_closed(monkeypatch):
    monkeypatch.setattr(rw, "build_prompt", lambda *args, **kwargs: "Nueva plantilla")
    with pytest.raises(RuntimeError, match="plantilla"):
        trial.build_pair([sample()])


def test_legacy_null_json_is_still_parsed_by_original_writer():
    parsed = rw.parse_answer('[{"id":"p1","reply":null},{"id":"p2","reply":"Buen apunte"}]')
    assert parsed == [{"id": "p1", "reply": None},
                      {"id": "p2", "reply": "Buen apunte"}]


def test_h1_never_runs_model_and_has_no_production_entrypoint():
    assert callable(trial.build_pair)
    assert not hasattr(trial, "consult")
    assert not hasattr(trial, "publish")

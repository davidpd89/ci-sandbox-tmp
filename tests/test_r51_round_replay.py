"""R51: replay offline real de selector, builder, preflight, executor y ledger.

Los snapshots son sintéticos, basados en las claves de _build_output de cada scan.
Ningún test utiliza perfiles, credenciales, red ni archivos de operación.
"""
from contextlib import ExitStack
import datetime as dt


def fresh_post_date():
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat()

from pathlib import Path
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pytest
import action_ledger
import api_comment_writer as writer
import bluesky_build_plan as blue_build
import bluesky_execute as blue_exec
import mastodon_build_plan as mast_build
import mastodon_execute as mast_exec
import conversation_turn_policy as turns
import like_context_policy as likes
import exec_common as ec


POST_TEXT = "Estoy leyendo una novela de fantasía juvenil cuyo segundo capítulo cambia la historia por completo."
ANSWER = "Ese giro del segundo capítulo me ha despertado curiosidad por la novela."
DID = "did:plc:abcdefghijklmnopqrstuvwx"
URI = f"at://{DID}/app.bsky.feed.post/3kabcde12345"
BLUE_URL = "https://bsky.app/profile/lectora.bsky.social/post/3kabcde12345"


def snapshot(network, *, author=True, different=False):
    mast = network == "mastodon"
    post_id = "M001-P1" if mast else "G001-P1"
    post = {"id": post_id, "text": POST_TEXT, "actions": ["reply"],
            "sources": ["post_search"], "es": True,
            "created_at": fresh_post_date()}
    if mast:
        post.update(status_id="654321" if different else "123456",
                    url="https://ejemplo.social/@lectora/123456")
        profile = {"id": "M001", "score": 8, "account_id": "987",
                   "actions": ["follow"], "posts": [post], "sources": []}
        if author:
            profile["acct"] = "lectora@ejemplo.social"
    else:
        post.update(uri=(f"at://{DID}/app.bsky.feed.post/3knewrecord" if different else URI),
                    url=BLUE_URL)
        profile = {"id": "G001", "did": DID, "score": 8,
                   "actions": ["follow"], "posts": [post], "sources": []}
        if author:
            profile["handle"] = "lectora.bsky.social"
    return {"shortlist": [profile], "auto_plan": []}


def modules(network):
    return (mast_build, mast_exec) if network == "mastodon" else (blue_build, blue_exec)


def decision(network, state):
    selected = writer.pick_posts(state, 1, network=network, log=lambda _: None)
    reply = [{"kind": "reply", "post": p["id"], "post_uri": p["post_uri"],
              "text": ANSWER} for p in selected]  # escritor GPT falso
    return writer.merge({"actions": []}, reply), selected


def patch_api(stack, network, calls, *, failure=None):
    _, exe = modules(network)
    stack.enter_context(mock.patch("reply_writer.require_gpt", side_effect=lambda p, *a: p))
    stack.enter_context(mock.patch("repost_policy.guard", side_effect=lambda p, *a: p))
    for module, name in [(exe, "_prefetch_window"), (exe, "_pause"),
                         (exe.sc, "report_plan_style"),
                         (exe.dup, "check")]:
        stack.enter_context(mock.patch.object(module, name, return_value=[] if name == "check" else None))
    def fake_reply(target, text):
        calls.append((target, text))
        if failure:
            raise failure
        return {"id": "sent-1", "url": "https://ejemplo.social/post/1"} if network == "mastodon" else None
    if network == "mastodon":
        stack.enter_context(mock.patch.object(exe, "_pace_for_rate_limit", return_value=None))
        stack.enter_context(mock.patch.object(exe.m, "patient", side_effect=lambda f, **kw: f()))
        for name in ("_check_length", "_check_spanish_orthography"):
            stack.enter_context(mock.patch.object(exe.m, name, return_value=None))
        stack.enter_context(mock.patch.object(exe.m, "reply_to", side_effect=fake_reply))
    else:
        stack.enter_context(mock.patch.object(exe, "_hourly_guard", return_value=None))
        stack.enter_context(mock.patch.object(exe.b, "warm_dids", return_value=None))
        stack.enter_context(mock.patch.object(exe.b, "_url_to_uri", return_value=URI))
        for name in ("_check_length", "_check_spanish_orthography"):
            stack.enter_context(mock.patch.object(exe.b, name, return_value=None))
        stack.enter_context(mock.patch.object(exe.b, "reply_to", side_effect=fake_reply))
    return exe


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_replay_sintetico_hasta_ledger_y_segundo_intento(network, tmp_path):
    state = snapshot(network)
    choices, selected = decision(network, state)
    assert len(selected) == 1
    assert selected[0]["author"] == ("lectora@ejemplo.social" if network == "mastodon" else "lectora.bsky.social")
    builder, _ = modules(network)
    plan = builder.build(state, choices)
    assert len(plan) == 1
    calls, callbacks = [], []
    ledger = action_ledger.ActionLedger(str(tmp_path / "ledger.sqlite3"), clock=lambda: 1000)
    with ExitStack() as stack:
        exe = patch_api(stack, network, calls)
        first = exe.run_plan(plan, ledger=ledger, on_result=callbacks.append)
        second = exe.run_plan(plan, ledger=ledger, on_result=callbacks.append)
    assert [r["resultado"] for r in first] == ["confirmado"]
    assert second[0]["resultado"].startswith("saltado_en_ledger:")
    assert calls == [(("123456" if network == "mastodon" else URI), ANSWER)]
    assert len(callbacks) == 2
    target = ledger.target_for("reply", plan[0])
    assert ledger.reserve("reply", target) == action_ledger.CONFIRMED


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_autor_ausente_no_sale_del_builder(network):
    state = snapshot(network, author=False)
    assert decision(network, state) == ({"actions": []}, [])
    builder, _ = modules(network)
    post_id = state["shortlist"][0]["posts"][0]["id"]
    with pytest.raises(ValueError, match="falta_(acct|handle)"):
        builder.build(state, {"actions": [{"post": post_id, "kind": "reply", "text": ANSWER}]})


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_reescaneo_con_ordinal_igual_pero_destino_nuevo(network):
    original = snapshot(network)
    choices, _ = decision(network, original)
    builder, _ = modules(network)
    with pytest.raises(ValueError, match="referencia remota distinta"):
        builder.build(snapshot(network, different=True), choices)


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_ordinal_duplicado_en_scan_se_rechaza(network):
    scan = snapshot(network)
    scan["shortlist"].append(dict(scan["shortlist"][0]))
    builder, _ = modules(network)
    with pytest.raises(ValueError, match="duplicado"):
        builder.build(scan, {"actions": []})


def test_429_bluesky_para_sin_confirmar_en_ledger(tmp_path):
    state = snapshot("bluesky")
    choices, _ = decision("bluesky", state)
    plan = blue_build.build(state, choices)
    ledger = action_ledger.ActionLedger(str(tmp_path / "ledger.sqlite3"))
    class RateLimit(Exception):
        pass
    calls = []
    with ExitStack() as stack:
        exe = patch_api(stack, "bluesky", calls, failure=RateLimit("429"))
        stack.enter_context(mock.patch.object(exe, "RateLimitExceeded", RateLimit))
        results = exe.run_plan(plan, ledger=ledger)
    assert len(calls) == 1
    assert results[0]["resultado"].startswith("parada_rate_limit:")
    assert ledger.reserve("reply", ledger.target_for("reply", plan[0])) != action_ledger.CONFIRMED


def test_cierre_social_y_like_con_imagen_desconocida():
    allowed, reason = turns.check_execution(
        "bluesky", {"kind": "reply", "reply_to_us": True, "post_text": "Gracias, compañero.",
                      "post_created_at": fresh_post_date()}
    )
    assert (allowed, reason) == (False, "cierre_social")
    allowed, why = likes.can_like("", media_present=True)
    assert not allowed and why == "sin_texto_interpretable"


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
@pytest.mark.parametrize("exception", [TimeoutError, ConnectionError])
def test_fallo_previo_a_post_no_se_confunde_con_ack_perdido(network, exception, tmp_path):
    state = snapshot(network)
    choices, _ = decision(network, state)
    builder, _ = modules(network)
    plan = builder.build(state, choices)
    ledger = action_ledger.ActionLedger(str(tmp_path / "ledger.sqlite3"), clock=lambda: 1000)
    calls = []
    # El doble levanta la excepción directamente *antes* del POST.
    # No puede demostrar que hubiese escritura remota.
    with ExitStack() as stack:
        exe = patch_api(stack, network, calls, failure=exception("fallo previo"))
        first = exe.run_plan(plan, ledger=ledger)
        second = exe.run_plan(plan, ledger=ledger)
    assert first[0]["resultado"].startswith("fallo:")
    assert second[0]["resultado"].startswith("fallo:")
    assert len(calls) == 2
    assert ledger.reserve("reply", ledger.target_for("reply", plan[0])) == "ok"



@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_follow_compacto_usa_el_autor_remoto_correcto(network):
    state = snapshot(network)
    builder, _ = modules(network)
    row = builder.build(state, {"actions": [{
        "candidate": state["shortlist"][0]["id"], "kind": "follow",
    }]})[0]
    assert row["kind"] == "follow"
    assert row["handle"] == ("lectora@ejemplo.social" if network == "mastodon"
                              else "lectora.bsky.social")


def test_auto_plan_bluesky_no_pasa_con_handle_vacio_o_de_otra_red():
    state = snapshot("bluesky")
    for wrong in ("", "cuenta_ajena@mastodon.social", None):
        state["auto_plan"] = [{"kind": "follow", "handle": wrong}]
        with pytest.raises(ValueError, match="handle"):
            blue_build.build(state, {"actions": []})


def _bluesky_reply_with_post_stub(stack, post_stub=None):
    b = blue_exec.b
    for name, result in [
        ("_require_credentials", None), ("_check_length", None),
        ("_check_spanish_orthography", None),
        ("_url_to_uri", URI), ("_already_commented", False),
        ("_get_post_record", {"root": None, "uri": URI, "cid": "cid-1"}),
        ("_session", {"did": DID}), ("_now", "2026-10-09T08:00:00Z"),
    ]:
        stack.enter_context(mock.patch.object(b, name, return_value=result))
    stack.enter_context(mock.patch.object(b, "_add_richtext", side_effect=lambda record: record))
    if post_stub is not None:
        stack.enter_context(mock.patch.object(b, "_post_xrpc", **post_stub))
    return b


class FakeHttpResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self.text = "respuesta ficticia"
        self.headers = {}
        self.body = {} if body is None else body

    def json(self):
        return self.body


def _stub_remote_status_post(stack, failure):
    import requests

    problem = {
        "timeout": requests.exceptions.ReadTimeout("POST sin respuesta"),
        "connection": requests.exceptions.ConnectionError("POST interrumpido"),
    }.get(failure)
    response = FakeHttpResponse(status=503 if failure == "server_error" else 200)
    return {"side_effect": problem} if problem else {"return_value": response}


def _mastodon_status_without_real_network(stack, stub):
    m = mast_exec.m
    for name, value in [("_assert_expected_account", None),
                        ("_headers", {}), ("_wait_for_budget", None),
                        ("_record_rate_limit", None)]:
        stack.enter_context(mock.patch.object(m, name, return_value=value))
    stack.enter_context(mock.patch.object(m.requests, "post", **stub))
    return m


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
@pytest.mark.parametrize("failure", ["timeout", "connection", "server_error", "invalid_ack"])
def test_cliente_distingue_frontera_de_post_y_ack_incierto(network, failure):
    stub = _stub_remote_status_post(None, failure)
    with ExitStack() as stack:
        if network == "mastodon":
            m = _mastodon_status_without_real_network(stack, stub)
            action = lambda: m._create_status(
                {"status": ANSWER, "in_reply_to_id": "123456"},
                {"status": ANSWER, "reply_to": "123456"},
            )
        else:
            b = _bluesky_reply_with_post_stub(stack)
            stack.enter_context(mock.patch.object(b, "_headers", return_value={}))
            stack.enter_context(mock.patch.object(b.requests, "post", **stub))
            action = lambda: b.reply_to(BLUE_URL, ANSWER)
        with pytest.raises(ec.WriteOutcomeUnknown):
            action()


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_4xx_explicitamente_rechazado_no_se_transforma_en_incierto(network):
    with ExitStack() as stack:
        if network == "mastodon":
            m = _mastodon_status_without_real_network(
                stack, {"return_value": FakeHttpResponse(status=403)})
            action = lambda: m._create_status({"status": ANSWER}, {"status": ANSWER})
            expected = m.MastodonAPIError
        else:
            b = _bluesky_reply_with_post_stub(stack)
            stack.enter_context(mock.patch.object(b, "_headers", return_value={}))
            stack.enter_context(mock.patch.object(
                b.requests, "post", return_value=FakeHttpResponse(status=403)))
            action = lambda: b.reply_to(BLUE_URL, ANSWER)
            expected = RuntimeError
        with pytest.raises(expected) as raised:
            action()
        assert not isinstance(raised.value, ec.WriteOutcomeUnknown)


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_error_de_consulta_previa_nunca_es_ack_incierto(network):
    import requests
    with ExitStack() as stack:
        err = requests.exceptions.ConnectionError("GET previo no disponible")
        if network == "mastodon":
            stack.enter_context(mock.patch.object(mast_exec.m, "_check_spanish_orthography"))
            stack.enter_context(mock.patch.object(mast_exec.m, "_status_id", return_value="123456"))
            stack.enter_context(mock.patch.object(mast_exec.m, "_already_commented", side_effect=err))
            action = lambda: mast_exec.m.reply_to("123456", ANSWER)
        else:
            b = _bluesky_reply_with_post_stub(stack, {"return_value": {"uri": URI, "cid": "cid"}})
            stack.enter_context(mock.patch.object(b, "_already_commented", side_effect=err))
            action = lambda: b.reply_to(BLUE_URL, ANSWER)
        with pytest.raises(requests.exceptions.ConnectionError):
            action()


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_excepcion_tipificada_de_post_bloquea_segundo_intento(network, tmp_path):
    state = snapshot(network)
    choices, _ = decision(network, state)
    plan = modules(network)[0].build(state, choices)
    ledger = action_ledger.ActionLedger(str(tmp_path / "ledger.sqlite3"), clock=lambda: 1000)
    calls = []
    with ExitStack() as stack:
        exe = patch_api(stack, network, calls,
                        failure=ec.WriteOutcomeUnknown("POST sin confirmación"))
        first = exe.run_plan(plan, ledger=ledger)
        second = exe.run_plan(plan, ledger=ledger)
    assert first[0]["resultado"] == "incierto:transporte_sin_ack"
    assert second[0]["resultado"].startswith("saltado_en_ledger:")
    assert ledger.reserve("reply", ledger.target_for("reply", plan[0])) == action_ledger.UNCERTAIN
    assert len(calls) == 1


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_guardia_gpt_real_bloquea_texto_desconocido_y_permite_marcado(network, tmp_path, monkeypatch):
    import reply_writer as rw

    # Test real del punto de entrada del ejecutor, sin bypass global del
    # origen GPT; el registro usa únicamente un fichero dentro de tmp_path.
    original_guard = rw.require_gpt
    monkeypatch.delenv("RRSS_ALLOW_UNMARKED_TEXT", raising=False)
    monkeypatch.setattr(rw, "GPT_TEXTS", str(tmp_path / "gpt_texts.json"))
    state = snapshot(network)
    decisions, _ = decision(network, state)
    plan = modules(network)[0].build(state, decisions)
    ledger = action_ledger.ActionLedger(str(tmp_path / "ledger.sqlite3"))
    calls = []
    with ExitStack() as stack:
        exe = patch_api(stack, network, calls)
        stack.enter_context(mock.patch.object(rw, "require_gpt", side_effect=original_guard))
        assert exe.run_plan(plan, ledger=ledger) == []
        assert calls == []
        # Compatible con la guardia histórica y con #79. Al integrar #79,
        # el texto debe tener una prueba del objetivo/contexto, no solo
        # un hash global reutilizable.
        import inspect
        if "network" in inspect.signature(rw.mark_gpt).parameters:
            import reply_provenance as provenance
            proof_path = str(tmp_path / "proof.json")
            monkeypatch.setenv("RRSS_GPT_PROVENANCE_PATH", proof_path)
            post = state["shortlist"][0]["posts"][0]
            source = {"text": post["text"]}
            if network == "bluesky":
                source["post_uri"] = URI
                plan[0]["post_uri"] = URI
            else:
                source["status_id"] = post["status_id"]
            assert rw.mark_gpt(ANSWER, network=network, source=source)
            plan[0] = provenance.attach(plan[0], source, network)
            assert plan[0] is not None
        else:
            rw.mark_gpt(ANSWER)
        results = exe.run_plan(plan, ledger=ledger)
    assert results[0]["resultado"] == "confirmado"
    assert len(calls) == 1


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_preflight_opinion_real_rechaza_respuesta_critica(network):
    state = snapshot(network)
    post = state["shortlist"][0]["posts"][0]
    post["text"] = "Lee mi relato y dime qué te parece; busco lectores beta."
    answer = "El principio no funciona y necesita bastantes correcciones."
    builder, _ = modules(network)
    with pytest.raises(ValueError):
        builder.build(state, {"actions": [{"kind": "reply", "post": post["id"],
                                            "text": answer}]})


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_fallo_credenciales_o_cupo_anterior_a_POST_no_es_incierto(network):
    import requests

    err = requests.exceptions.ConnectionError("sin sesión o presupuesto antes de POST")
    with ExitStack() as stack:
        if network == "mastodon":
            m = mast_exec.m
            stack.enter_context(mock.patch.object(m, "_assert_expected_account", side_effect=err))
            write = stack.enter_context(mock.patch.object(m.requests, "post"))
            action = lambda: m._create_status({"status": ANSWER}, {"status": ANSWER})
        else:
            b = _bluesky_reply_with_post_stub(stack)
            stack.enter_context(mock.patch.object(b, "_headers", side_effect=err))
            write = stack.enter_context(mock.patch.object(b.requests, "post"))
            action = lambda: b.reply_to(BLUE_URL, ANSWER)
        with pytest.raises(requests.exceptions.ConnectionError):
            action()
        write.assert_not_called()


class FakeInvalidJsonResponse(FakeHttpResponse):
    def json(self):
        raise ValueError("respuesta 200 no contiene JSON válido")


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_post_200_con_json_invalido_queda_incierto(network):
    response = FakeInvalidJsonResponse()
    with ExitStack() as stack:
        if network == "mastodon":
            m = _mastodon_status_without_real_network(stack, {"return_value": response})
            action = lambda: m._create_status({"status": ANSWER}, {"status": ANSWER})
        else:
            b = _bluesky_reply_with_post_stub(stack)
            stack.enter_context(mock.patch.object(b, "_headers", return_value={}))
            stack.enter_context(mock.patch.object(b.requests, "post", return_value=response))
            action = lambda: b.reply_to(BLUE_URL, ANSWER)
        with pytest.raises(ec.WriteOutcomeUnknown):
            action()


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_post_429_explicito_no_se_asienta_como_incierto(network):
    response = FakeHttpResponse(status=429)
    with ExitStack() as stack:
        if network == "mastodon":
            m = _mastodon_status_without_real_network(stack, {"return_value": response})
            action = lambda: m._create_status({"status": ANSWER}, {"status": ANSWER})
            expected = m.MastodonRateLimitExceeded
        else:
            b = _bluesky_reply_with_post_stub(stack)
            stack.enter_context(mock.patch.object(b, "_headers", return_value={}))
            stack.enter_context(mock.patch.object(b.requests, "post", return_value=response))
            action = lambda: b.reply_to(BLUE_URL, ANSWER)
            expected = b.RateLimitExceeded
        with pytest.raises(expected) as caught:
            action()
        assert not isinstance(caught.value, ec.WriteOutcomeUnknown)


@pytest.mark.parametrize("network", ["mastodon", "bluesky"])
def test_connect_timeout_de_requests_es_reintentable_y_no_incierto(network):
    import requests

    exc = requests.exceptions.ConnectTimeout("no se llegó a conectar")
    with ExitStack() as stack:
        stub = {"side_effect": exc}
        if network == "mastodon":
            m = _mastodon_status_without_real_network(stack, stub)
            action = lambda: m._create_status({"status": ANSWER}, {"status": ANSWER})
        else:
            b = _bluesky_reply_with_post_stub(stack)
            stack.enter_context(mock.patch.object(b, "_headers", return_value={}))
            stack.enter_context(mock.patch.object(b.requests, "post", **stub))
            action = lambda: b.reply_to(BLUE_URL, ANSWER)
        with pytest.raises(requests.exceptions.ConnectTimeout) as raised:
            action()
        assert not isinstance(raised.value, ec.WriteOutcomeUnknown)


def test_mastodon_tres_5xx_de_reply_incierta_abren_parada_sin_reintentar(tmp_path):
    error = ec.WriteOutcomeUnknown("POST status sin confirmación")
    error.__cause__ = mast_exec.m.MastodonAPIError("POST statuses", 503, "respuesta incierta")
    plan = [{
        "kind": "reply", "handle": "lectora@ejemplo.social",
        "status_id": str(123456 + n), "url": f"https://ejemplo.social/@lectora/{123456 + n}",
        "post_text": POST_TEXT, "text": ANSWER + f" ({n})",
        "post_created_at": fresh_post_date(),
    } for n in range(4)]
    ledger = action_ledger.ActionLedger(str(tmp_path / "ledger.sqlite3"))
    calls = []
    with ExitStack() as stack:
        exe = patch_api(stack, "mastodon", calls, failure=error)
        stack.enter_context(mock.patch.object(exe, "_retry_sleep", return_value=None))
        results = exe.run_plan(plan, ledger=ledger)
    assert len(calls) == 3
    assert [r["resultado"] for r in results[:2]] == ["incierto:transporte_sin_ack"] * 2
    assert results[2]["resultado"] == "parada:incierto_5xx_servidor"
    assert results[3]["resultado"] == "no_intentado"
    assert [ledger.status("reply", str(123456 + n)) for n in range(3)] == [action_ledger.UNCERTAIN] * 3
    assert ledger.status("reply", "123459") is None


def test_bluesky_reply_usa_at_uri_de_preflight_y_ledger_url_legacy(tmp_path):
    state = snapshot("bluesky")
    decisions, _ = decision("bluesky", state)
    plan = blue_build.build(state, decisions)
    ledger = action_ledger.ActionLedger(str(tmp_path / "ledger.sqlite3"), clock=lambda: 1000)
    calls = []
    with ExitStack() as stack:
        exe = patch_api(stack, "bluesky", calls)
        resolver = stack.enter_context(mock.patch.object(
            exe.b, "_url_to_uri", side_effect=[URI, RuntimeError("resolución posterior prohibida")]
        ))
        results = exe.run_plan(plan, ledger=ledger)
    assert results[0]["resultado"] == "confirmado"
    assert calls == [(URI, ANSWER)]  # no hay segunda resolución de handle/permalink
    resolver.assert_called_once_with(BLUE_URL)
    # No sustituir en caliente la clave usada por las reservas históricas:
    # cambiar URL -> AT-URI sin reconciliar la DB reabriría acciones antiguas.
    assert ledger.status("reply", BLUE_URL) == action_ledger.CONFIRMED
    assert ledger.status("reply", URI) is None


def test_bluesky_tres_5xx_de_reply_incierta_detienen_lote(tmp_path):
    error = ec.WriteOutcomeUnknown("createRecord POST 503 sin ACK", status_code=503)
    uris = [f"at://{DID}/app.bsky.feed.post/3kabcde1234{n}" for n in range(4)]
    plan = [{
        "kind": "reply", "handle": "lectora.bsky.social",
        "url": f"https://bsky.app/profile/lectora.bsky.social/post/3kabcde1234{n}",
        "post_text": POST_TEXT, "text": ANSWER + f" ({n})",
        "post_created_at": fresh_post_date(),
    } for n in range(4)]
    calls = []
    ledger = action_ledger.ActionLedger(str(tmp_path / "ledger.sqlite3"))
    with ExitStack() as stack:
        exe = patch_api(stack, "bluesky", calls, failure=error)
        stack.enter_context(mock.patch.object(exe.b, "_url_to_uri", side_effect=uris))
        results = exe.run_plan(plan, ledger=ledger)
    assert len(calls) == 3
    assert [r["resultado"] for r in results[:2]] == ["incierto:transporte_sin_ack"] * 2
    assert results[2]["resultado"] == "parada:incierto_5xx_servidor"
    assert results[3]["resultado"] == "no_intentado"
    assert [ledger.status("reply", plan[n]["url"]) for n in range(3)] == [action_ledger.UNCERTAIN] * 3
    assert ledger.status("reply", plan[3]["url"]) is None


def test_mastodon_error_local_presupuesto_tras_POST_es_incierto():
    response = FakeHttpResponse(status=200, body={"id": "publicado-en-remoto"})
    with ExitStack() as stack:
        m = _mastodon_status_without_real_network(stack, {"return_value": response})
        stack.enter_context(mock.patch.object(m, "_record_rate_limit",
                                             side_effect=OSError("no disponible el registro local de cuota")))
        with pytest.raises(ec.WriteOutcomeUnknown) as caught:
            m._create_status({"status": ANSWER}, {"status": ANSWER})
        assert caught.value.status_code == 200


def test_mastodon_registro_local_de_cuota_no_oculta_429():
    response = FakeHttpResponse(status=429, body={})
    with ExitStack() as stack:
        m = _mastodon_status_without_real_network(stack, {"return_value": response})
        stack.enter_context(mock.patch.object(m, "_record_rate_limit",
                                             side_effect=OSError("no disponible el registro local de cuota")))
        with pytest.raises(m.MastodonRateLimitExceeded):
            m._create_status({"status": ANSWER}, {"status": ANSWER})

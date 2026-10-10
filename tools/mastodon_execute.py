"""Ejecutor de INTERACCIONES Mastodon por API oficial.

Kinds operativos:
- reply
- follow
- favourite
- boost

Post propio, quote y poll se rechazan: desde 28/09/2026 David
publica/programa manualmente en la interfaz nativa de cada red.

Uso:
    python tools/mastodon_execute.py plan.json
"""
import csv
import datetime
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import mastodon_interact as m
import check_duplicate_phrase as dup
import scan_common as sc
import growth_policy as gp
import exec_common as ec

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_MASTODON")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
METRICAS_CSV = os.path.join(ROOT, "metricas.csv")
ESTADO_MD = os.path.join(ROOT, "ESTADO.md")
BOOST_TTL_CSV = os.path.join(ROOT, "boost_ttl.csv")
# Limpieza a los 5 dias (29/09, a peticion explicita de David: el auto-borrado
# de repost/cita debe ser una funcion comun a todas las redes, no solo
# Bluesky, "para tener nuestro feed limpio... no un vertedero de repost").
# Mismo valor que Bluesky porque un boost es funcionalmente el mismo gesto
# (senal de interaccion de corto plazo, no contenido propio autorado) - X
# mantiene su propia ventana de 21 dias ya establecida en REGLAS.md.
BOOST_TTL_DAYS = gp.SHARE_TTL_DAYS

ALLOWED_KINDS = {"reply", "follow", "favourite", "boost"}
OWN_PUBLICATION_KINDS = {"post", "quote", "poll"}
VALID_KINDS = ALLOWED_KINDS | OWN_PUBLICATION_KINDS


PREFETCH_WINDOW = 40


def _pause(a=1.5, b=5.0):
    # El limite real (300 llamadas/5 min) lo gobierna _pace_for_rate_limit(); aqui solo el ritmo humano variable entre acciones con el rango de la etapa de la rampa (logica comun: exec_common).
    ec.network_pause("mastodon", a, b, default=(1.5, 5.0))


def _prefetch_window(items):
    """Estado de las proximas acciones en lote (1 peticion por 20 estados / 40 cuentas): cada favorito/boost/follow queda en 1 sola peticion de escritura."""
    status_ids = [it.get("status_id") for it in items if it.get("kind") in ("favourite", "boost") and it.get("status_id")]
    account_ids = [it.get("account_id") for it in items if it.get("kind") == "follow" and it.get("account_id")]
    if not (status_ids or account_ids):
        return
    try:
        m.prefetch(status_ids=status_ids, account_ids=account_ids)
    except Exception as exc:     # incluido un 429: la propia accion lo vuelve a encontrar y lo gestiona con su parada
        print(f"(precarga omitida: {type(exc).__name__}: {str(exc)[:80]})")


def _pace_for_rate_limit(safety_margin=5, max_wait_seconds=310):
    """Mismo pacing real que el scan (mastodon_growth_scan.py, 29/09): si la
    cuota real que reporta mastodon.social esta a punto de agotarse, esperar
    hasta el reset en vez de seguir escribiendo hasta un 429 real a mitad de
    lote - "se pueden hacer aunque tarden no pasa nada al ser una api,
    configuras tiempos y listo" (David, 29/09)."""
    snapshot = m.rate_limit_snapshot()
    remaining = snapshot.get("remaining")
    reset = snapshot.get("reset")
    if remaining is None or reset is None or remaining > safety_margin:
        return
    wait_seconds = (reset - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    if wait_seconds <= 0:
        return
    wait_seconds = min(wait_seconds, max_wait_seconds) + 2
    print(f"[pacing] cuota real casi agotada ({remaining} restantes) - esperando {wait_seconds:.0f}s")
    time.sleep(wait_seconds)


<<<<<<< HEAD
def _preflight_plan(plan):
=======
def _preflight_plan(plan, *, skipped=None):
>>>>>>> origin/research/public-reuse-parent
    """Valida y resuelve el lote completo antes de cualquier escritura API.

    Acepta un `status_id` ya resuelto en el item (lo que entrega
    mastodon_build_plan.py) para no volver a llamar a `_status_id()` -
    para un status remoto/federado eso es una búsqueda real por API
    (`search(..., resolve=True)`), no una operación local gratis."""
    if not isinstance(plan, list):
        raise ValueError("plan.json debe contener una lista")

    validated = []
<<<<<<< HEAD
    status_targets = set()
=======
    omissions = ec.PreflightSkipBuffer("mastodon", skipped)
    status_targets = {}
>>>>>>> origin/research/public-reuse-parent
    follow_targets = set()
    comment_texts = set()
    for index, raw in enumerate(plan, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"elemento {index}: debe ser un objeto")
        item = dict(raw)
        kind = item.get("kind")
        if kind in OWN_PUBLICATION_KINDS:
            # No es una interacción API; el rechazo explícito por elemento
            # ya vive en run_plan(), no repetir el criterio aquí.
            validated.append(item)
            continue
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"elemento {index}: kind inválido {kind!r}")

        if kind == "follow":
            handle = item.get("handle")
            if not isinstance(handle, str) or not handle.strip().lstrip("@"):
                raise ValueError(f"elemento {index}: follow exige handle")
            handle = handle.strip().lstrip("@")
            if any(ch.isspace() for ch in handle):
                raise ValueError(f"elemento {index}: handle de Mastodon inválido")
            key = handle.casefold()
            if key in follow_targets:
<<<<<<< HEAD
                raise ValueError(f"elemento {index}: follow duplicado para @{handle}")
=======
                omissions.add(index, kind, "relacion_repetida_lote")
                continue
>>>>>>> origin/research/public-reuse-parent
            follow_targets.add(key)
            item["handle"] = handle
        else:
            status_id = item.get("status_id")
            if status_id is not None:
                if not str(status_id).isdigit():
                    raise ValueError(f"elemento {index}: status_id inválido")
                status_id = str(status_id)
            else:
                url = item.get("url")
                if not isinstance(url, str) or not url.strip():
                    raise ValueError(f"elemento {index}: {kind} exige url o ID de status")
                status_id = m._status_id(url)
<<<<<<< HEAD
            if status_id in status_targets:
                raise ValueError(f"elemento {index}: varias acciones para el mismo status")
            status_targets.add(status_id)
            item["status_id"] = status_id
=======
            item["status_id"] = status_id
            if ec.post_too_old(kind, status_id, item.get("post_created_at") or item.get("created_at")):
                omissions.add(index, kind, "post_antiguo")      # necroposting: nunca actuar sobre estados viejos
                continue
>>>>>>> origin/research/public-reuse-parent

            if kind == "reply":
                text = item.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError(f"elemento {index}: reply exige texto")
                text = text.strip()
                m._check_length(text)
                sc.guard_plan_item(item, index)
                m._check_spanish_orthography(text)
                if ec.omit_previously_published_reply(
<<<<<<< HEAD
                    text, dup.check, network="mastodon", index=index
                ):
                    # El status fue reservado para este item antes del chequeo.
                    # Liberarlo para que una accion distinta sobre ese status
                    # pueda seguir en el plan sin un conflicto falso.
                    status_targets.discard(status_id)
                    continue
                text_key = " ".join(text.split()).casefold()
                if text_key in comment_texts:
                    raise ValueError(f"elemento {index}: reply repetida en este plan")
                comment_texts.add(text_key)
                item["text"] = text

        validated.append(item)
=======
                    text, dup.check, network="mastodon", index=index,
                    log=lambda _: None
                ):
                    omissions.add(index, kind, "texto_publicado")
                    continue
                text_key = " ".join(text.split()).casefold()
                if text_key in comment_texts:
                    omissions.add(index, kind, "texto_repetido_lote")
                    continue
                item["text"] = text

            if status_id in status_targets:
                if status_targets[status_id] != kind:
                    raise ValueError(f"elemento {index}: varias acciones para el mismo status")
                omissions.add(index, kind, "objetivo_repetido_lote")
                continue
            status_targets[status_id] = kind
            if kind == "reply":
                comment_texts.add(text_key)

        validated.append(item)
    omissions.commit()
>>>>>>> origin/research/public-reuse-parent
    return validated


_Results = ec.ResultList      # logica comun a todas las redes (exec_common)


TRANSIENT_STATUS = ec.TRANSIENT_HTTP   # servidor caido un momento: reintento, no parada (06/10: un 503 puntual paro una ronda de 82 acciones tras 19)
SKIPPABLE_STATUS = {404, 410, 422}        # estado borrado, cuenta eliminada o accion imposible: se salta esa accion
MAX_CONSECUTIVE_5XX = 3
ATTEMPT_BACKOFF = (6, 20)


def _retry_sleep(seconds):
    time.sleep(seconds)


def _do(kind, item):
    created = outcome = None
    if kind == "reply":
        created = m.reply_to(item["status_id"], item["text"])
    elif kind == "follow":
        outcome = m.follow(item["handle"].lstrip("@"), item.get("account_id"))
    elif kind == "favourite":
        outcome = m.favourite(item["status_id"])
    elif kind == "boost":
        outcome = m.boost(item["status_id"])
    return created, outcome


def _attempt(kind, item):
    """Ejecuta una accion; ante 5xx reintenta con espera creciente (favourite/follow/boost comprueban el estado antes: repetir no duplica). Una respuesta (texto nuevo) no se reintenta."""
    # 06/10 (David: «con tal de que funcione da igual lo que tarde»): un 429 ya no para el lote; se espera a que se renueve la ventana y se reintenta la MISMA accion
    # (una peticion rechazada por 429 no se aplico, asi que repetirla no duplica); solo tras 4 esperas seguidas (~20 min) se para.
    if kind == "reply":
        return m.patient(lambda: _do(kind, item), waits=4, priority="normal")
    return m.patient(lambda: ec.with_retries(lambda: _do(kind, item), transient=TRANSIENT_STATUS, backoff=ATTEMPT_BACKOFF, sleep=lambda seconds: _retry_sleep(seconds)),
                     waits=4, priority="normal")


def run_plan(plan, *, prevalidated=False, ledger=None, on_result=None):
    import reply_writer as _rw
    plan = _rw.require_gpt(plan, "mastodon")      # 08/10: nunca se publica texto que no venga de ChatGPT
    import repost_policy
    plan = repost_policy.guard(plan, globals().get("REGISTRO_CSV", ""))      # 07/10: reposts solo curados y max 3/dia, en todos los caminos
<<<<<<< HEAD
    if not prevalidated:
        try:
            plan = _preflight_plan(plan)
=======
    skipped = []
    if not prevalidated:
        try:
            plan = _preflight_plan(plan, skipped=skipped)
>>>>>>> origin/research/public-reuse-parent
            sc.report_plan_style(plan)
        except Exception as exc:
            print(f"FALLO DE PREFLIGHT: {type(exc).__name__}: {exc}")
            return [{"kind": "plan", "handle": "", "resultado": f"fallo_plan:{exc}"}]

    reserved = set()
    persisted = set()  # una clave propia solo admite el PRIMER resultado del lote

    def _persist(result):
<<<<<<< HEAD
        if ledger is not None and result.get("kind") in ALLOWED_KINDS:
=======
        if (ledger is not None and result.get("kind") in ALLOWED_KINDS
                and not ec.is_safe_preflight_omit(result.get("resultado"))):
>>>>>>> origin/research/public-reuse-parent
            key = (result.get("kind"), ledger.target_for(result.get("kind"), result))
            if key in reserved and key not in persisted:
                import action_ledger as _al
                ledger.settle(key[0], key[1], _al.outcome_to_status(result.get("resultado")), result.get("resultado"))
                persisted.add(key)
        if on_result:
            on_result(result)

    results = _Results(_persist)
<<<<<<< HEAD
    consecutive_5xx = 0
    for i, item in enumerate(plan):
=======
    for omitted in skipped:
        results.append(omitted)
    consecutive_5xx = 0
    for i, item in enumerate(plan):
        # Una ronda puede durar horas: revalidar la cuarentena antes de CADA
        # acción, incluso si el lanzador aprobó el lote al comienzo.
        import circuit_breaker as _cb
        _write_ok, _hold_reason = _cb.write_preflight("mastodon")
        if not _write_ok:
            print(f"[mastodon] cortacircuitos ABIERTO: {_hold_reason}; detener el lote")
            break
>>>>>>> origin/research/public-reuse-parent
        if i % PREFETCH_WINDOW == 0:
            _prefetch_window(plan[i:i + PREFETCH_WINDOW])
        kind = item["kind"]
        # Reservar antes de abstenerse para que el descarte editorial tenga TTL.
        if ledger is not None and kind in ALLOWED_KINDS:
            target = ledger.target_for(kind, item)
            if (kind, target) in reserved:
                # No relanzar el mismo objetivo tras un fallo en este lote.
                results.append({**item, "resultado": "saltado_en_ledger:already_in_plan"})
                continue
            verdict = ledger.reserve(kind, target)
            if verdict != "ok":
                print(f"SALTADO: ledger bloquea este objetivo ({verdict})")
                results.append({**item, "resultado": f"saltado_en_ledger:{verdict}"})
                continue
            reserved.add((kind, target))
        import conversation_turn_policy as ctp
        permitted, reason = ctp.check_execution("mastodon", item)
        if not permitted:
            results.append({**item, "resultado": f"saltado_cierre_conversacion:{reason}"})
            continue
        if kind in ("like", "favourite"):
            import like_context_policy as lcp
            allowed, why = lcp.check_execution("mastodon", item, mastodon_client=m)
            if not allowed:
                results.append({**item, "resultado": f"saltado_like_contexto:{why}"})
                continue
        print(f"=== {i+1}/{len(plan)}: {kind} ===")
        _pace_for_rate_limit()

        if kind in OWN_PUBLICATION_KINDS:
            print(
                f"RECHAZADO: '{kind}' es publicación propia; "
                "desde 28/09 se publica manualmente en Mastodon."
            )
            results.append({
                **item,
                "resultado": f"rechazado_publicacion_manual:{kind}",
            })
            continue
        if kind not in ALLOWED_KINDS:
            print(f"RECHAZADO: kind '{kind}' desconocido.")
            results.append({
                **item,
                "resultado": f"rechazado_kind_desconocido:{kind}",
            })
            continue

        try:
            outcome = None
            created = None
            created, outcome = _attempt(kind, item)
            consecutive_5xx = 0
            if outcome == "already":
                results.append({**item, "resultado": f"saltado_ya_{kind}"})
                continue
            row = {**item, "resultado": "confirmado"}
            if isinstance(created, dict):
                row["created_id"] = created.get("id")
                row["created_url"] = created.get("url")
            results.append(row)
        except m.MastodonAPIError as e:
            code = e.status_code
            if isinstance(e, m.MastodonRateLimitExceeded):
                print(f"PARADA TOTAL: {e}")
                results.append({**item, "resultado": f"parada:{e}"})
                for pending in plan[i + 1:]:
                    results.append({**pending, "resultado": "no_intentado"})
                break
            if code in SKIPPABLE_STATUS:
                print(f"SALTADO: {e}")
                results.append({**item, "resultado": f"saltado_api_{code}"})
            elif code in TRANSIENT_STATUS:
                consecutive_5xx += 1
                print(f"FALLO TRANSITORIO ({consecutive_5xx} seguidos): {e}")
                results.append({**item, "resultado": f"fallo:{e}"})
                if consecutive_5xx < MAX_CONSECUTIVE_5XX:
                    _retry_sleep(20 * consecutive_5xx)
                    if i < len(plan) - 1:
                        _pause()
                    continue
                print("PARADA TOTAL: el servidor falla de forma sostenida")
                for pending in plan[i + 1:]:
                    results.append({**pending, "resultado": "no_intentado"})
                break
            else:
                print(f"PARADA TOTAL: {e}")
                results.append({**item, "resultado": f"parada:{e}"})
                for pending in plan[i + 1:]:
                    results.append({**pending, "resultado": "no_intentado"})
                break
        except (m.BotWarningDetected, m.WrongAccountActive) as e:
            print(f"PARADA TOTAL: {e}")
            results.append({**item, "resultado": f"parada:{e}"})
            for pending in plan[i + 1:]:
                results.append({**pending, "resultado": "no_intentado"})
            break
        except m.AlreadyCommented as e:
            print(f"SALTADO: {e}")
            results.append({**item, "resultado": "saltado_ya_comentado"})
        except Exception as e:
<<<<<<< HEAD
            print(f"FALLO: {type(e).__name__}: {e}")
            results.append({**item, "resultado": f"fallo:{e}"})
=======
            if kind == "reply" and isinstance(e, ec.WriteOutcomeUnknown):
                print("RESULTADO INCIERTO: respuesta sin ACK; verificar remotamente antes de repetir")
                code = ec.status_code_of(e) or ec.status_code_of(e.__cause__)
                if code in TRANSIENT_STATUS:
                    consecutive_5xx += 1
                    if consecutive_5xx >= MAX_CONSECUTIVE_5XX:
                        # La parada se registra como incierta (no FAILED)
                        # y el orquestador recibe 'parada:' para que no
                        # anuncie una ronda sana tras tres 5xx seguidos.
                        results.append({**item, "resultado": "parada:incierto_5xx_servidor"})
                        for pending in plan[i + 1:]:
                            results.append({**pending, "resultado": "no_intentado"})
                        break
                    results.append({**item, "resultado": "incierto:transporte_sin_ack"})
                    _retry_sleep(20 * consecutive_5xx)
                    if i < len(plan) - 1:
                        _pause()
                    continue
                results.append({**item, "resultado": "incierto:transporte_sin_ack"})
            else:
                print(f"FALLO: {type(e).__name__}: {e}")
                results.append({**item, "resultado": f"fallo:{e}"})
>>>>>>> origin/research/public-reuse-parent

        if i < len(plan) - 1:
            _pause()

    if ledger is not None:
<<<<<<< HEAD
        ledger.settle_results(reserved, results)
=======
        ledger.settle_results(reserved, [r for r in results
                           if not ec.is_safe_preflight_omit(r.get("resultado"))])
>>>>>>> origin/research/public-reuse-parent
    return results


def _registro_account(r):
    """Cuenta para el registro. Follow usa el handle del plan; el resto lo
    deduce de la URL del status, pero un status puenteado (blog/RSS) trae la
    URL externa y daba "@https:" (50 filas el 02/10): ahi manda el handle."""
    handle = r.get("handle", "").lstrip("@")
    if r["kind"] == "follow":
        return handle
    url = r.get("url", "")
    if "/@" in url:
        return url.split("/@")[-1].split("/")[0]
    return handle or url


def _append_registro(results):
    fecha = datetime.date.today().isoformat()
    with open(REGISTRO_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in results:
            if r["resultado"] != "confirmado":
                continue
            cuenta = _registro_account(r)
            post_ref = r.get("url", "")
            notes = r.get("motivo", "")
            if r.get("created_url") and r["kind"] in ("reply", "quote"):
                notes = (notes + f" | creado={r['created_url']}").strip(" |")
            w.writerow([
                fecha, "@" + cuenta, r["kind"],
                post_ref, r.get("text", ""),
                "publicado", notes,
            ])


def _append_boost_ttl(results):
    """Programa el retiro de cada boost confirmado hoy (ver BOOST_TTL_DAYS) -
    mismo patron que repost_quote_ttl.csv en Bluesky/reposts_activos.csv en X:
    solo boosts entran aqui, nunca un favourite (sin rastro visible en el
    perfil propio) ni una reply (conversacion real)."""
    fecha = datetime.date.today()
    borrar_el = (fecha + datetime.timedelta(days=BOOST_TTL_DAYS)).isoformat()
    rows = [
        r for r in results
        if r["resultado"] == "confirmado" and r["kind"] == "boost" and r.get("status_id")
    ]
    if not rows:
        return
    exists = os.path.exists(BOOST_TTL_CSV) and os.path.getsize(BOOST_TTL_CSV) > 0
    with open(BOOST_TTL_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["fecha", "acct", "status_id", "url", "borrar_el", "estado"])
        for r in rows:
            w.writerow([
                fecha.isoformat(), r.get("handle", "") or r.get("url", "").split("/@")[-1].split("/")[0],
                r["status_id"], r.get("url", ""), borrar_el, "pendiente",
            ])


def _fetch_metrics():
    try:
        data = m._get("accounts/verify_credentials")
        return {
            "followers": data.get("followers_count", "?"),
            "following": data.get("following_count", "?"),
            "posts": data.get("statuses_count", "?"),
        }
    except Exception:
        return {"followers": "?", "following": "?", "posts": "?"}


def _append_metricas(results, metrics):
    ec.append_metricas(METRICAS_CSV, results, metrics, keys=("followers", "following", "posts"))


def _update_estado(results, metrics):
    ec.update_estado(ESTADO_MD, results, metrics, fields=(("Seguidores", "followers"), ("Siguiendo", "following"), ("Publicaciones", "posts")))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        plan = json.load(f)

    import action_ledger as al
    LEDGER_PATH = os.path.join(os.path.dirname(REGISTRO_CSV), "cache", "action_ledger.sqlite")
    try:
        with al.exclusive("exec_mastodon"):
            persisted = set()

            def _on_result(r):
                persisted.add(id(r))
                _append_registro([r])
                _append_boost_ttl([r])

            results = run_plan(plan, ledger=al.ActionLedger(LEDGER_PATH), on_result=_on_result)

            print("\n=== RESUMEN ===")
            for r in results:
                print(f"{r['resultado']:35s} {r['kind']:8s}")

            leftover = [r for r in results if id(r) not in persisted]       # lo que no se registro accion a accion (red de seguridad)
            if leftover:
                _append_registro(leftover)
                _append_boost_ttl(leftover)

            if any(str(r.get("resultado", "")).startswith("parada:") for r in results):
                print(
                    "\nPARADA TOTAL: se conserva el registro de acciones previas, "
                    "pero no se actualizan métricas/ESTADO como sesión normal."
                )
                raise SystemExit(5)
            metrics = _fetch_metrics()
            _append_metricas(results, metrics)
            _update_estado(results, metrics)
            print(
                "\nregistro_interacciones.csv, metricas.csv y ESTADO.md "
                "actualizados para las interacciones confirmadas."
            )
            print(
                f"Metricas finales: seguidores={metrics['followers']} "
                f"siguiendo={metrics['following']} publicaciones={metrics['posts']}"
            )
    except al.RoundBusy as exc:
        print(f"PARADA: {exc}")
        sys.exit(6)

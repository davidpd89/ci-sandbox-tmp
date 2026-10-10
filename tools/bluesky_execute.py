"""
Fase 3 del pipeline diario de Bluesky (22/09) - mismo patron que
`tools/x_execute.py`/`threads_execute.py`, simplificado porque Bluesky
habla API directa (sin navegador, sin CDP, sin techo de calentamiento por
deteccion de bots - ver REGLAS.md: "sin bot-detection agresiva, pero con
rate limits reales"). El presupuesto de calidad de REGLAS.md (hasta 5
perfiles puntuados, hasta 3 respuestas buenas, sin cuota minima) sigue
siendo decision de Claude en la fase 2, este script no impone un techo
numerico como instagram_execute.py.

Kinds soportados: "follow", "unfollow", "like", "repost", "quote", "reply".

Formato de plan.json:
    [
      {"handle": "foo.bsky.social", "kind": "follow", "motivo": "..."},
      {"handle": "foo.bsky.social", "kind": "reply", "url": "https://bsky.app/profile/foo.bsky.social/post/xyz",
       "text": "el texto de la respuesta", "motivo": "..."},
      {"handle": "foo.bsky.social", "kind": "like", "url": "...", "motivo": "..."}
    ]

Cada item con "text" pasa por `check_duplicate_phrase` antes de tocar la
API (mismo criterio que x_execute.py). La API se usa con una pausa corta de
3-8s entre escrituras: la protección real es el presupuesto de calidad y
parar ante 429/error, no imitar tiempos humanos de un navegador.

Uso:
    python tools/bluesky_execute.py plan.json
"""
import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import bluesky_interact as b
import check_duplicate_phrase as dup
import scan_common as sc
import growth_policy as gp
import exec_common as ec

RateLimitExceeded = getattr(
    b,
    "RateLimitExceeded",
    type("_NoRateLimitExceeded", (Exception,), {}),
)

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
METRICAS_CSV = os.path.join(ROOT, "metricas.csv")
ESTADO_MD = os.path.join(ROOT, "ESTADO.md")
TTL_CSV = os.path.join(ROOT, "repost_quote_ttl.csv")
# Cuanto duran repost/cita antes de que bluesky_cleanup_ttl.py los borre.
# Pedido explicito de David (29/09): el impacto a corto plazo del repost/cita
# no depende de que se quede fijado para siempre en el perfil - el post
# propio original nunca se toca, solo el registro de repost/cita generado
# hoy. 5 dias es el valor por defecto, no una promesa: ajustar aqui si hace
# falta otro ciclo.
REPOST_QUOTE_TTL_DAYS = gp.SHARE_TTL_DAYS      # 7 dias (David, 06/10): umbral comun a todas las redes (growth_policy)


def _pause(a=1.5, b=5.0):
    # Bluesky documenta 5.000 puntos de escritura/hora y CREATE=3 puntos (~1.666 acciones/hora): ritmo humano variable con el rango de la etapa de la rampa (logica comun en exec_common).
    ec.network_pause("bluesky", a, b, default=(1.5, 5.0))


PREFETCH_WINDOW = 100


def _prefetch_window(items):
    """Estado (viewer, cid, did) de las proximas acciones en 1 peticion por cada 25: cada like/follow queda en 1 sola peticion de escritura (05/10: ~11 s/accion
    y 3 peticiones por like hacian imposible el volumen objetivo). Un fallo no importa: la accion hace sus consultas de siempre."""
    uris = [it.get("_target_uri") or it.get("url") for it in items if it.get("kind") in ("like", "repost")]
    handles = [it["handle"] for it in items if it.get("kind") == "follow"]
    if not (uris or handles):
        return
    try:
        b.prefetch(uris=[b._url_to_uri(u) for u in uris if u], handles=handles)
    except Exception as exc:       # incluido un 429: la propia accion lo volvera a encontrar y lo gestiona con su parada habitual
        print(f"(precarga omitida: {type(exc).__name__}: {str(exc)[:80]})")


def _drop_stacked_actions(plan, *, key="url"):
    """Quita acciones baratas si el mismo post ya tiene reply/quote."""
    return sc.drop_stacked_actions(
        plan,
        cheap_kinds=("like", "repost"),
        rich_kinds=("reply", "quote"),
        key=key,
    )


_CONTENT_KINDS = {"like", "repost", "reply", "quote"}
_TEXT_KINDS = {"reply", "quote"}
_RELATION_KINDS = {"follow", "unfollow"}
_VALID_KINDS = _CONTENT_KINDS | _RELATION_KINDS


def _validated_plan_item(item, index):
    if not isinstance(item, dict):
        raise ValueError(f"elemento {index}: debe ser un objeto")
    out = dict(item)
    kind = out.get("kind")
    if kind not in _VALID_KINDS:
        raise ValueError(f"elemento {index}: kind inválido: {kind!r}")
    handle = out.get("handle")
    if not isinstance(handle, str) or not handle.strip().lstrip("@"):
        raise ValueError(f"elemento {index}: handle obligatorio")
    out["handle"] = handle.strip().lstrip("@")

    if kind in _CONTENT_KINDS:
        url = out.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError(f"elemento {index}: {kind} exige url")
        out["url"] = url.strip()
        # Solo lectura/resolución: normaliza el objetivo antes de cualquier escritura.
        out["_target_uri"] = b._url_to_uri(out["url"])

    if kind in _TEXT_KINDS:
        text = out.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"elemento {index}: {kind} exige texto")
        b._check_length(text)
        sc.guard_plan_item(out, index)
        b._check_spanish_orthography(text)
        hits = dup.check(text)
        if hits:
            raise ValueError(
                f"elemento {index}: solape de texto detectado - {hits[0]}"
            )
    return out


def _preflight_plan(plan):
    """Valida el plan completo antes de la primera escritura remota."""
    if not isinstance(plan, list):
        raise ValueError("plan.json debe contener una lista")
    validated = []
    try:   # 05/10: resolver los handles del plan en paralelo; el preflight serie tardaba minutos antes de la primera accion
        warm = []
        for item in plan:
            if isinstance(item, dict):
                warm.append(item.get("handle") or "")
                match = re.search(r"/profile/([^/]+)/post/", str(item.get("url") or ""))
                if match:
                    warm.append(match.group(1))
        b.warm_dids(warm)
    except Exception:
        pass
    for i, item in enumerate(plan):
        try:
            validated.append(_validated_plan_item(item, i + 1))
        except RuntimeError as exc:
            # 05/10: UN handle que ya no resuelve (cuenta borrada o renombrada) tumbaba el lote ENTERO ("Unable to resolve handle") y la ronda
            # principal de la franja de las 12:45 no ejecuto nada. Un objetivo inexistente se omite y el resto sigue; los errores de plan
            # (formato, texto duplicado, ortografia) siguen siendo ValueError y paran el lote.
            if "resolve" in str(exc).lower() or "(400)" in str(exc) or "(404)" in str(exc):
                who = (item or {}).get("handle", "?") if isinstance(item, dict) else "?"
                print(f"OMITIDO: elemento {i + 1} (@{who}): el objetivo ya no existe o no resuelve ({str(exc)[:90]})")
                continue
            raise
    # Canonicalizar por AT-URI evita que dos permalinks distintos del mismo post
    # esquiven el anti-stacking. Like/repost se omiten si hay reply/quote.
    validated = _drop_stacked_actions(validated, key="_target_uri")

    relation_seen = {}
    content_seen = {}
    for i, item in enumerate(validated, 1):
        kind = item["kind"]
        if kind in _RELATION_KINDS:
            key = item["handle"].casefold()
            if key in relation_seen:
                prev = relation_seen[key]
                raise ValueError(
                    f"elemento {i}: relación duplicada/conflictiva para @{item['handle']} "
                    f"(ya aparece como {prev})"
                )
            relation_seen[key] = kind
        elif kind in _CONTENT_KINDS:
            key = item["_target_uri"]
            if key in content_seen:
                prev = content_seen[key]
                raise ValueError(
                    f"elemento {i}: varias interacciones para el mismo post "
                    f"({prev} + {kind})"
                )
            content_seen[key] = kind

    for item in validated:
        item.pop("_target_uri", None)
    return validated


def _hourly_guard(done_times, ledger, sleeper=None, now=None, limit=None):
    """No pasar del limite horario de la API (5.000 puntos/hora = 1.666 CREATE; margen: volume_ramp.MAX_HOURLY_CREATES). Cuenta las escrituras de
    ESTE proceso (aun sin asentar en el ledger) y las confirmadas por otros en la ultima hora; si se llega al tope espera en tramos de 30 s."""
    import time as _time
    import volume_ramp
    sleeper = sleeper or _time.sleep
    limit = limit or volume_ramp.MAX_HOURLY_CREATES
    waited = 0
    while waited < 3600:
        moment = (now() if now else _time.time())
        mine = sum(1 for t in done_times if t > moment - 3600)
        others = ledger.count_since(moment - 3600) if ledger is not None else 0
        if mine + others < limit:
            return waited
        print(f"limite horario ({mine + others} escrituras en 60 min >= {limit}): espero 30 s")
        sleeper(30)
        waited += 30
    return waited


def _voice_quote(item, bridge):
    """El quote lleva texto propio incluso cuando no es una reply."""
    import voice_output_finalization as voice
    voice.inspect(item["text"], network="bluesky", queue="API")
    return bridge.quote(item["url"], item["text"])


def run_plan(plan, ledger=None, on_result=None):
    import reply_writer as _rw
    plan = _rw.require_gpt(plan, "bluesky")      # 08/10: nunca se publica texto que no venga de ChatGPT
    import repost_policy
    plan = repost_policy.guard(plan, globals().get("REGISTRO_CSV", ""))      # 07/10: reposts solo curados y max 3/dia, en todos los caminos
    results = []
    done_times = []
    try:
        plan = _preflight_plan(plan)
        sc.report_plan_style(plan)
    except Exception as e:
        print(f"FALLO DE PREFLIGHT: {type(e).__name__}: {e}")
        return [{
            "kind": "plan",
            "handle": "",
            "resultado": f"fallo_plan:{e}",
        }]
    reserved = set()
    persisted = set()  # una clave propia solo admite el PRIMER resultado del lote

    def _persist(result):
        if ledger is not None:
            key = (result.get("kind"), ledger.target_for(result.get("kind"), result))
            if key in reserved and key not in persisted:
                import action_ledger as _al
                ledger.settle(key[0], key[1], _al.outcome_to_status(result.get("resultado")), result.get("resultado"))
                persisted.add(key)
        if on_result:
            on_result(result)

    results = ec.ResultList(_persist)
    for i, item in enumerate(plan):
        if i % PREFETCH_WINDOW == 0:
            _prefetch_window(plan[i:i + PREFETCH_WINDOW])
        kind = item["kind"]
        # El filtro editorial debe poder asentar SKIPPED_POLICY en la reserva.
        if ledger is not None:
            target = ledger.target_for(kind, item)
            if (kind, target) in reserved:
                # Un FAILED previo se podría reservar de nuevo en este mismo lote.
                # No autorizar dos llamadas remotas para la misma clave.
                results.append({**item, "resultado": "saltado_en_ledger:already_in_plan"})
                continue
            verdict = ledger.reserve(kind, target)
            if verdict != "ok":
                print(f"SALTADO: ledger bloquea este objetivo ({verdict})")
                results.append({**item, "resultado": f"saltado_en_ledger:{verdict}"})
                continue
            reserved.add((kind, target))
        import conversation_turn_policy as ctp
        permitted, reason = ctp.check_execution("bluesky", item)
        if not permitted:
            results.append({**item, "resultado": f"saltado_cierre_conversacion:{reason}"})
            continue
        if kind in ("like", "favourite"):
            import like_context_policy as lcp
            allowed, why = lcp.check_execution("bluesky", item, bluesky_client=b)
            if not allowed:
                results.append({**item, "resultado": f"saltado_like_contexto:{why}"})
                continue
        handle = item["handle"].lstrip("@")
        print(f"=== {i+1}/{len(plan)}: {kind} -> @{handle} ===")

        _hourly_guard(done_times, ledger)
        try:
            if kind == "follow":
                outcome = ec.with_retries(lambda: b.follow(handle))
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_seguido"})
                    continue
                if outcome != "followed":
                    raise RuntimeError(f"follow devolvió estado inesperado: {outcome!r}")
            elif kind == "unfollow":
                outcome = ec.with_retries(lambda: b.unfollow(handle))
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_no_seguido"})
                    continue
                if outcome != "unfollowed":
                    raise RuntimeError(f"unfollow devolvió estado inesperado: {outcome!r}")
            elif kind == "like":
                outcome = ec.with_retries(lambda: b.like(item["url"]))   # 06/10: un 502 puntual de createRecord fallaba la accion; like/follow/repost comprueban el estado antes, asi que repetir es seguro
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_reaccionado"})
                    continue
                if outcome != "created":
                    raise RuntimeError(f"{kind} devolvió estado inesperado: {outcome!r}")
            elif kind in ("repost", "quote"):
                outcome, own_uri = (
                    ec.with_retries(lambda: b.repost(item["url"])) if kind == "repost"
                    else _voice_quote(item, b)
                )
                if outcome == "already":
                    results.append({
                        **item,
                        "resultado": "saltado_ya_citado" if kind == "quote" else "saltado_ya_reaccionado",
                    })
                    continue
                if outcome != "created":
                    raise RuntimeError(f"{kind} devolvió estado inesperado: {outcome!r}")
                item = {**item, "own_uri": own_uri}
            elif kind == "reply":
                import voice_output_finalization as voice
                voice.inspect(item["text"], network="bluesky", queue="API")
                b.reply_to(item["url"], item["text"])
            else:
                raise ValueError(f"kind desconocido: {kind}")
            results.append({**item, "resultado": "confirmado"})
            done_times.append(__import__("time").time())
        except RateLimitExceeded as e:
            print(f"PARADA RATE LIMIT: {e}")
            results.append({**item, "resultado": f"parada_rate_limit:{e}"})
            for pending in plan[i + 1:]:
                results.append({**pending, "resultado": "no_intentado"})
            break
        except b.BotWarningDetected as e:
            print(f"PARADA TOTAL: {e}")
            results.append({**item, "resultado": f"parada:{e}"})
            for pending in plan[i + 1:]:
                results.append({**pending, "resultado": "no_intentado"})
            break
        except b.AlreadyCommented as e:
            print(f"SALTADO: {e}")
            results.append({**item, "resultado": "saltado_ya_comentado"})
        except Exception as e:
            print(f"FALLO: {type(e).__name__}: {e}")
            results.append({**item, "resultado": f"fallo:{e}"})

        if i < len(plan) - 1:
            _pause()

    if ledger is not None:
        ledger.settle_results(reserved, results)
    return results


def _append_registro(results):
    fecha = datetime.date.today().isoformat()
    with open(REGISTRO_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in results:
            if r["resultado"] != "confirmado":
                continue
            w.writerow([
                fecha, "@" + r["handle"].lstrip("@"), r["kind"],
                r.get("url") or r.get("resumen", ""), r.get("text", ""),
                "publicado" if r["kind"] in ("reply", "quote") else "confirmado",
                r.get("motivo", ""),
            ])


def _append_repost_ttl(results):
    """Programar el borrado de cada repost/cita creado hoy.

    Solo repost/quote entran aqui - un like no deja rastro visible en el
    perfil propio y un reply es conversacion real, no impacto temporal.
    Sin own_uri (plan antiguo, ejecutor viejo) no se programa nada: mejor no
    borrar nunca que borrar a ciegas."""
    fecha = datetime.date.today()
    borrar_el = (fecha + datetime.timedelta(days=REPOST_QUOTE_TTL_DAYS)).isoformat()
    rows = [
        r for r in results
        if r["resultado"] == "confirmado"
        and r["kind"] in ("repost", "quote")
        and r.get("own_uri")
    ]
    if not rows:
        return
    exists = os.path.exists(TTL_CSV) and os.path.getsize(TTL_CSV) > 0
    with open(TTL_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["fecha", "kind", "handle", "own_uri", "target_url", "borrar_el", "estado"])
        for r in rows:
            w.writerow([
                fecha.isoformat(), r["kind"], "@" + r["handle"].lstrip("@"),
                r["own_uri"], r.get("url", ""), borrar_el, "pendiente",
            ])


def _stop_result(results):
    """Devuelve la primera parada que obliga a no hacer más llamadas remotas."""
    for row in results:
        outcome = str(row.get("resultado") or "")
        if outcome.startswith(("parada_rate_limit:", "parada:")):
            return outcome
    return None


def _finalize(results, persisted=False):
    """Persistir éxitos previos y evitar health/métricas después de una parada. `persisted`: el registro ya se fue escribiendo accion a accion."""
    if not persisted:
        _append_registro(results)
        _append_repost_ttl(results)
    stop = _stop_result(results)
    if stop:
        print(
            "\nSesión interrumpida: se guardan las acciones ya confirmadas, "
            "pero NO se solicitan métricas ni se actualiza ESTADO.md."
        )
        return None
    metrics = _fetch_metrics()
    _append_metricas(results, metrics)
    _update_estado(results, metrics)
    return metrics


def _fetch_metrics():
    ok, msg, profile = b._health_check()
    if not ok:
        return {"followers": "?", "following": "?", "posts": "?"}
    return {
        "followers": profile.get("followersCount", "?"),
        "following": profile.get("followsCount", "?"),
        "posts": profile.get("postsCount", "?"),
    }


def _append_metricas(results, metrics):
    ec.append_metricas(METRICAS_CSV, results, metrics, keys=("followers", "following", "posts"))


def _update_estado(results, metrics):
    ec.update_estado(ESTADO_MD, results, metrics, fields=(("Seguidores", "followers"), ("Siguiendo", "following"), ("Posts", "posts")))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        plan = json.load(f)

    import action_ledger as al
    LEDGER_PATH = os.path.join(os.path.dirname(REGISTRO_CSV), "cache", "action_ledger.sqlite")
    try:
        with al.exclusive("exec_bluesky"):
            results = run_plan(plan, ledger=al.ActionLedger(LEDGER_PATH),
                               on_result=lambda r: (_append_registro([r]), _append_repost_ttl([r])))

            print("\n=== RESUMEN ===")
            for r in results:
                print(f"{r['resultado']:20s} {r['kind']:8s} @{r['handle'].lstrip('@')}")

            metrics = _finalize(results, persisted=True)
            if metrics is None:
                sys.exit(5)
            print(f"\nregistro_interacciones.csv, metricas.csv y ESTADO.md actualizados automaticamente.")
            print(f"Metricas finales: seguidores={metrics['followers']} siguiendo={metrics['following']} posts={metrics['posts']}")
    except al.RoundBusy as exc:
        print(f"PARADA: {exc}")
        sys.exit(6)

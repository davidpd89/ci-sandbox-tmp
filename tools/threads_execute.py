"""
Fase 3 del pipeline diario de Threads (22/09) - mismo patron que
`tools/x_execute.py`. Kinds soportados: "follow", "like" y "reply"
(anadido el mismo dia tras corregir en vivo el diagnostico del bug de
respuesta - ver docstring de threads_interact.py: lo que estaba roto era
solo pg.goto() directo a la URL del post, no el click en "Responder" desde
un listado). "quote" sigue sin implementar (Threads no tiene un flujo de
cita tan directo como X, no investigado todavia). El "like"/"reply"
SIEMPRE actuan sobre el post tal y como aparece en un listado (feed/
perfil/busqueda), nunca navegando primero a su URL propia - misma regla
para los dos, ver PENDIENTES.md.

Formato de plan.json:
    [
      {"handle": "foo", "kind": "follow", "motivo": "..."},
      {"handle": "foo", "kind": "like", "text_fragment": "fragmento del post",
       "motivo": "..."},
      {"handle": "foo", "kind": "reply", "text_fragment": "fragmento del post",
       "text": "el texto de la respuesta", "motivo": "..."}
    ]

Cada item con "text" pasa por `check_duplicate_phrase` antes de tocar el
navegador (mismo criterio que x_execute.py - evita frases repetidas entre
redes).

Uso:
    python tools/threads_execute.py plan.json
"""
import csv
import time
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import threads_interact as t
import check_duplicate_phrase as dup
import scan_common as sc
import exec_common as ec
import growth_policy as gp

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_THREADS")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
METRICAS_CSV = os.path.join(ROOT, "metricas.csv")
ESTADO_MD = os.path.join(ROOT, "ESTADO.md")


FOLLOW_MAX_FOLLOWERS = gp.FOLLOW_MAX_FOLLOWERS       # cuentas enormes casi nunca devuelven el follow (umbral comun: growth_policy)


def _pause(a=30, b=55):
    """Pausa entre acciones por navegador: el rango y las dudas los pone la etapa de la rampa (exec_common); el valor por defecto de siempre (30-55 s) es la etapa 0."""
    ec.network_pause("threads", a, b, default=(30, 55))


_follow_vet = ec.follow_vet        # filtro comun de perfiles (exec_common.follow_vet), compartido con X


def _drop_stacked_actions(plan):
    """Corregido 23/09 (mismo criterio aplicado primero en x_execute.py, a
    peticion explicita de David: "si ya tienen una interaccion no necesitan
    mas") - ya no solo avisa, quita de verdad el like redundante sobre un
    handle que ya tiene reply en el mismo plan. Logica compartida en
    scan_common.drop_stacked_actions (23/09)."""
    return sc.drop_stacked_actions(plan, cheap_kinds=("like",), rich_kinds=("reply",),
                                    key="handle", normalize=lambda h: h.lstrip("@"))


_VALID_KINDS = {"follow", "like", "reply", "like_latest"}


def _preflight_plan(plan):
    """Valida el lote editorial antes de abrir el navegador para actuar."""
    if not isinstance(plan, list):
        raise ValueError("plan.json debe contener una lista")
    validated = []
    seen_actions = set()
    for index, raw in enumerate(plan, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"elemento {index}: debe ser un objeto")
        item = dict(raw)
        kind = item.get("kind")
        if kind not in _VALID_KINDS:
            raise ValueError(f"elemento {index}: kind inválido {kind!r}")
        handle = item.get("handle")
        if not isinstance(handle, str) or not handle.strip().lstrip("@"):
            raise ValueError(f"elemento {index}: handle obligatorio")
        item["handle"] = handle.strip().lstrip("@")
        if kind == "reply" and item.get("reply_to_id"):
            # Respuesta por API oficial (ID de la propia API, p. ej. de threads_api.py followups):
            # no hace falta localizar el post por texto en el navegador.
            item["reply_to_id"] = str(item["reply_to_id"]).strip()
            item.setdefault("text_fragment", (item.get("post_text") or item["reply_to_id"])[:60])
        if kind in {"like", "reply"}:
            fragment = item.get("text_fragment")
            if not isinstance(fragment, str) or not fragment.strip():
                raise ValueError(f"elemento {index}: {kind} exige text_fragment")
            item["text_fragment"] = fragment.strip()
        permalink = item.get("permalink")
        if permalink is not None:
            # solo un permalink canonico de Threads del MISMO autor sirve para actuar; cualquier otra cosa se descarta y se usa el fragmento (nunca se navega a una URL ajena)
            ok = (isinstance(permalink, str) and permalink.startswith("https://www.threads.com/@") and "/post/" in permalink
                  and permalink[len("https://www.threads.com/@"):].split("/")[0].casefold() == item["handle"].casefold())
            if ok and kind == "like":
                item["permalink"] = permalink.rstrip("/")
            else:
                item.pop("permalink", None)
        if kind == "reply":
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"elemento {index}: reply exige text")
            text = text.strip()
            t._check_length(text)
            sc.guard_plan_item(item, index)
            t._check_spanish_orthography(text)
            hits = [] if item.get("bank") else dup.check(text)       # el banco de frases cortas repite a proposito (ventana propia de 7 dias en x_replies)
            if hits:
                raise ValueError(f"elemento {index}: texto duplicado - {hits[0]}")
            item["text"] = text
        # Priorizar el ID del destino en replies API: dos posts de un mismo
        # autor pueden compartir extracto, pero un mismo ID no se responde dos veces.
        # Para WEB/follow/like se conserva la clave previa autor + fragmento.
        duplicate_key = sc.plan_action_duplicate_key(
            item, stable_target_fields=("reply_to_id",) if kind == "reply" else (),
        )
        if duplicate_key in seen_actions:
            raise ValueError(f"elemento {index}: accion duplicada ({kind} sobre @{item['handle']})")
        seen_actions.add(duplicate_key)
        validated.append(item)
    return _drop_stacked_actions(validated)


PRESENT, ABSENT, UNKNOWN = "present", "absent", "unknown"


def _reply_state(text):
    """Tres estados, nunca un booleano (revision de GPT 05/10): PRESENT = la API oficial ve ya una respuesta nuestra con
    EXACTAMENTE este texto; ABSENT = la API se consulto y no esta; UNKNOWN = no se pudo consultar (sin credenciales, red,
    token roto). Antes cualquier error se devolvia como 'no existe' y un fallo del verificador pasaba por permiso para publicar."""
    try:
        import threads_api as api
        env = api._env()
        data = api.api_get("me/replies", env["THREADS_ACCESS_TOKEN"], fields="id,text", limit=50)
    except Exception:
        return UNKNOWN
    wanted = " ".join(text.split())
    found = any(" ".join((r.get("text") or "").split()) == wanted for r in data.get("data", []))
    return PRESENT if found else ABSENT


def _already_replied_via_api(text):
    """True SOLO si la API confirma que ya existe. En UNKNOWN devuelve False (se sigue con la comprobacion del navegador),
    pero queda dicho en pantalla: ver `_reply_state`."""
    state = _reply_state(text)
    if state == UNKNOWN:
        print("AVISO: no se pudo consultar /me/replies; se confia en la comprobacion del navegador (resultado incierto si falla)")
    return state == PRESENT


def _verified_via_api(text, attempts=2, wait=4):
    """La respuesta publicada por el navegador aparece en /me/replies (puede tardar unos segundos)."""
    for attempt in range(attempts):
        if _reply_state(text) == PRESENT:
            return True
        if attempt + 1 < attempts:
            time.sleep(wait)
    return False


def run_plan(plan, *, prevalidated=False, on_result=None):
    import reply_writer as _rw
    plan = _rw.require_gpt(plan, "threads")      # 08/10: nunca se publica texto que no venga de ChatGPT
    import repost_policy
    plan = repost_policy.guard(plan, globals().get("REGISTRO_CSV", ""))      # 07/10: reposts solo curados y max 3/dia, en todos los caminos
    results = ec.ResultList(on_result)
    if not prevalidated:
        try:
            plan = _preflight_plan(plan)
            sc.report_plan_style(plan)
        except Exception as exc:
            print(f"FALLO DE PREFLIGHT: {type(exc).__name__}: {exc}")
            return [{"kind": "plan", "handle": "", "resultado": f"fallo_plan:{exc}"}]
    for i, item in enumerate(plan):
        # Una ronda puede durar horas: revalidar la cuarentena antes de CADA
        # acción, incluso si el lanzador aprobó el lote al comienzo.
        import circuit_breaker as _cb
        _write_ok, _hold_reason = _cb.write_preflight("threads")
        if not _write_ok:
            print(f"[threads] cortacircuitos ABIERTO: {_hold_reason}; detener el lote")
            break
        kind = item["kind"]
        import conversation_turn_policy as ctp
        permitted, reason = ctp.check_execution("threads", item)
        if not permitted:
            results.append({**item, "resultado": f"saltado_cierre_conversacion:{reason}"})
            continue
        if kind in ("like", "like_latest"):
            import like_context_policy as lcp
            allowed, why = lcp.check_execution("threads", item)
            if not allowed:
                results.append({**item, "resultado": f"saltado_like_contexto:{why}"})
                continue
        handle = item["handle"].lstrip("@")
        print(f"=== {i+1}/{len(plan)}: {kind} -> @{handle} ===")
        if hasattr(t, "beat"):
            t.beat()

        try:
            if kind == "follow":
                vet = globals().get("_follow_vet") if item.get("vet", True) else None
                outcome = t.follow(handle, vet=vet) if vet else t.follow(handle)
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_seguido"})
                    continue
                if outcome == "pending":
                    results.append({**item, "resultado": "pendiente_aprobacion"})
                    continue
                if outcome != "followed":
                    raise RuntimeError(f"follow devolvió estado inesperado: {outcome!r}")
            elif kind == "like":
                if item.get("permalink"):       # 05/10: abrir el permalink (probado en vivo) en vez de buscar el texto en el perfil del autor
                    outcome = t.like_post(item["permalink"], handle)
                else:
                    profile_url = f"https://www.threads.com/@{handle}"
                    outcome = t.like_in_feed(item.get("text_fragment", ""), profile_url)
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_like"})
                    continue
                if outcome != "created":
                    raise RuntimeError(f"like devolvió estado inesperado: {outcome!r}")
            elif kind == "like_latest":        # 06/10: like al ultimo post propio y reciente de la cuenta (cuentas de la reserva sin un post concreto)
                outcome, fragment = t.like_latest(handle, vet=globals().get("_follow_vet"))
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_like"})
                    continue
                item = {**item, "kind": "like", "text_fragment": fragment}      # en el registro es un like normal
            elif kind == "reply" and item.get("reply_to_id"):
                import threads_api as api
                env = api._env()
                api.publish_reply(env["THREADS_ACCESS_TOKEN"], env["THREADS_USER_ID"],
                                  item["reply_to_id"], item["text"], proof_action=item)
            elif kind == "reply":
                if _already_replied_via_api(item["text"]):
                    # 03/10: una ronda cortada dejo la respuesta publicada sin registrar y el reintento la
                    # duplico (la comprobacion del navegador falla con hilos de varias partes "1/2").
                    results.append({**item, "resultado": "saltado_ya_comentado"})
                    continue
                profile_url = f"https://www.threads.com/@{handle}"
                outcome = t.reply_to(item.get("text_fragment", ""), item["text"], profile_url)
                if outcome == "unverified":
                    # la interfaz no siempre muestra la respuesta al instante: la API oficial es la fuente fiable
                    if _verified_via_api(item["text"]):
                        results.append({**item, "resultado": "confirmado"})
                    else:
                        results.append({**item, "resultado": "pendiente_verificacion"})
                    continue
                if outcome != "created":
                    raise RuntimeError(f"reply devolvió estado inesperado: {outcome!r}")
            else:
                raise ValueError(f"kind desconocido: {kind}")
            results.append({**item, "resultado": "confirmado"})
        except (t.BotWarningDetected, t.WrongAccountActive) as e:
            print(f"PARADA TOTAL: {e}")
            results.append({**item, "resultado": f"parada:{e}"})
            for pending in plan[i + 1:]:
                results.append({**pending, "resultado": "no_intentado"})
            break
        except t.AlreadyCommented as e:
            print(f"SALTADO: {e}")
            results.append({**item, "resultado": "saltado_ya_comentado"})
        except ec.WriteOutcomeUnknown:
            # No hay ACK tras el POST: se retiene UNCERTAIN en el ledger común.
            # Ni fallo reintentable ni éxito inventado. Continuar otras acciones.
            print("PENDIENTE_VERIFICACION: Threads sin ACK remoto; no reintentar")
            results.append({**item, "resultado": "pendiente_verificacion"})
        except PermissionError as e:
            if kind == "reply" and item.get("reply_to_id"):
                print(f"OMITIDO: contrato contextual de Threads: {type(e).__name__}")
                results.append({**item, "resultado": "saltado_contexto_api_no_verificado"})
            else:
                print(f"FALLO: {type(e).__name__}")
                results.append({**item, "resultado": "fallo:permiso_denegado"})
        except getattr(t, "ProfileRejected", ()) as e:
            print(f"SALTADO: perfil no apto: {e}")
            results.append({**item, "resultado": f"saltado_perfil:{e}"})
        except Exception as e:
            print(f"FALLO: {type(e).__name__}: {e}")
            results.append({**item, "resultado": f"fallo:{e}"})

        if i < len(plan) - 1:
            _pause()

    return results


def _append_registro(results):
    fecha = datetime.date.today().isoformat()
    with open(REGISTRO_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in results:
            outcome = r["resultado"]
            if outcome not in (
                "confirmado", "pendiente_verificacion", "pendiente_aprobacion"
            ):
                continue
            stored = (
                outcome if outcome.startswith("pendiente_")
                else ("publicado" if r["kind"] == "reply" else "confirmado")
            )
            w.writerow([
                fecha, "@" + r["handle"].lstrip("@"), r["kind"],
                r.get("text_fragment", ""), r.get("text", ""),
                stored, r.get("motivo", ""),
            ])


def _fetch_metrics():
    p, pg = t._connect()
    try:
        pg.goto("https://www.threads.com/@davidportodiaz", wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(2200)
        body = pg.inner_text("body")[:1500]
        followers = re.search(r"([\d.,mil]+)\s+seguidores", body, re.I)
        return {"followers": followers.group(1) if followers else "?"}
    finally:
        p.stop()


def _append_metricas(results, metrics):
    ec.append_metricas(METRICAS_CSV, results, metrics, keys=("followers", "following", "posts"))


def _update_estado(results, metrics):
    ec.update_estado(ESTADO_MD, results, metrics, fields=(("Seguidores", "followers"),))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        plan = json.load(f)

    try:
        plan = _preflight_plan(plan)
        sc.report_plan_style(plan)
    except Exception as exc:
        print(f"FALLO DE PREFLIGHT: {type(exc).__name__}: {exc}")
        raise SystemExit(2)

    t.ensure_browser()
    persisted = set()

    def _on_result(r):
        persisted.add(id(r))
        _append_registro([r])
        try:       # la reserva anota que se hizo con cada post (nunca se vuelve a elegir el mismo)
            import threads_pool as pool
            db = pool.connect()
            try:
                if r.get("permalink"):
                    pool.mark(db, r["permalink"], "done" if r["resultado"] in ("confirmado", "saltado_ya_like") else "failed")
                if r.get("kind") in ("follow", "like", "like_latest") and r.get("handle"):
                    outcome = r["resultado"]
                    status = ("done" if outcome in ("confirmado", "saltado_ya_like", "saltado_ya_seguido", "pendiente_aprobacion")
                              else "rejected" if outcome.startswith("saltado_perfil") else None)
                    if status:       # una cuenta tocada o rechazada no vuelve a ofrecerse; un fallo puntual si
                        pool.mark_account(db, r["handle"], status)
            finally:
                db.close()
        except Exception:
            pass

    with t.session():       # UNA conexion para todo el plan (antes: una por accion)
        results = run_plan(plan, prevalidated=True, on_result=_on_result)

    print("\n=== RESUMEN ===")
    for r in results:
        print(f"{r['resultado']:20s} {r['kind']:8s} @{r['handle']}")

    leftover = [r for r in results if id(r) not in persisted]
    if leftover:
        _append_registro(leftover)
    # PARADA TOTAL debe incluir la recogida de métricas: esta función
    # navega por el perfil y antes volvía a abrir la red tras un CAPTCHA,
    # bloqueo o cuenta incorrecta detectados en run_plan.
    if any(str(item.get("resultado", "")).startswith("parada:") for item in results):
        print("PARADA TOTAL: resultados guardados; no se abre de nuevo el navegador para métricas.")
        sys.exit(5)
    metrics = _fetch_metrics()
    _append_metricas(results, metrics)
    _update_estado(results, metrics)
    print(f"\nregistro_interacciones.csv, metricas.csv y ESTADO.md actualizados automaticamente.")
    print(f"Metricas finales: seguidores={metrics['followers']}")

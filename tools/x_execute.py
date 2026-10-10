"""
Fase 3 del pipeline diario de X (anadido 22/09). Recibe un plan.json que
Claude escribe a mano tras leer la salida de `x_scan.py` (fase 1) y decide
que hacer con cada candidato, y lo ejecuta con ritmo humano, comprobaciones
de seguridad automaticas, y **registro automatico** en registro_interacciones.csv
y metricas.csv al terminar - lo que antes se escribia a mano con `python -c`
o editando los CSV directamente.

Formato de plan.json (lista de objetos):
    [
      {"url": "https://x.com/foo/status/123", "kind": "reply",
       "handle": "@foo", "resumen": "una linea de que trata el post",
       "text": "el texto de la respuesta", "motivo": "comunidad|visibilidad"},
      {"url": "https://x.com/bar/status/456", "kind": "quote", ...},
      {"handle": "@baz", "kind": "follow", "motivo": "..."},
      {"url": "https://x.com/foo/status/123", "kind": "like", "motivo": "..."}
    ]

Regla aplicada automaticamente (REGLAS.md, "Una interaccion por candidato";
corregida 23/09 a peticion explicita de David - "si ya tienen una
interaccion no necesitan mas"): si el plan ya tiene un reply/quote para una
URL, cualquier like/repost adicional sobre esa MISMA URL se elimina antes de
ejecutar el plan (`_drop_stacked_actions`) - repartir el esfuerzo en mas
cuentas distintas vale mas que apilar acciones en una.

Seguro adicional anadido 23/09: nunca se comenta dos veces el mismo post,
ni siquiera en sesiones distintas. La comprobacion real vive dentro de
`x_interact.reply_to()` (escanea los comentarios existentes en vivo antes de
escribir); si detecta que ya hay un comentario nuestro, lanza
`AlreadyCommented` y este script lo registra como "saltado_ya_comentado" en
vez de intentarlo.

Cada item pasa automaticamente por: `check_duplicate_phrase` (si lleva
texto), `_check_length`, `_check_spanish_orthography` (los dos ultimos ya
viven dentro de reply_to/repost, aqui se listan porque son la razon de que
un item pueda salir "saltado" antes de tocar el navegador). Un
BotWarningDetected o WrongAccountActive para TODO el plan de inmediato -
el resto de items quedan "no intentado", nunca "fallido" a ciegas.

Uso:
    python tools/x_execute.py plan.json
"""
import csv
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import x_interact as x
import check_duplicate_phrase as dup
import scan_common as sc
import growth_policy as gp
import exec_common as ec

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_X")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
METRICAS_CSV = os.path.join(ROOT, "metricas.csv")
ESTADO_MD = os.path.join(ROOT, "ESTADO.md")


def _pause(a=30, b=55):
    """Pausa entre acciones por navegador: el rango y las dudas los pone la etapa de la rampa (exec_common); el valor de siempre (30-55 s) es la etapa por defecto."""
    ec.network_pause("x", a, b, default=(30, 55))


_follow_vet = ec.follow_vet        # filtro comun de perfiles (exec_common.follow_vet), compartido con Threads


def _drop_stacked_actions(plan):
    """Corregido 23/09 a peticion explicita de David ("si ya tienen una
    interaccion no necesitan mas"): antes esto solo avisaba y dejaba pasar
    igual un like/repost sobre una URL que ya tenia reply/quote en el mismo
    plan - ahora se elimina de verdad. Logica compartida en
    scan_common.drop_stacked_actions (23/09)."""
    return sc.drop_stacked_actions(plan, cheap_kinds=("like", "repost"), rich_kinds=("reply", "quote"), key="url")


_CONTENT_KINDS = {"reply", "quote", "like", "repost"}
_TEXT_KINDS = {"reply", "quote"}
_VALID_KINDS = _CONTENT_KINDS | {"follow", "like_latest"}
_HANDLE_KINDS = {"follow", "like_latest"}          # acciones sobre una CUENTA (no sobre un post concreto)


def _preflight_plan(plan):
    """Valida y canonicaliza el plan entero antes de su primera escritura."""
    if not isinstance(plan, list):
        raise ValueError("plan.json debe contener una lista")

    validated = []
    for index, raw in enumerate(plan, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"elemento {index}: debe ser un objeto")
        item = dict(raw)
        kind = item.get("kind")
        if kind in ("like", "like_latest"):
            # Plan heredado: descartarlo ANTES de validar/publicar;
            # no deshabilitar el resto de la ronda.
            continue
        if kind not in _VALID_KINDS:
            raise ValueError(f"elemento {index}: kind inválido {kind!r}")
        if kind in _HANDLE_KINDS:
            handle = item.get("handle")
            if not isinstance(handle, str) or not handle.strip().lstrip("@"):
                raise ValueError(f"elemento {index}: {kind} exige handle")
            item["handle"] = handle.strip().lstrip("@")
        else:
            item["url"] = x._validated_status_url(item.get("url"))
            if kind in _TEXT_KINDS:
                text = item.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError(f"elemento {index}: {kind} exige texto")
                item["text"] = text.strip()
                x._check_length(item["text"])
                sc.guard_plan_item(item, index)
                x._check_spanish_orthography(item["text"])
                # las replies del banco por intencion (`x_replies.py`) reutilizan frases a proposito (ventana propia de 7 dias); el resto, que sigue siendo editorial, no puede repetir texto
                hits = [] if item.get("bank") else dup.check(item["text"])
                if hits:
                    raise ValueError(
                        f"elemento {index}: solape de texto detectado - {hits[0]}"
                    )
        validated.append(item)

    validated = _drop_stacked_actions(validated)
    relation_seen = set()
    content_seen = set()
    for index, item in enumerate(validated, start=1):
        kind = item["kind"]
        if kind in _HANDLE_KINDS:
            key = (kind, item["handle"].casefold())
            if key in relation_seen:
                raise ValueError(f"elemento {index}: {kind} duplicado para @{item['handle']}")
            relation_seen.add(key)
        else:
            key = item["url"]
            if key in content_seen:
                raise ValueError(
                    f"elemento {index}: varias interacciones para el mismo status {key}"
                )
            content_seen.add(key)
    return validated


def run_plan(plan, *, prevalidated=False, on_result=None):
    import reply_writer as _rw
    plan = _rw.require_gpt(plan, "x")      # 08/10: nunca se publica texto que no venga de ChatGPT
    import repost_policy
    plan = repost_policy.guard(plan, globals().get("REGISTRO_CSV", ""))      # 07/10: reposts solo curados y max 3/dia, en todos los caminos
    results = ec.ResultList(on_result)
    if not prevalidated:
        try:
            plan = _preflight_plan(plan)
            sc.report_plan_style(plan)
        except Exception as exc:
            message = f"FALLO DE PREFLIGHT: {type(exc).__name__}: {exc}"
            print(message)
            return [{"kind": "plan", "handle": "", "resultado": f"fallo_plan:{exc}"}]
    import x_automation_policy as xap
    for i, item in enumerate(plan):
        # Barrera también para prevalidated=True y planes históricos/externos.
        if xap.is_automatic_like(item):
            results.append({**item, "resultado": "saltado_politica_auto_like"})
            continue
        # Una ronda puede durar horas: revalidar la cuarentena antes de CADA
        # acción, incluso si el lanzador aprobó el lote al comienzo.
        import circuit_breaker as _cb
        _write_ok, _hold_reason = _cb.write_preflight("x")
        if not _write_ok:
            print(f"[x] cortacircuitos ABIERTO: {_hold_reason}; detener el lote")
            break
        kind = item["kind"]
        import conversation_turn_policy as ctp
        permitted, reason = ctp.check_execution("x", item)
        if not permitted:
            results.append({**item, "resultado": f"saltado_cierre_conversacion:{reason}"})
            continue
        if kind in ("like", "like_latest"):
            import like_context_policy as lcp
            allowed, why = lcp.check_execution("x", item)
            if not allowed:
                results.append({**item, "resultado": f"saltado_like_contexto:{why}"})
                continue
        label = item.get("handle") or item.get("url", "")
        print(f"=== {i+1}/{len(plan)}: {kind} -> {label} ===")
        x.beat()

        try:
            if kind == "reply":
                import voice_output_finalization as voice
                voice.inspect(item["text"], network="x", queue="WEB")
                outcome = x.reply_to(item["url"], item["text"])
                if outcome != "created":
                    raise RuntimeError(f"reply devolvió estado inesperado: {outcome!r}")
            elif kind == "quote":
                import voice_output_finalization as voice
                voice.inspect(item["text"], network="x", queue="WEB")
                outcome, own_uri = x.repost(item["url"], item["text"])
                if outcome == "unverified":
                    results.append({**item, "resultado": "pendiente_verificacion"})
                    for pending in plan[i + 1:]:
                        results.append({**pending, "resultado": "no_intentado"})
                    break
                if outcome != "created":
                    raise RuntimeError(f"quote devolvió estado inesperado: {outcome!r}")
                item = {**item, "own_uri": own_uri}
            elif kind == "follow":
                outcome = x.follow(item["handle"].lstrip("@"), vet=_follow_vet if item.get("vet", True) else None)
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_seguido"})
                    continue
                if outcome == "pending":
                    results.append({**item, "resultado": "pendiente_aprobacion"})
                    continue
                if outcome != "followed":
                    raise RuntimeError(f"follow devolvió estado inesperado: {outcome!r}")
            elif kind == "like":
                outcome = x.like(item["url"])
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_like"})
                    continue
                if outcome != "created":
                    raise RuntimeError(f"like devolvió estado inesperado: {outcome!r}")
            elif kind == "like_latest":        # 06/10: like al ultimo post propio y reciente de la cuenta (cuentas de la reserva sin un post concreto)
                outcome, fragment = x.like_latest(item["handle"].lstrip("@"), vet=_follow_vet)
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_like"})
                    continue
                item = {**item, "kind": "like", "resumen": fragment}      # en el registro es un like normal
            elif kind == "repost":
                outcome, _own_uri = x.repost(item["url"])
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_reposteado"})
                    continue
                if outcome != "created":
                    raise RuntimeError(f"repost devolvió estado inesperado: {outcome!r}")
            else:
                raise ValueError(f"kind desconocido: {kind}")
            results.append({**item, "resultado": "confirmado"})
        except (x.BotWarningDetected, x.WrongAccountActive) as e:
            print(f"PARADA TOTAL: {type(e).__name__}")
            # Si el aviso llegó DESPUÉS de un tap, guardar también el
            # posible ACK. La pausa de plataforma sigue siendo obligatoria.
            status = ("pendiente_verificacion" if getattr(e, "possible_write", False)
                      else f"parada:{type(e).__name__}")
            results.append({**item, "resultado": status})
            for pending in plan[i + 1:]:
                results.append({**pending, "resultado": "no_intentado"})
            break
        except x.XWriteUnverified as e:
            # El POST/click pudo haberse ejecutado: registrar incierto y
            # DETENER la sesión. Nunca degradar a fallo reintentable.
            print(f"PARADA ACK INCIERTO: {type(e).__name__}")
            results.append({**item, "resultado": "pendiente_verificacion"})
            for pending in plan[i + 1:]:
                results.append({**pending, "resultado": "no_intentado"})
            break
        except x.AlreadyCommented as e:
            print(f"SALTADO: {e}")
            results.append({**item, "resultado": "saltado_ya_comentado"})
        except x.ProfileRejected as e:
            print(f"SALTADO: perfil no apto: {e}")
            results.append({**item, "resultado": f"saltado_perfil:{e}"})
        except Exception as e:
            print(f"FALLO: {type(e).__name__}: {e}")
            results.append({**item, "resultado": f"fallo:{e}"})

        if i < len(plan) - 1:
            _pause()

    return results


def _append_registro(results):
    if not any(r.get("resultado") in (
            "confirmado", "pendiente_verificacion", "pendiente_aprobacion",
            "saltado_ya_seguido", "saltado_ya_like",
            "saltado_ya_comentado", "saltado_ya_reposteado") for r in results):
        return
    fecha = datetime.date.today().isoformat()
    expected = ["fecha", "cuenta", "tipo", "post_resumen", "texto_usado", "resultado", "notas"]
    # No añadir columnas a un CSV truncado/migrado sin comprobar el esquema.
    with open(REGISTRO_CSV, encoding="utf-8-sig", newline="") as current:
        if next(csv.reader(current), None) != expected:
            raise ValueError("CSV X: cabecera incompatible, revisión manual")
    with open(REGISTRO_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in results:
            outcome = r["resultado"]
            observed = {
                "follow": "saltado_ya_seguido",
                "like": "saltado_ya_like",
                "like_latest": "saltado_ya_like",
                "reply": "saltado_ya_comentado",
                "repost": "saltado_ya_reposteado",
            }.get(r.get("kind"))
            if outcome not in ("confirmado", "pendiente_verificacion", "pendiente_aprobacion", observed):
                continue
            # 'Ya estaba hecho' es observación, NO un nuevo follow/like
            # confirmado. Guardarlo permite evitar volver al mismo destino.
            stored = (
                outcome if outcome.startswith(("pendiente_", "saltado_ya_"))
                else ("publicado" if r["kind"] in ("reply", "quote") else "confirmado")
            )
            w.writerow([
                fecha, r.get("handle", ""), r["kind"], r.get("url") or r.get("resumen", ""),
                r.get("text", ""), stored, r.get("motivo", ""),
            ])
        f.flush()
        os.fsync(f.fileno())


REPOST_TTL_CSV = os.path.join(ROOT, "reposts_activos.csv")
# Ventana ya establecida en REGLAS.md ("Vencimiento a 3 semanas", 17/09) -
# no se cambia aqui, solo se automatiza (antes era un paso manual, "revisar
# reposts_activos.csv cada ~2 semanas") y se extiende a citas (29/09, a
# peticion explicita de David: auto-borrado comun a repost Y cita, no solo
# Bluesky - "para tener nuestro feed limpio... no un vertedero de repost").
REPOST_QUOTE_TTL_DAYS = gp.SHARE_TTL_DAYS


def _append_repost_ttl(results):
    """Programa la limpieza de cada repost/cita confirmado hoy. Repost no
    tiene own_uri propio (se deshace sobre la URL original con unrepost());
    cita si (se borra con delete_post() sobre own_uri) - sin own_uri
    localizado, no se programa el borrado de esa cita: mejor no borrar nunca
    que borrar a ciegas el post equivocado."""
    fecha = datetime.date.today()
    borrar_el = (fecha + datetime.timedelta(days=REPOST_QUOTE_TTL_DAYS)).isoformat()
    rows = [
        r for r in results
        if r["resultado"] == "confirmado" and r["kind"] in ("repost", "quote")
        and (r["kind"] == "repost" or r.get("own_uri"))
    ]
    if not rows:
        return
    exists = os.path.exists(REPOST_TTL_CSV) and os.path.getsize(REPOST_TTL_CSV) > 0
    with open(REPOST_TTL_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["fecha", "kind", "handle", "url", "own_uri", "borrar_el", "estado"])
        for r in rows:
            w.writerow([
                fecha.isoformat(), r["kind"], "@" + (r.get("handle") or "").lstrip("@"),
                r.get("url", ""), r.get("own_uri", ""), borrar_el, "pendiente",
            ])


def _fetch_metrics():
    p, pg = x._connect()
    try:
        pg.goto("https://x.com/davidportodiaz", wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(2000)
        body = pg.inner_text("main")[:800]
        import re
        following = re.search(r"([\d.,]+)\s+Following", body)
        followers = re.search(r"([\d.,]+)\s+Followers?", body)
        posts = re.search(r"([\d.,]+)\s+posts", body)
        return {
            "following": following.group(1) if following else "?",
            "followers": followers.group(1) if followers else "?",
            "posts": posts.group(1) if posts else "?",
        }
    finally:
        p.stop()


def _append_metricas(results, metrics):
    fecha = datetime.date.today().isoformat()
    counts = {}
    for r in results:
        if r["resultado"] == "confirmado":
            counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    resumen = ", ".join(f"{v} {k}" for k, v in counts.items())
    with open(METRICAS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([fecha, metrics["followers"], metrics["following"], metrics["posts"],
                    f"Sesion via pipeline scan->plan->execute: {resumen}."])


def _update_estado(results, metrics):
    if not os.path.exists(ESTADO_MD):
        return
    with open(ESTADO_MD, encoding="utf-8") as f:
        content = f.read()
    fecha = datetime.date.today().isoformat()
    counts = {}
    for r in results:
        if r["resultado"] == "confirmado":
            counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    resumen = ", ".join(f"{v} {k}" for k, v in counts.items()) or "sin acciones confirmadas"
    import re
    # (?=\n## |\Z) en vez de solo \n\n: la cabecera de una seccion puede
    # llevar su propio parrafo entre parentesis antes del primer salto
    # doble (ej. "## Metricas actuales (de metricas.csv...)\n\nSeguidores:
    # ..."), y un \n\n no ancorado a la SIGUIENTE cabecera paraba ahi
    # mismo en vez de sustituir el contenido real de la seccion - visto en
    # vivo al probar esta funcion antes de dejarla en produccion.
    content = re.sub(
        r"## Última sesión\n\n.*?(?=\n## |\Z)",
        f"## Última sesión\n\n{fecha}. {resumen}. Detalle: `diario/{fecha}.md` (si se escribio) "
        f"o `registro_interacciones.csv`.\n\n",
        content, count=1, flags=re.S,
    )
    content = re.sub(
        r"## Métricas actuales.*?(?=\n## |\Z)",
        f"## Métricas actuales (de `metricas.csv`, última fila)\n\n"
        f"Seguidores: {metrics['followers']}. Siguiendo: {metrics['following']}. "
        f"Posts: {metrics['posts']}.\n\n",
        content, count=1, flags=re.S,
    )
    with open(ESTADO_MD, "w", encoding="utf-8") as f:
        f.write(content)


def _pool_post_status(resultado):
    """No atribuir intento/fallo a un destino cuyo turno nunca ocurrió."""
    if resultado in ("confirmado", "saltado_ya_like", "saltado_ya_reposteado"):
        return "done"
    if resultado == "pendiente_verificacion":
        return "uncertain"
    return None


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

    # Un fichero de plan antiguo puede sobrevivir a otra ejecución. La
    # comprobación se repite JUSTO antes de conectar con Edge.
    import x_acquisition_audit as xa
    followed, treated = xa.read_history(REGISTRO_CSV)
    plan, skipped = xa.filter_known_plan(plan, followed, treated)
    if any(group["descartadas_registro"] for group in skipped.values()):
        print("X_DEDUPE_PREFLIGHT: destinos ya tratados omitidos; no se repiten")
    if not plan:
        print("X_DEDUPE_PREFLIGHT: cero acciones pendientes, no se abre Edge")
        raise SystemExit(0)

    x.ensure_browser()
    persisted = set()

    def _on_result(r):
        persisted.add(id(r))
        _append_registro([r])               # cada accion queda registrada al momento: un corte del proceso solo pierde la accion en curso
        try:       # la reserva anota que se hizo con cada post/cuenta (nunca se vuelve a elegir el mismo)
            import x_pool as pool
            db = pool.connect()
            try:
                outcome = r["resultado"]
                if r.get("url") and r.get("kind") in ("like", "repost"):
                    status = _pool_post_status(outcome)
                    if status:
                        # no_intentado, saltados de política y fallos previos
                        # al tap NO deben consumir el candidato de la reserva.
                        pool.mark(db, r["url"], status)
                if r.get("handle") and (r["kind"] in ("follow", "like_latest") or (r["kind"] == "like" and not r.get("url"))):       # follow o like_latest (que se registra como like sin URL)
                    status = ("done" if outcome in ("confirmado", "saltado_ya_like", "saltado_ya_seguido", "pendiente_aprobacion")
                              else "uncertain" if outcome == "pendiente_verificacion"
                              else "rejected" if outcome.startswith("saltado_perfil") else None)
                    if status:       # una cuenta tocada o rechazada no vuelve a ofrecerse; un fallo puntual si
                        pool.mark_account(db, r["handle"], status)
            finally:
                db.close()
        except Exception:
            pass

    with x.session():       # UNA conexion para todo el plan (antes: una por accion)
        results = run_plan(plan, prevalidated=True, on_result=_on_result)

    print("\n=== RESUMEN ===")
    for r in results:
        print(f"{r['resultado']:20s} {r['kind']:8s} {r.get('handle') or r.get('url','')}")

    leftover = [r for r in results if id(r) not in persisted]
    if leftover:
        _append_registro(leftover)
    _append_repost_ttl(results)
    # PARADA TOTAL debe incluir la recogida de métricas: esta función
    # navega por el perfil y antes volvía a abrir la red tras un CAPTCHA,
    # bloqueo o cuenta incorrecta detectados en run_plan.
    if any(str(item.get("resultado", "")).startswith("parada:")
           or item.get("resultado") == "pendiente_verificacion" for item in results):
        print("PARADA TOTAL: ACK incierto/seguridad; revisión manual, no se consultan métricas.")
        sys.exit(5)
    metrics = _fetch_metrics()
    _append_metricas(results, metrics)
    _update_estado(results, metrics)
    print(f"\nregistro_interacciones.csv, metricas.csv y ESTADO.md actualizados automaticamente.")
    print(f"Metricas finales: seguidores={metrics['followers']} siguiendo={metrics['following']} posts={metrics['posts']}")

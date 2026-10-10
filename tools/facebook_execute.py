"""
Fase 3 del pipeline de Facebook (22/09, descubrimiento externo anadido
24/09) - mismo patron que las otras ocho redes. Sin techo de calentamiento
automatico como Instagram/TikTok - no se vio ninguna senal de deteccion de
bots agresiva, solo re-renderizados frecuentes del DOM (un problema de
fiabilidad tecnica, no de riesgo de cuenta). Pausas moderadas igualmente por
prudencia.

Kinds soportados:
- "like"/"comment": sobre un post PROPIO por INDICE (ver facebook_interact.py:
  localizar por fragmento de texto no es fiable en el DOM de Facebook).
- "like_external"/"comment_external" (24/09): sobre un post AJENO encontrado
  por `facebook_scan.py` (hashtags), identificado por su `permalink` exacto
  en vez de un indice.

Formato de plan.json:
    [
      {"kind": "like", "index": 0, "motivo": "..."},
      {"kind": "comment", "index": 1, "text": "el comentario", "motivo": "..."},
      {"kind": "like_external", "permalink": "https://www.facebook.com/photo/?fbid=...", "autor": "Nombre Pagina", "motivo": "..."},
      {"kind": "comment_external", "permalink": "...", "autor": "...", "text": "el comentario", "motivo": "..."}
    ]

Uso:
    python tools/facebook_execute.py plan.json
"""
import csv
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import facebook_interact as fb
import check_duplicate_phrase as dup
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_FACEBOOK")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
METRICAS_CSV = os.path.join(ROOT, "metricas.csv")
ESTADO_MD = os.path.join(ROOT, "ESTADO.md")


def _pause(a=45, b=90):
    sc.pause(a, b)


def _drop_stacked_actions(plan):
    """Anadido 23/09 (mismo criterio que en las otras redes, hueco real
    encontrado el mismo dia: Facebook soporta like+comment sobre el mismo
    post pero nunca tuvo esta proteccion) - quita un like sobre un indice
    de post propio que ya tiene un comment en el mismo plan. Ampliado 24/09
    para los kinds externos, con "permalink" como key en vez de "index"."""
    plan = sc.drop_stacked_actions(plan, cheap_kinds=("like",), rich_kinds=("comment",), key="index")
    plan = sc.drop_stacked_actions(
        plan, cheap_kinds=("like_external",), rich_kinds=("comment_external",), key="permalink"
    )
    return plan


_ALLOWED_KINDS = {"like", "comment", "like_external", "comment_external"}


def _preflight_plan(plan):
    """Valida destinos, textos y duplicados antes de cualquier clic."""
    if not isinstance(plan, list):
        raise ValueError("plan.json debe contener una lista")
    validated = []
    for index, raw in enumerate(plan, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"elemento {index}: debe ser un objeto")
        item = dict(raw)
        kind = item.get("kind")
        if kind not in _ALLOWED_KINDS:
            raise ValueError(f"elemento {index}: kind inválido {kind!r}")
        if kind in {"like", "comment"}:
            post_index = item.get("index", 0)
            if isinstance(post_index, bool) or not isinstance(post_index, int) or post_index < 0:
                raise ValueError(f"elemento {index}: índice propio inválido")
            item["index"] = post_index
            item["_target"] = ("own", post_index)
        else:
            permalink = item.get("permalink")
            item["permalink"] = fb._validated_facebook_permalink(permalink)
            item["_target"] = ("external", item["permalink"])
        if kind in {"comment", "comment_external"}:
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"elemento {index}: {kind} exige texto")
            text = text.strip()
            fb._check_length(text)
            sc.guard_plan_item(item, index)
            fb._check_spanish_orthography(text)
            hits = [] if item.get("bank") else dup.check(text)      # comentarios del banco por intencion: ventana propia de reutilizacion
            if hits:
                raise ValueError(f"elemento {index}: texto duplicado - {hits[0]}")
            item["text"] = text
        validated.append(item)

    validated = _drop_stacked_actions(validated)
    targets = set()
    for index, item in enumerate(validated, start=1):
        key = item["_target"]
        if key in targets:
            raise ValueError(f"elemento {index}: varias acciones para el mismo post")
        targets.add(key)
    for item in validated:
        item.pop("_target", None)
    return validated


def _validate_own_indices(plan, available_counts):
    """Bloquea el lote si algún índice no existe en el feed cargado."""
    for position, item in enumerate(plan, start=1):
        kind = item["kind"]
        if kind in {"like", "comment"} and item["index"] >= available_counts[kind]:
            raise ValueError(
                f"elemento {position}: indice {item['index']} fuera del feed "
                f"(solo {available_counts[kind]} destinos de {kind} cargados)"
            )


def run_plan(plan, *, prevalidated=False):
    import reply_writer as _rw
    plan = _rw.require_gpt(plan, "facebook")      # 08/10: nunca se publica texto que no venga de ChatGPT
    results = []
    if not prevalidated:
        try:
            plan = _preflight_plan(plan)
            sc.report_plan_style(plan)
        except Exception as exc:
            print(f"FALLO DE PREFLIGHT: {type(exc).__name__}: {exc}")
            return [{"kind": "plan", "resultado": f"fallo_plan:{exc}"}]
    for i, item in enumerate(plan):
<<<<<<< HEAD
=======
        # Una ronda puede durar horas: revalidar la cuarentena antes de CADA
        # acción, incluso si el lanzador aprobó el lote al comienzo.
        import circuit_breaker as _cb
        _write_ok, _hold_reason = _cb.write_preflight("facebook")
        if not _write_ok:
            print(f"[facebook] cortacircuitos ABIERTO: {_hold_reason}; detener el lote")
            break
>>>>>>> origin/research/public-reuse-parent
        kind = item["kind"]
        import conversation_turn_policy as ctp
        permitted, reason = ctp.check_execution("facebook", item)
        if not permitted:
            results.append({**item, "resultado": f"saltado_cierre_conversacion:{reason}"})
            continue
        if kind in ("like", "like_external"):
            import like_context_policy as lcp
            allowed, why = lcp.check_execution("facebook", item)
            if not allowed:
                results.append({**item, "resultado": f"saltado_like_contexto:{why}"})
                continue
        label = (
            f"post propio indice {item.get('index', 0)}"
            if kind in ("like", "comment") else item.get("permalink", "")
        )
        print(f"=== {i+1}/{len(plan)}: {kind} -> {label} ===")

        try:
            if kind == "like":
                outcome = fb.like(item["index"])
                if outcome != "created":
                    raise RuntimeError(f"like devolvió estado inesperado: {outcome!r}")
            elif kind == "comment":
                outcome = fb.comment(item["text"], item["index"])
                if outcome == "unverified":
                    results.append({**item, "resultado": "pendiente_verificacion"})
                    continue
                if outcome != "created":
                    raise RuntimeError(f"comment devolvió estado inesperado: {outcome!r}")
            elif kind == "like_external":
                outcome = fb.like_external(item["permalink"])
                if outcome != "created":
                    raise RuntimeError(f"like_external devolvió estado inesperado: {outcome!r}")
            elif kind == "comment_external":
                outcome = fb.comment_external(item["text"], item["permalink"])
                if outcome == "unverified":
                    results.append({**item, "resultado": "pendiente_verificacion"})
                    continue
                if outcome != "created":
                    raise RuntimeError(
                        f"comment_external devolvió estado inesperado: {outcome!r}"
                    )
            results.append({**item, "resultado": "confirmado"})
        except fb.BotWarningDetected as exc:
            print(f"PARADA TOTAL: {exc}")
            results.append({**item, "resultado": f"parada:{exc}"})
            for pending in plan[i + 1:]:
                results.append({**pending, "resultado": "no_intentado"})
            break
        except fb.AlreadyCommented as exc:
            print(f"SALTADO: {exc}")
            results.append({**item, "resultado": "saltado_ya_comentado"})
        except Exception as exc:
            print(f"FALLO: {type(exc).__name__}: {exc}")
            results.append({**item, "resultado": f"fallo:{exc}"})

        if i < len(plan) - 1:
            _pause()

    return results


def _append_registro(results):
    fecha = datetime.date.today().isoformat()
    with open(REGISTRO_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in results:
            if r["resultado"] not in ("confirmado", "pendiente_verificacion"):
                continue
            if r["kind"] in ("like_external", "comment_external"):
                cuenta = r.get("autor", "?")
                resumen = r.get("permalink", "")
            else:
                cuenta = fb.MY_PAGE_NAME
                resumen = f"indice={r.get('index', 0)}"
            stored = (
                "pendiente_verificacion"
                if r["resultado"] == "pendiente_verificacion"
                else ("publicado" if "comment" in r["kind"] else "confirmado")
            )
            w.writerow([
                fecha, cuenta, r["kind"], resumen,
                r.get("text", ""), stored, r.get("motivo", ""),
            ])


def _append_metricas(results):
    fecha = datetime.date.today().isoformat()
    counts = {}
    for r in results:
        if r["resultado"] == "confirmado":
            counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    resumen = ", ".join(f"{v} {k}" for k, v in counts.items()) or "sin acciones confirmadas"
    with open(METRICAS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([fecha, "?", f"Sesion via pipeline scan->plan->execute: {resumen}."])


def _update_estado(results):
    if not os.path.exists(ESTADO_MD):
        return
    import re
    with open(ESTADO_MD, encoding="utf-8") as f:
        content = f.read()
    fecha = datetime.date.today().isoformat()
    counts = {}
    for r in results:
        if r["resultado"] == "confirmado":
            counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    resumen = ", ".join(f"{v} {k}" for k, v in counts.items()) or "sin acciones confirmadas"
    content = re.sub(
        r"## Última sesión.*?(?=\n## |\Z)",
        f"## Última sesión\n\n{fecha}. {resumen}. Detalle: `registro_interacciones.csv`.\n\n",
        content, count=1, flags=re.S,
    )
    with open(ESTADO_MD, "w", encoding="utf-8") as f:
        f.write(content)


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

    fb.ensure_browser()
    if any(item["kind"] in {"like", "comment"} for item in plan):
        p, pg = fb._connect()
        try:
            fb._dump_own_feed(pg)
            available_counts = {
                "like": pg.locator('div[aria-label="Me gusta"][role="button"]').count(),
                "comment": pg.locator(
                    'div[aria-label="Dejar un comentario"][role="button"]'
                ).count(),
            }
        finally:
            p.stop()
        try:
            _validate_own_indices(plan, available_counts)
        except ValueError as exc:
            print(f"FALLO DE PREFLIGHT DEL FEED: {exc}")
            raise SystemExit(2)
    results = run_plan(plan, prevalidated=True)

    print("\n=== RESUMEN ===")
    for r in results:
        label = f"indice={r.get('index', 0)}" if r["kind"] in ("like", "comment") else r.get("permalink", "")
        print(f"{r['resultado']:20s} {r['kind']:16s} {label}")

    _append_registro(results)
    if any(str(item.get("resultado", "")).startswith("parada:") for item in results):
        print(
            "PARADA TOTAL: resultados guardados; no se actualizan métricas/estado "
            "como si la sesión hubiera terminado con normalidad."
        )
        sys.exit(5)
    _append_metricas(results)
    _update_estado(results)
    print("\nregistro_interacciones.csv, metricas.csv y ESTADO.md actualizados automaticamente.")

"""
Fase 3 del pipeline diario de Instagram (22/09) - mismo patron que
`tools/x_execute.py`/`tools/threads_execute.py`, con una pieza extra
especifica de esta red: el TECHO DE CALENTAMIENTO PROGRESIVO de
`REGLAS.md` se aplica aqui de forma automatica, no a mano cada vez - es
la red mas sensible a deteccion de bots de las cinco, asi que este es
el sitio exacto donde automatizar la comprobacion ahorra tokens Y reduce
el riesgo de que un calculo mental se equivoque un dia cualquiera.

Kinds soportados: "follow", "like", "comment". Cada uno pasa por:
1. Techo de fase (ver TECHO_POR_FASE abajo, copiado de REGLAS.md) - un
   item que se pasa del techo de HOY para su tipo se salta con
   "saltado_fase_calentamiento", nunca se ejecuta.
2. Como mucho 1 sesion real de accion por dia durante el calentamiento
   (las 4 fases de REGLAS.md dicen "1" en la columna Sesiones/dia) - si
   `metricas.csv` ya tiene una fila de HOY, el script para antes de tocar
   el navegador.
3. `check_duplicate_phrase` para cualquier item con "text" (comment).

Formato de plan.json:
    [
      {"handle": "foo", "kind": "follow", "motivo": "..."},
      {"handle": "foo", "kind": "like", "permalink": "https://www.instagram.com/p/ID/",
       "motivo": "..."},
      {"handle": "foo", "kind": "comment", "permalink": "https://www.instagram.com/p/ID/",
       "text": "el comentario", "motivo": "..."}
    ]

Uso:
    python tools/instagram_execute.py plan.json
"""
import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import instagram_interact as ig
import check_duplicate_phrase as dup
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_INSTAGRAM")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
METRICAS_CSV = os.path.join(ROOT, "metricas.csv")
ESTADO_MD = os.path.join(ROOT, "ESTADO.md")

# Copiado literal de REGLAS.md ("Fases", tabla de calentamiento progresivo)
# el 22/09 - si REGLAS.md cambia esta tabla, actualizar aqui tambien (se
# avisa en el propio archivo: "cuando el calentamiento progresivo pase de
# fase, anotar en metricas.csv y REGLAS.md").
TECHO_POR_FASE = [
    # (dias_min, dias_max, likes, follows, comments)
    # 04/10/2026 (David): arrancar con 10 follows al dia desde ya; likes/comentarios siguen la tabla de calentamiento.
    (1, 3, 0, 10, 0),
    (4, 7, 10, 10, 0),
    (8, 10, 15, 10, 2),
    (11, 10**9, 20, 10, 3),
]


def _fase_de(dias_activo):
    """Claves iguales a los valores de 'kind' del plan.json (follow/like/
    comment, todo en singular) - BUG REAL encontrado en dry-run el 22/09
    antes de usar esto en vivo: la primera version devolvia 'likes'/
    'follows' (plural), y `_apply_warmup_gate` buscaba por 'like'/'follow'
    (singular, igual que kind) - el mismatch hacia que TODO se saltara
    siempre, techo o no techo. Verificado con un plan de prueba antes de
    confiar en esto con acciones reales."""
    for dmin, dmax, likes, follows, comments in TECHO_POR_FASE:
        if dmin <= dias_activo <= dmax:
            return {"like": likes, "follow": follows, "comment": comments}
    return {"like": 0, "follow": 0, "comment": 0}


def _ultima_fila_metricas():
    if not os.path.exists(METRICAS_CSV):
        return None
    with open(METRICAS_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows[-1] if rows else None


def _pause(a=45, b=90):
    """45-90s entre acciones (REGLAS.md) - mas lento que X/Threads a
    proposito, Instagram es la red mas sensible de las cinco."""
    sc.pause(a, b)


def _apply_warmup_gate(plan, dias_activo):
    """Filtra el plan contra el techo de la fase actual ANTES de tocar el
    navegador - cuenta cuantos items de cada kind hay y marca como
    'saltado_fase_calentamiento' los que sobran por encima del techo
    (los primeros N de cada kind se quedan, el resto se salta - el orden
    del plan.json ya refleja la prioridad que decidio Claude)."""
    techo = _fase_de(dias_activo)
    counts = {"like": 0, "follow": 0, "comment": 0}
    kept, skipped = [], []
    for item in plan:
        kind = item["kind"]
        limite = techo.get(kind, 0)
        if counts.get(kind, 0) < limite:
            counts[kind] = counts.get(kind, 0) + 1
            kept.append(item)
        else:
            skipped.append(item)
    return kept, skipped, techo


def _drop_stacked_actions(plan):
    """Anadido 23/09 (mismo criterio de x_execute.py: "si ya tienen una
    interaccion no necesitan mas"). Logica compartida en
    scan_common.drop_stacked_actions (23/09)."""
    return sc.drop_stacked_actions(plan, cheap_kinds=("like",), rich_kinds=("comment",), key="permalink")


def _preflight_plan(plan):
    if not isinstance(plan, list):
        raise ValueError("plan.json debe contener una lista")
    validated = []
    for index, raw in enumerate(plan, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"elemento {index}: debe ser un objeto")
        item = dict(raw)
        kind = item.get("kind")
        if kind not in {"follow", "like", "comment"}:
            raise ValueError(f"elemento {index}: kind inválido {kind!r}")
        handle = item.get("handle")
        if not isinstance(handle, str) or not handle.strip().lstrip("@"):
            raise ValueError(f"elemento {index}: handle obligatorio")
        item["handle"] = handle.strip().lstrip("@")
        if kind in {"like", "comment"}:
            item["permalink"] = ig._validated_post_permalink(item.get("permalink"))
        if kind == "comment":
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"elemento {index}: comment exige texto")
            item["text"] = text.strip()
            ig._check_length(item["text"])
            sc.guard_plan_item(item, index)
            ig._check_spanish_orthography(item["text"])
            hits = dup.check(item["text"])
            if hits:
                raise ValueError(f"elemento {index}: texto duplicado - {hits[0]}")
        validated.append(item)
    validated = _drop_stacked_actions(validated)
    seen_follow = set()
    seen_posts = set()
    for index, item in enumerate(validated, start=1):
        if item["kind"] == "follow":
            key = item["handle"].casefold()
            if key in seen_follow:
                raise ValueError(f"elemento {index}: follow duplicado para @{item['handle']}")
            seen_follow.add(key)
        else:
            key = item["permalink"]
            if key in seen_posts:
                raise ValueError(f"elemento {index}: varias acciones para el mismo post")
            seen_posts.add(key)
    return validated


def run_plan(plan, *, prevalidated=False):
    results = []
    if not prevalidated:
        try:
            plan = _preflight_plan(plan)
        except Exception as exc:
            print(f"FALLO DE PREFLIGHT: {type(exc).__name__}: {exc}")
            return [{"kind": "plan", "handle": "", "resultado": f"fallo_plan:{exc}"}]
    ig._refuse_if_paused()
    for i, item in enumerate(plan):
        kind = item["kind"]
        handle = item["handle"].lstrip("@")
        print(f"=== {i+1}/{len(plan)}: {kind} -> @{handle} ===")
        try:
            if kind == "follow":
                outcome = ig.follow(handle)
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_seguido"})
                    continue
                if outcome == "pending":
                    results.append({**item, "resultado": "pendiente_aprobacion"})
                    continue
                if outcome != "followed":
                    raise RuntimeError(f"follow devolvió estado inesperado: {outcome!r}")
            elif kind == "like":
                outcome = ig.like(item["permalink"])
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_like"})
                    continue
                if outcome != "created":
                    raise RuntimeError(f"like devolvió estado inesperado: {outcome!r}")
            elif kind == "comment":
                outcome = ig.comment(item["permalink"], item["text"])
                if outcome != "created":
                    raise RuntimeError(f"comment devolvió estado inesperado: {outcome!r}")
            else:
                raise ValueError(f"kind desconocido: {kind}")
            results.append({**item, "resultado": "confirmado"})
        except ig.BotWarningDetected as e:
            print(f"PARADA TOTAL: {e}")
            results.append({**item, "resultado": f"parada:{e}"})
            for pending in plan[i + 1:]:
                results.append({**pending, "resultado": "no_intentado"})
            break
        except ig.AlreadyCommented as e:
            print(f"SALTADO: {e}")
            results.append({**item, "resultado": "saltado_ya_comentado"})
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
            if outcome not in ("confirmado", "pendiente_aprobacion"):
                continue
            tipo = "comentario" if r["kind"] == "comment" else r["kind"]
            stored = "pendiente_aprobacion" if outcome == "pendiente_aprobacion" else "confirmado"
            w.writerow([
                fecha, "@" + r["handle"].lstrip("@"), tipo,
                r.get("resumen", ""), r.get("text", ""), stored, r.get("motivo", ""),
            ])


def _fetch_metrics():
    p, pg = ig._connect()
    try:
        pg.goto(f"https://www.instagram.com/{ig.MY_HANDLE}/", wait_until="domcontentloaded", timeout=20000)
        pg.wait_for_timeout(2500)
        body = pg.inner_text("body")[:1500]
        posts = re.search(r"([\d.,]+)\s+publicaciones", body, re.I)
        followers = re.search(r"([\d.,]+)\s+seguidores", body, re.I)
        following = re.search(r"([\d.,]+)\s+seguidos", body, re.I)
        return {
            "posts": posts.group(1) if posts else "?",
            "followers": followers.group(1) if followers else "?",
            "following": following.group(1) if following else "?",
        }
    finally:
        p.stop()


def _append_metricas(results, metrics, dias_activo, resumen_calentamiento):
    fecha = datetime.date.today().isoformat()
    counts = {}
    for r in results:
        if r["resultado"] == "confirmado":
            counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    resumen = ", ".join(f"{v} {k}" for k, v in counts.items()) or "sin acciones confirmadas"
    with open(METRICAS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            fecha, metrics["followers"], metrics["following"], metrics["posts"], dias_activo,
            f"Sesion via pipeline scan->plan->execute: {resumen}. {resumen_calentamiento}",
        ])


def _update_estado(results, metrics, dias_activo):
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
    content = re.sub(
        r"## Última sesión.*?(?=\n## |\Z)",
        f"## Última sesión\n\n{fecha}. {resumen}. dias_activo={dias_activo}. "
        f"Detalle: `registro_interacciones.csv`.\n\n",
        content, count=1, flags=re.S,
    )
    content = re.sub(
        r"## Métricas actuales.*?(?=\n## |\Z)",
        f"## Métricas actuales (de `metricas.csv`, última fila)\n\n"
        f"Seguidores: {metrics['followers']}. Siguiendo: {metrics['following']}. "
        f"Posts: {metrics['posts']}. dias_activo: {dias_activo}.\n\n",
        content, count=1, flags=re.S,
    )
    with open(ESTADO_MD, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    import atexit
    import action_ledger as al
    _browser_turn = al.browser_session()   # un solo Playwright a la vez en el Edge compartido (04/10)
    _browser_turn.__enter__()
    atexit.register(lambda: _browser_turn.__exit__(None, None, None))
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        plan = json.load(f)

    hoy = datetime.date.today().isoformat()
    ultima = _ultima_fila_metricas()
    if ultima and ultima.get("fecha") == hoy:
        print(
            f"PARADA: ya hay una fila de metricas.csv con fecha {hoy} - el calentamiento "
            "progresivo de REGLAS.md limita a 1 sesion real de accion por dia en TODAS "
            "las fases. No se ejecuta el plan. Si esto es un error (p.ej. la fila de hoy "
            "fue solo de diagnostico), revisar metricas.csv a mano antes de forzar nada."
        )
        sys.exit(4)
    dias_activo = int(ultima["dias_activo"]) + 1 if ultima else 1

    try:
        plan = _preflight_plan(plan)
    except Exception as exc:
        print(f"FALLO DE PREFLIGHT: {type(exc).__name__}: {exc}")
        raise SystemExit(2)

    kept, skipped, techo = _apply_warmup_gate(plan, dias_activo)
    resumen_calentamiento = (
        f"Fase de calentamiento: dias_activo={dias_activo}, techo hoy "
        f"likes={techo['like']} follows={techo['follow']} comments={techo['comment']}."
    )
    print(resumen_calentamiento)
    if skipped:
        print(f"\n{len(skipped)} item(s) del plan por encima del techo de hoy - saltados sin tocar el navegador:")
        for s in skipped:
            print(f"  saltado_fase_calentamiento: {s['kind']} -> @{s['handle'].lstrip('@')}")

    ig.ensure_browser()
    results = run_plan(kept, prevalidated=True)
    results += [{**s, "resultado": "saltado_fase_calentamiento"} for s in skipped]

    print("\n=== RESUMEN ===")
    for r in results:
        print(f"{r['resultado']:28s} {r['kind']:8s} @{r['handle'].lstrip('@')}")

    _append_registro(results)
    # PARADA TOTAL debe incluir la recogida de métricas: esta función
    # navega por el perfil y antes volvía a abrir la red tras un CAPTCHA,
    # bloqueo o cuenta incorrecta detectados en run_plan.
    if any(str(item.get("resultado", "")).startswith("parada:") for item in results):
        print("PARADA TOTAL: resultados guardados; no se abre de nuevo el navegador para métricas.")
        sys.exit(5)
    metrics = _fetch_metrics()
    _append_metricas(results, metrics, dias_activo, resumen_calentamiento)
    _update_estado(results, metrics, dias_activo)
    print(f"\nregistro_interacciones.csv, metricas.csv y ESTADO.md actualizados automaticamente.")
    print(f"Metricas finales: seguidores={metrics['followers']} siguiendo={metrics['following']} posts={metrics['posts']} dias_activo={dias_activo}")

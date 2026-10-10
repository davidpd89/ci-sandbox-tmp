"""
Fase 3 del pipeline diario de TikTok (22/09) - mismo patron que
instagram_execute.py (techo de calentamiento automatico por dias_activo),
pero MAS LENTO todavia: TikTok goteo un captcha real el mismo dia de
construir esto (ver tiktok_interact.py) solo con una navegacion de
lectura, sin ninguna accion de escritura - la senal mas fuerte de
sensibilidad a bots de las seis redes de este proyecto. David, avisado de
esto explicitamente, decidio seguir adelante igual que en las otras
cinco pero con un calentamiento "mucho mas conservador" - esta tabla es
esa decision.

Kinds soportados: "follow", "like", "comment". Cada uno pasa por el techo
de fase automatico (TECHO_POR_FASE) igual que Instagram - un item por
encima del techo de hoy se salta con "saltado_fase_calentamiento", nunca
se ejecuta. Maximo 1 sesion real cada 2 dias en Fase 1 (no cada dia como
Instagram) - ver `_puede_ejecutar_hoy`.

Formato de plan.json:
    [
      {"handle": "foo", "kind": "follow", "motivo": "..."},
      {"handle": "foo", "kind": "like", "text_fragment": "fragmento de la descripcion",
       "motivo": "..."},
      {"handle": "foo", "kind": "comment", "text_fragment": "fragmento de la descripcion",
       "text": "el comentario", "motivo": "..."}
    ]

Uso:
    python tools/tiktok_execute.py plan.json
"""
import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import tiktok_interact as tt
import check_duplicate_phrase as dup
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_TIKTOK")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
METRICAS_CSV = os.path.join(ROOT, "metricas.csv")
ESTADO_MD = os.path.join(ROOT, "ESTADO.md")

# Mas lento que Instagram a proposito (ver docstring del modulo) - menos
# follows, cero comentarios hasta Fase 3, y solo 1 sesion cada 2 dias en
# Fase 1 (aplicado en _puede_ejecutar_hoy, no en esta tabla).
TECHO_POR_FASE = [
    # (dias_min, dias_max, likes, follows, comments)
    (1, 5, 0, 2, 0),
    (6, 10, 5, 0, 0),
    (11, 15, 8, 3, 1),
    (16, 10**9, 12, 5, 2),
]


def _fase_de(dias_activo):
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


def _puede_ejecutar_hoy(ultima, dias_activo):
    """En Fase 1 (dias_activo 1-5), maximo 1 sesion real cada 2 dias - mas
    lento que Instagram (que permite 1/dia incluso en su Fase 1). A partir
    de Fase 2 vuelve al mismo criterio que Instagram (1 sesion/dia)."""
    if not ultima:
        return True, None
    hoy = datetime.date.today()
    fecha_ultima = datetime.date.fromisoformat(ultima["fecha"])
    dias_desde_ultima = (hoy - fecha_ultima).days
    if dias_activo <= 5 and dias_desde_ultima < 2:
        return False, (
            f"Fase 1 de TikTok permite como mucho 1 sesion real cada 2 dias - "
            f"la ultima fue hace {dias_desde_ultima} dia(s) ({ultima['fecha']})."
        )
    if dias_desde_ultima < 1:
        return False, f"Ya hay una fila de metricas.csv con fecha de hoy ({ultima['fecha']})."
    return True, None


def _pause(a=60, b=120):
    """60-120s entre acciones - mas lento que Instagram (45-90s) a
    proposito, misma logica que el resto de esta tabla."""
    sc.pause(a, b)


def _drop_stacked_actions(plan):
    """Anadido 23/09 (mismo criterio que en las otras redes, hueco real
    encontrado el mismo dia: TikTok soporta like+comment sobre la misma
    cuenta pero nunca tuvo esta proteccion) - quita un like sobre un handle
    que ya tiene un comment en el mismo plan (mismo criterio de
    threads_execute.py: clave por handle, no por video concreto)."""
    return sc.drop_stacked_actions(plan, cheap_kinds=("like",), rich_kinds=("comment",),
                                    key="handle", normalize=lambda h: h.lstrip("@"))


def _apply_warmup_gate(plan, dias_activo):
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


def run_plan(plan):
    results = []
    for i, item in enumerate(plan):
        kind = item["kind"]
        handle = item["handle"].lstrip("@")
        print(f"=== {i+1}/{len(plan)}: {kind} -> @{handle} ===")

        if item.get("text"):
            hits = dup.check(item["text"])
            if hits:
                print(f"SALTADO: solape de texto detectado - {hits[0]}")
                results.append({**item, "resultado": "saltado_duplicado"})
                continue

        try:
            if kind == "follow":
                outcome = tt.follow(handle)
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_seguido"})
                    continue
                if outcome != "followed":
                    raise RuntimeError(f"follow devolvió estado inesperado: {outcome!r}")
            elif kind == "like":
                outcome = tt.like(handle, item.get("text_fragment", ""))
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_like"})
                    continue
                if outcome != "created":
                    raise RuntimeError(f"like devolvió estado inesperado: {outcome!r}")
            elif kind == "comment":
                outcome = tt.comment(handle, item.get("text_fragment", ""), item["text"])
                if outcome != "unverified":
                    raise RuntimeError(f"comment devolvió estado inesperado: {outcome!r}")
                results.append({**item, "resultado": "pendiente_verificacion"})
                if i < len(plan) - 1:
                    _pause()
                continue
            else:
                raise ValueError(f"kind desconocido: {kind}")
            results.append({**item, "resultado": "confirmado"})
        except tt.BotWarningDetected as e:
            print(f"PARADA TOTAL: {e}")
            results.append({**item, "resultado": f"parada:{e}"})
            for pending in plan[i + 1:]:
                results.append({**pending, "resultado": "no_intentado"})
            break
        except tt.AlreadyCommented as e:
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
            if r["resultado"] not in ("confirmado", "pendiente_verificacion"):
                continue
            # Conservar la acción incierta para no perderla al cerrar consola:
            # otra sesión no debe repetir automáticamente un comentario enviado
            # solo porque todavía no se pudo comprobar su publicación.
            resultado = (
                r["resultado"] if r["resultado"] == "pendiente_verificacion"
                else ("publicado" if r["kind"] == "comment" else "confirmado")
            )
            w.writerow([
                fecha, "@" + r["handle"].lstrip("@"), r["kind"],
                r.get("text_fragment", ""), r.get("text", ""),
                resultado, r.get("motivo", ""),
            ])


def _fetch_metrics():
    p, pg = tt._connect()
    try:
        tt._dump_profile(pg, tt.MY_HANDLE)
        body = pg.inner_text("body")[:1500]
        followers = re.search(r"([\d.,mMkK]+)\s*\n?\s*Seguidores", body)
        following = re.search(r"([\d.,mMkK]+)\s*\n?\s*Siguiendo", body)
        return {
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
            fecha, metrics["followers"], dias_activo,
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
        f"Seguidores: {metrics['followers']}. dias_activo: {dias_activo}.\n\n",
        content, count=1, flags=re.S,
    )
    with open(ESTADO_MD, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    tt._refuse_if_paused()
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        plan = json.load(f)

    ultima = _ultima_fila_metricas()
    dias_activo = int(ultima["dias_activo"]) + 1 if ultima else 1

    puede, motivo = _puede_ejecutar_hoy(ultima, dias_activo)
    if not puede:
        print(f"PARADA: {motivo} No se ejecuta el plan.")
        sys.exit(4)

    plan = _drop_stacked_actions(plan)
    import reply_writer as _rw
    plan = _rw.require_gpt(plan, "tiktok")      # 08/10: nunca se publica texto que no venga de ChatGPT
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

    tt.ensure_browser()
    results = run_plan(kept)
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
    print("\nregistro_interacciones.csv, metricas.csv y ESTADO.md actualizados automaticamente.")
    print(f"Metricas finales: seguidores={metrics['followers']} dias_activo={dias_activo}")

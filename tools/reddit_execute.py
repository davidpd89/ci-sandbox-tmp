"""
Fase 3 del pipeline diario de Reddit (22/09, ampliado 25/09) - mismo patron
que las otras redes. Hasta el 25/09 la unica accion real era "comment" (no
habia follows en Reddit ni votos - "no perseguir karma"). David pidio ese
dia anadir voto como interaccion minima real ("Reddit lo mejoramos para
votar y demas tambien, un minimo de interacciones necesitamos") - sigue sin
haber follows (Reddit no tiene ese concepto igual que las otras redes) pero
"vote" ya es una accion soportada, con el mismo criterio de calidad de
Claude en la fase de decision (votar solo lo que de verdad aporta, no por
cupo). Sin techo de calentamiento (Reddit no es tan sensible a patrones de
comportamiento como Instagram) ni pausas cortas (2-3 sesiones por semana,
no una sesion diaria de rango, ver REGLAS.md).

Formato de plan.json:
    [
      {"subreddit": "libros", "kind": "comment", "url": "https://www.reddit.com/r/libros/comments/.../",
       "text": "el comentario", "motivo": "..."},
      {"subreddit": "books", "kind": "vote", "url": "https://www.reddit.com/r/books/comments/.../",
       "direction": "up", "motivo": "..."}
    ]

Uso:
    python tools/reddit_execute.py plan.json
"""
import csv
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding="utf-8")
import reddit_interact as r
import check_duplicate_phrase as dup
import scan_common as sc
import exec_common as ec

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_REDDIT")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
METRICAS_CSV = os.path.join(ROOT, "metricas.csv")
ESTADO_MD = os.path.join(ROOT, "ESTADO.md")


def _pause(a=45, b=90):
    sc.pause(a, b)


def _validated_plan_item(item):
    """La URL manda; un subreddit declarado distinto bloquea la acción."""
    if not isinstance(item, dict):
        raise ValueError("cada elemento del plan debe ser un objeto")
    url = item.get("url")
    actual_subreddit, _ = r._thread_identity(url)
    declared = item.get("subreddit")
    if declared not in (None, ""):
        declared = r._normalize_subreddit_name(declared).casefold()
        if declared != actual_subreddit:
            raise ValueError(
                f"subreddit del plan r/{declared} no coincide con la URL r/{actual_subreddit}"
            )
    return {**item, "subreddit": actual_subreddit}


_RECENT_MICRO_WINDOW = 40      # 07/10: banco amplio de frases amables (reddit_comments.py)


def _recent_micro_repeat(text, registro=None, window=_RECENT_MICRO_WINDOW):
    """True si `text` (ignorando mayusculas/espacios/puntuacion final) coincide con
    alguno de los ultimos `window` comentarios de Reddit del registro."""
    import csv
    registro = registro or os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_REDDIT",
                                        "registro_interacciones.csv")
    norm = lambda t: " ".join((t or "").casefold().split()).strip(" .,!;")
    target = norm(text)
    try:
        with open(registro, encoding="utf-8", newline="") as stream:
            used = [norm(r.get("texto_usado")) for r in csv.DictReader(stream)
                    if r.get("tipo") in ("comentario", "comment")  # _append_registro escribe "comentario"
                    and r.get("resultado") in ("confirmado", "publicado")
                    and (r.get("texto_usado") or "").strip()]
    except OSError:
        return False
    return target in used[-window:]


def _preflight_plan(plan, *, skipped=None):
    """Valida el plan completo antes de la primera escritura real."""
    if not isinstance(plan, list):
        raise ValueError("el plan debe ser una lista JSON")

    normalized = []
    omissions = ec.PreflightSkipBuffer("reddit", skipped)
    comment_targets = set()
    vote_targets = {}
    comment_texts = {}
    for index, raw_item in enumerate(plan, start=1):
        item = _validated_plan_item(raw_item)
        kind = item.get("kind")
        if kind not in {"comment", "vote"}:
            raise ValueError(f"elemento {index}: kind desconocido {kind!r}")

        target = r._thread_identity(item["url"])
        if kind == "comment":
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"elemento {index}: comment requiere texto no vacío")

            # Todo lo que puede fallar localmente debe resolverse antes de la
            # primera escritura remota del plan.
            r._check_length(text)
            try:
                r._check_micro_comment(text)
            except ValueError as exc:
                raise ValueError(f"elemento {index}: {exc}") from None
            sc.guard_plan_item(item, index)
            r._check_spanish_orthography(text)
            # Una microrrespuesta ("Escribir.", "Sí") coincide por subcadena con casi
            # cualquier texto largo de otras redes, asi que dup.check daria falsos
            # positivos (o bloquearia repetirla siempre). Aqui solo se evita repetir
            # EXACTAMENTE la misma en los ultimos comentarios de Reddit.
            if _recent_micro_repeat(text):
                omissions.add(index, kind, "microtexto_publicado")
                continue
            text = " ".join(text.split())
            text_key = text.casefold()
            if text_key in comment_texts:
                omissions.add(index, kind, "texto_repetido_lote")
                continue
            if target in comment_targets:
                omissions.add(index, kind, "objetivo_repetido_lote")
                continue
            comment_texts[text_key] = index
            comment_targets.add(target)
            item["text"] = text
        else:
            direction = item.get("direction", "up")
            if direction not in {"up", "down"}:
                raise ValueError(f"elemento {index}: direction debe ser 'up' o 'down'")
            if target in vote_targets:
                if vote_targets[target] != direction:
                    raise ValueError(f"elemento {index}: voto duplicado/conflictivo")
                omissions.add(index, kind, "objetivo_repetido_lote")
                continue
            vote_targets[target] = direction
            item = {**item, "direction": direction}

        normalized.append(item)
    omissions.commit()
    return normalized


def run_plan(plan, *, prevalidated=False):
    import reply_writer as _rw
    plan = _rw.require_gpt(plan, "reddit")      # 08/10: nunca se publica texto que no venga de ChatGPT
    skipped = []
    try:
        if not prevalidated:
            plan = _preflight_plan(plan, skipped=skipped)
    except Exception as e:
        print(f"FALLO DE PREFLIGHT: {type(e).__name__}: {e}")
        return [{
            "kind": "plan",
            "subreddit": "",
            "resultado": f"fallo_plan:{e}",
        }]

    results = list(skipped)
    for i, item in enumerate(plan):
        # Una ronda puede durar horas: revalidar la cuarentena antes de CADA
        # acción, incluso si el lanzador aprobó el lote al comienzo.
        import circuit_breaker as _cb
        _write_ok, _hold_reason = _cb.write_preflight("reddit")
        if not _write_ok:
            print(f"[reddit] cortacircuitos ABIERTO: {_hold_reason}; detener el lote")
            break
        kind = item["kind"]
        import conversation_turn_policy as ctp
        permitted, reason = ctp.check_execution("reddit", item)
        if not permitted:
            results.append({**item, "resultado": f"saltado_cierre_conversacion:{reason}"})
            continue
        if kind in ("vote",):
            import like_context_policy as lcp
            allowed, why = lcp.check_execution("reddit", item)
            if not allowed:
                results.append({**item, "resultado": f"saltado_like_contexto:{why}"})
                continue
        print(f"=== {i+1}/{len(plan)}: {kind} -> r/{item['subreddit']} ===")

        try:
            if kind == "comment":
                r.comment(item["url"], item["text"])
            elif kind == "vote":
                outcome = r.vote(item["url"], item.get("direction", "up"))
                if outcome == "already":
                    results.append({**item, "resultado": "saltado_ya_votado"})
                    continue
                if outcome != "created":
                    raise RuntimeError(f"vote devolvió estado inesperado: {outcome!r}")
            else:
                raise ValueError(f"kind desconocido: {kind}")
            results.append({**item, "resultado": "confirmado"})
        except r.BotWarningDetected as e:
            print(f"PARADA TOTAL: {e}")
            results.append({**item, "resultado": f"parada:{e}"})
            for pending in plan[i + 1:]:
                results.append({**pending, "resultado": "no_intentado"})
            break
        except r.AlreadyCommented as e:
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
        for r_ in results:
            if r_["resultado"] != "confirmado":
                continue
            sub = r_.get("subreddit", "")
            sub = sub[2:] if sub.startswith("r/") else sub
            if r_["kind"] == "vote":
                tipo, detalle = f"voto_{r_.get('direction', 'up')}", ""
            else:
                tipo, detalle = "comentario", r_.get("text", "")
            w.writerow([
                fecha, f"r/{sub}", r_["url"], tipo, detalle,
                "confirmado", r_.get("motivo", ""),
            ])


def _append_metricas(results):
    fecha = datetime.date.today().isoformat()
    comments = sum(1 for r_ in results if r_["resultado"] == "confirmado" and r_["kind"] == "comment")
    votes = sum(1 for r_ in results if r_["resultado"] == "confirmado" and r_["kind"] == "vote")
    with open(METRICAS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([fecha, "?", f"Sesion via pipeline scan->plan->execute: {comments} comentario(s), {votes} voto(s)."])


def _update_estado(results):
    if not os.path.exists(ESTADO_MD):
        return
    import re
    with open(ESTADO_MD, encoding="utf-8") as f:
        content = f.read()
    fecha = datetime.date.today().isoformat()
    comments = sum(1 for r_ in results if r_["resultado"] == "confirmado" and r_["kind"] == "comment")
    votes = sum(1 for r_ in results if r_["resultado"] == "confirmado" and r_["kind"] == "vote")
    total = comments + votes
    resumen = f"{comments} comentario(s), {votes} voto(s)" if total else "sin acciones confirmadas"
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

    preflight_skipped = []
    try:
        plan = _preflight_plan(plan, skipped=preflight_skipped)
    except Exception as e:
        print(f"FALLO DE PREFLIGHT: {type(e).__name__}: {e}")
        raise SystemExit(2)

    if plan:
        r.ensure_browser()
    results = preflight_skipped + (run_plan(plan, prevalidated=True) if plan else [])

    print("\n=== RESUMEN ===")
    for r_ in results:
        print(
            f"{str(r_.get('resultado', '')):20s} "
            f"{str(r_.get('kind', '<invalid>')):8s} r/{r_.get('subreddit','')}"
        )

    _append_registro(results)
    _append_metricas(results)
    _update_estado(results)
    print("\nregistro_interacciones.csv, metricas.csv y ESTADO.md actualizados automaticamente.")

"""Autoauditoria de Mastodon (05/10/2026): el sistema encuentra solo sus huecos en cada ronda (clon conceptual de `bluesky_self_audit.py`).

David: «todo el esfuerzo puesto en Bluesky aprovechalo tambien en Mastodon». En Bluesky cada revision devolvia los mismos huecos hasta que se automatizo su deteccion;
aqui nace con las metricas propias de Mastodon (consulta F a GPT): oferta (plan frente a tope de ronda), objetivos unicos, reserva de candidatos en dias de inventario, % de la
shortlist sin ningun estado, calidad del plan (idioma y tema del ESTADO, no solo de la bio), fallos de ejecucion, 429/403, follow-back por fuente, concentracion de fuente y
ratio siguiendo/seguidores. Escribe `SISTEMA_DIARIO_MASTODON/cache/audit_latest.md/.json` y con `--decide` aplica la rampa una vez al dia
(`volume_ramp.py` con network=mastodon: 3 dias sanos por etapa, techo ~2.500/dia).

    python tools/mastodon_self_audit.py [--decide] [--online]
"""
import datetime
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bluesky_self_audit as base
import volume_ramp as vr

NETWORK = "mastodon"
ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_MASTODON")
REGISTRO = os.path.join(ROOT, "registro_interacciones.csv")
METRICAS = os.path.join(ROOT, "metricas.csv")
DISCOVERY = os.path.join(ROOT, "discovery_metrics.csv")
OUT_MD = os.path.join(ROOT, "cache", "audit_latest.md")
DECIDED = os.path.join(ROOT, "cache", "ramp_last_decision.txt")
STATE = os.path.join(ROOT, "..", "mastodon_growth_state.json")
PLAN = os.path.join(ROOT, "..", "mastodon_mech_plan.json")
WRITE_KINDS = {"favourite", "follow", "reply", "boost", "unfollow"}
OK_RESULTS = ("confirmado", "publicado")          # el ejecutor de Mastodon anota todo como «publicado»
ACCOUNTS_PER_ACTION = 2.0                          # favoritos+follows por cuenta nueva: para el inventario de la reserva
RATE_RE = re.compile(r"MastodonRateLimitExceeded|HTTP 429|Too Many Requests|rate.?limit exceeded", re.I)
FORBIDDEN_RE = re.compile(r"\b403\b|Forbidden", re.I)
GAP_UNIQUE = 0.60
GAP_SOURCE_SHARE = 0.35


def confirmed(rows, since, until=None):
    return base.confirmed(rows, since, until, ok=OK_RESULTS)


def write_actions(rows):
    return [r for r in rows if set((r.get("tipo") or "").split("+")) & WRITE_KINDS]


def gaps(m):
    """Lista de (hueco, accion correctiva) a partir del diccionario de metricas `m`."""
    out = []
    target, done = m.get("target"), m.get("done_today")
    if target and m.get("hours_elapsed", 24) >= 14 and done is not None and done < 0.6 * target:
        out.append((f"volumen: {done} acciones hoy frente a {target} del objetivo de la etapa {m.get('stage')}",
                    "mirar oferta (siguiente linea) y rondas: si el plan sale por debajo del tope, ampliar fuentes (reserva, hashtags con cursores) o subir de etapa"))
    if m.get("plan") and m.get("cap") and m["plan"] < 0.7 * m["cap"]:
        out.append((f"OFERTA: el plan de la ultima ronda tuvo {m['plan']} acciones frente a un tope de {m['cap']} ({100 * m['plan'] / m['cap']:.0f} %)",
                    "ampliar candidatos: mas semillas (mastodon_pool.py seeds), hashtags nuevos en growth_config.json, subir --pages del minero o de etapa"))
    ratio = m.get("unique_ratio")
    if ratio is not None and ratio < GAP_UNIQUE:
        out.append((f"objetivos unicos {100 * ratio:.0f} % (<{100 * GAP_UNIQUE:.0f} %): demasiadas acciones sobre las mismas cuentas",
                    "no subir volumen hasta ampliar fuentes; revisar limit_per_target y cooldowns"))
    if m.get("rate_limited"):
        out.append((f"{m['rate_limited']} respuestas 429 en las ultimas 24 h", "la rampa baja una etapa; revisar pausas y lecturas por ronda (las lecturas comparten el cupo de 300/5 min)"))
    if m.get("forbidden"):
        out.append((f"{m['forbidden']} respuestas 403 en las ultimas 24 h (accion no permitida)", "mirar si la instancia o las cuentas objetivo rechazan nuestras acciones; frenar la fuente que las provoca"))
    fb_n, fb = m.get("followback_n", 0), m.get("followback_rate")
    if fb is not None and fb_n >= vr.MIN_FOLLOWBACK_N and fb < vr.MIN_FOLLOWBACK:
        out.append((f"follow-back {100 * fb:.0f} % (n={fb_n}) bajo el 15 %", "revisar la tabla por fuente y volver a follows solo del pool de alta probabilidad"))
    share = m.get("top_source_share")
    if share is not None and share > GAP_SOURCE_SHARE:
        out.append((f"concentracion de fuente: '{m.get('top_source')}' aporta {100 * share:.0f} % del ultimo plan", "reservar huecos para otras fuentes y ampliar las demas"))
    if m.get("plan_failures"):
        out.append((f"EJECUCION: {m['plan_failures']} lote(s) rechazado(s) por el ejecutor en las ultimas 26 h (fallo_plan / preflight)",
                    "leer el log cache/mech_*.log (`=== RESUMEN ===`) y corregir el generador del plan"))
    pool = m.get("pool")
    if pool is not None:
        needed = max(1500, int(2 * (m.get("target") or 0) / ACCOUNTS_PER_ACTION))
        if pool.get("available_now", 0) < needed:
            out.append((f"RESERVA de candidatos: {pool.get('available_now', 0)} cuentas aprovechables (<{needed} = 2 dias de inventario a esta etapa)",
                        "subir --pages de la tarea RRSS_pool_minero_mastodon, regenerar semillas (mastodon_pool.py seeds) o anadir otra fuente"))
    no_posts = m.get("shortlist_no_posts")
    if no_posts is not None and no_posts > 0.15:
        out.append((f"{100 * no_posts:.0f} % de la shortlist sin ningun estado cargado (no puede recibir favorito)", "subir vet_gap_profiles (rampa) o revisar _vet_shortlist_gaps"))
    quality = m.get("plan_quality")
    if quality and quality.get("favourites", 0) >= 40:
        if quality["spanish"] < 0.9:
            out.append((f"CALIDAD del plan: solo {100 * quality['spanish']:.0f} % de los favoritos son a estados en espanol (>=90 %)", "revisar `_spanish_post` y las fuentes con otros idiomas"))
        if quality["niche_post"] < 0.4:
            out.append((f"CALIDAD del plan: solo {100 * quality['niche_post']:.0f} % de los favoritos llevan un termino del nicho en el propio estado (<40 %)",
                        "subir el minimo de terminos o muestrear con mastodon_reply_queue"))
    ex = m.get("exhausted") or []
    if ex:
        out.append((f"{len(ex)} fuentes sin cuentas nuevas en >=5 ejecuciones: " + ", ".join(e[0] for e in ex[:6]), "aparcar o sustituir esas superficies/hashtags"))
    for note in m.get("reply_notes") or []:
        out.append((f"replies: {note}", "reescribir el lote siguiendo el menu de formatos de GUIA_VOZ_REPLIES.md"))
    ratio_ff = m.get("follow_ratio")
    if ratio_ff is not None and ratio_ff > 4.0:
        out.append((f"siguiendo/seguidores = {ratio_ff:.1f} (>4)", "solo follows del pool de alta probabilidad; revisar con follow_review.py mastodon"))
    return out


def _recent_logs(hours=26):
    return base.recent_logs(ROOT, hours)


def collect(today=None, online=False):
    today = today or datetime.date.today()
    state = vr.load(network=NETWORK)
    stage = vr.stages(NETWORK)[state["stage"]]
    rows = base.read_csv(REGISTRO)
    todays = write_actions(confirmed(rows, today))
    last3 = write_actions(confirmed(rows, today - datetime.timedelta(days=2)))
    ratio, touched = base.unique_ratio(last3)
    logs_text = _recent_logs()
    logs = [base.parse_round_log(t) for t in logs_text]
    last_log = next((l for l in reversed(logs) if l["plan"] is not None and l["cap"] is not None), {}) or next((l for l in reversed(logs) if l["plan"] is not None), {})
    metricas = base.read_csv(METRICAS)
    follow_ratio = None
    if metricas:
        try:
            follow_ratio = int(metricas[-1]["siguiendo"]) / max(int(metricas[-1]["seguidores"]), 1)
        except (ValueError, KeyError):
            pass
    m = {"date": today.isoformat(), "stage": stage["stage"], "target": stage["daily"], "done_today": len(todays), "hours_elapsed": datetime.datetime.now().hour,
         "mix": {}, "unique_ratio": ratio, "touched_share": touched, "plan": last_log.get("plan"), "cap": last_log.get("cap"),
         "rate_limited": sum(len(RATE_RE.findall(t)) for t in logs_text), "forbidden": sum(len(FORBIDDEN_RE.findall(re.sub(r"\d{6,}", "", t))) for t in logs_text if "403" in t),
         "exhausted": base.exhausted_surfaces(base.read_csv(DISCOVERY), today - datetime.timedelta(days=7)), "reply_notes": base.reply_notes(rows), "follow_ratio": follow_ratio,
         "days_at_stage": vr.days_at_stage(state, today), "followback_rate": None, "followback_n": 0, "by_source": {},
         "plan_failures": sum(len(re.findall(r"^fallo_plan:|FALLO DE PREFLIGHT", t, re.M)) for t in logs_text),
         "unique_today": len({(r.get("cuenta") or "").casefold() for r in todays if (r.get("cuenta") or "").strip()})}
    for row in todays:
        for kind in (row.get("tipo") or "").split("+"):
            m["mix"][kind] = m["mix"].get(kind, 0) + 1
    yday = write_actions(confirmed(rows, today - datetime.timedelta(days=1), today - datetime.timedelta(days=1)))
    m["done_yesterday"] = len(yday)
    m["utilization"] = len(yday) / stage["daily"] if stage["daily"] else None
    try:
        with open(STATE, encoding="utf-8") as stream:
            data = json.load(stream)
        shortlist = data.get("shortlist") or []
        if shortlist:
            m["shortlist_no_posts"] = sum(1 for row in shortlist if not row.get("posts")) / len(shortlist)
        by_url = {post.get("url"): post for row in shortlist for post in row.get("posts") or []}
        with open(PLAN, encoding="utf-8") as stream:
            plan = json.load(stream)
        favs = [by_url[a["url"]] for a in plan if a.get("kind") == "favourite" and a.get("url") in by_url]
        if favs:
            import text_common as bp
            m["plan_quality"] = {"favourites": len(favs),
                                 "spanish": sum(1 for p in favs if (p.get("language") or "es").startswith("es")) / len(favs),
                                 "niche_post": sum(1 for p in favs if bp.niche_hits(p.get("text") or "") > 0) / len(favs)}
        counts = {}
        for a in plan:
            src = a.get("motivo", "").split(":src=")[-1] if ":src=" in a.get("motivo", "") else "desconocida"
            counts[src] = counts.get(src, 0) + 1
        if counts:
            top = max(counts, key=counts.get)
            m["top_source"], m["top_source_share"] = top, counts[top] / sum(counts.values())
    except (OSError, ValueError):
        pass
    try:
        import mastodon_pool as pool
        conn = pool.connect()
        m["pool"] = pool.stats(conn)
        conn.close()
    except Exception:
        m["pool"] = None
    if online:
        import growth_attribution as ga
        followers = ga.mastodon_followers()
        table = ga.attribute(rows, followers, today, 3)
        n = sum(v[0] for v in table.values())
        back = sum(v[1] for v in table.values())
        m["followback_n"], m["followback_rate"] = n, (back / n if n else None)
        m["by_source"] = ga.by_source(rows, followers, today, 3)
    return m


def render(m, found):
    unique = "n/d" if m["unique_ratio"] is None else f"{100 * m['unique_ratio']:.0f} %"
    lines = [f"# Autoauditoria Mastodon {m['date']}", "",
             f"- Rampa: etapa {m['stage']} (objetivo {m['target']}/dia); {m['days_at_stage']} dia(s) en la etapa",
             f"- Acciones: hoy {m['done_today']} (mezcla {m['mix']}); ayer {m['done_yesterday']} -> utilizacion {100 * (m['utilization'] or 0):.0f} %",
             f"- Objetivos unicos (3 dias): {unique}; cuentas distintas hoy: {m.get('unique_today')} (objetivo de la etapa: ~{int(m['target'] / ACCOUNTS_PER_ACTION)})",
             f"- Oferta (ultima ronda): plan {m['plan']} acciones, tope {m['cap']}",
             f"- Reserva de candidatos: {m.get('pool')}",
             f"- Calidad del plan (favoritos): {m.get('plan_quality')}",
             f"- Shortlist sin estados: {'n/d' if m.get('shortlist_no_posts') is None else format(100 * m['shortlist_no_posts'], '.0f') + ' %'}",
             f"- 429 en 24 h: {m['rate_limited']} | 403: {m['forbidden']} | siguiendo/seguidores: {'n/d' if m['follow_ratio'] is None else format(m['follow_ratio'], '.1f')}"]
    if m.get("followback_rate") is not None:
        lines.append(f"- Follow-back (>=3 dias): {100 * m['followback_rate']:.0f} % (n={m['followback_n']})")
        for source, (n, back) in sorted((m.get("by_source") or {}).items(), key=lambda kv: -kv[1][0])[:6]:
            lines.append(f"    · {source}: {back}/{n}")
    lines += ["", "## Huecos detectados"]
    lines += [f"GAP: {gap}\n  -> {action}" for gap, action in found] or ["(ninguno)"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    m = collect(online="--online" in argv or "--decide" in argv)
    found = gaps(m)
    report = render(m, found)
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as stream:
        stream.write(report)
    with open(OUT_MD.replace(".md", ".json"), "w", encoding="utf-8") as stream:
        json.dump({"date": m["date"], "stage": m["stage"], "gaps": [{"gap": g, "action": a} for g, a in found]}, stream, ensure_ascii=False, indent=1)
    print(report)
    if "--decide" in argv:
        today = datetime.date.today().isoformat()
        try:
            with open(DECIDED, encoding="utf-8") as stream:
                already = stream.read().strip() == today
        except OSError:
            already = False
        if already:
            print("rampa: ya se decidio hoy; sin cambios")
        else:
            state = vr.load(network=NETWORK)
            m["followback_baseline"] = state.get("baseline_followback")
            decision, reason = vr.decide(m, vr.days_at_stage(state), state["stage"], network=NETWORK)
            new = vr.apply(state, decision, reason, followback=m.get("followback_rate"), network=NETWORK)
            vr.save(new, network=NETWORK)
            with open(DECIDED, "w", encoding="utf-8") as stream:
                stream.write(today)
            print(f"rampa: {decision} (etapa {state['stage']} -> {new['stage']}): {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

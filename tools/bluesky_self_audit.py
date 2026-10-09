"""Autoauditoria diaria de Bluesky (05/10/2026): que el SISTEMA encuentre sus huecos en cada ejecucion, no yo al revisar.

David: «para que en cada ejecucion no sigamos detectando estos gaps y problemas». Cada ronda (paso `post` de `mechanical_round`) y a mano:

    python tools/bluesky_self_audit.py            # informe corto + lineas GAP: con la accion correctiva; escribe cache/audit_latest.md
    python tools/bluesky_self_audit.py --decide   # ademas aplica la decision de la rampa de volumen (una vez al dia)
    python tools/bluesky_self_audit.py --online   # ademas calcula follow-back real (lista de seguidores por API) y por fuente

Que mide: volumen frente al objetivo de la rampa y al limite de la API · objetivos unicos · oferta (plan construido frente al tope de la ronda) ·
fuentes agotadas · cobertura de semillas · variedad de formato de las replies · follow-back por edad y por fuente · relacion siguiendo/seguidores · 429.
Umbrales y acciones correctivas en `gaps()`; las funciones son puras y estan probadas (`tests/test_bluesky_self_audit.py`).
"""
import csv
import datetime
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc
import volume_ramp as vr

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY")
REGISTRO = os.path.join(ROOT, "registro_interacciones.csv")
METRICAS = os.path.join(ROOT, "metricas.csv")
DISCOVERY = os.path.join(ROOT, "discovery_metrics.csv")
SEEDS = os.path.join(ROOT, "bluesky_seeds.json")
OUT_MD = os.path.join(ROOT, "cache", "audit_latest.md")
DECIDED = os.path.join(ROOT, "cache", "ramp_last_decision.txt")

GAP_UNIQUE = 0.60            # GPT 05/10: objetivos unicos / acciones; la rampa solo se frena por debajo de vr.MIN_UNIQUE_RATIO
GAP_SOURCE_SHARE = 0.35      # una fuente no debe aportar mas del 35 % del plan
WRITE_KINDS = {"like", "follow", "reply", "repost", "quote", "unfollow"}
RATE_RE = re.compile(r"(?:HTTP|status|codigo|error|RateLimit)\D{0,15}429|RATE.?LIMIT|Too Many Requests", re.I)
PLAN_RE = re.compile(r"plan construido:\s*(\d+)\s*acciones")
CAP_RE = re.compile(r"tope de esta ronda\s*(\d+)\s*\(hoy ya\s*(\d+)\)")
OMITTED_RE = re.compile(r"(\d+) likes de cuentas repetidas omitidos")


# ------------------------------------------------------------------------------------------ funciones puras
def read_csv(path):
    try:
        with open(path, encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))
    except OSError:
        return []


def confirmed(rows, since, until=None, ok=("confirmado",)):
    """Filas de resultado correcto entre `since` y `until` (comun a las tres redes: cada una indica que resultados cuentan como hechos; Mastodon y Threads anotan «publicado»)."""
    out = []
    for row in rows:
        if row.get("resultado") not in ok:
            continue
        try:
            when = datetime.date.fromisoformat((row.get("fecha") or "")[:10])
        except ValueError:
            continue
        if when >= since and (until is None or when <= until):
            out.append(row)
    return out


def write_actions(rows):
    return [r for r in rows if set((r.get("tipo") or "").split("+")) & WRITE_KINDS]


def unique_ratio(rows):
    """(cuentas distintas / acciones, % de acciones sobre cuentas con mas de una accion en el periodo)."""
    accounts = [(r.get("cuenta") or "").casefold() for r in rows if (r.get("cuenta") or "").strip() and not (r.get("cuenta") or "").startswith("http")]
    if not accounts:
        return None, None
    distinct = len(set(accounts))
    return distinct / len(accounts), 1 - distinct / len(accounts)


def parse_round_log(text):
    """{'plan': N construido, 'cap': tope de la ronda, 'omitted': likes omitidos por cuenta repetida, 'rate_limited': 429} de un log de ronda."""
    plan = [int(x) for x in PLAN_RE.findall(text or "")]
    cap = CAP_RE.findall(text or "")
    omitted = [int(x) for x in OMITTED_RE.findall(text or "")]
    return {"plan": plan[-1] if plan else None, "cap": int(cap[-1][0]) if cap else None,
            "omitted": omitted[-1] if omitted else 0, "rate_limited": len(RATE_RE.findall(text or ""))}


def exhausted_surfaces(metric_rows, since, min_runs=5, max_new=2):
    """Superficies de descubrimiento con >=min_runs ejecuciones desde `since` y casi ningun handle nuevo: agotadas o mal planteadas."""
    agg = {}
    for row in metric_rows:
        if (row.get("fecha") or "") < since.isoformat():
            continue
        a = agg.setdefault(row["surface"], [0, 0, 0])
        a[0] += 1
        a[1] += int(row.get("fetched") or 0)
        a[2] += int(row.get("new_handles") or 0)
    return sorted((s, v[0], v[1], v[2]) for s, v in agg.items() if v[0] >= min_runs and v[1] > 0 and v[2] <= max_new)


def seed_coverage(seeds, today, days=7):
    by_type, scanned_recently, parked = {}, 0, 0
    for rec in seeds.values():
        by_type[rec.get("type")] = by_type.get(rec.get("type"), 0) + 1
        last = rec.get("last_scanned")
        if last and (today - datetime.date.fromisoformat(last)).days <= days:
            scanned_recently += 1
        if rec.get("yield") is not None and rec["yield"] < 2:
            parked += 1
    return {"total": len(seeds), "by_type": by_type, "scanned_recently": scanned_recently, "parked": parked}


def reply_notes(rows, n=20):
    texts = [r.get("texto_usado") for r in rows if "reply" in (r.get("tipo") or "").split("+") and (r.get("texto_usado") or "").strip()][-n:]
    return sc.reply_style_report(texts) if len(texts) >= 6 else []


def gaps(m):
    """Lista de (gap, accion correctiva) a partir del diccionario de metricas `m`. Umbrales explicitos y comentados."""
    out = []
    target, done = m.get("target"), m.get("done_today")
    if target and m.get("hours_elapsed", 24) >= 14 and done is not None and done < 0.6 * target:
        out.append((f"volumen: {done} acciones hoy frente a {target} del objetivo de la etapa {m.get('stage')}",
                    "mirar oferta (siguiente linea) y rondas: si el plan sale por debajo del tope, bajar umbrales o ampliar fuentes"))
    if m.get("plan") and m.get("cap") and m["plan"] < 0.7 * m["cap"]:
        out.append((f"OFERTA: el plan de la ultima ronda tuvo {m['plan']} acciones frente a un tope de {m['cap']} ({100 * m['plan'] / m['cap']:.0f} %); "
                    f"{m.get('omitted', 0)} likes se omitieron por cuentas repetidas",
                    "ampliar candidatos: mas semillas (bluesky_seed_wave discover), consultas nuevas en growth_config.json, o subir de etapa la rampa de umbrales"))
    if m.get("plan_failures"):
        out.append((f"EJECUCION: {m['plan_failures']} lote(s) rechazado(s) por el ejecutor en las ultimas 26 h (fallo_plan / preflight): el plan principal NO se ejecuto",
                    "leer el log cache/mech_*.log (`=== RESUMEN ===`) y corregir el generador del plan; el 05/10 un like + repost en el mismo post tiro una ronda de 428 acciones"))
    ratio = m.get("unique_ratio")
    if ratio is not None and ratio < GAP_UNIQUE:
        out.append((f"objetivos unicos {100 * ratio:.0f} % (<{100 * GAP_UNIQUE:.0f} %): demasiadas acciones sobre las mismas cuentas",
                    "no subir volumen hasta ampliar fuentes; revisar limit_per_target y cooldowns del shortlist"))
    if m.get("rate_limited"):
        out.append((f"{m['rate_limited']} respuestas 429 en las ultimas 24 h", "la rampa baja una etapa; revisar pausas y lecturas por ronda"))
    fb_n, fb = m.get("followback_n", 0), m.get("followback_rate")
    if fb is not None and fb_n >= vr.MIN_FOLLOWBACK_N and fb < vr.MIN_FOLLOWBACK:
        out.append((f"follow-back {100 * fb:.0f} % (n={fb_n}) bajo el 15 %", "revisar fuentes con peor rendimiento (tabla por fuente) y subir el umbral de follow"))
    share = m.get("top_source_share")
    if share is not None and share > GAP_SOURCE_SHARE:
        out.append((f"concentracion de fuente: '{m.get('top_source')}' aporta {100 * share:.0f} % del ultimo plan automatico (>{100 * GAP_SOURCE_SHARE:.0f} %)",
                    "reservar huecos para otras fuentes (balance por fuente en el plan) y ampliar las demas: Jetstream, comentaristas, engagers, semillas"))
    points = m.get("points_today")
    if points is not None and points > 0.8 * vr.POINTS_PER_DAY:
        out.append((f"puntos de escritura hoy {points} > 80 % del limite diario ({vr.POINTS_PER_DAY})", "impedir lotes no prioritarios hasta manana"))
    jet = m.get("jetstream_posts_2h")
    if jet is not None and jet < 100:
        out.append((f"COLECTOR de Jetstream: solo {jet} posts nuevos en las ultimas 2 h (esperados cientos/hora)",
                    "revisar la tarea RRSS_jetstream_collector (Programador de tareas) y cache/jetstream_collect.log"))
    quality = m.get("plan_quality")
    if quality and quality.get("likes", 0) >= 50:
        if quality["spanish"] < 0.9:
            out.append((f"CALIDAD del plan: solo {100 * quality['spanish']:.0f} % de los likes son a posts en espanol (>=90 %)",
                        "revisar el filtro de idioma de _post_actions / _spanish_post y las fuentes que traen posts en otros idiomas"))
        if quality["niche_post"] < 0.35:
            out.append((f"CALIDAD del plan: solo {100 * quality['niche_post']:.0f} % de los likes llevan un termino del nicho en el propio post (<35 %): "
                        "el resto se da por la bio de la cuenta", "subir el minimo de terminos de la bio (bio_hits) o el umbral de like; muestrear con bluesky_plan_sample"))
    pool = m.get("pool")
    if pool is not None:
        needed = max(3000, int(2 * (m.get("target") or 0) / 2.5))   # ~2,5 acciones por cuenta nueva; GPT (consulta E): 2-3 dias de inventario antes de escalar, no uno
        if pool.get("available_now", 0) < needed:
            out.append((f"RESERVA de candidatos: {pool.get('available_now', 0)} cuentas aprovechables (<{needed} = 2 dias de inventario a esta etapa)",
                        "subir --pages de la tarea RRSS_pool_minero, minar mas semillas (bluesky_seed_wave discover) o anadir otra fuente a bluesky_pool.py"))
    no_posts = m.get("shortlist_no_posts")
    if no_posts is not None and no_posts > 0.15:
        out.append((f"{100 * no_posts:.0f} % de la shortlist sin ningun post cargado (no puede recibir like)",
                    "subir vet_gap_profiles / revisar _vet_shortlist_gaps en bluesky_growth_scan.py (cada verificacion cuesta 1 lectura)"))
    ex = m.get("exhausted") or []
    if ex:
        out.append((f"{len(ex)} fuentes sin handles nuevos en >=5 ejecuciones: " + ", ".join(e[0] for e in ex[:6]),
                    "aparcar o sustituir esas superficies/consultas y registrar la sustituta en growth_config.json"))
    seeds = m.get("seeds") or {}
    if seeds.get("total", 0) < 150:
        out.append((f"semillas curadas: {seeds.get('total', 0)} (<150)", "ejecutar bluesky_seed_wave.py discover (5 consultas/dia) y ampliar SEED_QUERIES"))
    if seeds.get("total") and seeds.get("scanned_recently", 0) < 0.5 * seeds["total"]:
        out.append((f"solo {seeds['scanned_recently']}/{seeds['total']} semillas recorridas en 7 dias", "subir SEEDS_PER_DAY en bluesky_seed_wave.py"))
    for note in m.get("reply_notes") or []:
        out.append((f"replies: {note}", "reescribir el lote siguiendo el menu de formatos de GUIA_VOZ_REPLIES.md"))
    ratio_ff = m.get("follow_ratio")
    if ratio_ff is not None and ratio_ff > 4.0:
        out.append((f"siguiendo/seguidores = {ratio_ff:.1f} (>4)", "python tools/follow_review.py bluesky y plan de unfollow de quien no devuelve a 30 dias"))
    return out


# ------------------------------------------------------------------------------------------------ recogida
def recent_logs(root, hours=26, sched_dirs=("", "cache")):
    """Textos de los logs de las rondas de las ultimas `hours` horas de la carpeta `root` de una red (comun a las tres: logs por paso `cache/mech_*.log` y el log de las tareas
    programadas, que puede estar en la raiz o en `cache/`, donde se imprimen «plan construido: N» y «tope de esta ronda»)."""
    now = datetime.datetime.now().timestamp()
    texts = []
    for path in sorted(glob.glob(os.path.join(root, "cache", "mech_*.log"))):
        if now - os.path.getmtime(path) <= hours * 3600:
            with open(path, encoding="utf-8", errors="replace") as stream:
                texts.append(stream.read())
    for folder in sched_dirs:
        try:
            with open(os.path.join(root, folder, "mech_sched.log"), encoding="utf-8", errors="replace") as stream:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - 60000))
                texts.append(stream.read())
        except OSError:
            continue
    return texts


def _recent_logs(hours=26):
    return recent_logs(ROOT, hours)


def collect(today=None, online=False):
    today = today or datetime.date.today()
    state = vr.load()
    stage = vr.STAGES[state["stage"]]
    rows = read_csv(REGISTRO)
    todays = write_actions(confirmed(rows, today))
    last3 = write_actions(confirmed(rows, today - datetime.timedelta(days=2)))
    ratio, touched = unique_ratio(last3)
    logs = [parse_round_log(t) for t in _recent_logs()]
    last_log = next((l for l in reversed(logs) if l["plan"] is not None and l["cap"] is not None), {}) or next((l for l in reversed(logs) if l["plan"] is not None), {})
    seeds = {}
    try:
        with open(SEEDS, encoding="utf-8") as stream:
            seeds = json.load(stream)
    except (OSError, ValueError):
        pass
    metricas = read_csv(METRICAS)
    follow_ratio = None
    if metricas:
        try:
            followers, following = int(metricas[-1]["seguidores"]), int(metricas[-1]["siguiendo"])
            follow_ratio = following / max(followers, 1)
        except (ValueError, KeyError):
            pass
    m = {"date": today.isoformat(), "stage": stage["stage"], "target": stage["daily"], "done_today": len(todays),
         "hours_elapsed": datetime.datetime.now().hour, "mix": {}, "unique_ratio": ratio, "touched_share": touched,
         "plan": last_log.get("plan"), "cap": last_log.get("cap"), "omitted": last_log.get("omitted", 0),
         "rate_limited": sum(l["rate_limited"] for l in logs), "exhausted": exhausted_surfaces(read_csv(DISCOVERY), today - datetime.timedelta(days=7)),
         "seeds": seed_coverage(seeds, today), "reply_notes": reply_notes(rows), "follow_ratio": follow_ratio, "utilization": None,
         "days_at_stage": vr.days_at_stage(state, today), "followback_rate": None, "followback_n": 0, "by_source": {}}
    m["plan_failures"] = sum(len(re.findall(r"^fallo_plan:|FALLO DE PREFLIGHT", t, re.M)) for t in _recent_logs(hours=26))
    m["points_today"] = len(todays) * vr.POINTS_PER_CREATE
    m["unique_today"] = len({(r.get("cuenta") or "").casefold() for r in todays if (r.get("cuenta") or "").strip() and not (r.get("cuenta") or "").startswith("http")})   # GPT: medir DIDs distintos/dia, no solo el ratio
    try:   # concentracion por fuente del ultimo plan automatico (motivo ...:src=<fuente>)
        with open(os.path.join(ROOT, "..", "growth_state.json"), encoding="utf-8") as stream:
            plan = json.load(stream).get("auto_plan") or []
        counts = {}
        for item in plan:
            src = item.get("motivo", "").split(":src=")[-1] if ":src=" in item.get("motivo", "") else "desconocida"
            counts[src] = counts.get(src, 0) + 1
        if counts:
            top = max(counts, key=counts.get)
            m["top_source"], m["top_source_share"] = top, counts[top] / sum(counts.values())
    except (OSError, ValueError):
        pass
    try:   # huecos de la shortlist: perfiles sin ningun post (no pueden recibir like)
        with open(os.path.join(ROOT, "..", "growth_state.json"), encoding="utf-8") as stream:
            shortlist = json.load(stream).get("shortlist") or []
        if shortlist:
            m["shortlist_no_posts"] = sum(1 for row in shortlist if not row.get("posts")) / len(shortlist)
    except (OSError, ValueError):
        pass
    try:   # calidad del ultimo plan automatico: idioma y tema de los posts a los que se daria like (muestreo sobre el estado del scan)
        import bluesky_growth_scan as gs
        with open(os.path.join(ROOT, "..", "growth_state.json"), encoding="utf-8") as stream:
            state = json.load(stream)
        by_url = {post["url"]: post for row in state.get("shortlist") or [] for post in row.get("posts") or []}
        likes = [by_url[a["url"]] for a in state.get("auto_plan") or [] if a.get("kind") == "like" and a.get("url") in by_url]
        if likes:
            m["plan_quality"] = {"likes": len(likes),
                                 "spanish": sum(1 for p in likes if p.get("es") is not False) / len(likes),
                                 "niche_post": sum(1 for p in likes if gs._hits(p.get("text") or "") > 0) / len(likes)}
    except Exception:
        pass
    try:   # reserva persistente de candidatos
        import bluesky_pool as pool
        conn = pool.connect()
        m["pool"] = pool.stats(conn)
        conn.close()
    except Exception:
        m["pool"] = None
    try:   # salud del recolector de Jetstream: posts guardados en las ultimas 2 h
        import sqlite3
        conn = sqlite3.connect(os.path.join(ROOT, "cache", "jetstream.sqlite3"), timeout=30)
        since = int((datetime.datetime.now().timestamp() - 7200) * 1_000_000)
        m["jetstream_posts_2h"] = conn.execute("SELECT COUNT(*) FROM posts WHERE time_us >= ?", (since,)).fetchone()[0]
        conn.close()
    except Exception:
        m["jetstream_posts_2h"] = None
    for row in todays:
        for kind in (row.get("tipo") or "").split("+"):
            m["mix"][kind] = m["mix"].get(kind, 0) + 1
    # utilizacion = media de los ultimos 2 dias completos frente al objetivo (hoy aun no ha terminado)
    yday = write_actions(confirmed(rows, today - datetime.timedelta(days=1), today - datetime.timedelta(days=1)))
    m["done_yesterday"] = len(yday)
    m["utilization"] = len(yday) / stage["daily"] if stage["daily"] else None
    if online:
        import growth_attribution as ga
        followers = ga.bluesky_followers()
        table = ga.attribute(rows, followers, today, 3)
        n = sum(v[0] for v in table.values())
        back = sum(v[1] for v in table.values())
        m["followback_n"], m["followback_rate"] = n, (back / n if n else None)
        m["by_source"] = ga.by_source(rows, followers, today, 3)
    return m


def render(m, found):
    unique = "n/d" if m["unique_ratio"] is None else f"{100 * m['unique_ratio']:.0f} %"
    lines = [f"# Autoauditoria Bluesky {m['date']}", "",
             f"- Rampa: etapa {m['stage']} (objetivo {m['target']}/dia = {100 * m['target'] / vr.API_WRITES_PER_DAY:.0f} % del limite de la API); {m['days_at_stage']} dia(s) en la etapa",
             f"- Acciones: hoy {m['done_today']} (mezcla {m['mix']}); ayer {m['done_yesterday']} -> utilizacion {100 * (m['utilization'] or 0):.0f} %",
             f"- Objetivos unicos (3 dias): {unique}; cuentas distintas hoy: {m.get('unique_today', 'n/d')} (objetivo de la etapa: ~{int(m['target'] / 2.5)})",
             f"- Oferta (ultima ronda): plan {m['plan']} acciones, tope {m['cap']}, likes omitidos por cuenta repetida {m['omitted']}",
             f"- Reserva de candidatos: {m.get('pool')}",
             f"- Calidad del plan (likes): {m.get('plan_quality')}",
             f"- Shortlist sin posts: {'n/d' if m.get('shortlist_no_posts') is None else format(100 * m['shortlist_no_posts'], '.0f') + ' %'}",
             f"- Semillas: {m['seeds'].get('total', 0)} ({m['seeds'].get('by_type')}), recorridas en 7 dias {m['seeds'].get('scanned_recently', 0)}",
             f"- 429 en 24 h: {m['rate_limited']} | siguiendo/seguidores: {'n/d' if m['follow_ratio'] is None else round(m['follow_ratio'], 1)}"]
    if m.get("followback_rate") is not None:
        lines.append(f"- Follow-back (>=3 dias): {100 * m['followback_rate']:.0f} % (n={m['followback_n']})")
        for label, (n, back) in sorted(m["by_source"].items(), key=lambda kv: -kv[1][0])[:12]:
            lines.append(f"    · {label}: {back}/{n}")
    lines += ["", "## Huecos detectados" if found else "## Sin huecos detectados"]
    for gap, action in found:
        lines.append(f"GAP: {gap}\n  -> {action}")
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
    with open(OUT_MD.replace(".md", ".json"), "w", encoding="utf-8") as stream:   # legible por maquina (health_gaps)
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
            state = vr.load()
            m["followback_baseline"] = state.get("baseline_followback")
            decision, reason = vr.decide(m, vr.days_at_stage(state), state["stage"])
            new = vr.apply(state, decision, reason, followback=m.get("followback_rate"))
            vr.save(new)
            with open(DECIDED, "w", encoding="utf-8") as stream:
                stream.write(today)
            print(f"rampa: {decision} (etapa {state['stage']} -> {new['stage']}): {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

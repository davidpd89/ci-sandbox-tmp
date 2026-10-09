"""Autoauditoria de las redes por NAVEGADOR (Threads y X; 05/10/2026, generalizada el 06/10), gemela de `bluesky_self_audit.py` / `mastodon_self_audit.py`.

En estas redes no hay cuota oficial que defina la capacidad: el sistema vigila su oferta (reserva de posts, plan frente al objetivo de la etapa), su fiabilidad (`ActionTargetNotFound`,
perfiles rechazados), cualquier AVISO de la interfaz (cortacircuitos) y su rendimiento editorial (seguidores, replies), y deja los huecos en `SISTEMA_DIARIO_<RED>/cache/audit_latest.md`.
`--decide` aplica la regla de la rampa (`volume_ramp.decide`): sube tras un dia sano, baja ante cualquier aviso.

Cada red solo aporta su configuracion (`Config`): carpeta, modulo de la reserva y los textos de sus huecos. La logica es una.
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

WRITE_KINDS = {"like", "follow", "reply", "repost", "quote"}
OK_RESULTS = ("confirmado", "publicado", "pendiente_verificacion", "pendiente_aprobacion")
NOT_FOUND_RE = re.compile(r"ActionTargetNotFound|no se encontro")
WARNING_RE = re.compile(r"AVISO REAL (?:DE X )?DETECTADO|PARADA TOTAL|cortacircuitos ABIERTO|CAPTCHA|captcha", re.I)
REJECTED_RE = re.compile(r"saltado_perfil|perfil no apto")
ACTION_RE = re.compile(r"^=== \d+/\d+: (like|follow|reply|like_latest) ->", re.M)


class Config:
    def __init__(self, network, title, root, pool_module, supply_hint, reply_hint, growth_hint="mas replies editoriales y seguir primero a quien ya nos sigue; medir por first_source"):
        self.network, self.title, self.root, self.pool_module = network, title, root, pool_module
        self.supply_hint, self.reply_hint, self.growth_hint = supply_hint, reply_hint, growth_hint
        self.registro = os.path.join(root, "registro_interacciones.csv")
        self.metricas = os.path.join(root, "metricas.csv")
        self.out_md = os.path.join(root, "cache", "audit_latest.md")
        self.decided = os.path.join(root, "cache", "ramp_last_decision.txt")


def confirmed(rows, since, until=None):
    return base.confirmed(rows, since, until, ok=OK_RESULTS)


def gaps(m, cfg=None):
    supply_hint = cfg.supply_hint if cfg else "ampliar fuentes del scan o revisar los filtros de idioma/nicho en la reserva"
    reply_hint = cfg.reply_hint if cfg else "pase editorial diario de replies"
    growth_hint = cfg.growth_hint if cfg else "mas replies editoriales y seguir primero a quien ya nos sigue; medir por first_source"
    out = []
    target, done = m.get("target"), m.get("done_today")
    if target and m.get("hours_elapsed", 24) >= 18 and done is not None and done < 0.6 * target:
        out.append((f"volumen: {done} acciones hoy frente a {target} del objetivo de la etapa {m.get('stage')}",
                    "mirar la reserva de posts y el plan de las rondas; si hay oferta y las rondas no corren, revisar el cortacircuitos y el bloqueo del Edge"))
    if m.get("plan") is not None and m.get("plan_target") and m["plan"] < 0.7 * m["plan_target"]:
        out.append((f"OFERTA: el plan de la ultima ronda tuvo {m['plan']} acciones frente a {m['plan_target']} de la etapa", supply_hint))
    pool = m.get("pool")
    if pool is not None and pool.get("available_now", 0) < 2 * max(1, m.get("likes_per_round", 24)):
        out.append((f"RESERVA de posts: {pool.get('available_now', 0)} aprovechables (<2 rondas de likes)", "subir busquedas/scroll por ronda (etapa) o anadir superficies nuevas al scan"))
    nf = m.get("not_found_rate")
    if nf is not None and nf > 0.03 and m.get("attempted", 0) >= 20:
        out.append((f"ActionTargetNotFound en {100 * nf:.0f} % de las acciones (>3 %)", "comprobar que el plan lleva permalink y que la interfaz de la red no cambio (like_post)"))
    if m.get("ui_warnings"):
        out.append((f"{m['ui_warnings']} AVISO(S) de la interfaz o captcha en las ultimas 26 h", "el cortacircuitos para la red; avisar a David; NO subir etapa ni reintentar sin que lo vea"))
    ratio = m.get("unique_ratio")
    if ratio is not None and ratio < 0.7:
        out.append((f"objetivos unicos {100 * ratio:.0f} % (<70 %)", "ampliar la reserva; el filtro de «cuentas tocadas hace <5 dias» deberia evitarlo"))
    if m.get("followers_gain_7d") is not None and m["followers_gain_7d"] < 3 and m.get("done_7d", 0) >= 150:
        out.append((f"crecimiento: +{m['followers_gain_7d']} seguidores en 7 dias con {m['done_7d']} acciones", growth_hint))
    if m.get("replies_7d") is not None and m["replies_7d"] < 20:
        out.append((f"solo {m['replies_7d']} replies en 7 dias", reply_hint))
    for note in m.get("reply_notes") or []:
        out.append((f"replies: {note}", "reescribir el lote siguiendo el menu de formatos de GUIA_VOZ_REPLIES.md"))
    return out


def _logs(cfg, hours=26):
    now = datetime.datetime.now().timestamp()
    texts = []
    for path in sorted(glob.glob(os.path.join(cfg.root, "cache", "mech_*.log"))):
        if now - os.path.getmtime(path) <= hours * 3600:
            with open(path, encoding="utf-8", errors="replace") as stream:
                texts.append(stream.read())
    return texts


def collect(cfg, today=None):
    today = today or datetime.date.today()
    state = vr.load(network=cfg.network)
    stage = vr.stages(cfg.network)[state["stage"]]
    rows = base.read_csv(cfg.registro)
    todays = [r for r in confirmed(rows, today) if set((r.get("tipo") or "").split("+")) & WRITE_KINDS]
    week = [r for r in confirmed(rows, today - datetime.timedelta(days=6)) if set((r.get("tipo") or "").split("+")) & WRITE_KINDS]
    ratio, _ = base.unique_ratio(week)
    texts = _logs(cfg)
    attempted = sum(len(ACTION_RE.findall(t)) for t in texts)
    not_found = sum(len(NOT_FOUND_RE.findall(t)) for t in texts)
    plan = None
    try:
        with open(os.path.join(cfg.root, "mech_sched.log"), encoding="utf-8", errors="replace") as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 20000))
            found = re.findall(r"plan construido:\s*(\d+)\s*acciones", stream.read())
            plan = int(found[-1]) if found else None
    except OSError:
        pass
    metricas = base.read_csv(cfg.metricas)
    gain = None
    try:
        recent = [int(r["seguidores"]) for r in metricas if (r.get("fecha") or "") >= (today - datetime.timedelta(days=7)).isoformat() and str(r.get("seguidores")).isdigit()]
        if recent:
            gain = recent[-1] - recent[0]
    except (ValueError, KeyError):
        pass
    m = {"date": today.isoformat(), "stage": stage["stage"], "target": stage["daily"], "likes_per_round": stage["likes"], "done_today": len(todays), "done_7d": len(week),
         "hours_elapsed": datetime.datetime.now().hour, "mix": {}, "unique_ratio": ratio, "plan": plan, "plan_target": stage["likes"] + stage["follows"],
         "attempted": attempted, "not_found_rate": (not_found / attempted) if attempted else None, "rejected_profiles": sum(len(REJECTED_RE.findall(t)) for t in texts),
         "ui_warnings": sum(len(WARNING_RE.findall(t)) for t in texts), "rate_limited": 0, "followers_gain_7d": gain,
         "replies_7d": sum(1 for r in week if "reply" in (r.get("tipo") or "").split("+")), "reply_notes": base.reply_notes(rows), "days_at_stage": vr.days_at_stage(state, today)}
    for row in todays:
        for kind in (row.get("tipo") or "").split("+"):
            m["mix"][kind] = m["mix"].get(kind, 0) + 1
    try:
        import importlib
        pool = importlib.import_module(cfg.pool_module)
        conn = pool.connect()
        m["pool"] = pool.stats(conn)
        conn.close()
    except Exception:
        m["pool"] = None
    return m


def render(cfg, m, found):
    unique = "n/d" if m["unique_ratio"] is None else f"{100 * m['unique_ratio']:.0f} %"
    nf = "n/d" if m["not_found_rate"] is None else f"{100 * m['not_found_rate']:.1f} %"
    lines = [f"# Autoauditoria {cfg.title} {m['date']}", "",
             f"- Etapa {m['stage']} (objetivo {m['target']}/dia; avance automatico por salud): {m['days_at_stage']} dia(s) en la etapa",
             f"- Acciones: hoy {m['done_today']} (mezcla {m['mix']}); ultimos 7 dias {m['done_7d']}",
             f"- Objetivos unicos (7 dias): {unique} | ActionTargetNotFound: {nf} | perfiles rechazados: {m['rejected_profiles']} | avisos de la interfaz: {m['ui_warnings']}",
             f"- Oferta: plan de la ultima ronda {m['plan']} acciones (objetivo {m['plan_target']}); reserva de posts: {m.get('pool')}",
             f"- Seguidores en 7 dias: {m['followers_gain_7d']} | replies en 7 dias: {m['replies_7d']}", "", "## Huecos detectados"]
    lines += [f"GAP: {gap}\n  -> {action}" for gap, action in found] or ["(ninguno)"]
    return "\n".join(lines) + "\n"


def main(cfg, argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    m = collect(cfg)
    found = gaps(m, cfg)
    report = render(cfg, m, found)
    os.makedirs(os.path.dirname(cfg.out_md), exist_ok=True)
    with open(cfg.out_md, "w", encoding="utf-8") as stream:
        stream.write(report)
    with open(cfg.out_md.replace(".md", ".json"), "w", encoding="utf-8") as stream:
        json.dump({"date": m["date"], "stage": m["stage"], "gaps": [{"gap": g, "action": a} for g, a in found]}, stream, ensure_ascii=False, indent=1)
    print(report)
    if "--decide" in argv:
        today = datetime.date.today().isoformat()
        try:
            with open(cfg.decided, encoding="utf-8") as stream:
                already = stream.read().strip() == today
        except OSError:
            already = False
        if already:
            print("rampa: ya se decidio hoy; sin cambios")
        else:
            state = vr.load(network=cfg.network)
            decision, reason = vr.decide(m, vr.days_at_stage(state), state["stage"], network=cfg.network)
            new = vr.apply(state, decision, reason, network=cfg.network)
            vr.save(new, network=cfg.network)
            with open(cfg.decided, "w", encoding="utf-8") as stream:
                stream.write(today)
            print(f"rampa: {decision} (etapa {state['stage']} -> {new['stage']}): {reason}")
    return 0

"""Rampa de volumen de Bluesky hacia la capacidad de la API (05/10/2026, decision de David).

David: la API permite ~11.600 escrituras/dia (5.000 puntos/hora y 35.000/dia, 3 puntos por like/follow/reply) y hacemos ~1.000: hay que llegar a
~10.000. Subir de golpe sin oferta de candidatos solo repite objetivos (medido: 39 % de acciones a cuentas distintas) y el 05/10 se vio que el techo
real NO era la cuota sino el plan: los umbrales mecanicos (`auto_like_score_min`, `auto_follow_score_min`), los perfiles que se revisan y las rondas por dia
dejaban un plan de ~120 acciones por ronda aunque el tope era 340. Esta rampa mueve juntas las tres palancas por etapas:

  etapa -> objetivo diario, rondas/dia, perfiles del shortlist, perfiles verificados por ronda, umbrales de like/follow y lecturas.

Cada dia `bluesky_self_audit.py` mide la salud (429, objetivos unicos, follow-back por edad, utilizacion del presupuesto) y llama a `decide()`:
sube una etapa solo si dos dias seguidos todo esta sano; baja una etapa ante cualquier 429 o si el follow-back cae. La etapa vive en
`SISTEMA_DIARIO_BLUESKY/ramp.json` (con historial) y `bluesky_growth_scan._load_config` aplica `overlay()` sobre `growth_config.json`.

    python tools/volume_ramp.py            # etapa actual y tabla
    python tools/volume_ramp.py set 3      # forzar etapa (David/Claude), queda en el historial
"""
import copy
import datetime
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_BLUESKY")
RAMP_PATH = os.path.join(ROOT, "ramp.json")

# (objetivo diario, rondas/dia, perfiles del shortlist, perfiles verificados, umbral like, umbral follow, lecturas por ronda)
STAGES = [
    {"stage": 0, "daily": 700, "rounds": 3, "profiles": 400, "vet": 120, "like_min": 10.0, "follow_min": 14.0, "reads": 1800, "jet_posts": 75, "jet_authors": 25},
    {"stage": 1, "daily": 1500, "rounds": 4, "profiles": 700, "vet": 220, "like_min": 8.5, "follow_min": 13.0, "reads": 2200, "jet_posts": 300, "jet_authors": 100},
    {"stage": 2, "daily": 2500, "rounds": 5, "profiles": 1000, "vet": 330, "like_min": 7.0, "follow_min": 12.0, "reads": 2600, "jet_posts": 600, "jet_authors": 200},
    {"stage": 3, "daily": 4000, "rounds": 6, "profiles": 1400, "vet": 450, "like_min": 6.5, "follow_min": 11.5, "reads": 3000, "jet_posts": 1200, "jet_authors": 400},
    {"stage": 4, "daily": 6000, "rounds": 7, "profiles": 1900, "vet": 600, "like_min": 6.0, "follow_min": 11.0, "reads": 3400, "jet_posts": 2000, "jet_authors": 700},
    {"stage": 5, "daily": 8000, "rounds": 8, "profiles": 2400, "vet": 750, "like_min": 5.5, "follow_min": 10.5, "reads": 3800, "jet_posts": 3000, "jet_authors": 1000},
    {"stage": 6, "daily": 9000, "rounds": 9, "profiles": 3000, "vet": 900, "like_min": 5.0, "follow_min": 10.0, "reads": 4200, "jet_posts": 4000, "jet_authors": 1400},
]
# Mastodon (05/10 noche, David: «lo aprendido en Bluesky aplicalo a Mastodon»): misma rampa, otras palancas. mastodon.social permite 300 peticiones/5 min por cuenta
# y las LECTURAS comparten ese cupo con las escrituras (1 peticion/s): el volumen lo limita la oferta de objetivos nuevos y las lecturas por accion, no una cuota de
# escrituras. Estas etapas siguen la consulta F a GPT (05/10): mastodon.social NO documenta una cuota diaria pero prohibe el engagement artificial y la automatizacion que perturba
# conversaciones; el limite de comportamiento lo decide la evidencia (3 dias sanos por etapa y techo ~2.500/dia), no X-RateLimit.
MASTODON_RAMP_PATH = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_MASTODON", "ramp.json")
MASTODON_STAGES = [
    {"stage": 0, "daily": 500, "rounds": 3, "profiles": 300, "reads": 1200, "vet": 30, "pool": 150, "hashtags": 12, "post_queries": 15, "account_queries": 8, "seeds": 30},
    {"stage": 1, "daily": 800, "rounds": 4, "profiles": 420, "reads": 1500, "vet": 80, "pool": 280, "hashtags": 16, "post_queries": 20, "account_queries": 12, "seeds": 45},
    {"stage": 2, "daily": 1100, "rounds": 5, "profiles": 550, "reads": 1800, "vet": 130, "pool": 400, "hashtags": 20, "post_queries": 26, "account_queries": 16, "seeds": 60},
    {"stage": 3, "daily": 1500, "rounds": 6, "profiles": 700, "reads": 2100, "vet": 200, "pool": 520, "hashtags": 24, "post_queries": 32, "account_queries": 20, "seeds": 80},
    {"stage": 4, "daily": 2000, "rounds": 7, "profiles": 900, "reads": 2400, "vet": 280, "pool": 680, "hashtags": 28, "post_queries": 38, "account_queries": 24, "seeds": 100},
    {"stage": 5, "daily": 2600, "rounds": 8, "profiles": 1100, "reads": 2700, "vet": 360, "pool": 850, "hashtags": 32, "post_queries": 44, "account_queries": 28, "seeds": 120},
    {"stage": 6, "daily": 3400, "rounds": 9, "profiles": 1400, "reads": 3000, "vet": 450, "pool": 1100, "hashtags": 38, "post_queries": 50, "account_queries": 32, "seeds": 150},
    {"stage": 7, "daily": 4300, "rounds": 10, "profiles": 1700, "reads": 3300, "vet": 540, "pool": 1400, "hashtags": 44, "post_queries": 56, "account_queries": 36, "seeds": 180},
    {"stage": 8, "daily": 5200, "rounds": 10, "profiles": 2000, "reads": 3600, "vet": 640, "pool": 1700, "hashtags": 50, "post_queries": 62, "account_queries": 40, "seeds": 210},
]
# Threads (05/10 noche): red por NAVEGADOR. El limite no es una cuota de API sino el ritmo humano de la interfaz y la tolerancia de Meta a la automatizacion: se sube por
# etapas acortando las pausas y alargando el plan por ronda, con la misma salud medida (avisos de la interfaz = cortacircuitos, follow-back, objetivos unicos).
THREADS_RAMP_PATH = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_THREADS", "ramp.json")
THREADS_STAGES = [
    {"stage": 0, "daily": 75, "rounds": 3, "likes": 24, "follows": 4, "searches": 4, "passes": 1, "profile_queries": 2, "seeds": 1, "pause": (30, 55), "doubts": (0.12, 0.03)},
    {"stage": 1, "daily": 150, "rounds": 3, "likes": 44, "follows": 7, "searches": 6, "passes": 3, "profile_queries": 3, "seeds": 2, "pause": (24, 48), "doubts": (0.10, 0.02)},
    {"stage": 2, "daily": 300, "rounds": 5, "likes": 52, "follows": 8, "searches": 8, "passes": 4, "profile_queries": 4, "seeds": 3, "pause": (20, 40), "doubts": (0.08, 0.02)},
    {"stage": 3, "daily": 600, "rounds": 7, "likes": 70, "follows": 26, "searches": 10, "passes": 5, "profile_queries": 5, "seeds": 4, "pause": (14, 30), "doubts": (0.06, 0.015)},
    {"stage": 4, "daily": 900, "rounds": 8, "likes": 88, "follows": 32, "searches": 12, "passes": 6, "profile_queries": 6, "seeds": 5, "pause": (12, 26), "doubts": (0.06, 0.01)},
    {"stage": 5, "daily": 1300, "rounds": 10, "likes": 108, "follows": 40, "searches": 14, "passes": 7, "profile_queries": 7, "seeds": 6, "pause": (10, 22), "doubts": (0.05, 0.01)},
]
# X (06/10, David: «quitale tanta restriccion, que tenga rondas y vamos a hacerla crecer igual que el resto»): red por NAVEGADOR como Threads, con la misma rampa por salud.
# Antes: UNA sesion diaria de ~80 acciones (12 follows, sin busqueda de personas ni seguidores de semillas). Los topes por accion siguen por debajo de los limites que X publica para una
# cuenta normal (~1.000 likes/dia, ~400 follows/dia); la etapa decide cuantas acciones por ronda, cuantas busquedas (Recientes + Personas), el scroll y las semillas.
X_RAMP_PATH = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_X", "ramp.json")
X_STAGES = [
    {"stage": 0, "daily": 150, "rounds": 3, "likes": 40, "follows": 20, "searches": 6, "passes": 3, "profile_queries": 3, "seeds": 2, "pause": (26, 50), "doubts": (0.10, 0.03)},
    {"stage": 1, "daily": 300, "rounds": 4, "likes": 62, "follows": 30, "searches": 8, "passes": 4, "profile_queries": 4, "seeds": 3, "pause": (22, 44), "doubts": (0.08, 0.02)},
    {"stage": 2, "daily": 500, "rounds": 5, "likes": 85, "follows": 36, "searches": 10, "passes": 5, "profile_queries": 5, "seeds": 4, "pause": (18, 38), "doubts": (0.07, 0.02)},
    {"stage": 3, "daily": 750, "rounds": 6, "likes": 108, "follows": 40, "searches": 12, "passes": 6, "profile_queries": 6, "seeds": 5, "pause": (15, 32), "doubts": (0.06, 0.015)},
    {"stage": 4, "daily": 1000, "rounds": 7, "likes": 128, "follows": 44, "searches": 14, "passes": 7, "profile_queries": 7, "seeds": 6, "pause": (12, 27), "doubts": (0.06, 0.01)},
    {"stage": 5, "daily": 1300, "rounds": 8, "likes": 148, "follows": 46, "searches": 16, "passes": 8, "profile_queries": 8, "seeds": 7, "pause": (10, 22), "doubts": (0.05, 0.01)},
]
BROWSER_NETWORKS = ("threads", "x")       # redes por navegador: la rampa sube por salud (avisos de la interfaz), sin cuota de API
NETWORK_STAGES = {"bluesky": STAGES, "mastodon": MASTODON_STAGES, "threads": THREADS_STAGES, "x": X_STAGES}
NETWORK_PATHS = {"bluesky": RAMP_PATH, "mastodon": MASTODON_RAMP_PATH, "threads": THREADS_RAMP_PATH, "x": X_RAMP_PATH}
NETWORK_ENV = {"bluesky": "RRSS_RAMP_PATH", "mastodon": "RRSS_RAMP_PATH_MASTODON", "threads": "RRSS_RAMP_PATH_THREADS", "x": "RRSS_RAMP_PATH_X"}
API_WRITES_PER_DAY = 11_666      # 35.000 puntos/dia y 5.000/hora por DID, CREATE=3 puntos (documentacion oficial de Bluesky, confirmada por GPT el 05/10)
POINTS_PER_DAY, POINTS_PER_HOUR, POINTS_PER_CREATE = 35_000, 5_000, 3
MAX_HOURLY_CREATES = 1_450      # guarda del ejecutor: por debajo de las 1.666 por hora del limite oficial

# Reglas de la decision (ver `decide`)
MIN_DAYS_BY_NETWORK = {"bluesky": 2, "mastodon": 1, "threads": 1, "x": 1}   # 06/10: David pide dejar de autolimitarse; la salud (429, avisos, objetivos unicos) sigue frenando
MIN_DAYS_AT_STAGE = 2   # GPT 05/10 pedia >=3 dias de evidencia; David (05/10) quiere llegar al 70 % y la oferta ya existe: >=2 dias sanos (0 x 429, follow-back y objetivos unicos) por etapa
MIN_UNIQUE_RATIO = 0.45   # etapas bajas; ver min_unique_ratio(stage): sube a 0.55/0.60 a escala (GPT 05/10)


def min_unique_ratio(stage):
    return 0.45 if stage < 3 else 0.55 if stage < 5 else 0.60
MIN_FOLLOWBACK = 0.15
REGRESS_FOLLOWBACK = 0.08
MIN_FOLLOWBACK_N = 30
MAX_FOLLOW_RATIO = 6.0
REGRESS_FOLLOWBACK_N = 40
# La utilizacion NO frena la subida: con los umbrales de una etapa el plan queda corto (oferta), y lo que lo arregla es justo pasar a la
# siguiente etapa (umbrales mas bajos, mas perfiles). Frenan la salud (429, follow-back, objetivos unicos), no el volumen alcanzado.


def stages(network="bluesky"):
    return NETWORK_STAGES[network]


def _path(path, network="bluesky"):
    """RRSS_RAMP_PATH (RRSS_RAMP_PATH_MASTODON) aisla los tests de la etapa real de la rampa (no dependen de en que etapa este hoy el sistema)."""
    default = NETWORK_PATHS[network]
    return path if path not in (None, default) else (os.environ.get(NETWORK_ENV[network]) or default)


def load(path=None, network="bluesky"):
    path = _path(path, network)
    try:
        with open(path, encoding="utf-8") as stream:
            state = json.load(stream)
    except (OSError, ValueError):
        state = {}
    state.setdefault("stage", 0)
    state.setdefault("since", datetime.date.today().isoformat())
    state.setdefault("history", [])
    state["stage"] = max(0, min(int(state["stage"]), len(stages(network)) - 1))
    return state


def save(state, path=None, network="bluesky"):
    with open(_path(path, network), "w", encoding="utf-8") as stream:
        json.dump(state, stream, ensure_ascii=False, indent=1)


def current(path=None, network="bluesky"):
    return stages(network)[load(path, network)["stage"]]


def overlay(config, path=None):
    """Copia de `growth_config.json` con los parametros de la etapa vigente. Etapa 0 = la configuracion tal cual esta en el fichero."""
    stage = current(path)
    if stage["stage"] == 0:
        return config
    out = copy.deepcopy(config)
    out["budgets"]["max_read_requests"] = max(out["budgets"].get("max_read_requests", 0), stage["reads"])
    out["budgets"]["max_profiles_to_vet"] = max(out["budgets"].get("max_profiles_to_vet", 0), stage["vet"])
    out["budgets"]["actionability_profiles"] = max(out["budgets"].get("actionability_profiles", 0), stage["profiles"])
    out["budgets"]["pool_candidates"] = max(out["budgets"].get("pool_candidates", 0), stage["profiles"])   # la reserva persistente aporta tantas cuentas como plazas tiene la shortlist; la diversidad por fuente reparte
    out["budgets"]["fetch_workers"] = max(out["budgets"].get("fetch_workers", 1), 6)   # feeds de autor en paralelo (~1,6 s cada uno en secuencial = 25 min por scan)
    out["budgets"]["vet_gap_profiles"] = max(out["budgets"].get("vet_gap_profiles", 0), int(0.7 * stage["profiles"]))   # posts de los perfiles de la shortlist que aun no tienen ninguno
    # Jetstream (05/10): la cache de posts en espanol del nicho es la mayor fuente de oferta y no se habia usado nunca; la rampa sube cuantos posts y autores recurrentes lee el scan
    out["budgets"]["jetstream_cache_posts"] = max(out["budgets"].get("jetstream_cache_posts", 0), stage["jet_posts"])
    out["budgets"]["jetstream_active_authors"] = max(out["budgets"].get("jetstream_active_authors", 0), stage["jet_authors"])
    # Mas consultas por ronda (05/10): con 2 consultas por familia y 5 hashtags por ronda el vocabulario nuevo apenas se usaba; crece con la etapa
    n = stage["stage"]
    coverage = out.setdefault("coverage", {})
    coverage["post_queries_per_family"] = max(coverage.get("post_queries_per_family", 0), 2 + n)
    coverage["actor_queries_total"] = max(coverage.get("actor_queries_total", 0), 5 + 3 * n)
    coverage["tag_queries_per_round"] = max(coverage.get("tag_queries_per_round", 0), 5 + 3 * n)
    coverage["replies_only_queries_total"] = max(coverage.get("replies_only_queries_total", 0), 6 + 2 * n)
    coverage["popular_feed_queries_per_round"] = max(coverage.get("popular_feed_queries_per_round", 0), 4 + n)
    out["budgets"]["starter_pack_queries_per_round"] = max(out["budgets"].get("starter_pack_queries_per_round", 0), 6 + 2 * n)
    out["budgets"]["custom_feeds"] = max(out["budgets"].get("custom_feeds", 0), 2 + n)
    # Grafo de gustos (likes de las cuentas del nicho -> posts/autores nuevos): el recolector `bluesky_taste_collect.py` nunca se habia arrancado
    out["budgets"]["taste_listener_dids"] = max(out["budgets"].get("taste_listener_dids", 0), 50 + 150 * n)
    out["budgets"]["taste_cache_posts"] = max(out["budgets"].get("taste_cache_posts", 0), 75 + 250 * n)
    shortlist = out["shortlist"]
    shortlist["profiles"] = max(shortlist.get("profiles", 0), stage["profiles"])
    shortlist["auto_repost_per_round"] = max(shortlist.get("auto_repost_per_round", 0), 8)   # ~1,5 % del volumen (GPT, consulta E); 0 en la etapa 0
    shortlist["auto_like_score_min"] = min(shortlist.get("auto_like_score_min", 99.0), stage["like_min"])
    shortlist["auto_follow_score_min"] = min(shortlist.get("auto_follow_score_min", 99.0), stage["follow_min"])
    return out


def overlay_mastodon(config, path=None):
    """Copia de `SISTEMA_DIARIO_MASTODON/growth_config.json` con las palancas de la etapa vigente (etapa 0 = el fichero tal cual)."""
    stage = current(path, "mastodon")
    if stage["stage"] == 0:
        return config
    out = copy.deepcopy(config)
    budgets, coverage = out.setdefault("budgets", {}), out.setdefault("coverage", {})
    vet = max(stage["vet"], int(0.6 * stage["profiles"]))                                    # 06/10: con 200 verificaciones quedaban 339 de 700 perfiles sin estados (48 %)
    budgets["max_read_requests"] = max(budgets.get("max_read_requests", 0), stage["reads"] + vet)
    budgets["shortlist_profiles"] = max(budgets.get("shortlist_profiles", 0), stage["profiles"])
    budgets["vet_gap_profiles"] = max(budgets.get("vet_gap_profiles", 0), vet)      # estados de los perfiles de la shortlist que aun no tienen ninguno
    budgets["pool_candidates"] = max(budgets.get("pool_candidates", 0), stage["pool"])       # cuentas de la reserva persistente ofrecidas al scan
    budgets["remote_resolve"] = max(budgets.get("remote_resolve", 0), 80 + 60 * stage["stage"])      # estados de las instancias en espanol (mastodon_remote.py) resueltos a locales: 1 lectura cada uno
    for key in ("thread_seeds", "engager_seeds", "graph_seeds"):
        budgets[key] = max(budgets.get(key, 0), int(stage["seeds"] * (1.0 if key != "engager_seeds" else 0.8)))
    coverage["post_queries_per_round"] = max(coverage.get("post_queries_per_round", 0), stage["post_queries"])
    coverage["account_queries_per_round"] = max(coverage.get("account_queries_per_round", 0), stage["account_queries"])
    coverage["hashtags_per_round"] = max(coverage.get("hashtags_per_round", 0), stage["hashtags"])
    discovery = out.setdefault("discovery", {})
    discovery["second_wave_seeds"] = max(discovery.get("second_wave_seeds", 0), stage["seeds"])
    return out


def pause_range(path=None, network="bluesky"):
    """Pausa (min, max) entre escrituras segun la etapa: 1,5-5 s al principio; 1,2-3,5 s desde la etapa 3 para que 6-10 mil acciones/dia quepan en el dia
    sin pasar de los ~1.660 escrituras/hora que permite la API (media ~2,3 s con las rafagas y dudas de `human_gap`)."""
    stage = current(path, network)
    if "pause" in stage:       # redes por navegador: cada etapa trae su propio rango (segundos)
        return tuple(stage["pause"])
    return (1.5, 5.0) if load(path, network)["stage"] < 3 else (1.2, 3.5)


def pause_doubts(path=None, network="bluesky"):
    """(probabilidad de duda de 8-25 s, probabilidad de paron de 40-90 s) entre escrituras. 12 % y 3 % a baja escala (media ~6,7 s por pausa); en las etapas altas
    6 % y 1 % (media ~3,9 s) para que 6.000-9.000 acciones/dia quepan en el dia sin quitar la variacion humana."""
    stage = current(path, network)
    if "doubts" in stage:
        return tuple(stage["doubts"])
    return (0.12, 0.03) if load(path, network)["stage"] < 3 else (0.06, 0.01)


def daily_target(path=None, network="bluesky"):
    return current(path, network)["daily"]


def rounds_per_day(path=None, network="bluesky"):
    return current(path, network)["rounds"]


def decide(metrics, days_at_stage, stage, network="bluesky"):
    """('advance'|'hold'|'regress', motivo) a partir de las metricas del dia (diccionario):
    rate_limited (429 en 24 h), unique_ratio, followback_rate, followback_n (follows con >=3 dias), utilization (hecho/objetivo)."""
    if network in BROWSER_NETWORKS:
        # 06/10 (David: «quita ese limite inventado»): la rampa de Threads tambien SUBE sola. No hay cuota publicada, asi que manda la salud medida: cualquier aviso de la
        # interfaz/captcha/rechazo baja una etapa; sube con >=1 dia sano (0 avisos, ActionTargetNotFound <=5 %, objetivos unicos >=55 %) y la oferta de la reserva cubre la etapa.
        if metrics.get("rate_limited", 0) > 0 or metrics.get("ui_warnings", 0) > 0:
            return "regress", f"{metrics.get('rate_limited', 0) + metrics.get('ui_warnings', 0)} aviso(s) de la interfaz o rechazo(s) en 24 h"
        if stage >= len(stages(network)) - 1:
            return "hold", "ya en la etapa maxima"
        needed = MIN_DAYS_BY_NETWORK.get(network, 1)
        if days_at_stage < needed:
            return "hold", f"solo {days_at_stage} dia(s) en la etapa; hacen falta {needed}"
        nf = metrics.get("not_found_rate")
        if nf is not None and nf > 0.05 and metrics.get("attempted", 0) >= 20:
            return "hold", f"ActionTargetNotFound {100 * nf:.0f} % > 5 %: arreglar la fiabilidad antes de subir"
        ratio = metrics.get("unique_ratio")
        if ratio is not None and ratio < 0.55:
            return "hold", f"objetivos unicos {100 * ratio:.0f} % < 55 %: falta oferta"
        if metrics.get("done_today", 0) < 0.3 * (metrics.get("target") or 0) and metrics.get("hours_elapsed", 24) >= 20:
            return "hold", "las rondas de hoy no llegaron ni al 30 % del objetivo: revisar que corren antes de subir"
        return "advance", "0 avisos de la interfaz, fiabilidad y objetivos unicos en rango"
    if metrics.get("rate_limited", 0) > 0:
        return "regress", f"{metrics['rate_limited']} respuestas 429 en 24 h"
    n, rate = metrics.get("followback_n", 0), metrics.get("followback_rate")
    if n >= REGRESS_FOLLOWBACK_N and rate is not None and rate < REGRESS_FOLLOWBACK:
        return "regress", f"follow-back {100 * rate:.0f} % (n={n}) bajo el minimo {100 * REGRESS_FOLLOWBACK:.0f} %"
    base = metrics.get("followback_baseline")
    if n >= REGRESS_FOLLOWBACK_N and rate is not None and base and rate < 0.7 * base:
        return "regress", f"follow-back {100 * rate:.0f} % cae >30 % frente a {100 * base:.0f} % al entrar en la etapa"
    if stage >= len(stages(network)) - 1:
        return "hold", "ya en la etapa maxima"
    if (metrics.get("follow_ratio") or 0) > MAX_FOLLOW_RATIO:
        return "hold", f"siguiendo/seguidores {metrics['follow_ratio']:.1f} > {MAX_FOLLOW_RATIO}: crecimiento de follows sin followers proporcionales"
    needed = MIN_DAYS_BY_NETWORK.get(network, MIN_DAYS_AT_STAGE)
    if days_at_stage < needed:
        return "hold", f"solo {days_at_stage} dia(s) en la etapa; hacen falta {needed}"
    floor = min_unique_ratio(stage + 1)   # para ENTRAR en la etapa siguiente se exige su umbral
    if (metrics.get("unique_ratio") or 0) < floor:
        return "hold", f"objetivos unicos {100 * (metrics.get('unique_ratio') or 0):.0f} % < {100 * floor:.0f} %: falta oferta de candidatos nuevos"
    if n >= MIN_FOLLOWBACK_N and rate is not None and rate < MIN_FOLLOWBACK:
        return "hold", f"follow-back {100 * rate:.0f} % < {100 * MIN_FOLLOWBACK:.0f} %"
    return "advance", "429=0, objetivos unicos y follow-back en rango"


def apply(state, decision, reason, today=None, followback=None, network="bluesky"):
    """Aplica la decision al estado (devuelve el nuevo estado y lo anota en el historial)."""
    today = (today or datetime.date.today()).isoformat()
    old = state["stage"]
    new = old + 1 if decision == "advance" else old - 1 if decision == "regress" else old
    new = max(0, min(new, len(stages(network)) - 1))
    state = dict(state)
    if new != old:
        state["stage"], state["since"] = new, today
        if followback is not None:
            state["baseline_followback"] = round(followback, 3)   # referencia para detectar una caida >30 % en la etapa nueva
    state["history"] = (state.get("history") or [])[-60:] + [{"date": today, "decision": decision, "from": old, "to": new, "reason": reason}]
    return state


def days_at_stage(state, today=None):
    today = today or datetime.date.today()
    try:
        return (today - datetime.date.fromisoformat(state["since"])).days
    except ValueError:
        return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    network = next((n for n in ("mastodon", "threads", "x") if n in argv), "bluesky")
    argv = [a for a in argv if a not in ("bluesky", "mastodon", "threads", "x")]
    state = load(network=network)
    rows = stages(network)
    if argv and argv[0] == "set" and len(argv) > 1:
        state = apply({**state}, "hold", f"fijada a mano a la etapa {argv[1]}", network=network)
        state["stage"], state["since"] = max(0, min(int(argv[1]), len(rows) - 1)), datetime.date.today().isoformat()
        save(state, network=network)
    stage = rows[state["stage"]]
    share = f" ({100 * stage['daily'] / API_WRITES_PER_DAY:.0f} % de la API)" if network == "bluesky" else ""
    print(f"Rampa {network.capitalize()}: etapa {stage['stage']} desde {state['since']} -> objetivo {stage['daily']}/dia{share}, {stage['rounds']} rondas/dia")
    for row in rows:
        mark = "->" if row["stage"] == stage["stage"] else "  "
        if network in BROWSER_NETWORKS:
            print(f" {mark} {row['stage']}: {row['daily']:>6}/dia | rondas {row['rounds']} | likes/ronda {row['likes']} follows/ronda {row['follows']} | busquedas {row['searches']} scroll {row['passes']} | pausa {row['pause'][0]}-{row['pause'][1]} s")
            continue
        print(f" {mark} {row['stage']}: {row['daily']:>6}/dia | rondas {row['rounds']} | shortlist {row['profiles']} | lecturas {row['reads']}"
              + (f" | verificados {row['vet']} | like>={row['like_min']} follow>={row['follow_min']}" if network == "bluesky" else f" | verificados {row['vet']} | reserva {row['pool']}"))
    for item in state["history"][-5:]:
        print(f"    {item['date']} {item['decision']} {item['from']}->{item['to']}: {item['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

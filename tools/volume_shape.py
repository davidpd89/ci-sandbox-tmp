"""Volumen alto pero variable (03/10).

David: si la API permite X, se usa lo que da, con variacion para no cantar a cuenta
bot. Los limites oficiales (Bluesky 5.000 puntos/hora y 35.000/dia con 3 puntos por
like/follow/reply = ~11.600 acciones/dia; Mastodon 300 llamadas/5 min) estan muy por
encima de lo que hacemos, asi que el techo lo ponen la oferta de objetivos y la salud medida (rampa de volumen_ramp.py; la cuota es de infraestructura, no una recomendacion)
relevantes, no la API. Este modulo decide cuanto hacer en cada ronda:

* `day_factor` / `week_factor`: multiplicadores deterministas (el de semana persiste 7
  dias: hay semanas mas intensas que otras; el del dia 0,6-1,4 con algun dia flojo).
* `run_cap`: tope de acciones de ESTA ronda = objetivo diario x semana x dia / rondas,
  con +-30 % de ruido propio.
* `shape_plan`: recorta un plan que lo supere en tres zonas (revision de ChatGPT, 03/10):
  elite (lo mejor, siempre), muestra ponderada por posicion y exploracion uniforme del
  resto (datos contrafactuales para saber si el scoring funciona). Los follows tienen un
  tope duro de proporcion. Devuelve tambien los candidatos NO elegidos.
* `split_holdout`: aparta una fraccion de follows NO elite para observar
  seguimientos sin contacto. Es un indicador descriptivo: compararlo con TODOS
  los seguidos, que incluyen elite, introduce sesgo de seleccion.
* `run_seed`: semilla reproducible de cada ronda (fecha, red, franja) para poder explicar
  por que una accion entro o quedo fuera.
* `human_gap`: pausa entre acciones con rafagas, dudas y algun paron largo.
"""
import hashlib
import random

# Objetivo diario de acciones por red (4-6 % del limite real de Bluesky; Mastodon limitado
# por su cuota de llamadas). Ajustable: no es un techo de la API, es el ritmo de crucero.
BASE_DAILY = {"bluesky": 700, "mastodon": 500, "x": 150, "threads": 120}   # x/threads: por navegador (pausas de 30-55 s: ~40 acciones = 25 min por ronda)
RUNS_PER_DAY = 3


def base_daily(network):
    """Objetivo diario de la red. Bluesky y Mastodon (05/10) los manda la RAMPA (`volume_ramp.py`, 05/10); el resto, BASE_DAILY."""
    if network in ("bluesky", "mastodon", "threads", "x"):
        try:
            import volume_ramp
            return volume_ramp.daily_target(network=network)
        except Exception:   # sin rampa legible: el valor base de siempre
            pass
    return BASE_DAILY[network]


def runs_per_day(network, cfg=None):
    """Rondas por dia: la rampa en Bluesky, `runs_per_day` de la red si lo define, o el valor general."""
    if network in ("bluesky", "mastodon", "threads", "x"):
        try:
            import volume_ramp
            return volume_ramp.rounds_per_day(network=network)
        except Exception:
            pass
    return (cfg or {}).get("runs_per_day", RUNS_PER_DAY)
FOLLOW_SHARE = 0.15         # proporcion objetivo de follows dentro de una ronda (05/10: 0,25 -> 0,15; el follow solo da 8,5 % de follow-back y ahora sobran likes; siguiendo/seguidores = 5,4)
HARD_FOLLOW_SHARE_MAX = 0.25  # tope duro: si hay hueco sobrante, como mucho este porcentaje
ELITE_SHARE = 0.25          # lo mejor puntuado, siempre dentro
EXPLORATION_SHARE = 0.20    # muestra uniforme del resto
# 06/10 (David: «solo seguir y comentar convierte; X igual que Bluesky»): X reparte mas peso a los follows. (proporcion en la ronda, tope duro, tope diario sobre el objetivo, grupo de control);
# 45 % de 750 = ~340 follows/dia, por debajo de los 400 que X permite a una cuenta no verificada.
NETWORK_FOLLOW_SHARES = {"x": (0.40, 0.50, 0.30, 0.0), "threads": (0.35, 0.45, 0.40, 0.0)}   # 07/10: Threads igual (David: solo seguir y comentar convierte)
HOLDOUT_SHARE = 0.08        # follows no elite que se apartan a proposito (grupo de control)


def run_seed(today, network, slot):
    """Semilla reproducible: misma fecha+red+franja => mismas decisiones aleatorias."""
    digest = hashlib.sha256(f"{today.isoformat()}|{network}|{slot}".encode()).hexdigest()
    return int(digest[:12], 16)


def day_factor(today, network):
    rng = random.Random(f"{today.isoformat()}-{network}")
    factor = rng.uniform(0.6, 1.4)
    if rng.random() < 0.15:      # dia flojo: no todos los dias se hace lo mismo
        factor *= 0.4
    return round(factor, 2)


def week_factor(today, network):
    """Intensidad de la semana ISO (0,8-1,2): estructura temporal, no solo ruido diario."""
    year, week, _ = today.isocalendar()
    return round(random.Random(f"{year}-W{week}-{network}").uniform(0.8, 1.2), 2)


def run_cap(network, today, rng=None, runs_per_day=RUNS_PER_DAY, daily=None):
    rng = rng or random.Random()
    daily = daily if daily is not None else base_daily(network)
    base = daily * week_factor(today, network) * day_factor(today, network) / runs_per_day
    return max(10, int(base * rng.uniform(0.7, 1.3)))


def daily_budget(network, today, daily=None):
    """Presupuesto del dia = objetivo x semana x dia (sin ruido de ronda)."""
    daily = daily if daily is not None else base_daily(network)
    return daily * week_factor(today, network) * day_factor(today, network)


BUDGET_HEADROOM = 1.3   # el dia puede pasarse un 30 % del presupuesto antes de recortar rondas


def remaining_cap(cap, done_today, budget, headroom=BUDGET_HEADROOM, floor=10):
    """Tope de la ronda sin pasar del presupuesto del dia: si ya se hizo mucho (rondas manuales extra,
    reintentos) las siguientes rondas bajan solas; no hay minimo artificial mas alla de `floor`."""
    allowed = int(budget * headroom) - done_today
    return max(floor, min(cap, allowed))


def _weighted_sample(indexes, k, rng):
    """k indices sin reemplazo con probabilidad decreciente por posicion (Efraimidis-Spirakis)."""
    keyed = sorted(((rng.random() ** (1.0 / (1.0 / (pos + 10))), idx) for pos, idx in enumerate(indexes)),
                   reverse=True)
    return [idx for _, idx in keyed[:k]]


def _pick(indexes, n, rng, elite_share=ELITE_SHARE, exploration_share=EXPLORATION_SHARE):
    if n >= len(indexes):
        return list(indexes)
    elite = int(n * elite_share)
    explore = int(n * exploration_share)
    chosen = list(indexes[:elite])
    rest = list(indexes[elite:])
    weighted = _weighted_sample(rest, n - elite - explore, rng)
    chosen += weighted
    leftover = [i for i in rest if i not in set(weighted)]
    chosen += rng.sample(leftover, min(explore, len(leftover)))
    return chosen


def shape_plan(plan, cap, rng=None, follow_share=FOLLOW_SHARE, hard_follow_max=HARD_FOLLOW_SHARE_MAX,
               with_dropped=False):
    """Plan recortado a `cap` acciones (si ya cabe, se devuelve igual). Trabaja con
    (indice, accion) para conservar el orden original aunque haya acciones repetidas."""
    indexed = list(enumerate(plan))
    follows = [i for i, a in indexed if a.get("kind") == "follow"]
    others = [i for i, a in indexed if a.get("kind") != "follow"]
    if len(plan) <= cap and len(follows) <= int(cap * follow_share):
        return (list(plan), []) if with_dropped else list(plan)
    rng = rng or random.Random()
    follow_cap = min(len(follows), int(cap * follow_share))
    other_cap = min(len(others), cap - follow_cap)
    follow_cap = min(len(follows), cap - other_cap, int(cap * hard_follow_max), int(other_cap * hard_follow_max / (1 - hard_follow_max)))   # y nunca mas del tope duro sobre el TOTAL ejecutado (05/10)
    chosen = set(_pick(follows, follow_cap, rng)) | set(_pick(others, other_cap, rng))
    shaped = [plan[i] for i in sorted(chosen)]
    dropped = [plan[i] for i in range(len(plan)) if i not in chosen]
    return (shaped, dropped) if with_dropped else shaped


def split_holdout(plan, rng=None, share=HOLDOUT_SHARE, elite_share=ELITE_SHARE):
    """(plan_sin_holdout, holdout): separa una muestra de follows NO elite.

    El grupo apartado solo es comparable, en principio, con los NO elite elegibles;
    NO debe contrastarse con el total tratado para afirmar incrementalidad.
    La asignacion se explica en #70; este algoritmo no se altera. Solo follows.
    """
    rng = rng or random.Random()
    follow_idx = [i for i, a in enumerate(plan) if a.get("kind") == "follow"]
    eligible = follow_idx[int(len(follow_idx) * elite_share):]
    k = int(round(len(follow_idx) * share))
    held = set(rng.sample(eligible, min(k, len(eligible)))) if k else set()
    return [a for i, a in enumerate(plan) if i not in held], [plan[i] for i in sorted(held)]


FOLLOW_DAILY_SHARE = 0.15     # tope de follows del DIA sobre el objetivo diario (05/10: el 20:15 de Bluesky hizo 350 follows de 678 acciones; siguiendo/seguidores 6,7)


def follow_budget_left(network, followed_today, daily=None, share=FOLLOW_DAILY_SHARE):
    """Follows que aun caben hoy: `share` del objetivo diario menos los ya hechos. El tope por ronda de `shape_plan` no basta: con un plan que cabe en el
    tope de la ronda no recortaba nada, y todas las rondas del dia podian ser un 50 % de follows."""
    daily = daily if daily is not None else base_daily(network)
    return max(0, int(share * daily) - int(followed_today))


def cap_follows(plan, allowed):
    """(plan sin los follows que sobran, cuantos se quitaron): se conservan los primeros (el plan viene ordenado por puntuacion)."""
    kept, follows, dropped = [], 0, 0
    for action in plan:
        if action.get("kind") == "follow":
            if follows >= allowed:
                dropped += 1
                continue
            follows += 1
        kept.append(action)
    return kept, dropped


CHEAP_KINDS = ("like", "favourite")


def limit_per_target(plan, rng=None, weights=((1, 0.55), (2, 0.38), (3, 0.07)), already=None):
    """Limita las acciones baratas (like/favourite) por cuenta y ronda a 1-3 al azar (mayoria 1-2).
    Medido el 03/10: 536 acciones sobre 167 cuentas (0,31 unicas/accion) = 3 likes seguidos a la
    misma persona, patron tipico de spam; con mas descubrimiento hay amplitud de sobra. Conserva
    lo mejor (primeras posiciones) de cada cuenta y respeta replies/follows/reposts.
    `already` = {handle: acciones baratas ya hechas hoy}: el limite es por cuenta y DIA, no solo por
    ronda (ChatGPT, 03/10: con 3 rondas se podia tocar la misma cuenta en las tres)."""
    rng = rng or random.Random()
    counts, limits, out = dict(already or {}), {}, []
    for action in plan:
        if action.get("kind") not in CHEAP_KINDS:
            out.append(action)
            continue
        handle = str(action.get("handle") or "").lstrip("@").casefold()
        if not handle:
            out.append(action)
            continue
        if handle not in limits:
            roll, acc = rng.random(), 0.0
            limits[handle] = weights[-1][0]
            for n, w in weights:
                acc += w
                if roll < acc:
                    limits[handle] = n
                    break
        counts[handle] = counts.get(handle, 0) + 1
        if counts[handle] <= limits[handle]:
            out.append(action)
    return out


def human_gap(rng=None, a=1.5, b=5.0, doubt=0.12, stall=0.03):
    """Segundos de pausa entre dos acciones: normalmente a-b, a veces una duda de 8-25 s (probabilidad `doubt`) y,
    rara vez, un paron de 40-90 s (`stall`), como alguien que se distrae. Con 8.000 acciones/dia las dudas y parones por defecto (15 %) suman ~4 s de media
    por accion y el dia no cabe: la rampa los reduce en las etapas altas (volume_ramp.pause_doubts) sin quitar la variacion."""
    rng = rng or random.Random()
    roll = rng.random()
    if roll < stall:
        return rng.uniform(40, 90)
    if roll < stall + doubt:
        return rng.uniform(8, 25)
    return rng.uniform(a, b)


def follow_shares(network):
    """(follow_share, hard_follow_max, daily_share, holdout_share) de la red (por defecto, los generales)."""
    return NETWORK_FOLLOW_SHARES.get(network, (FOLLOW_SHARE, HARD_FOLLOW_SHARE_MAX, FOLLOW_DAILY_SHARE, HOLDOUT_SHARE))

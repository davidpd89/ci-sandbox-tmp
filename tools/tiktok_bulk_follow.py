"""TikTok: seguimiento RAPIDO por reciprocidad (07/10/2026, David: «solo 58 follows en todo el dia y casi nadie nos sigue de vuelta»).

El flujo normal (scan -> plan -> ejecutar) tarda ~90 min en escanear y ~70 en ejecutar para ~60 acciones, y sus candidatos eran sobre todo editoriales y librerias, que no devuelven el follow.
Aqui se sigue DIRECTAMENTE donde esta la gente que devuelve el follow, sin perfiles intermedios:

  * `followers`: abre el perfil de una cuenta semilla (lector/escritor pequeño), entra en «Seguidores» y pulsa «Seguir» fila a fila (~7 s por follow). Cada semilla ofrece ~40 filas.
  * `mutual`: busca videos de «escritores, apoyemonos / sigueme y te sigo / presenta tu novela», abre los comentarios y sigue a quien comenta (es gente que busca reciprocidad y es del nicho).

Se verifica cada follow en pantalla («Siguiendo»/«Amigos»), se anota en el registro (`notas: bulk:<modo>:<fuente>`) y se para ante captcha, aviso de limite o 3 fallos seguidos. Nunca se resuelve nada anti-bot.

    python tools/tiktok_bulk_follow.py [--max-follows 100] [--max-minutes 45] [--per-seed 45] [--modes followers,mutual]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import random
import re
import sys
import time

import tiktok_safety as safety

sys.path.insert(0, os.path.dirname(__file__))

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_TIKTOK")
CONFIG_PATH = os.path.join(ROOT, "growth_config.json")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
SEEDS_PATH = os.path.join(ROOT, "bulk_seeds.json")
STATE_PATH = os.path.join(ROOT, "..", "tiktok_state.json")
BUSINESS = re.compile(r"editorial|ediciones|librer|bookstore|biblioteca|publishing|tienda|shop|store|distribu|oficial|official|agencia|news|noticias|ayuntamiento|colegio|escuela|universidad|instituto", re.I)
DEFAULT_ACCOUNT = re.compile(r"^user\d{7,}$", re.I)
LIMIT_WARNING = re.compile(r"(demasiado r[aá]pid|too fast|int[eé]ntalo de nuevo m[aá]s tarde|try again later|actividad inusual|unusual activity|has alcanzado el l[ií]mite|reached the limit|temporalmente|temporarily|no puedes seguir|can.t follow)", re.I)
FOLLOWED = ("following", "friends", "requested")
DEFAULT_SEEDS = ["damaris_alvz_escritora", "escritordenovela", "bellataylorauthor", "autor.autopublicado", "rafamago1974", "ale.entrepaginas", "valu_reedings", "lauryn.books",
                 "bethlovesbooks64", "mai.libros_", "miriamolmo_autora", "tris_bookstagram", "sharkbooki", "celia_supongo", "lector.compulsivo", "booktokdajhe"]
MUTUAL_QUERIES = ["escritores apoyémonos", "apoyo mutuo escritores", "escritores sígueme y te sigo", "autores independientes apoyo mutuo", "nos apoyamos escritores", "escritores emergentes",
                  "booktok sígueme y te sigo", "lectores sigámonos", "comunidad lectora", "escritores de tiktok", "presenta tu novela", "autor emergente", "apoyo a escritores noveles",
                  "#escritoresdetiktok", "#escritoresemergentes", "#apoyoescritores", "#booktokespaña", "#lecturasdetiktok", "#sigueme", "#seguimosdevuelta"]
try:        # 07/10: busquedas de apoyo mutuo de la consulta M a GPT (descubrimiento_gpt.json)
    import discovery_terms
    MUTUAL_QUERIES = list(dict.fromkeys(MUTUAL_QUERIES + discovery_terms.terms("tiktok", "busquedas")[:30]))
except Exception:
    pass
MUTUAL_CARD = re.compile(r"apoy|sigue|sigo|follow|mutu|comunidad|presenta|emergente|escrit|autor|lector|novel|libro|booktok|lectur", re.I)


COOLDOWN_PATH = os.path.join(ROOT, "bulk_cooldown.json")


class StopSession(RuntimeError):
    """Parada limpia: captcha, aviso de limite o fallos seguidos."""


class RateLimited(StopSession):
    """TikTok mostro «Estas usando la opcion de seguir con demasiada frecuencia» (un toast que revierte el follow): se para y se descansa."""


def cooldown_left():
    """Minutos de descanso que quedan tras un aviso de limite (0 si no hay)."""
    try:
        until = datetime.datetime.fromisoformat(json.load(open(COOLDOWN_PATH, encoding="utf-8")).get("until", ""))
    except (OSError, ValueError):
        return 0
    return max(0.0, (until - datetime.datetime.now()).total_seconds() / 60)


def start_cooldown():
    """Descanso creciente: 60 min la primera vez, el doble si el aviso se repite el mismo dia (max. 4 h)."""
    try:
        data = json.load(open(COOLDOWN_PATH, encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    today = datetime.date.today().isoformat()
    strikes = int(data.get("strikes", 0)) + 1 if data.get("day") == today else 1
    minutes = min(240, 60 * 2 ** (strikes - 1))
    with open(COOLDOWN_PATH, "w", encoding="utf-8") as stream:
        json.dump({"day": today, "strikes": strikes, "until": (datetime.datetime.now() + datetime.timedelta(minutes=minutes)).isoformat(timespec="seconds")}, stream)
    return minutes


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as stream:
        return json.load(stream)


def followed_before():
    """Handles que el sistema ya siguio alguna vez (nunca se vuelve a seguir a quien se dejo de seguir) y follows de hoy."""
    done = set()
    try:
        with open(REGISTRO_CSV, encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if (row.get("tipo") or "").strip().casefold() == "follow" and (row.get("resultado") or "").strip().casefold() in ("confirmado", "saltado_ya_seguido", "pendiente_verificacion"):
                    handle = (row.get("cuenta") or "").strip().lstrip("@").casefold()
                    if handle:
                        done.add(handle)
    except OSError:
        pass
    used, _ = safety.recorded_actions(REGISTRO_CSV)
    return done, used["follow"]


def record_follow(handle, note, result="confirmado"):
    if result not in ("confirmado", "pendiente_verificacion"):
        raise ValueError("resultado invalido")
    new = not os.path.exists(REGISTRO_CSV) or os.path.getsize(REGISTRO_CSV) == 0
    with open(REGISTRO_CSV, "a", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        if new:
            writer.writerow(["fecha", "cuenta", "tipo", "post_resumen", "texto_usado", "resultado", "notas"])
        writer.writerow([datetime.date.today().isoformat(), "@" + handle.lstrip("@"), "follow", "", "", result, f"{note} | transporte=android_native"])
        stream.flush()
        os.fsync(stream.fileno())
    print(f"{result:<35} follow   @{handle}", flush=True)


def vet_name(name, handle):
    """Filtro de forma (la lista no muestra bio): fuera tiendas/editoriales y las cuentas sin nombre de usuario real."""
    if BUSINESS.search(f"{name} {handle}") or DEFAULT_ACCOUNT.match(handle or ""):
        return False
    return True


def parse_follower_rows(tree, handle_x=(222, 240), button_x=(770, 830)):
    """Filas de las listas Seguidores/Siguiendo/Amigos: {handle, name, relation, button}. Handle = TextView de ~44 px; boton «Seguir/Siguiendo/Amigos» a la derecha.
    En la lista de OTRA cuenta el handle esta en x=231 y el boton en x~794; en la de la cuenta propia el boton queda mas a la izquierda (hay un «...» a su derecha)."""
    from tiktok_mobile_nav import _HANDLE_RE, _norm, _tiktok_elements, clean, element_texts, relation_of
    elements = _tiktok_elements(tree)
    rows = []
    for e in elements:
        r = e["rect"]
        text = clean((element_texts(e) or [""])[0])
        if not (handle_x[0] <= float(r["x"]) <= handle_x[1] and 38 <= float(r["height"]) <= 48 and _HANDLE_RE.match(text) and "button" not in _norm(e.get("type"))):
            continue
        y = float(r["y"])
        button = None
        for other in elements:
            if "button" in _norm(other.get("type")) and button_x[0] <= float(other["rect"]["x"]) <= button_x[1] and abs(float(other["rect"]["y"]) - (y - 46)) < 45:
                label = clean((element_texts(other) or [""])[0])
                if relation_of(label):
                    button = (other, relation_of(label))
                    break
        if not button:
            continue
        name = ""
        for other in elements:
            o = other["rect"]
            if handle_x[0] <= float(o["x"]) <= handle_x[1] and 30 < y - float(o["y"]) < 90 and "button" not in _norm(other.get("type")):
                name = clean((element_texts(other) or [""])[0])
                break
        rows.append({"handle": text, "name": name, "relation": button[1], "button": button[0], "y": y})
    return rows


def check_warning(tree):
    from tiktok_mobile_interact import _visible_text
    hit = LIMIT_WARNING.search(_visible_text(tree) or "")
    if hit:
        raise StopSession(f"aviso de TikTok en pantalla ({hit.group(0)!r}): se para; lo revisa David")


class Session:
    def __init__(self, nav, pace, rng, *, max_follows, deadline, done):
        self.nav, self.pace, self.rng = nav, pace, rng
        self.max_follows, self.deadline, self.done = max_follows, deadline, done
        self.followed = 0
        self.fails = 0
        self.started = time.monotonic()
        self.progress_alarm = False
        self.count = 0
        self.next_break = rng.randint(12, 20)

    @property
    def over(self):
        if not self.progress_alarm and not self.followed and time.monotonic() - self.started >= 15 * 60:
            self.progress_alarm = True
            print("[TIKTOK_NO_PROGRESS] bulk 15 min sin follows confirmados; diagnostico, sin retry", flush=True)
        return self.followed >= self.max_follows or time.time() >= self.deadline

    def gap(self):
        time.sleep(max(4.0, self.rng.lognormvariate(2.45, 0.4)))       # mediana ~11,5 s (a 5,7 s TikTok avisaba de «demasiada frecuencia» a los ~35 follows)
        self.count += 1
        if self.count >= self.next_break:
            self.count, self.next_break = 0, self.rng.randint(12, 20)
            pause = self.rng.uniform(70, 200)
            print(f"(micro-descanso {pause:.0f}s)", flush=True)
            time.sleep(pause)

    def ok(self, handle, note):
        self.followed += 1
        self.fails = 0
        self.done.add(handle.casefold())
        record_follow(handle, note)

    def fail(self, why):
        self.fails += 1
        print(f"FALLO bulk: {why}", flush=True)
        if self.fails >= 2:
            raise RateLimited("el follow se revierte (TikTok: «demasiada frecuencia»): se para y se descansa")


def mine_followers(sess, seed, per_seed):
    """Sigue fila a fila desde la lista de seguidores de `seed`. Devuelve (leidas, seguidas)."""
    from mobile_client import element_center
    from tiktok_mobile_nav import _norm, _tiktok_elements, clean, element_texts
    nav = sess.nav
    nav.a.open_profile(seed)
    time.sleep(2.0)
    profile = nav.read_profile()
    if (profile.get("handle") or "").casefold() != seed.casefold():
        print(f"(semilla @{seed} no disponible: {profile.get('handle')!r})", flush=True)
        return 0, 0
    if profile.get("followers") is not None and not (150 <= profile["followers"] <= 8000):
        print(f"(semilla @{seed} descartada: {profile['followers']} seguidores; solo cuentas pequeñas, cuyos seguidores devuelven el follow)", flush=True)
        return 0, 0
    target = None
    for e in _tiktok_elements(nav.tree()):
        text = clean((element_texts(e) or [""])[0])
        if _norm(text) in ("seguidores", "followers") and 380 < float(e["rect"]["y"]) < 640:
            target = e
    if not target:
        return 0, 0
    x, y = element_center(target)
    nav.c.tap(x, y, nav.device.id)
    time.sleep(2.4)
    seen, mine, empty = set(), 0, 0
    while not sess.over and mine < per_seed and empty < 2:
        tree = nav.tree()
        check_warning(tree)
        rows = [r for r in parse_follower_rows(tree) if r["handle"].casefold() not in seen]
        if not rows:
            empty += 1
        else:
            empty = 0
        for row in rows:
            if sess.over or mine >= per_seed:
                break
            seen.add(row["handle"].casefold())
            if row["relation"] not in ("not_following", "follows_me") or row["handle"].casefold() in sess.done or not vet_name(row["name"], row["handle"]):
                continue
            # la lista sigue deslizandose un instante tras el swipe: se vuelve a leer la fila justo antes de pulsar y se usan las coordenadas FRESCAS (con las del volcado anterior el tap caia en otra fila)
            current = next((r for r in parse_follower_rows(nav.tree()) if r["handle"].casefold() == row["handle"].casefold()), None)
            if not current or current["relation"] not in ("not_following", "follows_me"):
                continue
            bx, by = element_center(current["button"])
            nav.c.tap(bx, by, nav.device.id)
            time.sleep(1.1)
            after = nav.tree()
            check_warning(after)
            fresh = next((r for r in parse_follower_rows(after) if r["handle"].casefold() == row["handle"].casefold()), None)
            if fresh and fresh["relation"] in FOLLOWED:
                sess.ok(row["handle"], f"bulk:followers:@{seed}")
                mine += 1
            else:
                try:
                    open(os.path.join(ROOT, "cache", "bulk_fail.png"), "wb").write(nav.c.screenshot_bytes(nav.device.id, max_size=500))
                except Exception:
                    pass
                shown = [(r["handle"], r["relation"], int(float(current["button"]["rect"]["y"]))) for r in parse_follower_rows(after)][:3]
                sess.fail(f"@{row['handle']} no quedo en «Siguiendo» (antes {row['relation']}; ahora {fresh['relation'] if fresh else 'fila ausente'}; filas {shown})")
            sess.gap()
        if not sess.over and mine < per_seed:
            nav.c.swipe(540, 1900, 540, 650, duration_ms=520 + sess.rng.randint(0, 200), device_id=nav.device.id)
            time.sleep(2.0)
    return len(seen), mine


def mine_mutual(sess, query, videos=3, pages=4):
    """Busca videos de apoyo mutuo y sigue a quien comenta. Devuelve seguidas."""
    from mobile_client import element_center
    from tiktok_mobile_nav import _norm, _tiktok_elements, clean
    nav, total = sess.nav, 0
    nav.return_to_feed()
    nav.search(query, "Vídeos")
    cards = [c for c in nav.video_cards() if MUTUAL_CARD.search(c["label"] + " " + c["author"])][:videos]
    for card in cards:
        if sess.over:
            break
        nav.open_video(card)
        nav.open_comments()
        for page in range(pages):
            if sess.over:
                break
            comments = nav.read_comments(max_pages=1)
            for comment in comments:
                if sess.over:
                    break
                if BUSINESS.search(comment["name"]):
                    continue
                nav.open_commenter_profile(comment)
                time.sleep(1.2)
                profile = nav.read_profile()
                handle = profile.get("handle")
                if handle and handle.casefold() not in sess.done and vet_name(profile.get("name") or "", handle) \
                        and profile.get("relation") in ("not_following", "follows_me") \
                        and not (profile.get("followers") and profile["followers"] > 150000):
                    bx, by = element_center(profile["relation_element"])
                    nav.c.tap(bx, by, nav.device.id)
                    time.sleep(1.4)
                    after = nav.read_profile()
                    check_warning(nav.tree())
                    if (after.get("handle") or "").casefold() == handle.casefold() and after.get("relation") in FOLLOWED:
                        sess.ok(handle, f"bulk:mutual:{query}")
                        total += 1
                    else:
                        sess.fail(f"@{handle} no quedo en «Siguiendo»")
                    sess.gap()
                nav.c.press("BACK", nav.device.id)
                time.sleep(1.0)
                if not nav.read_comments(max_pages=1):          # no se volvio al panel de comentarios: se abandona este video
                    break
            nav.scroll_down(0.45)
        nav.c.press("BACK", nav.device.id)
        time.sleep(0.8)
        nav.back_to_results()
    return total


def followback_own(sess, max_rows=120):
    """Sigue de vuelta a quien nos sigue: en NUESTRA lista de Seguidores, cada fila «Seguir tambien» (nos siguen y no les seguimos) se pulsa directamente. Es la reciprocidad mas segura:
    ya demostraron interes. Anota ademas a cada uno como seguidor entrante (fidelizacion). Devuelve (filas leidas, seguidas)."""
    from mobile_client import element_center
    from tiktok_mobile_nav import _norm, _tiktok_elements, clean, element_texts
    nav = sess.nav
    target = next((e for e in _tiktok_elements(nav.tree()) if _norm(clean((element_texts(e) or [""])[0])) in ("seguidores", "followers") and 380 < float(e["rect"]["y"]) < 640), None)
    if target is None:
        return 0, 0
    x, y = element_center(target)
    nav.c.tap(x, y, nav.device.id)
    time.sleep(2.6)
    seen, mine, empty = set(), 0, 0
    try:
        import relationship_policy as rp
    except Exception:
        rp = None
    while not sess.over and len(seen) < max_rows and empty < 2:
        tree = nav.tree()
        check_warning(tree)
        rows = [r for r in parse_follower_rows(tree, button_x=(690, 730)) if r["handle"].casefold() not in seen]
        empty = 0 if rows else empty + 1
        for row in rows:
            if sess.over:
                break
            seen.add(row["handle"].casefold())
            if row["relation"] != "follows_me" or row["handle"].casefold() in sess.done:
                continue
            if rp:
                rp.log_inbound("tiktok", row["handle"], "follow")
            current = next((r for r in parse_follower_rows(nav.tree(), button_x=(690, 730)) if r["handle"].casefold() == row["handle"].casefold()), None)
            if not current or current["relation"] != "follows_me":
                continue
            bx, by = element_center(current["button"])
            nav.c.tap(bx, by, nav.device.id)
            time.sleep(1.1)
            after = nav.tree()
            check_warning(after)
            fresh = next((r for r in parse_follower_rows(after, button_x=(690, 730)) if r["handle"].casefold() == row["handle"].casefold()), None)
            if fresh and fresh["relation"] in FOLLOWED:
                sess.ok(row["handle"], "bulk:followback:nuevo_seguidor")
                mine += 1
            else:
                sess.fail(f"@{row['handle']} no quedo en «Siguiendo» (follow-back)")
            sess.gap()
        if not sess.over and len(seen) < max_rows:
            nav.c.swipe(540, 1900, 540, 650, duration_ms=520 + sess.rng.randint(0, 200), device_id=nav.device.id)
            time.sleep(2.0)
    return len(seen), mine


def pick_seeds(cfg, done_seeds, limit):
    """Semillas: las de la config + personales del ultimo scan (ni tiendas ni gigantes); se rotan (no se repite una en 3 dias) y se prefieren las que mas follow-back dieron."""
    seeds = list(cfg.get("bulk_seeds") or []) + DEFAULT_SEEDS
    try:
        state = json.load(open(STATE_PATH, encoding="utf-8"))
        for c in sorted(state.get("shortlist") or [], key=lambda c: -float(c.get("score") or 0)):
            f = c.get("followers")
            if f and 400 <= f <= 80000 and vet_name(c.get("name") or "", c.get("handle") or ""):
                seeds.append(c["handle"])
    except (OSError, ValueError):
        pass
    cutoff = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
    uniq = []
    for s in seeds:
        if s.casefold() not in {u.casefold() for u in uniq} and (done_seeds.get(s, {}).get("last") or "") < cutoff:
            uniq.append(s)
    uniq.sort(key=lambda s: -float(done_seeds.get(s, {}).get("yield", 0.1)))      # `yield` = follow-back real suavizado (lo escribe tiktok_reciprocity_audit.py); sin datos, 10 %
    return uniq[:limit]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-follows", type=int, default=100)
    parser.add_argument("--max-minutes", type=float, default=45)
    parser.add_argument("--per-seed", type=int, default=45)
    parser.add_argument("--modes", default="followback,mutual,followers")
    parser.add_argument("--seeds", default="", help="semillas concretas separadas por comas (ignora la rotacion)")
    parser.add_argument("--device", default=os.getenv("ANDROID_DEVICE_ID"))
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    from mobile_client import MobileCliError
    from mobile_runtime import MobileSessionBusy, ensure_server, mobile_session_lock
    from tiktok_human import HumanClient, HumanProfile, Pace
    from tiktok_mobile_interact import MY_HANDLE, TikTokMobileAdapter, TikTokMobileChallenge, TikTokTargetNotFound, TikTokWrongAccount
    from tiktok_mobile_nav import TikTokNavigator

    left = cooldown_left()
    if left > 0:
        print(f"[bulk] en descanso por el aviso de TikTok: faltan {left:.0f} min; se omite el seguimiento masivo")
        return 0
    cfg = load_config()
    done, today_n = followed_before()
    ceiling = int((cfg.get("action_ceiling") or {}).get("follow", 400))
    budget = min(args.max_follows, max(0, ceiling - today_n))
    if budget <= 0:
        print(f"[bulk] techo diario de follows alcanzado ({today_n}/{ceiling})")
        return 0
    try:
        seeds_log = json.load(open(SEEDS_PATH, encoding="utf-8"))
    except (OSError, ValueError):
        seeds_log = {}
    rng = random.Random()
    profile = HumanProfile(**cfg["human"]) if cfg.get("human") else HumanProfile()
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    try:
        with mobile_session_lock():
            raw = ensure_server(device_id=args.device)
            client = HumanClient(raw, profile, rng)
            adapter = TikTokMobileAdapter(client, args.device, allow_writes=True)
            nav = TikTokNavigator(adapter)
            adapter.verify_active_account(MY_HANDLE)
            sess = Session(nav, Pace(profile, rng), rng, max_follows=budget, deadline=time.time() + args.max_minutes * 60, done=done)
            try:
                if "followback" in modes and not sess.over:
                    read, back = followback_own(sess)
                    print(f"[bulk] follow-back a nuevos seguidores: {read} filas, {back} follows", flush=True)
                if "mutual" in modes and not sess.over:
                    for query in rng.sample(MUTUAL_QUERIES, min(8, len(MUTUAL_QUERIES))):
                        if sess.over:
                            break
                        try:
                            n = mine_mutual(sess, query)
                        except TikTokTargetNotFound as exc:
                            print(f"(consulta {query!r} omitida: {str(exc)[:80]})", flush=True)
                            continue
                        print(f"[bulk] «{query}»: {n} follows", flush=True)
                if "followers" in modes and not sess.over:
                    for seed in ([x.strip() for x in args.seeds.split(",") if x.strip()] or pick_seeds(cfg, seeds_log, 12)):
                        if sess.over:
                            break
                        try:
                            read, mine = mine_followers(sess, seed, args.per_seed)
                        except TikTokTargetNotFound as exc:
                            print(f"(semilla @{seed} omitida: {str(exc)[:80]})", flush=True)
                            continue
                        entry = seeds_log.setdefault(seed, {})
                        entry.update({"last": datetime.date.today().isoformat(), "mined": mine, "rows": read})
                        print(f"[bulk] semilla @{seed}: {read} filas, {mine} follows", flush=True)
            finally:
                try:
                    nav.return_to_feed()
                except Exception:
                    pass
                with open(SEEDS_PATH, "w", encoding="utf-8") as stream:
                    json.dump(seeds_log, stream, ensure_ascii=False, indent=1)
            print(f"[bulk] sesion terminada: {sess.followed} follows nuevos (hoy ya {today_n} antes de la sesion)")
    except MobileSessionBusy:
        print("MobileSessionBusy: el movil lo usa otra sesion; se omite el seguimiento masivo")
    except RateLimited as exc:
        print(f"PARADA TIKTOK: {exc}; descanso de {start_cooldown()} min")
        return 0
    except StopSession as exc:
        print(f"PARADA TIKTOK: {exc}")
        return 0
    except (TikTokMobileChallenge, TikTokWrongAccount, MobileCliError) as exc:
        print(f"PARADA TIKTOK: {exc}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:                       # nunca tumba la ronda
        print(f"FALLO bulk: {type(exc).__name__}: {str(exc)[:160]}")
        raise SystemExit(0)

"""TikTok: revisar a quien seguimos y dejar de seguir a extranjeros/bots (04/10/2026, David).

David: "he seguido a mucha gente para hacer crecer la cuenta (y crece con esa tecnica), pero son muchos bots o ingleses...
unfollow a quien no sea espanol, bot o no nos aporte; amigos y gente real se quedan". La web publica de cada perfil
(`tiktok.com/@usuario`) trae en su JSON el idioma de la cuenta, biografia y cifras: se leen por HTTP simple (sin
navegador, sin captcha), con pausa entre peticiones y cache reanudable.

    python tools/tiktok_following_audit.py collect            # (navegador, lectura) lista de seguidos -> cache/following.json
    python tools/tiktok_following_audit.py enrich [--max N]   # (HTTP) idioma/bio/cifras de cada uno -> cache/profiles.json
    python tools/tiktok_following_audit.py classify           # -> audit.json + resumen: keep / unfollow con motivo
    python tools/tiktok_following_audit.py relations --following ... --registro ... --inbound ... --observed-on YYYY-MM-DD
    # PR39: el comando 'unfollow' queda bloqueado mientras no exista aprobación y verificación humana.

Conserva: cuentas en espanol (idioma `es`, o biografia claramente en espanol) con aspecto de persona real, las que ya tienen
interaccion nuestra en el registro, y las de `KEEP_HANDLES`. Quita: otro idioma, bots (sin videos y con muchisimo seguidos,
`userNNNNNNNN`, 0 seguidores...), ligue/sexo/negocio.
"""
import json
import os
import random
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_TIKTOK")
CACHE = os.path.join(ROOT, "cache")
FOLLOWING_JSON = os.path.join(CACHE, "following.json")
PROFILES_JSON = os.path.join(CACHE, "profiles.json")
AUDIT_JSON = os.path.join(ROOT, "audit.json")
REGISTRO_CSV = os.path.join(ROOT, "registro_interacciones.csv")
KEEP_HANDLES = {"eva.seaman.writer", "hugonaya"}   # cuentas ya valoradas a mano (CUENTAS_VIGILAR.md); David anade aqui amigos

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SPANISH = re.compile(r"\b(el|la|los|las|de|del|que|y|en|un|una|por|con|para|mi|soy|libros?|leer|lectur\w*|escrib\w*|"
                     r"novela\w*|vida|amo|amante|historias?|escritor\w*)\b", re.I)
BUSINESS = re.compile(r"(tienda|shop|store|sorteo|gratis|descuento|casino|crypto|cripto|inversi|trading|forex|"
                      r"dropship|onlyfans|vendo |ventas|whatsapp|wa\.me)", re.I)
DEFAULT_NAME = re.compile(r"^user\d{8,}$", re.I)


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return default


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=1)


# ----------------------------------------------------------------------------------------------------- HTTP
def fetch_profile(handle, timeout=20):
    """Idioma, biografia y cifras de un perfil publico. None si no se puede leer (borrado, privado, bloqueo)."""
    request = urllib.request.Request(f"https://www.tiktok.com/@{handle}",
                                     headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
    try:
        text = urllib.request.urlopen(request, timeout=timeout).read().decode("utf-8", "replace")
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"[:120]}
    match = re.search(r'id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', text, re.S)
    if not match:
        return {"error": "sin datos"}
    try:
        info = json.loads(match.group(1))["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]
        user, stats = info["user"], info["stats"]
    except (ValueError, KeyError):
        return {"error": "perfil no disponible"}
    return {"language": user.get("language"), "bio": (user.get("signature") or "")[:200],
            "nickname": user.get("nickname") or "", "private": bool(user.get("privateAccount")),
            "verified": bool(user.get("verified")), "followers": stats.get("followerCount"),
            "following": stats.get("followingCount"), "videos": stats.get("videoCount")}


# ------------------------------------------------------------------------------------------------ decision
def classify(handle, profile, *, mutual=False, interacted=False, keep=frozenset()):
    """('keep'|'unfollow'|'review', motivo). Pura: se prueba sin red."""
    if handle.casefold() in keep:
        return "keep", "lista de conservar"
    if interacted:
        return "keep", "ya hay interaccion nuestra"
    if not profile or profile.get("error"):
        return "review", f"perfil ilegible ({(profile or {}).get('error', 'sin datos')})"
    lang = (profile.get("language") or "").lower()
    bio = profile.get("bio") or ""
    text = f"{bio} {profile.get('nickname', '')}"
    followers, following, videos = profile.get("followers") or 0, profile.get("following") or 0, profile.get("videos") or 0
    spanish_text = len(SPANISH.findall(bio)) >= 2
    if sc.is_political(text):
        return "unfollow", "ligue/sexo/politica en el perfil"
    if BUSINESS.search(bio):
        return "unfollow", "negocio/promocion"
    if DEFAULT_NAME.match(handle) and videos == 0:
        return "unfollow", "cuenta sin nombre ni videos (bot probable)"
    if videos == 0 and following > 1500 and followers < 100:
        return "unfollow", "sin videos y sigue a miles (bot probable)"
    if lang != "es" and not spanish_text:
        return "unfollow", f"no es espanol (idioma={lang or '?'})"
    if lang == "es" or spanish_text:
        if videos == 0 and followers < 20 and not mutual:
            return "unfollow", "sin videos ni seguidores (bot/inactiva)"
        return "keep", "en espanol"
    return "review", "dudosa"


def interacted_handles():
    out = set()
    if os.path.exists(REGISTRO_CSV):
        import csv
        with open(REGISTRO_CSV, encoding="utf-8") as stream:
            for row in csv.reader(stream):
                if len(row) > 1 and row[1].startswith("@") and "comment" in ",".join(row[2:4]).lower():
                    out.add(row[1].lstrip("@").casefold())
    return out


# ---------------------------------------------------------------------------------------------- commands
_COLLECT_JS = """() => {
  const pop = document.querySelector('[data-e2e="follow-info-popup"]');
  if (!pop) return null;
  const rows = [];
  pop.querySelectorAll('li, [data-e2e="user-item"], div[class*="DivUserContainer"]').forEach(li => {
    const a = li.querySelector('a[href^="/@"]');
    if (!a) return;
    const handle = a.getAttribute('href').replace(/^\\/@/, '').split('/')[0].split('?')[0];
    const btn = li.querySelector('button');
    rows.push({handle, status: btn ? btn.innerText.trim() : ''});
  });
  return rows;
}"""
_SCROLL_JS = """() => {
  const pop = document.querySelector('[data-e2e="follow-info-popup"]');
  let box = null;
  pop.querySelectorAll('*').forEach(e => { if (!box && e.scrollHeight > e.clientHeight + 40 && getComputedStyle(e).overflowY !== 'visible') box = e; });
  if (!box) return -1;
  box.scrollTop = box.scrollHeight;
  return box.scrollHeight;
}"""


def collect():
    import action_ledger as al
    import tiktok_interact as tt
    with al.browser_session():
        p, pg = tt._connect()
        try:
            tt._dump_profile(pg)
            tt._assert_active_account(pg)
            pg.locator('[data-e2e="following"]').first.click()
            pg.wait_for_timeout(3000)
            seen, stale = {}, 0
            for _ in range(400):
                tt._check_bot_warning(pg)
                rows = pg.evaluate(_COLLECT_JS)
                if rows is None:
                    raise RuntimeError("no se abrio la lista de seguidos")
                before = len(seen)
                for row in rows:
                    seen.setdefault(row["handle"], row["status"])
                stale = stale + 1 if len(seen) == before else 0
                if stale >= 6:
                    break
                pg.evaluate(_SCROLL_JS)
                pg.wait_for_timeout(random.randint(900, 1800))
            _save(FOLLOWING_JSON, [{"handle": h, "status": s} for h, s in seen.items()])
            print(f"seguidos leidos: {len(seen)}")
        finally:
            p.stop()


def enrich(max_n=None):
    following = _load(FOLLOWING_JSON, [])
    profiles = _load(PROFILES_JSON, {})
    todo = [f["handle"] for f in following if f["handle"] not in profiles or profiles[f["handle"]].get("error")]
    if max_n:
        todo = todo[:max_n]
    print(f"por leer: {len(todo)} (ya en cache: {len(profiles)})")
    errors = 0
    for index, handle in enumerate(todo, 1):
        profiles[handle] = fetch_profile(handle)
        errors = errors + 1 if profiles[handle].get("error") else 0
        if index % 25 == 0:
            _save(PROFILES_JSON, profiles)
            print(f"  {index}/{len(todo)}")
        if errors >= 15:
            print("demasiados errores seguidos: parece un bloqueo temporal, se para (reanudable)")
            break
        time.sleep(random.uniform(1.2, 2.8))
    _save(PROFILES_JSON, profiles)


def run_classify():
    following = _load(FOLLOWING_JSON, [])
    profiles = _load(PROFILES_JSON, {})
    interacted = interacted_handles()
    audit, counts = [], {}
    for item in following:
        handle = item["handle"]
        verdict, why = classify(handle, profiles.get(handle), mutual=item.get("status", "").lower() in ("amigos", "friends"),
                                interacted=handle.casefold() in interacted, keep=frozenset(KEEP_HANDLES))
        audit.append({"handle": handle, "verdict": verdict, "why": why, "status": item.get("status")})
        counts[verdict] = counts.get(verdict, 0) + 1
    _save(AUDIT_JSON, audit)
    reasons = {}
    for row in audit:
        reasons[(row["verdict"], row["why"].split(" (")[0])] = reasons.get((row["verdict"], row["why"].split(" (")[0]), 0) + 1
    print(f"seguidos: {len(audit)} | {counts}")
    for (verdict, why), n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {verdict:9s} {n:4d}  {why}")
    return audit


def _open_following(pg, tt):
    tt._dump_profile(pg)
    tt._assert_active_account(pg)
    pg.locator('[data-e2e="following"]').first.click()
    pg.wait_for_timeout(3000)


def _popup_rows(pg):
    seen = {}
    for row in pg.evaluate(_COLLECT_JS) or []:
        seen.setdefault(row["handle"], row)   # el selector casa li y su contenedor interno: una fila por cuenta
    return list(seen.values())


def _click_unfollow(pg, tt, handle):
    """Pulsa el boton de la fila del popup y confirma que pasa a 'Seguir'. Devuelve el resultado."""
    row = pg.locator('[data-e2e="follow-info-popup"] li').filter(has=pg.locator(f'a[href="/@{handle}"]')).first
    if row.count() == 0:
        return "no_en_lista"
    button = row.locator("button").first
    if button.count() == 0:
        return "sin_boton"
    state = button.inner_text().strip()
    if state in ("Seguir", "Follow", "Seguir también"):
        return "ya_no_seguido"
    tt._check_bot_warning(pg)            # captcha visible = parar ANTES de tocar nada
    button.scroll_into_view_if_needed()
    button.click()
    pg.wait_for_timeout(1200)
    confirm = pg.get_by_role("button", name=re.compile(r"^(Dejar de seguir|Unfollow)$", re.I))
    if confirm.count():
        confirm.first.click()
        pg.wait_for_timeout(1000)
    tt._check_bot_warning(pg)
    after = button.inner_text().strip() if button.count() else "Seguir"
    return "ok" if after in ("Seguir", "Follow", "Seguir también") else f"no_confirmado:{after}"


def unfollow(max_n=30):
    """TikTok solo deja leer ~30 seguidos por apertura de la lista (la paginacion web no carga mas), asi que se
    trabaja por pasadas: se leen las 30 filas, se clasifican (HTTP) y se quitan las marcadas; al reabrir aparecen las
    siguientes. Para al llegar a `max_n`, sin marcadas en pantalla, o ante cualquier aviso/captcha."""
    # PR39: no hay autorización de unfollow. Este script permanece legible
    # para auditoría histórica pero NO puede hacer escrituras remotas.
    raise PermissionError("PR39: unfollow bloqueado; solo informe hasta aprobación humana explícita")
    import action_ledger as al
    import circuit_breaker as cb
    import tiktok_interact as tt
    allowed, why = cb.check(ROOT)
    if not allowed:
        print(f"cortacircuitos de TikTok ABIERTO, no se actua: {why} (reset: python tools/circuit_breaker.py tiktok reset)")
        return
    profiles = _load(PROFILES_JSON, {})
    interacted = interacted_handles()
    log = _load(os.path.join(CACHE, "unfollow_log.json"), [])
    tried = {row["handle"] for row in log}
    done = 0
    with al.browser_session():
        p, pg = tt._connect()
        try:
            _open_following(pg, tt)
            for round_no in range(1, 40):
                tt._check_bot_warning(pg)
                rows = _popup_rows(pg)
                for row in rows:
                    if row["handle"] not in profiles or profiles[row["handle"]].get("error"):
                        profiles[row["handle"]] = fetch_profile(row["handle"])
                        time.sleep(random.uniform(1.0, 2.2))
                _save(PROFILES_JSON, profiles)
                flagged = []
                for row in rows:
                    verdict, why = classify(row["handle"], profiles.get(row["handle"]),
                                            mutual=row["status"].lower() in ("amigos", "friends"),
                                            interacted=row["handle"].casefold() in interacted, keep=frozenset(KEEP_HANDLES))
                    if verdict == "unfollow" and row["handle"] not in tried:
                        flagged.append((row["handle"], why))
                print(f"pasada {round_no}: {len(rows)} filas, {len(flagged)} para dejar de seguir")
                if not flagged:
                    print("sin marcadas en pantalla: fin (el resto de la lista no es accesible desde la web o ya esta limpio)")
                    break
                for handle, why in flagged:
                    if done >= max_n:
                        break
                    try:
                        result = _click_unfollow(pg, tt, handle)
                    except tt.BotWarningDetected as exc:
                        print(f"PARADA TOTAL: {exc}")
                        _save(os.path.join(CACHE, "unfollow_log.json"), log)
                        cb.record(ROOT, False, signal="auth", reason="captcha/verificacion de TikTok")
                        return
                    tried.add(handle)
                    log.append({"handle": handle, "why": why, "result": result, "date": time.strftime("%Y-%m-%d")})
                    done += result == "ok"
                    print(f"  @{handle}: {result}  ({why})")
                    _save(os.path.join(CACHE, "unfollow_log.json"), log)
                    sc.pause(25, 60)   # 04/10: con 8-20 s (100 en 30 min) salto el captcha dos veces
                    try:
                        tt._check_bot_warning(pg)
                    except tt.BotWarningDetected as exc:
                        print(f"PARADA TOTAL: {exc}")
                        cb.record(ROOT, False, signal="auth", reason="captcha/verificacion de TikTok")
                        return
                if done >= max_n:
                    break
                _open_following(pg, tt)   # recargar: aparecen las siguientes
            print(f"dejados de seguir: {done}")
        finally:
            p.stop()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(__doc__)
        return 2
    max_n = int(argv[argv.index("--max") + 1]) if "--max" in argv else None
    command = argv[0]
    if command == "collect":
        collect()
    elif command == "enrich":
        enrich(max_n)
    elif command == "classify":
        run_classify()
    elif command == "relations":
        from tiktok_relation_report import main as relation_main
        return relation_main(argv[1:])
    elif command == "unfollow":
        print("PR39: unfollow BLOQUEADO. Utiliza el informe offline 'relations'; no hay aprobación de escritura.")
        return 3
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

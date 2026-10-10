"""Limpieza de a quien seguimos, GENERICA para todas las redes (06/10/2026, David: «a la gente que no nos siguio de vuelta se le hace unfollow, en todas las redes, automatico»).

Una sola logica (reglas, verificacion, registro) y un adaptador por red (como se lista a quien seguimos, como se sabe si nos sigue y como se deja de seguir):
  * bluesky  - API (`getFollows`, `viewer.followedBy`)
  * mastodon - API (`accounts/:id/following`, `relationships`)
  * threads  - navegador (dialogo de Seguidos/Seguidores del perfil y boton «Siguiendo»)
  * x        - navegador (paginas /following y /followers del perfil, indicador «Te sigue» y boton «Siguiendo»)
Para anadir otra red solo hace falta otro adaptador.

Reglas (siempre sobre cuentas que NO nos siguen; si nos siguen no se toca):
  1. **Sin devolver el follow**: follow confirmado por el sistema (registro) de hace >= `NONRECIPROCAL_DAYS` (7) dias. Si hubo reply, mas paciencia.
  2. **Otro idioma**: biografia claramente en otro idioma que el espanol (ingles, aleman, frances, italiano, neerlandes, portugues). David (06/10): «nos orientamos al espanol»; esta
     regla alcanza a TODAS las cuentas seguidas, tambien las que siguio a mano.
Seguridad: justo antes de cada unfollow se COMPRUEBA EN VIVO que la cuenta no nos sigue (las listas de seguidores pueden venir incompletas); cada unfollow confirmado queda en el registro con
tipo `unfollow` (`scan_common.discarded_handles` la excluye para siempre de los scans); tope por ejecucion y pausa humana. Sin `--apply` solo informa.

    python tools/unfollow_cleanup.py bluesky|mastodon|threads|x [--apply] [--max 40] [--days 7]
"""
import contextlib
import csv
import datetime
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import follow_review as fr
import growth_attribution as ga
import growth_policy as gp
import text_common as tc

ROOT = ga.ROOT


def candidates(rows, followers, today, *, days=gp.NONRECIPROCAL_DAYS, following=None):
    """[{account, reason}] a dejar de seguir. `following`: {handle_en_minuscula: biografia} de todo lo que seguimos (para la regla de idioma)."""
    out, seen = [], set()
    for item in fr.review(rows, followers, today, days):
        if "reply" in item["actions"]:
            continue                                        # hubo conversacion: mas paciencia
        out.append({"account": item["account"], "reason": f"no devuelve el follow tras {item['age_days']} dias"})
        seen.add(item["account"].casefold())
    followers_cf = {ga.norm(f).casefold() for f in followers}
    protected = protected_accounts()
    listed = {a.split("@")[0] for a in seen}
    for handle, bio in (following or {}).items():
        bare = handle.split("@")[0]
        if handle in seen or bare in listed or handle in followers_cf or bare in followers_cf or handle in protected or bare in protected:
            continue
        listed.add(bare)
        language = tc.foreign_language(bio or "")
        if language:
            out.append({"account": handle, "reason": f"biografia en otro idioma ({language})"})
    return out


PROTECTED_FILE = os.path.join(ROOT, "00_OPERATIVO", "cuentas_protegidas.txt")


def protected_accounts():
    """Cuentas que David quiere conservar aunque la regla de idioma las marque (una por linea, sin @; las lineas con # se ignoran)."""
    try:
        with open(PROTECTED_FILE, encoding="utf-8") as stream:
            return {line.strip().lstrip("@").casefold() for line in stream if line.strip() and not line.lstrip().startswith("#")}
    except OSError:
        return set()


def _append_registro(net, account, reason, result):
    path = os.path.join(ROOT, f"SISTEMA_DIARIO_{net.upper()}", "registro_interacciones.csv")
    with open(path, "a", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerow([datetime.date.today().isoformat(), "@" + account.lstrip("@"), "unfollow", "", "", result, f"cleanup:{reason}"])


# ------------------------------------------------------------------------------------------------------ adaptadores
class Bluesky:
    name = "bluesky"

    @contextlib.contextmanager
    def session(self):
        yield

    def load(self):
        import bluesky_interact as b
        self.b = b
        did = b._session()["did"]
        following, cursor = {}, None
        for _ in range(40):
            params = {"actor": did, "limit": 100}
            if cursor:
                params["cursor"] = cursor
            data = b._get(b.AUTH_BASE, "app.bsky.graph.getFollows", params)
            for profile in data.get("follows", []):
                following[profile["handle"].casefold()] = f"{profile.get('displayName') or ''} {profile.get('description') or ''}"
            cursor = data.get("cursor")
            if not cursor:
                break
        return following, ga.bluesky_followers()

    def follows_me(self, account):
        profile = self.b._get(self.b.AUTH_BASE, "app.bsky.actor.getProfile", {"actor": account})
        return bool((profile.get("viewer") or {}).get("followedBy"))

    def unfollow(self, account):
        return self.b.unfollow(account)


class Mastodon:
    name = "mastodon"

    @contextlib.contextmanager
    def session(self):
        yield

    def load(self):
        import mastodon_interact as m
        self.m = m
        me = m._get("accounts/verify_credentials")
        following, self.ids = {}, {}
        for account in m.patient(lambda: m.account_neighbors(me["id"], "following", limit=80, max_pages=15)):
            text = m._plain_text(f"{account.get('display_name', '')} {account.get('note', '')}")
            following[account["acct"].casefold()] = text
            for key in {account["acct"].casefold(), account["acct"].split("@")[0].casefold()}:
                self.ids.setdefault(key, account["id"])
        return following, ga.mastodon_followers()

    def _id(self, account):
        key = ga.norm(account).casefold()
        return self.ids.get(key) or self.ids.get(key.split("@")[0])

    def follows_me(self, account):
        account_id = self._id(account) or self.m._resolve_account_id(account)
        rel = self.m.patient(lambda: self.m._get("accounts/relationships", {"id[]": account_id}))
        return bool(rel and rel[0].get("followed_by"))

    def unfollow(self, account):
        return self.m.patient(lambda: self.m.unfollow(account, self._id(account)))


class Threads:
    name = "threads"

    def __init__(self):
        self._followers = set()

    @contextlib.contextmanager
    def session(self):
        import action_ledger
        import threads_interact as t
        self.t = t
        with action_ledger.browser_session(wait_minutes=40):
            t.ensure_browser()
            with t.session() as pg:
                self.pg = pg
                yield

    def load(self):
        t, pg = self.t, self.pg
        _, followers = t.collect_followers(pg, t.MY_HANDLE, passes=30, limit=2000, kind="seguidores")
        _, following_rows = t.collect_followers(pg, t.MY_HANDLE, passes=40, limit=3000, kind="seguidos")
        self._followers = {h.casefold() for h, _, _ in followers}
        return {h.casefold(): f"{name} {bio}" for h, name, bio in following_rows}, self._followers

    def follows_me(self, account):
        handle = ga.norm(account).casefold()
        if handle in self._followers:
            return True
        # La lista de seguidores del diálogo puede devolver 0 elementos por
        # timeout, scroll parcial o límite de lectura. Nunca inferir a partir
        # de su ausencia que la persona NO nos sigue antes de un unfollow.
        pg = self.pg
        pg.goto(f"https://www.threads.com/@{handle}",
                wait_until="domcontentloaded", timeout=50000)
        pg.wait_for_timeout(2200)
        self.t._check_bot_warning(pg)
        self.t._assert_active_account(pg)
        expected = f"https://www.threads.com/@{handle}"
        current = str(pg.url).split("?", 1)[0].rstrip("/")
        if current.casefold() != expected.casefold():
            raise RuntimeError(f"Threads: perfil inesperado al verificar followback de @{handle}")
        info = self.t.profile_info(pg)  # Extrae el indicador «Te sigue» ya implementado
        if not isinstance(info, dict) or info.get("followers") is None:
            # El lector de perfil devuelve followers=None ante fallo del DOM.
            # En una operación destructiva la incertidumbre no es autorización.
            raise RuntimeError(f"Threads: followback no verificable para @{handle}; omitir unfollow")
        return bool(info.get("follows_me"))

    def unfollow(self, account):
        return self.t.unfollow(account.lstrip("@"))


class X:
    name = "x"

    def __init__(self):
        self._followers = set()

    @contextlib.contextmanager
    def session(self):
        import action_ledger
        import x_interact as x
        self.x = x
        with action_ledger.browser_session(wait_minutes=40):
            x.ensure_browser()
            with x.session() as pg:
                self.pg = pg
                yield

    def load(self):
        x, pg = self.x, self.pg
        _, followers = x.collect_followers(pg, x.MY_HANDLE, passes=30, limit=2000, kind="seguidores")
        _, following_rows = x.collect_followers(pg, x.MY_HANDLE, passes=60, limit=3000, kind="seguidos")
        self._followers = {h.casefold() for h, _, _ in followers}
        return {h.casefold(): f"{name} {bio}" for h, name, bio in following_rows}, self._followers

    def follows_me(self, account):
        handle = ga.norm(account).casefold()
        if handle in self._followers:
            return True
        return self.x.follows_me(handle.lstrip("@"))          # comprobacion EN VIVO en el perfil («Te sigue»): la lista de seguidores puede venir incompleta

    def unfollow(self, account):
        return self.x.unfollow(account.lstrip("@"))


ADAPTERS = {"bluesky": Bluesky, "mastodon": Mastodon, "threads": Threads, "x": X}


def run(net, *, apply=False, limit=40, days=gp.NONRECIPROCAL_DAYS, pause=(0.8, 2.5), sleep=time.sleep, adapter=None, out=print):
    """Devuelve (candidatos, hechos, fallos)."""
    adapter = adapter or ADAPTERS[net]()
    try:
        rows = ga.load_registro(os.path.join(ROOT, f"SISTEMA_DIARIO_{net.upper()}", "registro_interacciones.csv"))
    except FileNotFoundError:
        rows = []
    done = failed = 0
    with adapter.session():
        following, followers = adapter.load()
        todo = candidates(rows, followers, datetime.date.today(), days=days, following=following)
        out(f"{net}: {len(todo)} cuentas a dejar de seguir ({len(followers)} seguidores leidos, {len(following)} seguidos); tope {limit}")
        for item in todo:
            if done >= limit:
                break
            out(f"  {item['account']:<42} {item['reason']}")
            if not apply:
                continue
            try:
                if adapter.follows_me(item["account"]):            # comprobacion EN VIVO: la lista de seguidores puede estar incompleta
                    out("    nos sigue (comprobado en vivo): no se toca")
                    continue
                outcome = adapter.unfollow(item["account"])
                if outcome in ("unfollowed", "already"):
                    _append_registro(net, item["account"], item["reason"], "confirmado" if outcome == "unfollowed" else "saltado_ya_no_seguido")
                    done += 1
            except Exception as exc:
                failed += 1
                out(f"    fallo: {type(exc).__name__}: {str(exc)[:100]}")
                if "429" in str(exc) or "RateLimit" in type(exc).__name__ or type(exc).__name__ == "BotWarningDetected":
                    out("    limite o aviso de la red: se para; la siguiente ronda sigue")
                    break
            sleep(random.uniform(*pause))
    return len(todo), done, failed


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv or argv[0] not in ADAPTERS:
        print(__doc__)
        return 2
    apply = "--apply" in argv
    limit = int(argv[argv.index("--max") + 1]) if "--max" in argv else 40
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else gp.NONRECIPROCAL_DAYS
    pause = (6.0, 14.0) if argv[0] in ("threads", "x") else (0.8, 2.5)
    total, done, failed = run(argv[0], apply=apply, limit=limit, days=days, pause=pause)
    print(f"{argv[0]}: {done} unfollow confirmados, {failed} fallos" if apply else "(informe) usa --apply para dejar de seguir")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

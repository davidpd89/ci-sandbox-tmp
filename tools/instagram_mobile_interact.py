"""Backend MOVIL (app Android real) de Instagram, con la misma API funcional que `instagram_interact` (Edge/CDP).

`instagram_execute.py` elige backend con RRSS_INSTAGRAM_BACKEND=mobile; el resto del flujo (techo de calentamiento, registro, metricas)
no cambia. Se apoya en la capa comun del movil (`mobile_client`, `mobile_runtime`, `tiktok_human` para el ritmo humano) y en las paradas
compartidas (`tiktok_safety`, con SU propio fichero de descanso: un aviso de TikTok no para Instagram ni al reves).

Los textos/identificadores de la UI NO son un contrato oficial de Instagram: se verificaron en vivo el 09/10/2026 (app 450.0.0.50.77, es-ES)
y toda ambiguedad falla cerrada. CAPTCHA / checkpoint / "accion bloqueada" => BotWarningDetected (parada total); nunca se resuelve.

Verificado en vivo (solo lectura): deep link https://www.instagram.com/<handle>/ abre el perfil en la app (UrlHandlerActivity);
`action_bar_title` = handle; `profile_header_follow_button` = texto "Seguir" / "Siguiendo" / "Solicitado" y etiqueta "Seguir a <nombre>" /
"Sigues a @<nombre>".
"""
from __future__ import annotations

import os
import re
import sys
import time
import unicodedata
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))
import instagram_interact as web  # noqa: E402  (constantes y validadores compartidos con el backend web)
from mobile_client import MobileCliError, element_center, element_texts, walk_ui  # noqa: E402

PACKAGE = "com.instagram.android"
MY_HANDLE = web.MY_HANDLE
BotWarningDetected = web.BotWarningDetected
AlreadyCommented = web.AlreadyCommented
InteractionsPaused = web.InteractionsPaused
_refuse_if_paused = web._refuse_if_paused
_check_length = web._check_length
_check_spanish_orthography = getattr(web, "_check_spanish_orthography", lambda text: None)
_validated_post_permalink = web._validated_post_permalink

ROOT = os.path.join(os.path.dirname(__file__), "..", "SISTEMA_DIARIO_INSTAGRAM")
COOLDOWN_PATH = os.environ.get("RRSS_INSTAGRAM_COOLDOWN_PATH") or os.path.join(ROOT, "mobile_cooldown.json")

FOLLOW_BUTTON_ID = "profile_header_follow_button"
TITLE_ID = "action_bar_title"
LIKE_BUTTON_ID = "row_feed_button_like"

# Estado del control de relacion -> clave interna.
_RELATION = {
    "seguir": "not_following", "follow": "not_following",
    "seguir tambien": "follows_me", "follow back": "follows_me",
    "siguiendo": "following", "following": "following",
    "solicitado": "requested", "requested": "requested", "pendiente": "requested",     # cuenta privada: tras seguir el boton dice «Pendiente»
}
# Etiquetas de accesibilidad del boton (texto vacio en algunos estados): «Has solicitado seguir a X», «Sigues a @X», «Seguir a X».
_LABEL_PREFIX = (("has solicitado", "requested"), ("you requested", "requested"), ("sigues a", "following"),
                 ("you follow", "following"), ("seguir a", "not_following"), ("follow ", "not_following"))


class InstagramMobileError(RuntimeError):
    pass


class InstagramTargetNotFound(InstagramMobileError):
    pass


class InstagramWrongAccount(InstagramMobileError):
    pass


class InstagramWriteUnverified(InstagramMobileError):
    pass


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def _short_id(element: dict[str, Any]) -> str:
    return str(element.get("identifier") or "").split("/")[-1]


# --------------------------------------------------------------------------------------------------------------------
# Lectura pura del arbol de UI (sin movil): testeable con capturas reales recortadas.
# --------------------------------------------------------------------------------------------------------------------

def app_elements(tree: Any) -> list[dict[str, Any]]:
    """Elementos de la app de Instagram. Fuera barra de estado y notificaciones del sistema (pueden traer datos privados)."""
    out = []
    for element in walk_ui(tree):
        ident = str(element.get("identifier") or "")
        if ident.startswith("com.android.systemui") or ident.startswith("android:id"):
            continue
        texts = element_texts(element)
        if texts and _fold(texts[0]).startswith("notificacion de"):
            continue
        out.append(element)
    return out


def visible_text(tree: Any) -> str:
    return " \n".join(t for el in app_elements(tree) for t in element_texts(el) if t)


def check_warning(tree: Any) -> None:
    """Parada total ante cualquiera de las senales anti-bot de Instagram (lista compartida con el backend web)."""
    blob = _fold(visible_text(tree))
    for signal in web.BOT_WARNING_SIGNALS:
        if _fold(signal) in blob:
            raise BotWarningDetected(f"aviso de Instagram en pantalla: {signal!r}")


def read_profile(tree: Any) -> dict[str, Any]:
    """{handle, relation, button, counts...}. relation=None si no hay cabecera de perfil con control de relacion."""
    handle = None
    button = None
    counts: dict[str, str] = {}
    for element in app_elements(tree):
        ident = _short_id(element)
        if ident == TITLE_ID and element_texts(element):
            handle = element_texts(element)[0].lstrip("@")
        elif ident == FOLLOW_BUTTON_ID:
            button = element
        elif ident.endswith("_value") and ident.startswith("profile_header_familiar_"):
            counts[ident[len("profile_header_familiar_"):-len("_value")]] = (element_texts(element) or [""])[0]
    relation = None
    if button is not None:
        relation = _RELATION.get(_fold(button.get("text")))
        if relation is None:                       # sin texto visible: la etiqueta de accesibilidad decide, solo por prefijos conocidos
            label = _fold(button.get("label"))
            relation = next((rel for prefix, rel in _LABEL_PREFIX if label.startswith(prefix)), None)
    return {"handle": handle, "relation": relation, "button": button, "counts": counts,
            "is_own": any(_fold(t) == "editar perfil" for el in app_elements(tree) for t in element_texts(el))}


def read_post_like_state(tree: Any) -> dict[str, Any]:
    """Estado del boton de like de un post abierto: liked True/False/None y el elemento."""
    for element in app_elements(tree):
        if _short_id(element) == LIKE_BUTTON_ID:
            label = _fold(" ".join(element_texts(element)))
            if label.startswith("ya no me gusta") or label.startswith("unlike"):
                return {"liked": True, "button": element}
            if label.startswith("me gusta") or label.startswith("like"):
                return {"liked": False, "button": element}
            return {"liked": None, "button": element}
    return {"liked": None, "button": None}


# --------------------------------------------------------------------------------------------------------------------
# Adaptador
# --------------------------------------------------------------------------------------------------------------------

class InstagramMobile:
    def __init__(self, client: Any, *, allow_writes: bool = False, human: Any = None, sleep=time.sleep) -> None:
        self.client = client
        self.device = client.select_device(None)
        self.allow_writes = bool(allow_writes)
        self.human = human or client
        self._sleep = sleep

    # -- infraestructura -------------------------------------------------------------------------------------------
    def _tree(self) -> Any:
        tree = self.client.dump_ui(self.device.id)
        check_warning(tree)
        return tree

    def _require_writes(self, action: str) -> None:
        if not self.allow_writes:
            raise InteractionsPaused(f"{action} movil bloqueado: solo el ejecutor con --apply crea el adaptador con escrituras")
        _refuse_if_paused()
        import tiktok_safety as safety
        try:
            safety.require_writable(COOLDOWN_PATH)
        except safety.SafetyBlocked as exc:
            raise BotWarningDetected(f"descanso de seguridad de Instagram activo: {exc}") from exc

    def _open_url(self, url: str) -> None:
        self.client.open_url(url, self.device.id)
        self._sleep(3.5)

    def _assert_foreground(self) -> None:
        app = self.client.foreground_app(self.device.id)
        if app.get("packageName") != PACKAGE:
            raise InstagramMobileError(f"Instagram no esta en primer plano ({app.get('packageName')!r}); posible chooser o cierre de la app")

    # -- lectura ---------------------------------------------------------------------------------------------------
    def open_profile(self, handle: str) -> dict[str, Any]:
        wanted = handle.lstrip("@").casefold()
        self._open_url(f"https://www.instagram.com/{wanted}/")
        self._assert_foreground()
        profile = {}
        for _ in range(3):
            profile = read_profile(self._tree())
            if profile["handle"] and profile["handle"].casefold() == wanted:
                return profile
            self._sleep(2.0)
        if profile.get("handle") and profile["handle"].casefold() != wanted:
            raise InstagramTargetNotFound(f"el perfil abierto es @{profile['handle']} y no @{wanted}")
        raise InstagramTargetNotFound(f"no se pudo abrir el perfil de @{wanted} (inexistente, restringido o sin cargar)")

    def verify_active_account(self, expected: str = MY_HANDLE) -> bool:
        profile = self.open_profile(expected)
        if not profile["is_own"]:
            raise InstagramWrongAccount(f"la app no esta logueada como @{expected}: el perfil no ofrece 'Editar perfil'")
        return True

    # -- escrituras ------------------------------------------------------------------------------------------------
    def follow(self, handle: str) -> str:
        """'followed' | 'already' | 'pending'. Nunca pulsa sobre 'Siguiendo' (abriria el menu de dejar de seguir)."""
        self._require_writes("follow")
        wanted = handle.lstrip("@").casefold()
        profile = self.open_profile(wanted)
        relation = profile["relation"]
        if relation == "following":
            return "already"
        if relation == "requested":
            return "pending"
        if relation not in ("not_following", "follows_me"):
            raise InstagramTargetNotFound(f"control de seguir desconocido en @{wanted}: {relation!r}")
        x, y = element_center(profile["button"])
        self.human.tap(x, y, self.device.id)
        self._sleep(2.0)
        after = {}
        for attempt in range(4):
            after = read_profile(self._tree())      # _tree() ya para ante cualquier aviso / accion bloqueada
            if (after["handle"] or "").casefold() == wanted and after["relation"] in ("following", "requested"):
                return "followed" if after["relation"] == "following" else "pending"
            self._sleep(2.0)
        shown = (after.get("button") or {})
        raise InstagramWriteUnverified(
            f"follow de @{wanted} no quedo confirmado en pantalla (relacion={after.get('relation')!r}, "
            f"boton={shown.get('text')!r}/{shown.get('label')!r})"
        )

    def like(self, permalink: str) -> str:
        """'created' | 'already'. El permalink ya viene validado por `_validated_post_permalink`."""
        self._require_writes("like")
        self._open_url(permalink)
        self._assert_foreground()
        state = {"liked": None, "button": None}
        for _ in range(3):
            state = read_post_like_state(self._tree())
            if state["button"] is not None:
                break
            self._sleep(2.0)
        if state["liked"] is True:
            return "already"
        if state["liked"] is None:
            raise InstagramTargetNotFound("boton de me gusta no localizado o ambiguo en el post")
        x, y = element_center(state["button"])
        self.human.tap(x, y, self.device.id)
        self._sleep(1.8)
        after = read_post_like_state(self._tree())
        if after["liked"] is True:
            return "created"
        raise InstagramWriteUnverified("el me gusta no quedo confirmado en pantalla")

    def comment(self, permalink: str, text: str) -> str:
        raise InstagramMobileError("comentar por la app aun no esta implementado (siguiente PR); el techo de comentarios de la fase actual es 0")


# --------------------------------------------------------------------------------------------------------------------
# API funcional (misma forma que instagram_interact) usada por instagram_execute con RRSS_INSTAGRAM_BACKEND=mobile
# --------------------------------------------------------------------------------------------------------------------
_ADAPTER: InstagramMobile | None = None
_LOCK = None


def ensure_browser() -> None:
    """Toma el turno del movil (exclusivo con TikTok), levanta mobilecli, comprueba cuenta y abre el adaptador con escrituras."""
    global _ADAPTER, _LOCK
    if _ADAPTER is not None:
        return
    import contextlib
    import tiktok_safety as safety
    from mobile_runtime import ensure_server, mobile_session_lock
    try:                                       # antes de tocar el movil: un descanso activo para sin abrir nada
        safety.require_writable(COOLDOWN_PATH)
    except safety.SafetyBlocked as exc:
        raise BotWarningDetected(f"descanso de seguridad de Instagram activo: {exc}") from exc
    from tiktok_human import HumanClient, HumanProfile
    stack = contextlib.ExitStack()
    stack.enter_context(mobile_session_lock())
    try:
        client = ensure_server()
        human = HumanClient(client, HumanProfile())
        adapter = InstagramMobile(client, allow_writes=True, human=human)
        adapter.verify_active_account()
    except BaseException:
        stack.close()
        raise
    _LOCK, _ADAPTER = stack, adapter


def release() -> None:
    global _ADAPTER, _LOCK
    if _LOCK is not None:
        _LOCK.close()
    _ADAPTER, _LOCK = None, None


def _adapter() -> InstagramMobile:
    if _ADAPTER is None:
        ensure_browser()
    return _ADAPTER


def follow(handle: str) -> str:
    return _adapter().follow(handle)


def like(url: str) -> str:
    return _adapter().like(url)


def comment(url: str, text: str) -> str:
    return _adapter().comment(url, text)


def fetch_my_metrics() -> dict[str, str]:
    """posts/seguidores/seguidos del propio perfil leidos en la app (misma forma que el backend web)."""
    profile = _adapter().open_profile(MY_HANDLE)
    counts = profile["counts"]
    return {"posts": counts.get("post_count", "?"), "followers": counts.get("followers", "?"), "following": counts.get("following", "?")}


def record_warning(reason: str) -> None:
    """Deja el descanso de seguridad (24 h) ante un aviso: el siguiente intento lo respeta sin tocar el movil."""
    import tiktok_safety as safety
    safety.restrict(reason, COOLDOWN_PATH)

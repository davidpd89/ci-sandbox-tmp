"""Adaptador nativo TikTok Android sobre mobilecli.

La ruta web/CDP histórica permanece retirada. Esta capa usa únicamente la app
Android real. Por defecto es de solo lectura: cualquier escritura exige crear
TikTokMobileAdapter(..., allow_writes=True), algo que solo debe hacer el executor
tras preflight y --apply.

Los textos de UI son selectores semánticos, no un contrato oficial de TikTok. Toda
ambigüedad falla cerrada. CAPTCHA/verificación => parada total; nunca se resuelve.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
import unicodedata
from typing import Any, Iterable

sys.path.insert(0, os.path.dirname(__file__))
from mobile_client import (  # noqa: E402
    MobileCliClient,
    MobileCliError,
    element_center,
    element_texts,
    walk_ui,
)


MY_HANDLE = "autorademoescritor"
TIKTOK_PACKAGE_CANDIDATES = (
    "com.zhiliaoapp.musically",
    "com.ss.android.ugc.trill",
)
TIKTOK_HOSTS = {"www.tiktok.com", "tiktok.com", "vm.tiktok.com"}

BOT_WARNING_SIGNALS = (
    "verify you're human", "verifica que eres humano", "confirma que eres humano",
    "security verification", "verificación de seguridad", "verificacion de seguridad",
    "unusual activity", "actividad inusual", "suspicious activity",
    "actividad sospechosa", "arrastra el deslizador", "encajar en el puzle",
    "captcha", "temporarily banned", "cuenta suspendida", "this action is limited",
    # throttles documentados por TikTok (restricción de hasta 24 h): parada total
    "demasiado rapido", "demasiado rápido", "too fast", "intentalo de nuevo mas tarde",
    "try again later", "accion limitada", "has alcanzado el limite",
)

# Anuncios/promociones: nunca son objetivo de interacción ni se pulsa su CTA.
AD_SIGNALS = (
    "patrocinado", "anuncio", "sponsored", "publicidad", "promocionado",
    "sugerencia de promocion", "boost oficial", "hacer crecer tu audiencia",
)

ALIASES = {
    "home": ("inicio", "home"),
    "profile": ("perfil", "profile"),
    "for_you": ("para ti", "for you"),
    "following": ("siguiendo", "following"),
    "follow": ("seguir", "follow"),
    "followed": ("siguiendo", "following", "amigos", "friends"),
    "like": ("me gusta", "like"),
    "unlike": ("quitar me gusta", "unlike", "liked", "video con me gusta"),
    "comments": ("comentarios", "comments"),
    "comment_input": (
        "añadir comentario", "agregar comentario", "escribe un comentario",
        "add comment", "write a comment",
    ),
    "post_comment": ("publicar", "enviar", "post", "send"),
    "share": ("compartir", "share"),
    "copy_link": ("copiar enlace", "copy link"),
}


class TikTokMobilePaused(RuntimeError):
    pass


class TikTokMobileChallenge(RuntimeError):
    pass


class TikTokWrongAccount(RuntimeError):
    pass


class TikTokTargetNotFound(RuntimeError):
    pass


class TikTokWriteUnverified(RuntimeError):
    pass


def _norm(value: Any) -> str:
    value = " ".join(str(value or "").strip().casefold().split())
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def _package_of(app: dict[str, Any]) -> str | None:
    for key in ("packageName", "bundleId", "id", "identifier"):
        value = app.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _discover_tiktok_package(client: MobileCliClient, device_id: str) -> str:
    installed = {_package_of(app) for app in client.apps(device_id)}
    installed.discard(None)
    matches = [pkg for pkg in TIKTOK_PACKAGE_CANDIDATES if pkg in installed]
    if len(matches) != 1:
        raise MobileCliError(
            "no se pudo identificar un único paquete TikTok instalado; "
            f"candidatos encontrados={matches}"
        )
    return matches[0]


def _element_values(element: dict[str, Any]) -> list[str]:
    values = element_texts(element)
    for key in ("identifier", "key"):
        value = element.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    return values


def _visible_text(tree: Any) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for element in walk_ui(tree):
        if _foreign_package(element):
            continue  # status bar/notificaciones de otras apps no son contenido TikTok
        for value in _element_values(element):
            folded = _norm(value)
            if folded and folded not in seen:
                seen.add(folded)
                values.append(value)
    return "\n".join(values)


def _check_challenge(tree: Any) -> None:
    text = _norm(_visible_text(tree))
    for signal in BOT_WARNING_SIGNALS:
        if _norm(signal) in text:
            raise TikTokMobileChallenge(
                f"TikTok muestra señal de verificación/bloqueo: {signal!r}; "
                "detener sin interactuar"
            )


def _ui_tree_looks_collapsed(
    elements: list[dict[str, Any]],
    device_info: dict[str, Any],
) -> bool:
    if not elements or len(elements) > 2:
        return False
    screen = device_info.get("screenSize")
    if not isinstance(screen, dict):
        return False
    try:
        screen_area = float(screen["width"]) * float(screen["height"])
    except (KeyError, TypeError, ValueError):
        return False
    if screen_area <= 0:
        return False
    for element in elements:
        rect = element.get("rect")
        if not isinstance(rect, dict):
            continue
        try:
            area = float(rect["width"]) * float(rect["height"])
        except (KeyError, TypeError, ValueError):
            continue
        children = element.get("children")
        if not (isinstance(children, list) and children) and area / screen_area >= 0.90:
            return True
    return False


def _alias_match(value: str, aliases: Iterable[str]) -> bool:
    current = _norm(value)
    for alias in aliases:
        wanted = _norm(alias)
        if current == wanted or current.startswith(wanted + " ") or current.endswith(" " + wanted):
            return True
    return False


def _foreign_package(element: dict[str, Any]) -> bool:
    identifier = element.get("identifier")
    if not isinstance(identifier, str) or ":id/" not in identifier:
        return False
    return identifier.split(":id/", 1)[0] not in TIKTOK_PACKAGE_CANDIDATES


def _semantic_matches(
    tree: Any,
    aliases: Iterable[str],
    *,
    enabled_only: bool = True,
) -> list[dict[str, Any]]:
    out = []
    for element in walk_ui(tree):
        if enabled_only and element.get("enabled") is False:
            continue
        if _foreign_package(element):
            continue  # barra de navegación/estado de Android (p. ej. systemui "Inicio")
        if any(_alias_match(value, aliases) for value in _element_values(element)):
            rect = element.get("rect")
            if isinstance(rect, dict) and rect.get("width", 0) and rect.get("height", 0):
                out.append(element)
    return out


def _prefer_interactive(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evita confundir contadores/labels con el botón que ejecuta la acción."""
    interactive = []
    for item in matches:
        kind = _norm(item.get("type"))
        if any(token in kind for token in (
            "button", "tab", "checkbox", "switch", "edittext", "textfield",
        )):
            interactive.append(item)
    return interactive or matches


def _rect_box(item: dict[str, Any]) -> tuple[float, float, float, float] | None:
    rect = item.get("rect") or {}
    try:
        x, y = float(rect["x"]), float(rect["y"])
        return x, y, x + float(rect["width"]), y + float(rect["height"])
    except (KeyError, TypeError, ValueError):
        return None


def _drop_nested(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """TikTok expone contenedor + TextView hijo con el mismo label y bounds distintos:
    es un único control. Se conserva el contenedor (el pulsable)."""
    boxes = [_rect_box(item) for item in matches]
    keep = []
    for i, item in enumerate(matches):
        inner = boxes[i]
        nested = inner is not None and any(
            j != i and outer is not None and outer != inner
            and outer[0] <= inner[0] and outer[1] <= inner[1]
            and outer[2] >= inner[2] and outer[3] >= inner[3]
            for j, outer in enumerate(boxes)
        )
        if not nested:
            keep.append(item)
    return keep


def _pick_unique(
    tree: Any,
    aliases: Iterable[str],
    *,
    description: str,
    bottom: bool = False,
    device_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    matches = _semantic_matches(tree, aliases)
    if bottom and device_info:
        # Primero la banda inferior (barra de pestañas); si no, "Visualizaciones del perfil" y
        # otros botones de la parte alta ganarían a _prefer_interactive y darían ambigüedad.
        screen = device_info.get("screenSize") or {}
        height = float(screen.get("height") or 0)
        if height > 0:
            bottom_matches = [
                item for item in matches
                if float((item.get("rect") or {}).get("y") or 0)
                + float((item.get("rect") or {}).get("height") or 0) / 2 >= height * 0.65
            ]
            if bottom_matches:
                matches = bottom_matches
    matches = _prefer_interactive(matches)
    # A menudo Android expone padre e hijo con el mismo label y bounds.
    deduped = {}
    for item in matches:
        rect = item.get("rect") or {}
        key = (rect.get("x"), rect.get("y"), rect.get("width"), rect.get("height"))
        deduped.setdefault(key, item)
    matches = _drop_nested(list(deduped.values()))
    if len(matches) != 1:
        raise TikTokTargetNotFound(
            f"{description}: objetivo ausente o ambiguo ({len(matches)} coincidencias)"
        )
    return matches[0]


def _find_comment_box(tree: Any) -> dict[str, Any]:
    """El placeholder real es 'Añadir comentario...' (con puntos, sin espacio): se localiza
    como el único EditText cuyo texto contiene 'comentario'."""
    boxes = [
        e for e in walk_ui(tree)
        if "edittext" in _norm(e.get("type")) and not _foreign_package(e)
        and any("comentario" in _norm(v) or "comment" in _norm(v) for v in _element_values(e))
    ]
    boxes = _drop_nested(boxes)
    if not boxes:
        raise TikTokTargetNotFound("campo de comentario ausente o ambiguo (0)")
    # Con la barra del panel y el campo expandido a la vez, el activo es el más alto de pantalla.
    boxes.sort(key=lambda e: float(e["rect"]["y"]))
    return boxes[0]


def _typed_text(tree: Any) -> str:
    """Texto escrito en el campo de comentario activo (el EditText más alto de pantalla)."""
    boxes = [e for e in walk_ui(tree) if "edittext" in _norm(e.get("type")) and not _foreign_package(e)]
    if not boxes:
        return ""
    boxes.sort(key=lambda e: float(e["rect"]["y"]))
    return (_element_values(boxes[0]) or [""])[0]


def _find_send_button(tree: Any) -> dict[str, Any]:
    """El botón enviar de TikTok es un icono sin label ('@2131…' no estable). Se localiza
    por geometría: Button a la derecha, en la fila bajo el campo de texto ya escrito."""
    try:
        return _pick_unique(tree, ALIASES["post_comment"], description="enviar comentario")
    except TikTokTargetNotFound:
        pass
    boxes = [
        e for e in walk_ui(tree)
        if "edittext" in _norm(e.get("type")) and not _foreign_package(e)
    ]
    if not boxes:
        raise TikTokTargetNotFound("campo de comentario ausente")
    # Con el teclado abierto el árbol expone también la barra de comentario del vídeo, que queda
    # detrás del teclado: el campo activo es el más alto de pantalla.
    boxes.sort(key=lambda e: float(e["rect"]["y"]))
    rect = boxes[0]["rect"]
    bottom = float(rect["y"]) + float(rect["height"])
    row = []
    for element in walk_ui(tree):
        if "button" not in _norm(element.get("type")) or _foreign_package(element):
            continue
        r = element["rect"]
        label = (_element_values(element) or [""])[0]
        unresolved = bool(re.fullmatch(r"@\d+", label.strip())) or _alias_match(label, ALIASES["post_comment"])
        # El enviar es un icono con label '@2131…' (recurso sin resolver); los botones con nombre de la
        # página de debajo (Favoritos, Comentarios, contadores) quedan fuera aunque caigan en la banda.
        if unresolved and float(r["x"]) >= 800 and bottom - 20 <= float(r["y"]) <= bottom + 260:
            row.append(element)
    row = _drop_nested(row)
    if len(row) > 1:
        # Los botones like/no-me-gusta de los comentarios de debajo también son '@id': el enviar es
        # la fila más cercana al campo (la de los comentarios queda >100 px más abajo).
        nearest = min(float(e["rect"]["y"]) for e in row)
        row = [e for e in row if float(e["rect"]["y"]) - nearest < 40]
    if len(row) != 1:
        raise TikTokTargetNotFound(f"botón enviar comentario ausente o ambiguo ({len(row)})")
    return row[0]


def _in_main_video_band(items: list[dict[str, Any]], device_info: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Con dos vídeos visibles (transición del pager) solo vale el principal: sus controles
    laterales viven en la banda ~38–72 % de la altura; los del siguiente caen debajo."""
    height = float(((device_info or {}).get("screenSize") or {}).get("height") or 2400)
    band = [
        i for i in items
        if height * 0.35 <= float((i.get("rect") or {}).get("y", 0)) <= height * 0.72
    ]
    return band or items


def _looks_selected(element: dict[str, Any], unlike_aliases: Iterable[str]) -> bool:
    if element.get("checked") is True or element.get("selected") is True:
        return True
    return any(_alias_match(value, unlike_aliases) for value in _element_values(element))


def _extract_handle(tree: Any) -> str | None:
    candidates = []
    for element in walk_ui(tree):
        for value in _element_values(element):
            for match in re.finditer(r"(?<![\w.])@([A-Za-z0-9._]{2,32})", value):
                handle = match.group(1)
                if handle.casefold() != MY_HANDLE.casefold():
                    candidates.append(handle)
    unique = list(dict.fromkeys(h.casefold() for h in candidates))
    if len(unique) == 1:
        return candidates[0]
    return None


_CAPTION_JUNK = (
    "leer o anadir comentarios", "compartir el video", "sonido", "contiene:", "capcut",
    "este creador ha limitado", "anade o elimina", "dar me gusta", "video con me gusta",
    "ver original", "sound:", "original sound",
)


def _extract_caption(tree: Any, handle: str | None) -> str:
    chrome = {_norm(v) for aliases in ALIASES.values() for v in aliases}
    values = []
    for element in walk_ui(tree):
        if _foreign_package(element):
            continue
        for value in element_texts(element):
            clean = " ".join(value.split())
            norm = _norm(clean)
            if not clean or norm in chrome or clean.startswith("@"):
                continue
            if norm.startswith(("notificacion de", "notification from")):
                continue  # toasts de otras apps expuestos sin identifier
            if handle and norm == _norm(handle):
                continue
            if re.fullmatch(r"[\d\s.,KkMm]+", clean):
                continue
            if norm.startswith(_CAPTION_JUNK) or "visualizaciones de las publicaciones" in norm:
                continue  # controles/etiquetas con texto largo (sonido, compartir, comentarios…), no la caption
            if 8 <= len(clean) <= 1000:
                values.append(clean)
    if not values:
        return ""
    # Una caption útil suele ser el texto no-cromático más informativo.
    return max(dict.fromkeys(values), key=len)


class TikTokMobileAdapter:
    def __init__(
        self,
        client: MobileCliClient,
        device_id: str | None = None,
        *,
        allow_writes: bool = False,
        behavior: Any = None,
    ) -> None:
        self.client = client
        self.behavior = behavior
        self.device = client.select_device(device_id)
        self.package = _discover_tiktok_package(client, self.device.id)
        self.allow_writes = bool(allow_writes)

    def _hook(self, name: str) -> None:
        """Hooks de comportamiento humano (no-op sin `behavior`)."""
        if self.behavior is not None:
            getattr(self.behavior, name)()

    def _require_writes(self, action: str) -> None:
        if not self.allow_writes:
            raise TikTokMobilePaused(
                f"{action} móvil bloqueado: crear el adaptador con allow_writes=True "
                "solo desde el executor tras preflight y --apply"
            )

    def _discard_draft(self) -> None:
        """Borra el borrador del campo de comentario y cierra teclado/panel."""
        try:
            import android_shell
            if android_shell.keyboard_shown():
                self.client._rpc("device.io.keys", {
                    "deviceId": self.client._device(self.device.id), "keys": ["ctrl+a", "backspace"],
                })
                time.sleep(0.4)
                self.client.press("BACK", self.device.id)   # cierra el teclado, no sale de la pantalla
                time.sleep(0.6)
        except Exception:  # noqa: BLE001
            pass

    def _launch(self, *, settle_seconds: float = 1.5) -> None:
        self.client.launch_app(self.package, self.device.id)
        time.sleep(settle_seconds)
        self._assert_foreground()

    def _assert_foreground(self) -> dict[str, Any]:
        foreground = self.client.foreground_app(self.device.id)
        if _package_of(foreground) != self.package:
            raise MobileCliError(
                f"TikTok no quedó confirmado en foreground: {_package_of(foreground)!r}"
            )
        return foreground

    def _tree(self, *, validate_shape: bool = True) -> dict[str, Any]:
        self._assert_foreground()
        tree = self.client.dump_ui(self.device.id)
        _check_challenge(tree)
        elements = list(walk_ui(tree))
        if not elements:
            raise MobileCliError("TikTok expuso un árbol UI vacío")
        if validate_shape:
            info = self.client.device_info(self.device.id)
            if _ui_tree_looks_collapsed(elements, info):
                raise MobileCliError(
                    "árbol UI colapsado a overlay fullscreen (mobilecli#461)"
                )
        return tree

    def readonly_probe(self, *, settle_seconds: float = 2.0) -> dict[str, Any]:
        self._launch(settle_seconds=settle_seconds)
        tree = self._tree()
        screenshot = self.client.screenshot_bytes(self.device.id, max_size=900)
        if not screenshot:
            raise MobileCliError("TikTok abrió pero no se pudo obtener screenshot")
        return {
            "device": self.device,
            "package": self.package,
            "foreground": self.client.foreground_app(self.device.id),
            "element_count": sum(1 for _ in walk_ui(tree)),
            "screenshot_bytes": len(screenshot),
        }

    def verify_active_account(self, expected: str = MY_HANDLE) -> bool:
        from tiktok_mobile_nav import TikTokNavigator
        self._launch()
        TikTokNavigator(self).return_to_feed()  # la pantalla inicial puede ser un perfil/vídeo
        info = self.client.device_info(self.device.id)
        try:
            profile = _pick_unique(
                self._tree(), ALIASES["profile"], description="pestaña Perfil",
                bottom=True, device_info=info,
            )
        except TikTokTargetNotFound:
            # 07/10: una sesion anterior dejo la app en un perfil/lista (sin barra inferior) y `on_feed` lo daba por feed: se reinicia SOLO la app (el login persiste) y se reintenta una vez
            import android_shell
            android_shell.run(["shell", "am", "force-stop", self.package])
            time.sleep(2.0)
            self._launch(settle_seconds=4.0)
            TikTokNavigator(self).return_to_feed()
            profile = _pick_unique(
                self._tree(), ALIASES["profile"], description="pestaña Perfil",
                bottom=True, device_info=info,
            )
        tree = None
        x, y = element_center(profile)
        self.client.tap(x, y, self.device.id)
        time.sleep(1.0)
        tree = self._tree()
        visible = _norm(_visible_text(tree))
        wanted = _norm(expected.lstrip("@"))
        tokens = set(re.findall(r"[a-z0-9._]+", visible))
        if wanted not in tokens and _norm("@" + wanted) not in visible:
            raise TikTokWrongAccount(
                f"no se pudo confirmar @{wanted} en la pantalla Perfil"
            )
        return True

    def open_surface(self, surface: str) -> None:
        if surface not in ("for_you", "following"):
            raise ValueError(f"surface TikTok desconocida: {surface}")
        self._launch()
        tree = self._tree()
        info = self.client.device_info(self.device.id)
        home = _pick_unique(
            tree, ALIASES["home"], description="pestaña Inicio",
            bottom=True, device_info=info,
        )
        x, y = element_center(home)
        self.client.tap(x, y, self.device.id)
        time.sleep(0.6)
        tree = self._tree()
        target = _pick_unique(
            tree, ALIASES[surface], description=f"surface {surface}"
        )
        x, y = element_center(target)
        self.client.tap(x, y, self.device.id)
        # El feed Siguiendo tarda ~2 s en cargar tras el tap.
        time.sleep(2.0)
        tree = self._tree()
        # Un banner de notificación in-app puede interceptar el tap (Story, perfil,
        # inbox...). Si ya no estamos en el feed con ambas pestañas, parar cerrado.
        if not all(
            _semantic_matches(tree, ALIASES[name]) for name in ("for_you", "following")
        ):
            self.client.press("BACK", self.device.id)
            raise TikTokTargetNotFound(
                f"surface {surface}: el tap no dejó el feed Inicio (¿banner/popup?); STOP"
            )

    def current_post_snapshot(self, *, source: str) -> dict[str, Any]:
        tree = self._tree()
        handle = _extract_handle(tree)
        caption = _extract_caption(tree, handle)
        visible = _norm(_visible_text(tree))
        return {
            "is_ad": any(signal in visible for signal in AD_SIGNALS),
            "source": source,
            "handle": handle,
            "caption": caption,
            "visible": _visible_text(tree)[:4000],
        }

    def resolve_author_handle(self, *, expect_feed: bool = True) -> str | None:
        """El feed solo muestra el nombre visible; el @handle exacto está en el perfil.

        Abre el perfil del autor desde el avatar, lee `@handle` y vuelve con BACK.
        Solo lectura. Si no queda de vuelta en el feed, STOP.
        """
        tree = self._tree()
        avatars = [
            item for item in _semantic_matches(tree, ("perfil de", "profile of"))
            if str(item.get("identifier") or "").endswith(":id/user_avatar")
        ]
        avatars = _drop_nested(avatars)
        if len(avatars) != 1:
            return None
        x, y = element_center(avatars[0])
        self.client.tap(x, y, self.device.id)
        time.sleep(1.4)
        profile = self._tree(validate_shape=False)
        exact = []
        for element in walk_ui(profile):
            if _foreign_package(element):
                continue
            for value in element_texts(element):
                if re.fullmatch(r"@[A-Za-z0-9._]{2,32}", value.strip()):
                    exact.append(value.strip().lstrip("@"))
        exact = list(dict.fromkeys(exact))
        self.client.press("BACK", self.device.id)
        time.sleep(0.8)
        back = self._tree()
        if expect_feed and not all(
            _semantic_matches(back, ALIASES[n]) for n in ("for_you", "following")
        ):
            raise TikTokTargetNotFound("tras leer el perfil no se volvió al feed; STOP")
        return exact[0] if len(exact) == 1 and exact[0].casefold() != MY_HANDLE.casefold() else None

    # --- referencias de vídeo sin URL (sin hoja de compartir) ---------------------------------
    @staticmethod
    def make_post_ref(handle: str, ordinal: int, caption: str) -> dict[str, Any]:
        cap = _norm(" ".join(caption.split()))[:60]
        digest = hashlib.sha1(cap.encode("utf-8")).hexdigest()[:8]
        return {
            "handle": handle.lstrip("@"), "ordinal": int(ordinal), "cap": cap,
            "id": f"tt://@{handle.lstrip('@')}/{int(ordinal)}/{digest}",
        }

    def open_post_ref(self, ref: dict[str, Any]) -> None:
        """Abre el vídeo `ref` desde el perfil de su autor (como haría una persona): perfil ->
        cuadrícula -> vídeo. Comprueba la caption; si el autor publicó algo nuevo, busca el
        vídeo entre los primeros de la cuadrícula. Nunca usa la hoja de compartir."""
        from tiktok_mobile_nav import TikTokNavigator
        nav = TikTokNavigator(self)
        self.open_profile(ref["handle"])
        time.sleep(1.5)
        profile = nav.read_profile()
        if (profile.get("handle") or "").casefold() != ref["handle"].casefold():
            raise TikTokTargetNotFound(f"perfil inesperado al abrir vídeo: {profile.get('handle')!r}")
        wanted = ref.get("cap") or ""
        for ordinal in [ref["ordinal"]] + [i for i in range(6) if i != ref["ordinal"]]:
            cells = nav.profile_video_cells()
            if ordinal >= len(cells):
                continue
            nav._tap_element(cells[ordinal], 2.2)
            caption = _norm(" ".join(nav.current_caption().split()))
            if not wanted or caption.startswith(wanted[:30]) or wanted[:30] in caption:
                return
            self.client.press("BACK", self.device.id)
            time.sleep(1.0)
        raise TikTokTargetNotFound(f"vídeo de @{ref['handle']} no localizado en su cuadrícula")

    def _open_target(self, target: Any) -> None:
        if isinstance(target, dict):
            self.open_post_ref(target)
        else:
            self._open_tiktok_url(target)

    def copy_current_post_url(self) -> str | None:
        tree = self._tree()
        try:
            share = _pick_unique(tree, ALIASES["share"], description="Compartir")
        except TikTokTargetNotFound:
            return None
        self.client.clipboard_set("", self.device.id)
        x, y = element_center(share)
        self.client.tap(x, y, self.device.id)
        time.sleep(0.6)
        tree = self._tree(validate_shape=False)
        try:
            copy_link = _pick_unique(
                tree, ALIASES["copy_link"], description="Copiar enlace"
            )
        except TikTokTargetNotFound:
            self.client.press("BACK", self.device.id)
            return None
        x, y = element_center(copy_link)
        self.client.tap(x, y, self.device.id)
        # El portapapeles tarda en rellenarse (visto 0.4 s insuficiente en el Xiaomi).
        value = ""
        for _ in range(6):
            time.sleep(0.5)
            value = self.client.clipboard_get(self.device.id).strip()
            if value:
                break
        # Si la hoja de compartir sigue abierta, cerrarla antes del siguiente swipe.
        try:
            after = self._tree(validate_shape=False)
            if _semantic_matches(after, ALIASES["copy_link"]):
                self.client.press("BACK", self.device.id)
                time.sleep(0.2)
        except TikTokMobileChallenge:
            raise
        except Exception:
            pass
        if value.startswith("https://") and "tiktok.com/" in value.casefold():
            return value
        return None

    def swipe_next(self) -> None:
        info = self.client.device_info(self.device.id)
        screen = info.get("screenSize") or {}
        width = int(screen.get("width") or 0)
        height = int(screen.get("height") or 0)
        if width <= 0 or height <= 0:
            raise MobileCliError("no se conocen dimensiones de pantalla")
        self.client.swipe(
            width // 2, int(height * 0.78),
            width // 2, int(height * 0.28),
            duration_ms=550, device_id=self.device.id,
        )
        time.sleep(0.8)
        self._tree()

    def _open_tiktok_url(self, url: str) -> None:
        if not isinstance(url, str) or not re.match(
            r"^https://(?:www\.)?(?:vm\.)?tiktok\.com/", url, re.I
        ):
            raise ValueError("URL TikTok inválida")
        self.client.open_url(url, self.device.id)
        time.sleep(1.2)
        self._assert_foreground()
        self._tree()

    def open_profile(self, handle: str) -> None:
        clean = str(handle or "").strip().lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9._]{2,32}", clean):
            raise ValueError("handle TikTok inválido")
        self._open_tiktok_url(f"https://www.tiktok.com/@{clean}")

    def follow(self, handle: str) -> str:
        """Follow verificado por geometría de perfil (el contador "Siguiendo" mide <190 px;
        el control de relación >=200 px). Exige que el @handle abierto coincida."""
        self._require_writes("follow")
        from tiktok_mobile_nav import TikTokNavigator
        wanted = handle.lstrip("@").casefold()
        self.open_profile(handle)
        time.sleep(1.2)
        nav = TikTokNavigator(self)
        profile = nav.read_profile()
        if (profile.get("handle") or "").casefold() != wanted:
            raise TikTokTargetNotFound(
                f"el perfil abierto es @{profile.get('handle')} y no @{wanted}"
            )
        relation = profile.get("relation")
        if relation in ("following", "friends", "requested"):
            return "already"
        if relation not in ("not_following", "follows_me"):
            raise TikTokTargetNotFound(f"estado del control follow desconocido: {relation!r}")
        self._hook("before_follow")
        # El hojeo previo puede haber movido el perfil: se relee y se usa el control FRESCO.
        for attempt in range(3):
            profile = nav.read_profile()
            if (profile.get("handle") or "").casefold() == wanted:
                break
            if attempt == 0:  # cabecera fuera de pantalla: subir y releer
                self.client.swipe(540, 900, 540, 1700, duration_ms=450, device_id=self.device.id)
                time.sleep(1.0)
            elif attempt == 1:  # sigue sin verse (vídeo/overlay): reabrir el perfil limpio
                self.open_profile(handle)
                time.sleep(1.8)
        if (profile.get("handle") or "").casefold() != wanted:
            raise TikTokTargetNotFound(f"el perfil cambió tras hojearlo: @{profile.get('handle')}")
        if profile.get("relation") in ("following", "friends", "requested"):
            return "already"
        if profile.get("relation") not in ("not_following", "follows_me"):
            raise TikTokTargetNotFound(f"estado del control follow desconocido: {profile.get('relation')!r}")
        x, y = element_center(profile["relation_element"])
        self.client.tap(x, y, self.device.id)
        time.sleep(1.4)
        self._hook("after_follow")
        after = nav.read_profile()
        # Tras el tap el perfil puede tardar en repintarse (o salir un aviso): se vuelve a
        # LEER (nunca a pulsar) hasta 3 veces y, si no, se reabre el perfil limpio.
        for attempt in range(4):
            if (after.get("handle") or "").casefold() == wanted and after.get("relation") in (
                "following", "friends", "requested",
            ):
                return "followed"
            time.sleep(2.0)
            if attempt == 2:
                self.open_profile(handle)
                time.sleep(1.5)
            after = nav.read_profile()
        raise TikTokWriteUnverified(
            f"follow de @{wanted} no quedó confirmado en pantalla (relación={after.get('relation')!r})"
        )

    def like(self, url: Any) -> str:
        self._require_writes("like")
        self._open_target(url)
        tree = self._tree()
        unlike = _prefer_interactive(_semantic_matches(tree, ALIASES["unlike"]))
        if any(_looks_selected(item, ALIASES["unlike"]) for item in unlike):
            return "already"
        import like_context_policy as lcp
        caption = _extract_caption(tree, _extract_handle(tree))
        allowed, reason = lcp.can_like(caption, media_present=True)
        if not allowed:
            raise TikTokTargetNotFound(f"like_contexto:{reason}")
        candidates = _prefer_interactive(_semantic_matches(tree, ALIASES["like"]))
        candidates = [
            item for item in candidates
            if not _looks_selected(item, ALIASES["unlike"])
        ]
        deduped = {}
        for item in candidates:
            rect = item.get("rect") or {}
            deduped.setdefault(
                (rect.get("x"), rect.get("y"), rect.get("width"), rect.get("height")),
                item,
            )
        picked = _in_main_video_band(
            list(deduped.values()), self.client.device_info(self.device.id)
        )
        if len(picked) != 1:
            raise TikTokTargetNotFound(
                f"Me gusta: control ausente o ambiguo ({len(picked)})"
            )
        button = picked[0]
        self._hook("before_like")
        x, y = element_center(button)
        self.client.tap(x, y, self.device.id)
        time.sleep(0.8)
        self._hook("after_like")
        tree = self._tree()
        post_like = _prefer_interactive(_semantic_matches(tree, ALIASES["unlike"]))
        if any(_looks_selected(item, ALIASES["unlike"]) for item in post_like):
            return "created"
        # Algunos builds conservan label "Me gusta" y solo cambian selected/checked.
        for item in _prefer_interactive(_semantic_matches(tree, ALIASES["like"])):
            if item.get("checked") is True or item.get("selected") is True:
                return "created"
        raise TikTokWriteUnverified("like no quedó confirmado; no reintentar automáticamente")

    def comment(self, url: Any, text: str) -> str:
        self._require_writes("comment")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("comentario vacío")
        text = text.strip()
        self._open_target(url)
        tree = self._tree()
        if _norm(text) in _norm(_visible_text(tree)):
            return "already"
        self._hook("before_comment")
        info = self.client.device_info(self.device.id)
        found = _drop_nested(_semantic_matches(tree, ALIASES["comments"]))
        found = _in_main_video_band(found, info)
        if len(found) != 1:
            raise TikTokTargetNotFound(f"Comentarios: objetivo ausente o ambiguo ({len(found)})")
        comments = found[0]
        x, y = element_center(comments)
        self.client.tap(x, y, self.device.id)
        time.sleep(0.6)
        tree = self._tree(validate_shape=False)
        if _norm(text) in _norm(_visible_text(tree)):
            return "already"
        self._hook("comments_opened")
        tree = self._tree(validate_shape=False)
        box = _find_comment_box(tree)
        x, y = element_center(box)
        self.client.tap(x, y, self.device.id)
        self._hook("before_typing")
        self.client.type_text(text, self.device.id)
        time.sleep(0.3)
        try:
            tree = self._tree(validate_shape=False)
            typed = _typed_text(tree)
            if _norm(typed) != _norm(text):
                raise TikTokTargetNotFound(f"el campo no contiene el texto esperado: {typed[:60]!r}")
            send = _find_send_button(tree)
            self._hook("before_send")
            x, y = element_center(send)
        except Exception:
            self._discard_draft()  # nunca dejar texto a medias en el campo
            raise
        self.client.tap(x, y, self.device.id)
        time.sleep(1.0)
        self._hook("after_send")
        tree = self._tree(validate_shape=False)
        _check_challenge(tree)
        if _norm(text) in _norm(_visible_text(tree)):
            return "created"
        raise TikTokWriteUnverified(
            "comentario enviado pero no confirmado en pantalla; parar y revisar, no reintentar"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("probe", "account", "snapshot"))
    parser.add_argument("--device", default=os.getenv("ANDROID_DEVICE_ID"))
    parser.add_argument(
        "--base-url", default=os.getenv("MOBILECLI_URL", "http://127.0.0.1:12000")
    )
    args = parser.parse_args()
    try:
        client = MobileCliClient(base_url=args.base_url, device_id=args.device)
        adapter = TikTokMobileAdapter(client, args.device)
        if args.command == "probe":
            result = adapter.readonly_probe()
            print(
                "TIKTOK MÓVIL READ-ONLY OK: "
                f"{result['device'].model or result['device'].name} | "
                f"{result['package']} | {result['element_count']} elemento(s)"
            )
        elif args.command == "account":
            adapter.verify_active_account()
            print(f"CUENTA TIKTOK OK: @{MY_HANDLE}")
        else:
            adapter._launch()
            print(adapter.current_post_snapshot(source="current"))
        return 0
    except (MobileCliError, TikTokMobileChallenge, TikTokWrongAccount) as exc:
        print(f"TIKTOK MÓVIL PARADO: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

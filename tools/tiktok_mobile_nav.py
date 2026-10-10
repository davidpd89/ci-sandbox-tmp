"""Navegación y lectura (solo lectura) de superficies de descubrimiento de TikTok Android.

Las superficies y etiquetas salen de la inspección real del árbol de accesibilidad en un
Xiaomi con TikTok 47.0.3 (ES) y de `TIKTOK_APP_GUIA_GPT_2026-10-05.md`:

  búsqueda -> pestaña Usuarios  : filas con @handle, nombre, seguidores/me gusta,
                                  prueba social ("Seguido por…") y botón de relación
  búsqueda -> pestaña Vídeos    : tarjetas de vídeo -> abrir -> Comentarios -> comentaristas
  perfil -> Seguidores/Siguiendo/Sugerencias, Reposts ("Vídeos compartidos")

Nada aquí escribe en la cuenta. Los controles de dinero/permisos (Promocionar, Regalo,
Monedas, Tienda, Sincronizar contactos…) están en DENYLIST y nunca se pulsan.
"""
from __future__ import annotations

import re
import time
from typing import Any

import android_shell
from mobile_client import MobileCliError, element_center, element_texts, walk_ui
<<<<<<< HEAD
=======
from mobile_ui_diagnostics import compare as compare_ui_diagnostics, diagnose as diagnose_ui_tree
>>>>>>> origin/research/public-reuse-parent
from tiktok_mobile_interact import (
    ALIASES,
    TikTokMobileAdapter,
    TikTokTargetNotFound,
    _drop_nested,
    _element_values,
    _foreign_package,
    _norm,
    _semantic_matches,
)

# Etiquetas que implican dinero, publicación o permisos: jamás se pulsan.
DENYLIST = (
    "promocionar", "promote", "monedas", "coins", "regalo", "gift", "recargar",
    "recharge", "tienda", "shop", "comprar", "buy", "suscripcion", "subscription",
    "sincronizar contactos", "sync contacts", "ubicacion", "location",
    "pregúntale a la ia", "preguntale a la ia", "tiktok tako", "crear", "publicar video",
)

_BIDI = dict.fromkeys(
    [0x200E, 0x200F, 0x2066, 0x2067, 0x2068, 0x2069, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E],
)
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{2,32}$")

RELATION_LABELS = {
    "seguir": "not_following",
    "follow": "not_following",
    "seguir tambien": "follows_me",
    "follow back": "follows_me",
    "siguiendo": "following",
    "following": "following",
    "amigos": "friends",
    "friends": "friends",
    "solicitado": "requested",
    "requested": "requested",
}


def clean(value: Any) -> str:
    return str(value or "").translate(_BIDI).strip()


def parse_count(text: str) -> int | None:
    """'41,7 mil' -> 41700; '1307' -> 1307; '1,2 M' -> 1200000; '2.5K' -> 2500."""
    value = clean(text).replace("\xa0", " ").casefold()
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(mill\.?|mil|m|k|b)?(?![a-z])", value)
    if not match:
        return None
    number = match.group(1)
    suffix = match.group(2)
    if suffix:
        number = number.replace(",", ".")
        factor = {
            "mil": 1_000, "k": 1_000, "m": 1_000_000, "mill": 1_000_000,
            "mill.": 1_000_000, "b": 1_000_000_000,
        }[suffix]
        return int(round(float(number) * factor))
    return int(re.sub(r"[.,]", "", number))


def _is_denied(values: list[str]) -> bool:
    folded = [_norm(v) for v in values]
    return any(deny in value for value in folded for deny in map(_norm, DENYLIST))


def _tiktok_elements(tree: Any) -> list[dict[str, Any]]:
    out = []
    for element in walk_ui(tree):
        if _foreign_package(element):
            continue
        rect = element.get("rect") or {}
        try:
            y = float(rect.get("y"))
        except (TypeError, ValueError):
            continue
        if y < 100:  # barra de estado
            continue
        out.append(element)
    out.sort(key=lambda e: (float(e["rect"]["y"]), float(e["rect"]["x"])))
    return out


def relation_of(label: str) -> str | None:
    return RELATION_LABELS.get(_norm(label))


def parse_user_rows(tree: Any) -> list[dict[str, Any]]:
    """Filas de la pestaña Usuarios de búsqueda.

    El @handle es el único TextView envuelto en marcas bidi (U+2068…U+2069); el nombre
    visible, los contadores y la prueba social no lo están.
    """
    elements = _tiktok_elements(tree)
    anchors = []
    for element in elements:
        for text in element_texts(element):
            if "⁨" in text and _HANDLE_RE.match(clean(text)):
                anchors.append((element, clean(text)))
                break
    rows: list[dict[str, Any]] = []
    for index, (anchor, handle) in enumerate(anchors):
        top = float(anchor["rect"]["y"]) - 40
        bottom = (
            float(anchors[index + 1][0]["rect"]["y"]) - 40
            if index + 1 < len(anchors) else float("inf")
        )
        texts: list[str] = []
        button = None
        for element in elements:
            y = float(element["rect"]["y"])
            if not (top <= y < bottom) or element is anchor:
                continue
            values = [v for v in _element_values(element) if ":id/" not in v]
            if not values:
                continue
            kind = _norm(element.get("type"))
            label = clean(values[0])
            if "button" in kind and relation_of(label):
                button = (element, label)
                continue
            if float(element["rect"]["x"]) < float(anchor["rect"]["x"]) - 5:
                continue
            if "button" in kind and _norm(label) in ("sigue a",):
                continue
            texts.append(clean(element_texts(element)[0] if element_texts(element) else label))
        name = texts[0] if texts else ""
        extras = texts[1:]
        followers = likes = None
        proof = None
        for line in extras:
            low = _norm(line)
            if "seguidores" in low or "followers" in low:
                parts = re.split(r"[·•]", line)
                followers = parse_count(parts[0])
                for part in parts[1:]:
                    if "me gusta" in _norm(part) or "likes" in _norm(part):
                        likes = parse_count(part)
            elif low.startswith(("seguido por", "es amigo", "sigue a", "followed by", "friend")):
                proof = line
        rows.append({
            "handle": handle,
            "name": name,
            "bio_line": extras[0] if extras and not proof and followers is None else "",
            "followers": followers,
            "likes": likes,
            "proof": proof,
            "relation": relation_of(button[1]) if button else None,
            "button": button[0] if button else None,
            "y": float(anchor["rect"]["y"]),
        })
    return rows


class TikTokNavigator:
    """Lectura de superficies sobre un TikTokMobileAdapter ya validado."""

    def __init__(self, adapter: TikTokMobileAdapter) -> None:
        self.a = adapter
        self.c = adapter.client
        self.device = adapter.device

    # --- utilidades de pantalla -------------------------------------------------
    def tree(self, *, validate_shape: bool = False) -> Any:
        return self.a._tree(validate_shape=validate_shape)

<<<<<<< HEAD
=======
    def diagnose_current_ui(self, *, reference: dict[str, Any] | None = None) -> dict[str, Any]:
        """Observe one UI tree without taps, raw text, screenshots or persistence.

        Optional reference is a schema-1 diagnostic, never a raw screenshot.
        """
        snapshot = diagnose_ui_tree(self.tree(validate_shape=True))
        if reference is None:
            return snapshot
        return {"snapshot": snapshot, "comparison": compare_ui_diagnostics(reference, snapshot)}

>>>>>>> origin/research/public-reuse-parent
    def _tap_element(self, element: dict[str, Any], wait: float = 1.2) -> None:
        values = _element_values(element)
        if _is_denied(values):
            raise TikTokTargetNotFound(f"control en denylist, no se pulsa: {values[:1]}")
        x, y = element_center(element)
        self.c.tap(x, y, self.device.id)
        time.sleep(wait)

    def on_feed(self, tree: Any | None = None) -> bool:
        tree = tree or self.tree()
        return all(_semantic_matches(tree, ALIASES[n]) for n in ("for_you", "following"))

    def return_to_feed(self, *, max_back: int = 12) -> None:
        for _ in range(max_back):
            try:
                if self.on_feed():
                    return
            except MobileCliError:
                focus = android_shell.foreground_component().lower()
                if "permissioncontroller" in focus or "packageinstaller" in focus:
                    # Diálogo de permisos (contactos, notificaciones…): BACK = denegar. Nunca aceptar.
                    self.c.press("BACK", self.device.id)
                    time.sleep(1.0)
                else:
                    self.a._launch()
                continue
            current = self.tree()
            if android_shell.keyboard_shown():
                # Teclado realmente abierto: las coordenadas de 'Inicio' caen sobre las teclas y
                # el tap escribiría letras ("GT GT"). Cerrarlo (y limpiar el borrador) primero.
                self.a._discard_draft()
                continue
            home = [
                e for e in _semantic_matches(current, ALIASES["home"])
                if float(e["rect"]["y"]) > 2000
            ]
            home = _drop_nested(home)
            if len(home) == 1:  # pestañas Mensajes/Amigos/Perfil: volver con Inicio
                self._tap_element(home[0], 1.5)
                continue
            self.c.press("BACK", self.device.id)
            time.sleep(1.0)
        # 07/10: una ronda cortada dejo la app en una pila profunda de perfiles/videos y 12 BACK no bastaron (las rondas se saltaban con el movil libre): ultimo recurso,
        # reiniciar SOLO la app de TikTok (la sesion y el login persisten) y comprobar el feed una vez mas
        try:
            android_shell.run(["shell", "am", "force-stop", self.a.package])
            time.sleep(2.0)
            self.a._launch(settle_seconds=4.0)
            time.sleep(2.0)
            if self.on_feed():
                return
        except (MobileCliError, TikTokTargetNotFound, RuntimeError):
            pass
        raise TikTokTargetNotFound("no se pudo volver al feed de Inicio; STOP")

    def on_search_results(self, tree: Any | None = None) -> bool:
        tree = tree or self.tree()
        has = lambda label: bool(_semantic_matches(tree, (label,)))  # noqa: E731
        return has("Usuarios") and has("Vídeos")

    def back_to_results(self, *, max_back: int = 6) -> None:
        for _ in range(max_back):
            if self.on_search_results():
                return
            self.c.press("BACK", self.device.id)
            time.sleep(1.0)
        raise TikTokTargetNotFound("no se pudo volver a los resultados de búsqueda; STOP")

    def scroll_down(self, fraction: float = 0.55) -> None:
        info = self.c.device_info(self.device.id)
        screen = info.get("screenSize") or {}
        width, height = int(screen.get("width") or 0), int(screen.get("height") or 0)
        if width <= 0 or height <= 0:
            raise MobileCliError("no se conocen dimensiones de pantalla")
        top = int(height * (0.78 - fraction))
        self.c.swipe(width // 2, int(height * 0.78), width // 2, max(top, int(height * 0.2)),
                     duration_ms=450, device_id=self.device.id)
        time.sleep(0.9)

    # --- búsqueda ----------------------------------------------------------------
    def search(self, query: str, tab: str = "Usuarios") -> None:
        """Abre Buscar, escribe `query`, ejecuta y selecciona la pestaña `tab`."""
        if not query or len(query) > 80:
            raise ValueError("consulta inválida")
        self.a._launch()
        self.return_to_feed()
        tree = self.tree()
        search_btn = [
            e for e in _semantic_matches(tree, ("buscar", "search"))
            if float(e["rect"]["y"]) < 300 and float(e["rect"]["x"]) > 800
        ]
        search_btn = _drop_nested(search_btn)
        if len(search_btn) != 1:
            raise TikTokTargetNotFound(f"botón Buscar del feed ambiguo ({len(search_btn)})")
        self._tap_element(search_btn[0], 1.2)
        tree = self.tree()
        boxes = [
            e for e in walk_ui(tree)
            if "edittext" in _norm(e.get("type")) and not _foreign_package(e)
        ]
        if len(boxes) != 1:
            raise TikTokTargetNotFound(f"campo de búsqueda ambiguo ({len(boxes)})")
        self._tap_element(boxes[0], 0.6)  # sin enfocar el campo, el texto va al teclado
        self.c.type_text(query, self.device.id)
        time.sleep(0.8)
        tree = self.tree()
        go = [
            e for e in _semantic_matches(tree, ("buscar", "search"))
            if "button" in _norm(e.get("type")) and float(e["rect"]["y"]) < 300
        ]
        go = _drop_nested(go)
        if len(go) != 1:
            raise TikTokTargetNotFound(f"botón ejecutar búsqueda ambiguo ({len(go)})")
        self._tap_element(go[0], 2.2)
        self.select_search_tab(tab)

    def select_search_tab(self, tab: str) -> None:
        tree = self.tree()
        wanted = [
            e for e in _semantic_matches(tree, (tab,))
            if "framelayout" in _norm(e.get("type")) and 200 < float(e["rect"]["y"]) < 330
        ]
        wanted = _drop_nested(wanted)
        if len(wanted) != 1:
            raise TikTokTargetNotFound(f"pestaña de resultados {tab!r} ausente o ambigua")
        self._tap_element(wanted[0], 1.8)
        self._wait_results(tab)

    def _wait_results(self, tab: str, *, timeout: float = 14.0) -> None:
        """Espera a que la pestaña tenga contenido (la página a veces se queda en blanco/spinner).
        Si no carga, reintenta UNA vez tocando de nuevo la pestaña y, si no, abandona esa query."""
        for attempt in range(2):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                tree = self.tree()
                if _norm(tab) == "usuarios" and parse_user_rows(tree):
                    return
                if _norm(tab) in ("videos", "vídeos") and self.video_cards():
                    return
                if _norm(tab) not in ("usuarios", "videos", "vídeos"):
                    return
                time.sleep(1.5)
            if attempt == 0:
                other = "Vídeos" if _norm(tab) == "usuarios" else "Usuarios"
                for label in (other, tab):  # alternar pestaña fuerza la recarga
                    found = _drop_nested([
                        e for e in _semantic_matches(self.tree(), (label,))
                        if "framelayout" in _norm(e.get("type")) and 200 < float(e["rect"]["y"]) < 330
                    ])
                    if len(found) == 1:
                        self._tap_element(found[0], 1.8)
        raise TikTokTargetNotFound(f"los resultados de {tab!r} no cargan; se abandona esta consulta")

    def autocomplete(self, prefix: str) -> list[str]:
        """Sugerencias de autocompletado para `prefix` (expansión de queries)."""
        self.a._launch()
        self.return_to_feed()
        tree = self.tree()
        search_btn = _drop_nested([
            e for e in _semantic_matches(tree, ("buscar", "search"))
            if float(e["rect"]["y"]) < 300 and float(e["rect"]["x"]) > 800
        ])
        if len(search_btn) != 1:
            raise TikTokTargetNotFound("botón Buscar del feed ambiguo")
        self._tap_element(search_btn[0], 1.2)
        tree = self.tree()
        boxes = [e for e in walk_ui(tree) if "edittext" in _norm(e.get("type"))]
        if len(boxes) != 1:
            raise TikTokTargetNotFound("campo de búsqueda ambiguo")
        self._tap_element(boxes[0], 0.6)
        self.c.type_text(prefix, self.device.id)
        time.sleep(1.5)
        out = []
        for element in _tiktok_elements(self.tree()):
            kind = _norm(element.get("type"))
            if "edittext" in kind or "button" in kind:
                continue
            for text in element_texts(element):
                text = clean(text)
                if text and _norm(text) != _norm(prefix) and 2 < len(text) < 70 and text not in out:
                    if float(element["rect"]["x"]) < 400 and float(element["rect"]["y"]) > 250:
                        out.append(text)
        return out

    def read_user_results(self, *, max_pages: int = 3) -> list[dict[str, Any]]:
        """Lee filas de la pestaña Usuarios con scroll; devuelve filas únicas por handle."""
        seen: dict[str, dict[str, Any]] = {}
        for page in range(max_pages):
            tree = self.tree()
            fresh = 0
            for row in parse_user_rows(tree):
                key = row["handle"].casefold()
                if key not in seen:
                    seen[key] = row
                    fresh += 1
            if page < max_pages - 1:
                if fresh == 0 and page > 0:
                    break
                self.scroll_down()
        return list(seen.values())

    # --- vídeos, comentarios y perfiles ---------------------------------------------
    def video_cards(self) -> list[dict[str, Any]]:
        """Tarjetas de la pestaña Vídeos de búsqueda (rejilla de 2 columnas).

        Cada tarjeta expone un Button con la caption (≈470 px de ancho) y, debajo, un
        Button con el nombre del autor. Tocar la caption abre el vídeo.
        """
        elements = _tiktok_elements(self.tree())
        cards = []
        for i, element in enumerate(elements):
            if "button" not in _norm(element.get("type")):
                continue
            rect = element["rect"]
            width, height = float(rect["width"]), float(rect["height"])
            if not (440 <= width <= 500 and height >= 60):
                continue
            label = clean((_element_values(element) or [""])[0])
            if not label or _is_denied([label]) or _norm(label).startswith(("video de ", "video by ")):
                continue
            x, y = float(rect["x"]), float(rect["y"])
            author = ""
            for other in elements[i + 1:i + 8]:
                orect = other["rect"]
                if "button" in _norm(other.get("type")) and abs(float(orect["x"]) - x) < 120                         and 60 < float(orect["y"]) - y < 160 and float(orect["width"]) < 440:
                    author = clean((_element_values(other) or [""])[0])
                    break
            if not author:
                continue
            cards.append({"label": label, "author": author, "element": element, "y": y})
        return cards

    def open_video(self, card: dict[str, Any]) -> None:
        self._tap_element(card["element"], 2.0)
        if self.a._assert_foreground() is None:
            raise TikTokTargetNotFound("TikTok perdió el foreground")

    def open_comments(self) -> None:
        tree = self.tree()
        target = _drop_nested(_semantic_matches(tree, ALIASES["comments"]))
        if len(target) != 1:
            raise TikTokTargetNotFound(f"botón Comentarios ambiguo ({len(target)})")
        self._tap_element(target[0], 2.0)

    def read_comments(self, *, max_pages: int = 3) -> list[dict[str, Any]]:
        """Comentarios visibles del panel abierto. El 'handle' real exige abrir el perfil."""
        out: dict[tuple[str, str], dict[str, Any]] = {}
        chrome = ("responder", "reply", "ver ", "view ", "ocultar", "hide", "@2131")
        for page in range(max_pages):
            elements = _tiktok_elements(self.tree())
            fresh = 0
            for i, element in enumerate(elements):
                kind = _norm(element.get("type"))
                label = clean((_element_values(element) or [""])[0])
                x = float(element["rect"]["x"])
                if "button" not in kind or not label or not (150 < x < 200):
                    continue
                if _norm(label).startswith(chrome):
                    continue
                y = float(element["rect"]["y"])
                text = ""
                for follower in elements[i + 1:i + 6]:
                    fy = float(follower["rect"]["y"])
                    if 20 < fy - y < 140 and 150 < float(follower["rect"]["x"]) < 200                             and "textview" in _norm(follower.get("type")):
                        text = clean((element_texts(follower) or [""])[0])
                        break
                if not text:
                    continue
                key = (label.casefold(), text[:80].casefold())
                if key not in out:
                    out[key] = {"name": label, "text": text, "element": element, "y": y}
                    fresh += 1
            if page < max_pages - 1:
                if fresh == 0 and page > 0:
                    break
                self.scroll_down(0.45)
        return list(out.values())

    def open_commenter_profile(self, comment: dict[str, Any]) -> None:
        self._tap_element(comment["element"], 1.8)

    def read_profile(self) -> dict[str, Any]:
        """Perfil abierto: handle, nombre, contadores, relación y bio visible."""
        elements = _tiktok_elements(self.tree())
        info: dict[str, Any] = {
            "handle": None, "name": "", "following": None, "followers": None, "likes": None,
            "relation": None, "bio": "",
        }
        labels = {
            "siguiendo": "following", "following": "following",
            "seguidores": "followers", "followers": "followers",
            "me gusta": "likes", "likes": "likes",
        }
        bio = []
        for element in elements:
            texts = [clean(t) for t in element_texts(element)]
            if not texts:
                continue
            text = texts[0]
            rect = element["rect"]
            y = float(rect["y"])
            handle_match = re.match(r"@([A-Za-z0-9._]{2,32})(?![A-Za-z0-9._])", text)
            if handle_match and info["handle"] is None and 300 < y < 520:
                info["handle"] = handle_match.group(1)
            elif 230 < y < 400 and "button" in _norm(element.get("type")) and not info.get("name") and not text.startswith("@"):
                info["name"] = text
            elif _norm(text) in labels and 380 < y < 640 and float(rect["height"]) < 80:
                x = float(rect["x"])
                for other in elements:
                    ot = clean((element_texts(other) or [""])[0])
                    if abs(float(other["rect"]["x"]) - x) < 8 and 30 < y - float(other["rect"]["y"]) < 90 and ot:
                        info[labels[_norm(text)]] = parse_count(ot)
                        break
            elif 480 < y < 820 and relation_of(text) and info["relation"] is None:
                # El control mide ~110 px de alto; las etiquetas de contador (Siguiendo/Seguidores) ~41.
                # (El ancho no sirve: "Amigos" mide 179 px.)
                if float(rect["height"]) >= 80:
                    info["relation"] = relation_of(text)
                    info["relation_element"] = element
            elif 680 < y < 1000 and len(text) > 3 and "button" in _norm(element.get("type")):
                bio.append(text)
        info["bio"] = " ".join(bio)[:400]
        return info

    # --- bandeja: nuevos seguidores y cuentas recomendadas ---------------------------
    def open_new_followers(self) -> None:
        self.return_to_feed()
        tabs = _drop_nested([
            e for e in _semantic_matches(self.tree(), ("mensajes", "inbox"))
            if float(e["rect"]["y"]) > 2000
        ])
        if len(tabs) != 1:
            raise TikTokTargetNotFound("pestaña Mensajes ambigua")
        self._tap_element(tabs[0], 2.0)
        # La fila "han empezado a seguirte" desaparece tras visitarla; la estable es
        # "Actividad y nuevos seguidores" -> pestaña superior "Nuevos seguidores".
        row = [
            e for e in _tiktok_elements(self.tree())
            if any(_norm(clean(t)) == "actividad y nuevos seguidores" for t in element_texts(e))
        ]
        if len(row) != 1:
            raise TikTokTargetNotFound(f"fila Actividad y nuevos seguidores ausente/ambigua ({len(row)})")
        self._tap_element(row[0], 2.0)
        tab = _drop_nested([
            e for e in _tiktok_elements(self.tree())
            if any(_norm(clean(t)) == "nuevos seguidores" for t in element_texts(e))
            and float(e["rect"]["y"]) < 300
        ])
        if len(tab) != 1:
            raise TikTokTargetNotFound(f"pestaña Nuevos seguidores ausente/ambigua ({len(tab)})")
        self._tap_element(tab[0], 2.0)

    def read_new_followers(self, *, limit: int = 8) -> list[dict[str, Any]]:
        """Filas de 'Nuevos seguidores': nombre visible, relación y elemento pulsable."""
        elements = _tiktok_elements(self.tree())
        rows = []
        for element in elements:
            kind = _norm(element.get("type"))
            label = (_element_values(element) or [""])[0]
            rect = element["rect"]
            if "button" not in kind or "⁨" not in label or not (200 < float(rect["x"]) < 260):
                continue
            if float(rect["y"]) > 1300:  # sección "Cuentas recomendadas" va aparte
                continue
            y = float(rect["y"])
            relation = None
            for other in elements:
                if "button" in _norm(other.get("type")) and float(other["rect"]["x"]) > 600                         and abs(float(other["rect"]["y"]) - y) < 90:
                    relation = relation_of(clean((_element_values(other) or [""])[0]))
                    if relation:
                        break
            rows.append({"name": clean(label), "relation": relation, "element": element})
        return rows[:limit]

    # --- perfil: cuadrícula de vídeos -------------------------------------------------
    def profile_video_cells(self) -> list[dict[str, Any]]:
        """Celdas `:id/cover` de la cuadrícula del perfil, sin los vídeos anclados."""
        elements = _tiktok_elements(self.tree())
        pinned_y = [
            float(e["rect"]["y"]) for e in elements
            if any(_norm(clean(t)) == "anclado" for t in element_texts(e))
        ]
        cells = []
        for element in elements:
            if not str(element.get("identifier") or "").endswith(":id/cover"):
                continue
            rect = element["rect"]
            x, y = float(rect["x"]), float(rect["y"])
            if y < 950 or float(rect["height"]) < 200:
                continue
            if any(abs(py - y) < 80 for py in pinned_y):
                continue  # los anclados son antiguos; el feed reciente va después
            cells.append(element)
        cells.sort(key=lambda e: (float(e["rect"]["y"]), float(e["rect"]["x"])))
        return cells

    def current_caption(self) -> str:
        """Caption visible del vídeo abierto (texto más largo no cromático)."""
        from tiktok_mobile_interact import _extract_caption
        return _extract_caption(self.tree(), None)

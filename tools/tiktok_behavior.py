"""Coreografía humana de la sesión TikTok: ver, saltar, hojear perfiles, leer comentarios.

`Behavior` se inyecta en `TikTokMobileAdapter(behavior=...)`; el adaptador llama a estos
hooks en los puntos donde una persona se detendría (antes de seguir, antes de dar like,
antes de comentar, tras enviar). Sin `behavior` el adaptador se comporta como siempre
(tests deterministas). Todo el azar sale del `rng` inyectado.
"""
from __future__ import annotations

import random
import time
from typing import Any, Callable

from tiktok_human import Pace


class Behavior:
    def __init__(
        self,
        adapter: Any,
        pace: Pace | None = None,
        rng: random.Random | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.adapter = adapter
        self.pace = pace or Pace()
        self.rng = rng or self.pace.rng
        self._sleep = sleep
        self._clock = clock

    # --- pausas ---------------------------------------------------------------------
    def pause(self, low: float, high: float) -> float:
        seconds = self.rng.uniform(low, high)
        self._sleep(seconds)
        return seconds

    # --- hooks del adaptador ----------------------------------------------------------
    def before_follow(self) -> None:
        """Mira el perfil: lee la bio y, a veces, baja por la cuadrícula; SIEMPRE vuelve arriba
        (el control de seguir y el @handle solo son legibles con la cabecera visible)."""
        self.pause(1.5, 4.5)
        if self.rng.random() < 0.55:
            self._scroll(0.35)
            self.pause(0.8, 2.5)
            self._scroll(-0.35)
            self._scroll(-0.35)   # segundo gesto por si el primero no devolvió la cabecera
            self.pause(0.6, 1.4)

    def after_follow(self) -> None:
        self.pause(1.2, 3.5)

    def watch_video(self) -> None:
        """Ve el vídeo antes de reaccionar: casi nunca menos de unos segundos."""
        kind, seconds = self.pace.video_dwell()
        if kind in ("skip", "short"):
            seconds = self.rng.uniform(3.0, 7.0)  # para reaccionar hay que haberlo visto
        self._sleep(seconds)

    def before_like(self) -> None:
        self.watch_video()

    def after_like(self) -> None:
        self.pause(0.8, 2.2)

    def before_comment(self) -> None:
        self.watch_video()

    def comments_opened(self) -> None:
        """Lee lo que ya hay antes de escribir (y a veces hace scroll)."""
        self.pause(1.5, 4.0)
        if self.rng.random() < 0.45:
            self._scroll(0.3)
            self.pause(1.0, 3.0)
            if self.rng.random() < 0.5:
                self._scroll(-0.3)

    def before_typing(self) -> None:
        self.pause(0.8, 2.6)

    def before_send(self) -> None:
        self._sleep(self.pace.reread())

    def after_send(self) -> None:
        self.pause(1.8, 4.5)

    # --- navegación libre --------------------------------------------------------------
    def _scroll(self, fraction: float) -> None:
        """fraction>0 baja, <0 sube (en listas/perfiles). Silencioso si no se puede."""
        try:
            client = self.adapter.client
            info = client.device_info(self.adapter.device.id)
            screen = info.get("screenSize") or {}
            width, height = int(screen.get("width") or 1080), int(screen.get("height") or 2400)
            span = int(height * abs(fraction))
            mid = int(height * 0.6)
            if fraction > 0:
                y1, y2 = mid + span // 2, mid - span // 2
            else:
                y1, y2 = mid - span // 2, mid + span // 2
            client.swipe(width // 2, y1, width // 2, y2, duration_ms=450, device_id=self.adapter.device.id)
        except Exception:  # noqa: BLE001  (el scroll decorativo nunca debe romper la acción)
            pass

    def recover(self) -> None:
        """Tras un fallo blando: vuelve al feed y respira antes de la siguiente acción."""
        from tiktok_mobile_nav import TikTokNavigator
        TikTokNavigator(self.adapter).return_to_feed()
        self.pause(3.0, 8.0)

    def browse(self, seconds: float, *, max_videos: int = 40) -> int:
        """Ve el feed durante ~`seconds` segundos: salta, ve, a veces vuelve atrás.

        Solo lectura (sin likes/follows). Devuelve cuántos vídeos pasó.
        """
        start = self._clock()
        seen = 0
        while self._clock() - start < seconds and seen < max_videos:
            kind, dwell = self.pace.video_dwell()
            remaining = seconds - (self._clock() - start)
            self._sleep(max(0.2, min(dwell, remaining)))
            seen += 1
            if self._clock() - start >= seconds:
                break
            if self.rng.random() < 0.06:
                self._scroll(-0.5)           # vuelve al vídeo anterior
                self._sleep(self.rng.uniform(1.5, 4.0))
            try:
                self.adapter.swipe_next()
            except Exception:  # noqa: BLE001
                break
        return seen

"""Capa de comportamiento humano para el móvil (taps, gestos, tecleo, ritmo).

Dos piezas:

* `HumanClient` envuelve a `MobileCliClient` y humaniza el *cómo* se hace cada gesto:
  taps con dispersión gaussiana y tiempo de reacción, swipes con deriva y duración variable,
  y tecleo por trozos con ritmo irregular, pausas entre palabras y erratas corregidas.
* `Pace` decide el *cuándo*: pausas log-normales entre acciones, micro-descansos, fatiga a lo
  largo de la sesión y dwell (ver o saltarse un vídeo) con distribución realista.

Nada aquí decide *qué* acción hacer ni la salta: los techos, la verificación y las paradas
siguen en el adaptador y el executor. Todo el azar sale de un `random.Random` inyectable
para que los tests sean deterministas.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any

_ADJACENT = {
    "a": "sqwz", "b": "vghn", "c": "xdfv", "d": "serfcx", "e": "wsdr", "f": "drtgvc",
    "g": "ftyhbv", "h": "gyujnb", "i": "ujko", "j": "huikmn", "k": "jiolm", "l": "kop",
    "m": "njk", "n": "bhjm", "o": "iklp", "p": "ol", "q": "wa", "r": "edft", "s": "awedxz",
    "t": "rfgy", "u": "yhji", "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu", "z": "asx",
}


@dataclass
class HumanProfile:
    """Parámetros del 'usuario'. `light` acelera el scan; `full` es para escrituras."""

    tap_sigma_px: float = 7.0
    tap_clamp_px: float = 16.0
    think_median_s: float = 0.55      # reacción antes de un tap
    think_sigma: float = 0.45
    swipe_duration_ms: tuple[int, int] = (260, 720)
    swipe_drift_px: float = 70.0
    chars_per_sec: float = 5.2        # ~60 palabras/min en móvil
    typing_sigma: float = 0.35
    word_pause_s: tuple[float, float] = (0.15, 0.7)
    typo_rate: float = 0.04           # por palabra de ≥4 letras
    reread_s: tuple[float, float] = (0.9, 3.2)   # relee antes de enviar
    dwell_skip_p: float = 0.50        # vídeos que se saltan casi al instante
    dwell_short_s: tuple[float, float] = (1.5, 5.0)
    dwell_watch_s: tuple[float, float] = (6.0, 22.0)
    dwell_long_s: tuple[float, float] = (22.0, 50.0)
    action_gap_median_s: float = 45.0
    action_gap_sigma: float = 0.65
    micro_break_every: tuple[int, int] = (7, 13)
    micro_break_s: tuple[float, float] = (120.0, 360.0)
    fatigue_per_action: float = 0.012  # el ritmo se va aflojando
    enabled: bool = True

    @classmethod
    def light(cls) -> "HumanProfile":
        return cls(
            think_median_s=0.2, swipe_duration_ms=(220, 520), dwell_skip_p=0.7,
            dwell_short_s=(0.4, 1.2), dwell_watch_s=(1.0, 3.0), dwell_long_s=(2.0, 5.0),
        )

    @classmethod
    def off(cls) -> "HumanProfile":
        return cls(
            tap_sigma_px=0, tap_clamp_px=0, think_median_s=0, swipe_duration_ms=(450, 450),
            swipe_drift_px=0, enabled=False,
        )


def _lognormal(rng: random.Random, median: float, sigma: float) -> float:
    return rng.lognormvariate(math.log(max(median, 1e-6)), sigma) if median > 0 else 0.0


class HumanClient:
    """Proxy de MobileCliClient con gestos humanizados; el resto se delega tal cual."""

    def __init__(
        self,
        client: Any,
        profile: HumanProfile | None = None,
        rng: random.Random | None = None,
        sleep=time.sleep,
    ) -> None:
        self._client = client
        self.profile = profile or HumanProfile()
        self.rng = rng or random.Random()
        self._sleep = sleep
        self.screen = (1080, 2400)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    # --- taps -----------------------------------------------------------------------
    def _jitter(self, value: float) -> int:
        p = self.profile
        if not p.enabled or p.tap_sigma_px <= 0:
            return int(value)
        delta = self.rng.gauss(0, p.tap_sigma_px)
        delta = max(-p.tap_clamp_px, min(p.tap_clamp_px, delta))
        return int(round(value + delta))

    def tap(self, x: int, y: int, device_id: str | None = None) -> Any:
        p = self.profile
        if p.enabled:
            self._sleep(min(_lognormal(self.rng, p.think_median_s, p.think_sigma), 4.0))
        return self._client.tap(self._jitter(x), self._jitter(y), device_id=device_id)

    def long_press(self, x: int, y: int, device_id: str | None = None, duration_ms: int = 600) -> Any:
        return self._client._rpc("device.io.longpress", {
            "deviceId": self._client._device(device_id), "x": self._jitter(x),
            "y": self._jitter(y), "duration": int(duration_ms * self.rng.uniform(0.85, 1.3)),
        })

    # --- swipes ---------------------------------------------------------------------
    def swipe(self, x1: int, y1: int, x2: int, y2: int, *, duration_ms: int | None = None,
              device_id: str | None = None) -> Any:
        p = self.profile
        if p.enabled and p.swipe_drift_px:
            drift = self.rng.uniform(-p.swipe_drift_px, p.swipe_drift_px)
            x1 = int(x1 + self.rng.uniform(-30, 30))
            x2 = int(x2 + drift)
            y1 = int(y1 + self.rng.uniform(-40, 40))
            y2 = int(y2 + self.rng.uniform(-40, 40))
            lo, hi = p.swipe_duration_ms
            duration_ms = int(self.rng.uniform(lo, hi))
        return self._client.swipe(x1, y1, x2, y2, duration_ms=duration_ms, device_id=device_id)

    # --- tecleo ---------------------------------------------------------------------
    def type_text(self, text: str, device_id: str | None = None) -> Any:
        p = self.profile
        if not p.enabled:
            return self._enter(text, device_id)
        result: Any = None
        for kind, chunk in self._typing_plan(text):
            if kind == "pause":
                self._sleep(float(chunk))
            elif kind == "backspace":
                self._client._rpc("device.io.keys", {
                    "deviceId": self._client._device(device_id), "keys": ["backspace"] * int(chunk),
                })
            else:
                result = self._enter(chunk, device_id)
                per_char = _lognormal(self.rng, 1.0 / p.chars_per_sec, p.typing_sigma)
                self._sleep(per_char * len(chunk))
        return result

    def _enter(self, chunk: str, device_id: str | None) -> Any:
        """`input text` de ADB pierde o corrompe tildes, ¿¡ y emojis: lo no-ASCII se pega desde el
        portapapeles (KEYCODE_PASTE) y lo ASCII se teclea."""
        if chunk.isascii():
            return self._client.type_text(chunk, device_id=device_id)
        from android_shell import run
        serial = self._client._device(device_id)
        self._client.clipboard_set(chunk, device_id=serial)
        time.sleep(0.15)
        return run(["shell", "input", "keyevent", "279"], serial=serial)

    def _typing_plan(self, text: str) -> list[tuple[str, Any]]:
        """Plan de tecleo: ('text', trozo) / ('pause', s) / ('backspace', n). Determinista dado rng."""
        p, rng = self.profile, self.rng
        plan: list[tuple[str, Any]] = []
        words = text.split(" ")
        for index, word in enumerate(words):
            piece = word if index == len(words) - 1 else word + " "
            letters = [c for c in word if c.isalpha() and c.lower() in _ADJACENT]
            make_typo = (
                len(word) >= 4 and len(letters) == len(word) and rng.random() < p.typo_rate
            )
            if make_typo:
                pos = rng.randrange(1, len(word) - 1)
                wrong = rng.choice(_ADJACENT[word[pos].lower()])
                plan.append(("text", word[:pos] + wrong))
                plan.append(("pause", rng.uniform(0.25, 0.8)))   # tarda en notar el fallo
                plan.append(("backspace", 1))
                plan.append(("text", word[pos:] + (piece[len(word):])))
            else:
                # trozos de 1–4 caracteres (ráfagas), no letra a letra ni todo de golpe
                i = 0
                while i < len(piece):
                    size = rng.choice((1, 2, 2, 3, 3, 4))
                    plan.append(("text", piece[i:i + size]))
                    i += size
            if index < len(words) - 1:
                plan.append(("pause", rng.uniform(*p.word_pause_s)))
        return plan


class Pace:
    """Ritmo de sesión: pausas entre acciones, descansos y dwell de visionado."""

    def __init__(self, profile: HumanProfile | None = None, rng: random.Random | None = None) -> None:
        self.profile = profile or HumanProfile()
        self.rng = rng or random.Random()
        self.actions = 0
        self._next_break = self.rng.randint(*self.profile.micro_break_every)

    @property
    def fatigue(self) -> float:
        return 1.0 + self.actions * self.profile.fatigue_per_action

    def action_gap(self) -> float:
        p = self.profile
        base = _lognormal(self.rng, p.action_gap_median_s, p.action_gap_sigma) * self.fatigue
        return max(4.0, min(base, 6 * p.action_gap_median_s))

    def register_action(self) -> float | None:
        """Cuenta una acción; devuelve la duración de un micro-descanso si toca."""
        self.actions += 1
        if self.actions >= self._next_break:
            self._next_break = self.actions + self.rng.randint(*self.profile.micro_break_every)
            return self.rng.uniform(*self.profile.micro_break_s)
        return None

    def video_dwell(self) -> tuple[str, float]:
        """('skip'|'short'|'watch'|'long', segundos) para un vídeo del feed."""
        p, rng = self.profile, self.rng
        roll = rng.random()
        if roll < p.dwell_skip_p * 0.5:
            return "skip", rng.uniform(0.4, 1.4)
        if roll < p.dwell_skip_p:
            return "short", rng.uniform(*p.dwell_short_s)
        if roll < p.dwell_skip_p + (1 - p.dwell_skip_p) * 0.75:
            return "watch", rng.uniform(*p.dwell_watch_s)
        return "long", rng.uniform(*p.dwell_long_s)

    def reread(self) -> float:
        return self.rng.uniform(*self.profile.reread_s)

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from .calibration import DeskCalibration


@dataclass(frozen=True, slots=True)
class Key:
    value: str
    label: str
    x: float
    y: float
    w: float
    h: float

    def contains(self, x: float, y: float, inset: float = 0.0) -> bool:
        ix = min(inset, self.w * 0.22)
        iy = min(inset, self.h * 0.22)
        return self.x + ix <= x <= self.x + self.w - ix and self.y + iy <= y <= self.y + self.h - iy


def _row(values: list[tuple[str, str, float]], y: float, *, x0: float = 0.025, right_margin: float = 0.025, h: float = 0.18) -> list[Key]:
    gap = 0.009
    total_units = sum(unit for _, _, unit in values)
    available = 1.0 - x0 - right_margin - gap * (len(values) - 1)
    unit_w = available / total_units
    x = x0
    keys: list[Key] = []
    for value, label, units in values:
        width = unit_w * units
        keys.append(Key(value, label, x, y, width, h))
        x += width + gap
    return keys


def default_layout() -> list[Key]:
    rows = [
        _row([(c.lower(), c, 1.0) for c in "QWERTYUIOP"], 0.04),
        _row([(c.lower(), c, 1.0) for c in "ASDFGHJKL"], 0.28, x0=0.065, right_margin=0.06),
        _row([("shift", "SHIFT", 1.45)] + [(c.lower(), c, 1.0) for c in "ZXCVBNM"] + [("backspace", "⌫", 1.45)], 0.52),
        _row([("space", "SPACE", 5.8), ("enter", "ENTER", 1.8)], 0.76, x0=0.15, right_margin=0.15),
    ]
    return [key for row in rows for key in row]


class VirtualKeyboard:
    def __init__(self, cooldown_ms: int = 180, *, dwell_ms: int = 90, release_ms: int = 70, edge_inset: float = 0.012, hover_dwell_ms: int = 650) -> None:
        self.keys = default_layout()
        self.cooldown = cooldown_ms / 1000.0
        self.dwell = dwell_ms / 1000.0
        self.release_time = release_ms / 1000.0
        self.edge_inset = edge_inset
        self.hover_dwell = hover_dwell_ms / 1000.0
        self._candidate: str | None = None
        self._candidate_since = 0.0
        self._released_since: float | None = None
        self._armed = True
        self._last_fire = 0.0
        self._hover_candidate: str | None = None
        self._hover_since = 0.0
        self._hover_latched = False
        self.shift = False

    @property
    def armed(self) -> bool:
        return self._armed

    def key_at(self, x: float, y: float) -> Key | None:
        for key in self.keys:
            if key.contains(x, y, self.edge_inset):
                return key
        return None

    def trigger(self, key: Key | None, pressed: bool, *, now: float | None = None) -> str | None:
        now = monotonic() if now is None else now
        value = key.value if key is not None else None
        if value != self._candidate:
            self._candidate = value
            self._candidate_since = now
        if not pressed:
            if self._released_since is None:
                self._released_since = now
            if now - self._released_since >= self.release_time:
                self._armed = True
            return None
        self._released_since = None
        if key is None or not self._armed:
            return None
        if now - self._candidate_since < self.dwell:
            return None
        if now - self._last_fire < self.cooldown:
            return None
        self._last_fire = now
        self._armed = False
        return key.value

    def trigger_hover(self, key: Key | None, *, now: float | None = None) -> str | None:
        now = monotonic() if now is None else now
        value = key.value if key is not None else None
        if value != self._hover_candidate:
            self._hover_candidate = value
            self._hover_since = now
            self._hover_latched = False
            return None
        if key is None or self._hover_latched:
            return None
        if now - self._hover_since < self.hover_dwell:
            return None
        if now - self._last_fire < self.cooldown:
            return None
        self._last_fire = now
        self._hover_latched = True
        return key.value

    def reset(self) -> None:
        self._candidate = None
        self._candidate_since = 0.0
        self._released_since = None
        self._armed = True
        self._hover_candidate = None
        self._hover_since = 0.0
        self._hover_latched = False

    def render_projected(self, frame, calibration: DeskCalibration, active: str | None = None) -> None:
        if not calibration.ready:
            return
        height, width = frame.shape[:2]
        overlay = frame.copy()
        for key in self.keys:
            projected = calibration.project_rect(key.x, key.y, key.w, key.h)
            polygon = np.asarray([[int(x * width), int(y * height)] for x, y in projected], dtype=np.int32)
            is_active = key.value == active
            if is_active:
                cv2.fillConvexPoly(overlay, polygon, (48, 150, 255))
            cv2.polylines(overlay, [polygon], True, (88, 190, 255) if is_active else (220, 235, 245), 3 if is_active else 1, cv2.LINE_AA)
            cx, cy = calibration.unmap((key.x + key.w / 2, key.y + key.h / 2))
            tx, ty = int(cx * width), int(cy * height)
            scale = 0.52 if len(key.label) <= 2 else 0.42
            (tw, th), _ = cv2.getTextSize(key.label, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
            cv2.putText(overlay, key.label, (tx - tw // 2, ty + th // 2), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.66, frame, 0.34, 0, frame)

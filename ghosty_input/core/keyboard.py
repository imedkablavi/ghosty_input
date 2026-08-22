from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

import cv2


@dataclass(frozen=True, slots=True)
class Key:
    value: str
    label: str
    x: float
    y: float
    w: float
    h: float

    def contains(self, x: float, y: float) -> bool:
        return self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h


def _row(values: list[tuple[str, str, float]], y: float, x0: float = 0.02) -> list[Key]:
    gap = 0.008
    total_units = sum(unit for _, _, unit in values)
    available = 0.96 - gap * (len(values) - 1)
    unit_w = available / total_units
    x = x0
    keys: list[Key] = []
    for value, label, units in values:
        width = unit_w * units
        keys.append(Key(value, label, x, y, width, 0.18))
        x += width + gap
    return keys


def default_layout() -> list[Key]:
    rows = [
        _row([(c.lower(), c, 1.0) for c in "QWERTYUIOP"], 0.02),
        _row([(c.lower(), c, 1.0) for c in "ASDFGHJKL"], 0.22, x0=0.06),
        _row(
            [("shift", "SHIFT", 1.45)]
            + [(c.lower(), c, 1.0) for c in "ZXCVBNM"]
            + [("backspace", "⌫", 1.45)],
            0.42,
        ),
        _row(
            [
                ("space", "SPACE", 5.8),
                ("enter", "ENTER", 1.8),
            ],
            0.62,
            x0=0.16,
        ),
    ]
    return [key for row in rows for key in row]


class VirtualKeyboard:
    def __init__(self, cooldown_ms: int = 350) -> None:
        self.keys = default_layout()
        self.cooldown = cooldown_ms / 1000.0
        self._last_key: str | None = None
        self._last_time = 0.0
        self.shift = False

    def key_at(self, x: float, y: float) -> Key | None:
        for key in self.keys:
            if key.contains(x, y):
                return key
        return None

    def trigger(self, key: Key | None, pinching: bool) -> str | None:
        if key is None or not pinching:
            self._last_key = None
            return None

        now = monotonic()
        if key.value == self._last_key and now - self._last_time < self.cooldown:
            return None

        self._last_key = key.value
        self._last_time = now
        return key.value

    def render(self, frame, active: str | None = None) -> None:
        height, width = frame.shape[:2]
        for key in self.keys:
            x1, y1 = int(key.x * width), int(key.y * height)
            x2, y2 = int((key.x + key.w) * width), int((key.y + key.h) * height)
            thickness = 3 if key.value == active else 1
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), thickness)
            cv2.putText(
                frame,
                key.label,
                (x1 + 8, y1 + max(22, (y2 - y1) // 2)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

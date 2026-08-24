from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from time import monotonic
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tracker import Hand


def distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def palm_scale(hand: Hand) -> float:
    wrist_to_middle_mcp = distance(hand.point(0), hand.point(9))
    palm_width = distance(hand.point(5), hand.point(17))
    return max(1e-6, (wrist_to_middle_mcp + palm_width) * 0.5)


def normalized_pinch(hand: Hand, finger_tip: int = 8) -> float:
    return distance(hand.point(4), hand.point(finger_tip)) / palm_scale(hand)


def pinch_center(hand: Hand, finger_tip: int = 8) -> tuple[float, float]:
    thumb = hand.point(4)
    finger = hand.point(finger_tip)
    return (thumb[0] + finger[0]) * 0.5, (thumb[1] + finger[1]) * 0.5


def fingers_up(hand: Hand) -> tuple[bool, bool, bool, bool, bool]:
    thumb_tip = hand.point(4)
    thumb_ip = hand.point(3)
    if hand.label.lower() == "right":
        thumb = thumb_tip[0] < thumb_ip[0]
    else:
        thumb = thumb_tip[0] > thumb_ip[0]
    return (thumb, hand.point(8)[1] < hand.point(6)[1], hand.point(12)[1] < hand.point(10)[1], hand.point(16)[1] < hand.point(14)[1], hand.point(20)[1] < hand.point(18)[1])


def is_fist(hand: Hand) -> bool:
    return sum(fingers_up(hand)[1:]) == 0


def left_hand_modifier(hand: Hand) -> str | None:
    count = sum(fingers_up(hand)[1:])
    return {1: "shift", 2: "backspace", 3: "enter", 4: "space"}.get(count)


@dataclass(slots=True)
class EdgeTrigger:
    active: bool = False

    def rising(self, value: bool) -> bool:
        was = self.active
        self.active = value
        return value and not was


@dataclass(slots=True)
class HysteresisGate:
    engage_threshold: float
    release_threshold: float
    active: bool = False

    def __post_init__(self) -> None:
        if self.release_threshold <= self.engage_threshold:
            raise ValueError("release_threshold must be greater than engage_threshold")

    def update(self, value: float) -> bool:
        if self.active:
            if value >= self.release_threshold:
                self.active = False
        elif value <= self.engage_threshold:
            self.active = True
        return self.active

    def reset(self) -> None:
        self.active = False


@dataclass(slots=True)
class DwellPointTrigger:
    dwell_seconds: float
    radius: float = 0.018
    release_radius: float = 0.035
    anchor: tuple[float, float] | None = None
    since: float | None = None
    latched: bool = False

    def __post_init__(self) -> None:
        if self.dwell_seconds <= 0:
            raise ValueError("dwell_seconds must be positive")
        if self.radius <= 0 or self.release_radius <= self.radius:
            raise ValueError("release_radius must be greater than radius")

    def update(self, point: tuple[float, float] | None, *, now: float | None = None) -> bool:
        now = monotonic() if now is None else now
        if point is None:
            self.reset()
            return False
        if self.anchor is None:
            self.anchor = point
            self.since = now
            return False
        drift = hypot(point[0] - self.anchor[0], point[1] - self.anchor[1])
        if self.latched:
            if drift >= self.release_radius:
                self.anchor = point
                self.since = now
                self.latched = False
            return False
        if drift > self.radius:
            self.anchor = point
            self.since = now
            return False
        if self.since is not None and now - self.since >= self.dwell_seconds:
            self.latched = True
            return True
        return False

    def reset(self) -> None:
        self.anchor = None
        self.since = None
        self.latched = False


@dataclass(slots=True)
class Cooldown:
    interval: float
    last: float = 0.0

    def ready(self) -> bool:
        now = monotonic()
        if now - self.last >= self.interval:
            self.last = now
            return True
        return False

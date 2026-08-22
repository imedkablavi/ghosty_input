from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from time import monotonic
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tracker import Hand


def distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def pinch(hand: Hand, finger_tip: int = 8) -> float:
    return distance(hand.point(4), hand.point(finger_tip))


def fingers_up(hand: Hand) -> tuple[bool, bool, bool, bool, bool]:
    thumb_tip = hand.point(4)
    thumb_ip = hand.point(3)
    # MediaPipe handedness is from the image perspective. This check is used
    # only for coarse gesture classification; the other four fingers rely on Y.
    if hand.label.lower() == "right":
        thumb = thumb_tip[0] < thumb_ip[0]
    else:
        thumb = thumb_tip[0] > thumb_ip[0]

    return (
        thumb,
        hand.point(8)[1] < hand.point(6)[1],
        hand.point(12)[1] < hand.point(10)[1],
        hand.point(16)[1] < hand.point(14)[1],
        hand.point(20)[1] < hand.point(18)[1],
    )


def is_fist(hand: Hand) -> bool:
    return sum(fingers_up(hand)[1:]) == 0


def left_hand_modifier(hand: Hand) -> str | None:
    """Map simple left-hand finger counts to keyboard modifiers.

    1=index -> Shift, 2 -> Backspace, 3 -> Enter, 4 -> Space.
    """
    state = fingers_up(hand)
    count = sum(state[1:])
    return {
        1: "shift",
        2: "backspace",
        3: "enter",
        4: "space",
    }.get(count)


@dataclass(slots=True)
class EdgeTrigger:
    active: bool = False

    def rising(self, value: bool) -> bool:
        was = self.active
        self.active = value
        return value and not was


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

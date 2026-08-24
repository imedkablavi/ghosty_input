from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import hypot

import cv2
import mediapipe as mp


@dataclass(frozen=True, slots=True)
class Hand:
    label: str
    score: float
    landmarks: tuple[tuple[float, float, float], ...]

    def point(self, index: int) -> tuple[float, float, float]:
        return self.landmarks[index]


class _LandmarkSmoother:
    def __init__(self, base_alpha: float = 0.58) -> None:
        self.base_alpha = base_alpha
        self._previous: dict[str, tuple[tuple[float, float, float], ...]] = {}

    def apply(
        self,
        label: str,
        points: tuple[tuple[float, float, float], ...],
    ) -> tuple[tuple[float, float, float], ...]:
        previous = self._previous.get(label)
        if previous is None or len(previous) != len(points):
            self._previous[label] = points
            return points

        wrist_motion = hypot(points[0][0] - previous[0][0], points[0][1] - previous[0][1])
        alpha = min(0.88, self.base_alpha + wrist_motion * 8.0)
        smoothed = tuple(
            (
                old[0] + alpha * (new[0] - old[0]),
                old[1] + alpha * (new[1] - old[1]),
                old[2] + alpha * (new[2] - old[2]),
            )
            for old, new in zip(previous, points, strict=True)
        )
        self._previous[label] = smoothed
        return smoothed

    def clear(self) -> None:
        self._previous.clear()


class HandTracker:
    """Offline MediaPipe Hands wrapper with temporal landmark stabilization.

    MediaPipe handedness assumes a mirrored/selfie image. Set
    ``swap_handedness=True`` for a non-mirrored camera stream such as a fixed
    top-down desk camera.
    """

    def __init__(
        self,
        *,
        max_hands: int = 2,
        min_detection_confidence: float = 0.65,
        min_tracking_confidence: float = 0.65,
        landmark_smoothing: float = 0.58,
        swap_handedness: bool = False,
    ) -> None:
        self._mp_hands = mp.solutions.hands
        self._drawer = mp.solutions.drawing_utils
        self._swap_handedness = swap_handedness
        self._hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            model_complexity=1,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._smoother = _LandmarkSmoother(landmark_smoothing)

    def process(self, frame, *, draw: bool = True) -> list[Hand]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._hands.process(rgb)
        hands: list[Hand] = []

        if not result.multi_hand_landmarks:
            return hands

        handedness = result.multi_handedness or []
        for idx, hand_landmarks in enumerate(result.multi_hand_landmarks):
            label = "Unknown"
            score = 0.0
            if idx < len(handedness):
                cls = handedness[idx].classification[0]
                label = cls.label
                score = float(cls.score)
                if self._swap_handedness:
                    if label == "Left":
                        label = "Right"
                    elif label == "Right":
                        label = "Left"

            raw_points = tuple(
                (float(lm.x), float(lm.y), float(lm.z))
                for lm in hand_landmarks.landmark
            )
            points = self._smoother.apply(label, raw_points)
            hands.append(Hand(label=label, score=score, landmarks=points))

            if draw:
                self._drawer.draw_landmarks(
                    frame,
                    hand_landmarks,
                    self._mp_hands.HAND_CONNECTIONS,
                )

        return hands

    def close(self) -> None:
        self._smoother.clear()
        self._hands.close()


def choose_hand(hands: Sequence[Hand], preferred: str) -> Hand | None:
    preferred_lower = preferred.lower()
    candidates = [h for h in hands if h.label.lower() == preferred_lower]
    if candidates:
        return max(candidates, key=lambda hand: hand.score)
    return max(hands, key=lambda hand: hand.score) if hands else None

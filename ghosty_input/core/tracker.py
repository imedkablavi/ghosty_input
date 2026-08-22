from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import mediapipe as mp


@dataclass(frozen=True, slots=True)
class Hand:
    label: str
    score: float
    landmarks: tuple[tuple[float, float, float], ...]

    def point(self, index: int) -> tuple[float, float, float]:
        return self.landmarks[index]


class HandTracker:
    """Thin wrapper around MediaPipe Hands.

    The legacy MediaPipe Hands solution is intentionally used because its model
    is bundled with the wheel and does not require downloading a .task model.
    """

    def __init__(
        self,
        *,
        max_hands: int = 2,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.6,
    ) -> None:
        self._mp_hands = mp.solutions.hands
        self._drawer = mp.solutions.drawing_utils
        self._hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            model_complexity=1,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

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

            points = tuple(
                (float(lm.x), float(lm.y), float(lm.z))
                for lm in hand_landmarks.landmark
            )
            hands.append(Hand(label=label, score=score, landmarks=points))

            if draw:
                self._drawer.draw_landmarks(
                    frame,
                    hand_landmarks,
                    self._mp_hands.HAND_CONNECTIONS,
                )

        return hands

    def close(self) -> None:
        self._hands.close()


def choose_hand(hands: Sequence[Hand], preferred: str) -> Hand | None:
    for hand in hands:
        if hand.label.lower() == preferred.lower():
            return hand
    return hands[0] if hands else None

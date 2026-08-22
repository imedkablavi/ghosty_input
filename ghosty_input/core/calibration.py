from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(slots=True)
class DeskCalibration:
    points: list[list[float]]

    def __post_init__(self) -> None:
        if self.points and len(self.points) != 4:
            raise ValueError("Desk calibration requires four points.")

    @property
    def ready(self) -> bool:
        return len(self.points) == 4

    def matrix(self):
        if not self.ready:
            raise RuntimeError("Desk calibration has not been completed.")
        source = np.asarray(self.points, dtype=np.float32)
        target = np.asarray(
            [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            dtype=np.float32,
        )
        return cv2.getPerspectiveTransform(source, target)

    def map(self, point: tuple[float, float]) -> tuple[float, float]:
        matrix = self.matrix()
        src = np.asarray([[[point[0], point[1]]]], dtype=np.float32)
        mapped = cv2.perspectiveTransform(src, matrix)[0][0]
        return float(mapped[0]), float(mapped[1])

    def contains(self, point: tuple[float, float], margin: float = 0.03) -> bool:
        if not self.ready:
            return False
        x, y = self.map(point)
        return -margin <= x <= 1 + margin and -margin <= y <= 1 + margin

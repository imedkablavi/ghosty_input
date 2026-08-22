from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


def _polygon_area(points: np.ndarray) -> float:
    x = points[:, 0]
    y = points[:, 1]
    return abs(float(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))) * 0.5


def _is_convex(points: np.ndarray) -> bool:
    signs: list[float] = []
    for i in range(4):
        a = points[(i + 1) % 4] - points[i]
        b = points[(i + 2) % 4] - points[(i + 1) % 4]
        cross = float(a[0] * b[1] - a[1] * b[0])
        if abs(cross) > 1e-6:
            signs.append(cross)
    return bool(signs) and (all(v > 0 for v in signs) or all(v < 0 for v in signs))


@dataclass(slots=True)
class DeskCalibration:
    """Perspective mapping between camera coordinates and keyboard coordinates.

    Points are expected clockwise: top-left, top-right, bottom-right, bottom-left.
    """

    points: list[list[float]]

    def __post_init__(self) -> None:
        if self.points and len(self.points) != 4:
            raise ValueError("Desk calibration requires four points.")
        if self.points:
            self._validate_geometry()

    def _validate_geometry(self) -> None:
        source = np.asarray(self.points, dtype=np.float32)
        if source.shape != (4, 2):
            raise ValueError("Calibration points must be four [x, y] pairs.")
        if not np.isfinite(source).all():
            raise ValueError("Calibration points must be finite.")
        if (source < -0.05).any() or (source > 1.05).any():
            raise ValueError("Calibration points are outside the camera frame.")
        if _polygon_area(source) < 0.025:
            raise ValueError("Calibration area is too small. Use the full keyboard area.")
        if not _is_convex(source):
            raise ValueError("Calibration corners must form a convex quadrilateral.")

    @property
    def ready(self) -> bool:
        return len(self.points) == 4

    @property
    def area(self) -> float:
        if not self.ready:
            return 0.0
        return _polygon_area(np.asarray(self.points, dtype=np.float32))

    @property
    def quality_score(self) -> int:
        """Heuristic 0-100 score for operator feedback."""
        if not self.ready:
            return 0
        source = np.asarray(self.points, dtype=np.float32)
        top = float(np.linalg.norm(source[1] - source[0]))
        bottom = float(np.linalg.norm(source[2] - source[3]))
        left = float(np.linalg.norm(source[3] - source[0]))
        right = float(np.linalg.norm(source[2] - source[1]))
        width_balance = min(top, bottom) / max(top, bottom, 1e-6)
        height_balance = min(left, right) / max(left, right, 1e-6)
        coverage = min(1.0, self.area / 0.35)
        return int(round(100 * (0.45 * coverage + 0.275 * width_balance + 0.275 * height_balance)))

    def matrix(self):
        if not self.ready:
            raise RuntimeError("Desk calibration has not been completed.")
        source = np.asarray(self.points, dtype=np.float32)
        target = np.asarray(
            [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            dtype=np.float32,
        )
        return cv2.getPerspectiveTransform(source, target)

    def inverse_matrix(self):
        if not self.ready:
            raise RuntimeError("Desk calibration has not been completed.")
        source = np.asarray(
            [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            dtype=np.float32,
        )
        target = np.asarray(self.points, dtype=np.float32)
        return cv2.getPerspectiveTransform(source, target)

    def map(self, point: tuple[float, float]) -> tuple[float, float]:
        src = np.asarray([[[point[0], point[1]]]], dtype=np.float32)
        mapped = cv2.perspectiveTransform(src, self.matrix())[0][0]
        return float(mapped[0]), float(mapped[1])

    def unmap(self, point: tuple[float, float]) -> tuple[float, float]:
        src = np.asarray([[[point[0], point[1]]]], dtype=np.float32)
        mapped = cv2.perspectiveTransform(src, self.inverse_matrix())[0][0]
        return float(mapped[0]), float(mapped[1])

    def project_rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> list[tuple[float, float]]:
        return [
            self.unmap((x, y)),
            self.unmap((x + w, y)),
            self.unmap((x + w, y + h)),
            self.unmap((x, y + h)),
        ]

    def contains(self, point: tuple[float, float], margin: float = 0.02) -> bool:
        if not self.ready:
            return False
        x, y = self.map(point)
        return -margin <= x <= 1 + margin and -margin <= y <= 1 + margin

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import median


@dataclass(frozen=True, slots=True)
class PinchProfile:
    engage_ratio: float
    release_ratio: float
    open_ratio: float
    pinch_ratio: float
    separation: float
    sample_count: int


class AdaptivePinchCalibrator:
    """Derive user-specific pinch hysteresis from short local samples.

    Raw landmark/pinch samples live only in memory while calibration is active.
    Callers should persist only the resulting thresholds.
    """

    def __init__(self, samples_per_phase: int = 45) -> None:
        if samples_per_phase < 10:
            raise ValueError("samples_per_phase must be at least 10")
        self.samples_per_phase = int(samples_per_phase)
        self.phase = "open"
        self._open: list[float] = []
        self._pinch: list[float] = []
        self.profile: PinchProfile | None = None
        self.error = ""

    @property
    def complete(self) -> bool:
        return self.profile is not None

    @property
    def progress(self) -> float:
        total = len(self._open) + len(self._pinch)
        return min(1.0, total / (self.samples_per_phase * 2))

    @property
    def sample_count(self) -> int:
        return len(self._open) + len(self._pinch)

    def add(self, ratio: float | None) -> str:
        if self.complete:
            return "complete"
        if ratio is None or not isfinite(float(ratio)):
            return self.phase
        value = float(ratio)
        if value <= 0.0 or value > 2.0:
            return self.phase

        if self.phase == "open":
            self._open.append(value)
            if len(self._open) >= self.samples_per_phase:
                self.phase = "pinch"
            return self.phase

        if self.phase == "pinch":
            self._pinch.append(value)
            if len(self._pinch) >= self.samples_per_phase:
                self._finish()
            return "complete" if self.complete else self.phase

        return self.phase

    def _finish(self) -> None:
        open_ratio = float(median(self._open))
        pinch_ratio = float(median(self._pinch))
        separation = open_ratio - pinch_ratio
        if separation < 0.08:
            self.error = (
                "Open-hand and pinch samples overlap too much. Keep the hand at a stable "
                "distance from the camera and repeat calibration."
            )
            self.phase = "failed"
            return

        engage = pinch_ratio + separation * 0.34
        release = pinch_ratio + separation * 0.62
        engage = max(0.12, min(0.80, engage))
        release = max(engage + 0.03, min(1.20, release))
        self.profile = PinchProfile(
            engage_ratio=engage,
            release_ratio=release,
            open_ratio=open_ratio,
            pinch_ratio=pinch_ratio,
            separation=separation,
            sample_count=self.sample_count,
        )
        self.phase = "complete"
        # Drop samples immediately after deriving the profile. They are not
        # needed for runtime and must never become persistence payloads.
        self._open.clear()
        self._pinch.clear()

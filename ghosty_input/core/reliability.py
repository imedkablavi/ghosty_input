from __future__ import annotations

from dataclasses import dataclass
from math import floor


@dataclass(frozen=True, slots=True)
class CaptureReliability:
    frames: int = 0
    estimated_dropped_frames: int = 0
    camera_errors: int = 0
    reconnects: int = 0
    capture_latency_ms: float = 0.0
    max_capture_latency_ms: float = 0.0


class CaptureReliabilityMonitor:
    """Track capture health without retaining frame contents.

    Dropped frames are estimated from the interval between successful reads and
    the requested capture FPS. This cannot replace a hardware timestamp from a
    camera driver, but it gives a portable signal for stalls, USB disconnects,
    and unexpectedly slow reads on OpenCV backends.
    """

    def __init__(self, expected_fps: float = 30.0) -> None:
        self.expected_fps = max(1.0, float(expected_fps))
        self.frames = 0
        self.estimated_dropped_frames = 0
        self.camera_errors = 0
        self.reconnects = 0
        self.capture_latency_ms = 0.0
        self.max_capture_latency_ms = 0.0
        self._last_success_at: float | None = None
        self._recovering = False

    def observe_success(self, *, now: float, capture_seconds: float) -> None:
        latency_ms = max(0.0, float(capture_seconds)) * 1000.0
        self.frames += 1
        if self.capture_latency_ms == 0.0:
            self.capture_latency_ms = latency_ms
        else:
            self.capture_latency_ms = self.capture_latency_ms * 0.9 + latency_ms * 0.1
        self.max_capture_latency_ms = max(self.max_capture_latency_ms, latency_ms)

        if self._last_success_at is not None:
            interval = max(0.0, float(now) - self._last_success_at)
            expected_intervals = interval * self.expected_fps
            # floor with a small tolerance avoids marking normal scheduler
            # noise around exactly one frame interval as a drop.
            missing = max(0, floor(expected_intervals + 0.15) - 1)
            self.estimated_dropped_frames += missing
        self._last_success_at = float(now)

        if self._recovering:
            self.reconnects += 1
            self._recovering = False

    def observe_failure(self) -> None:
        self.camera_errors += 1
        self._recovering = True

    def snapshot(self) -> CaptureReliability:
        return CaptureReliability(
            frames=self.frames,
            estimated_dropped_frames=self.estimated_dropped_frames,
            camera_errors=self.camera_errors,
            reconnects=self.reconnects,
            capture_latency_ms=self.capture_latency_ms,
            max_capture_latency_ms=self.max_capture_latency_ms,
        )

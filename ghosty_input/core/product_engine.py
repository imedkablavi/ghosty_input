from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

import cv2

from .camera import Camera, CameraError
from .engine import GhostyEngine, RuntimeMetrics, TickResult, _best_hand
from .gestures import normalized_pinch
from .reliability import CaptureReliabilityMonitor
from .tracker import Hand


@dataclass(frozen=True, slots=True)
class ProductRuntimeMetrics(RuntimeMetrics):
    front_capture_ms: float = 0.0
    top_capture_ms: float = 0.0
    max_capture_ms: float = 0.0
    estimated_dropped_frames: int = 0
    camera_errors: int = 0
    reconnects: int = 0
    tick_latency_ms: float = 0.0
    pinch_ratio: float | None = None
    calibration_reprojection_error: float | None = None


class ProductGhostyEngine(GhostyEngine):
    """Reliability-instrumented engine used by packaged Alpha runtimes."""

    def __init__(self, config) -> None:
        super().__init__(config)
        self.front_reliability = CaptureReliabilityMonitor(config.camera_fps)
        self.top_reliability = CaptureReliabilityMonitor(config.camera_fps)

    @staticmethod
    def _read_with_metrics(camera: Camera, monitor: CaptureReliabilityMonitor):
        started = monotonic()
        try:
            frame = camera.read()
        except CameraError:
            monitor.observe_failure()
            raise
        finished = monotonic()
        monitor.observe_success(now=finished, capture_seconds=finished - started)
        return frame

    def _product_metrics(
        self,
        hands: list[Hand],
        *,
        tick_latency_ms: float,
    ) -> ProductRuntimeMetrics:
        front_info = self.front.info
        front = self.front_reliability.snapshot()
        if self.top is not None:
            top_info = self.top.info
            top = self.top_reliability.snapshot()
        else:
            top_info = front_info
            top = front

        confidence = max((hand.score for hand in hands), default=0.0)
        right = _best_hand(hands, "Right")
        pinch_ratio = normalized_pinch(right, 8) if right is not None else None
        reprojection = None
        calibration_quality = self.calibration.quality_score
        if self.calibration.ready:
            reprojection = self.calibration.reprojection_error(
                self.config.calibration_validation_points
            )
            calibration_quality = self.calibration.quality_with_validation(
                self.config.calibration_validation_points
            )

        return ProductRuntimeMetrics(
            front_fps=front_info.fps,
            top_fps=top_info.fps,
            hand_confidence=confidence,
            hand_count=len(hands),
            camera_resolution=front_info.resolution,
            calibration_quality=calibration_quality,
            input_backend=self.input.backend_name,
            front_capture_ms=front.capture_latency_ms,
            top_capture_ms=top.capture_latency_ms,
            max_capture_ms=max(front.max_capture_latency_ms, top.max_capture_latency_ms),
            estimated_dropped_frames=(
                front.estimated_dropped_frames
                + (top.estimated_dropped_frames if self.top is not None else 0)
            ),
            camera_errors=front.camera_errors + (top.camera_errors if self.top is not None else 0),
            reconnects=front.reconnects + (top.reconnects if self.top is not None else 0),
            tick_latency_ms=max(0.0, tick_latency_ms),
            pinch_ratio=pinch_ratio,
            calibration_reprojection_error=reprojection,
        )

    def _error_metrics(self, started: float) -> ProductRuntimeMetrics:
        return self._product_metrics(
            [],
            tick_latency_ms=(monotonic() - started) * 1000.0,
        )

    def tick(self) -> TickResult:
        started = monotonic()
        try:
            front_frame = self._read_with_metrics(self.front, self.front_reliability)
            if self.config.mirror_front:
                front_frame = cv2.flip(front_frame, 1)

            front_hands = self.front_tracker.process(
                front_frame,
                draw=self.config.draw_landmarks,
            )
            mouse_hand = _best_hand(front_hands, "Right")
            event = self._process_mouse(mouse_hand)

            if self.top is not None:
                top_frame = self._read_with_metrics(self.top, self.top_reliability)
                assert self.top_tracker is not None
                top_hands = self.top_tracker.process(
                    top_frame,
                    draw=self.config.draw_landmarks,
                )
            else:
                top_frame = front_frame.copy()
                top_hands = front_hands

            keyboard_event = self._process_keyboard(top_frame, top_hands)
            if keyboard_event:
                event = keyboard_event

            status = "Paused" if self.paused else "Running"
            if self.config.keyboard_enabled and not self.calibration.ready:
                status += " · keyboard needs calibration"
            metrics = self._product_metrics(
                front_hands,
                tick_latency_ms=(monotonic() - started) * 1000.0,
            )
            return TickResult(front_frame, top_frame, status, event, metrics)
        except CameraError as exc:
            return TickResult(
                None,
                None,
                "Camera error",
                str(exc),
                self._error_metrics(started),
            )
        except Exception as exc:
            return TickResult(
                None,
                None,
                "Runtime error",
                f"{type(exc).__name__}: {exc}",
                self._error_metrics(started),
            )

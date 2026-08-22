from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic

import cv2

from ghosty_input.config import AppConfig

from .actions import InputController
from .calibration import DeskCalibration
from .camera import Camera, CameraError
from .gestures import (
    DwellPointTrigger,
    EdgeTrigger,
    HysteresisGate,
    fingers_up,
    is_fist,
    left_hand_modifier,
    normalized_pinch,
)
from .keyboard import VirtualKeyboard
from .tracker import Hand, HandTracker


@dataclass(frozen=True, slots=True)
class RuntimeMetrics:
    front_fps: float = 0.0
    top_fps: float = 0.0
    hand_confidence: float = 0.0
    hand_count: int = 0
    camera_resolution: str = "—"
    calibration_quality: int = 0
    input_backend: str = "—"


@dataclass(slots=True)
class TickResult:
    front_frame: object | None
    top_frame: object | None
    status: str
    event: str | None = None
    metrics: RuntimeMetrics = field(default_factory=RuntimeMetrics)


def _best_hand(hands: list[Hand], label: str) -> Hand | None:
    matching = [hand for hand in hands if hand.label.lower() == label.lower()]
    return max(matching, key=lambda hand: hand.score) if matching else None


class GhostyEngine:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        camera_args = dict(
            width=config.camera_width,
            height=config.camera_height,
            fps=config.camera_fps,
            autofocus=config.camera_autofocus,
            exposure=config.camera_exposure,
        )
        self.front = Camera(config.front_camera, **camera_args)
        self.top: Camera | None = None
        self.front_tracker = HandTracker(
            max_hands=2,
            min_detection_confidence=config.detection_confidence,
            min_tracking_confidence=config.tracking_confidence,
        )
        self.top_tracker: HandTracker | None = None
        screen_size = (
            (config.screen_width, config.screen_height)
            if config.screen_width and config.screen_height
            else None
        )
        self.input = InputController(
            smoothing=config.pointer_smoothing,
            deadzone_px=config.pointer_deadzone_px,
            backend=config.input_backend,
            screen_size=screen_size,
        )
        self.calibration = DeskCalibration(config.calibration_points.copy())
        self.keyboard = VirtualKeyboard(
            config.keyboard_cooldown_ms,
            dwell_ms=config.keyboard_dwell_ms,
            release_ms=config.keyboard_release_ms,
            edge_inset=config.keyboard_edge_inset,
            hover_dwell_ms=config.keyboard_hover_ms,
        )

        engage = config.pinch_engage_ratio
        release = config.pinch_release_ratio
        self.mouse_left_gate = HysteresisGate(engage, release)
        self.mouse_right_gate = HysteresisGate(engage, release)
        self.mouse_drag_gate = HysteresisGate(engage, release)
        self.keyboard_gate = HysteresisGate(engage, release)
        self.left_click_edge = EdgeTrigger()
        self.right_click_edge = EdgeTrigger()
        self.modifier_edge = EdgeTrigger()
        self.pointer_dwell = DwellPointTrigger(
            config.pointer_dwell_ms / 1000.0,
            radius=config.pointer_dwell_radius,
            release_radius=max(
                config.pointer_dwell_radius * 2.0,
                config.pointer_dwell_radius + 0.012,
            ),
        )

        self.paused = False
        self._fist_since: float | None = None
        self._fist_latched = False
        self._last_scroll_y: float | None = None

    def start(self) -> None:
        self.front.open()
        if self.config.dual_camera and self.config.top_camera != self.config.front_camera:
            camera_args = dict(
                width=self.config.camera_width,
                height=self.config.camera_height,
                fps=self.config.camera_fps,
                autofocus=self.config.camera_autofocus,
                exposure=self.config.camera_exposure,
            )
            self.top = Camera(self.config.top_camera, **camera_args)
            self.top.open()
            self.top_tracker = HandTracker(
                max_hands=2,
                min_detection_confidence=self.config.detection_confidence,
                min_tracking_confidence=self.config.tracking_confidence,
                swap_handedness=True,
            )

    def set_calibration(self, points: list[list[float]]) -> None:
        self.calibration = DeskCalibration(points)
        self.keyboard.reset()

    def _reset_mouse_gates(self) -> None:
        self.mouse_left_gate.reset()
        self.mouse_right_gate.reset()
        self.mouse_drag_gate.reset()
        self.left_click_edge.rising(False)
        self.right_click_edge.rising(False)
        self.pointer_dwell.reset()

    def _process_mouse(self, hand: Hand | None) -> str | None:
        if hand is None:
            self._fist_since = None
            self._reset_mouse_gates()
            self.input.drag_end()
            self.input.reset_pointer_filter()
            return None

        now = monotonic()
        if is_fist(hand):
            if self._fist_since is None:
                self._fist_since = now
            if now - self._fist_since > 0.75 and not self._fist_latched:
                self.paused = not self.paused
                self._fist_latched = True
                self.input.drag_end()
                self.input.reset_pointer_filter()
                self.pointer_dwell.reset()
                return "Mouse paused" if self.paused else "Mouse resumed"
        else:
            self._fist_since = None
            self._fist_latched = False

        if self.paused:
            self.pointer_dwell.reset()
            return None

        index = hand.point(8)
        margin = self.config.pointer_active_margin
        usable = max(0.2, 1.0 - margin * 2.0)
        self.input.move_normalized(
            (index[0] - margin) / usable,
            (index[1] - margin) / usable,
        )

        up = fingers_up(hand)
        hover_event: str | None = None
        if self.config.pointer_activation_mode == "hover":
            self.mouse_left_gate.reset()
            self.left_click_edge.rising(False)
            index_only = up[1] and not up[2] and not up[3] and not up[4]
            fired = self.pointer_dwell.update(
                (float(index[0]), float(index[1])) if index_only else None,
                now=now,
            )
            left = False
            if fired:
                self.input.click("left")
                hover_event = "Hover dwell click"
        else:
            self.pointer_dwell.reset()
            left = self.mouse_left_gate.update(normalized_pinch(hand, 8))

        right = self.mouse_right_gate.update(normalized_pinch(hand, 12))
        drag = self.mouse_drag_gate.update(normalized_pinch(hand, 16))

        if self.config.pointer_activation_mode == "pinch" and self.left_click_edge.rising(left):
            self.input.click("left")
            return "Left click"
        if self.right_click_edge.rising(right):
            self.input.click("right")
            return "Right click"

        if drag and not left and not right:
            self.input.drag_start()
        else:
            self.input.drag_end()

        scrolling = up[1] and up[2] and not up[3] and not up[4] and not left and not right
        if scrolling:
            self.pointer_dwell.reset()
            y_now = hand.point(8)[1]
            if self._last_scroll_y is not None:
                delta = self._last_scroll_y - y_now
                amount = int(delta * 80 * self.config.scroll_sensitivity)
                if amount:
                    self.input.scroll(amount)
                    self._last_scroll_y = y_now
                    return f"Scroll {amount:+d}"
            self._last_scroll_y = y_now
        else:
            self._last_scroll_y = None
        return hover_event

    def _apply_key(self, value: str) -> str:
        if value == "shift":
            self.keyboard.shift = not self.keyboard.shift
            return f"Shift {'on' if self.keyboard.shift else 'off'}"
        if value in {"space", "enter", "backspace"}:
            self.input.press(value)
            return value.capitalize()
        if len(value) == 1:
            if self.keyboard.shift:
                self.input.hotkey("shift", value)
                self.keyboard.shift = False
            else:
                self.input.press(value)
            return f"Key {value.upper()}"
        return value

    def _process_keyboard(self, frame, hands: list[Hand]) -> str | None:
        if not self.config.keyboard_enabled or not self.calibration.ready:
            return None

        right = _best_hand(hands, "Right")
        left = _best_hand(hands, "Left")
        event: str | None = None
        active_value: str | None = None

        if right is not None:
            index = right.point(8)
            xy = (float(index[0]), float(index[1]))
            key = None
            if self.calibration.contains(xy):
                kx, ky = self.calibration.map(xy)
                key = self.keyboard.key_at(kx, ky)
            active_value = key.value if key else None

            if self.config.keyboard_activation_mode == "hover":
                self.keyboard_gate.reset()
                value = self.keyboard.trigger_hover(key)
            else:
                pressed = self.keyboard_gate.update(normalized_pinch(right, 8))
                value = self.keyboard.trigger(key, pressed)
            if value:
                event = self._apply_key(value)
        else:
            self.keyboard_gate.reset()
            self.keyboard.trigger(None, False)
            self.keyboard.trigger_hover(None)

        if left is not None:
            modifier = left_hand_modifier(left)
            fired = self.modifier_edge.rising(modifier is not None)
            if fired and modifier:
                event = self._apply_key(modifier)
        else:
            self.modifier_edge.rising(False)

        self.keyboard.render_projected(frame, self.calibration, active_value)
        return event

    def _metrics(self, hands: list[Hand]) -> RuntimeMetrics:
        front_info = self.front.info
        top_fps = self.top.info.fps if self.top is not None else front_info.fps
        confidence = max((hand.score for hand in hands), default=0.0)
        return RuntimeMetrics(
            front_fps=front_info.fps,
            top_fps=top_fps,
            hand_confidence=confidence,
            hand_count=len(hands),
            camera_resolution=front_info.resolution,
            calibration_quality=self.calibration.quality_score,
            input_backend=self.input.backend_name,
        )

    def tick(self) -> TickResult:
        try:
            front_frame = self.front.read()
            if self.config.mirror_front:
                front_frame = cv2.flip(front_frame, 1)

            front_hands = self.front_tracker.process(
                front_frame,
                draw=self.config.draw_landmarks,
            )
            mouse_hand = _best_hand(front_hands, "Right")
            event = self._process_mouse(mouse_hand)

            if self.top is not None:
                top_frame = self.top.read()
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
            return TickResult(
                front_frame,
                top_frame,
                status,
                event,
                self._metrics(front_hands),
            )
        except CameraError as exc:
            return TickResult(None, None, "Camera error", str(exc))
        except Exception as exc:
            return TickResult(
                None,
                None,
                "Runtime error",
                f"{type(exc).__name__}: {exc}",
            )

    def close(self) -> None:
        self.input.close()
        self.front.release()
        if self.top is not None:
            self.top.release()
        self.front_tracker.close()
        if self.top_tracker is not None:
            self.top_tracker.close()

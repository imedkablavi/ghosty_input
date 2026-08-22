from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

import cv2

from ghosty_input.config import AppConfig

from .actions import InputController
from .calibration import DeskCalibration
from .camera import Camera, CameraError
from .gestures import EdgeTrigger, fingers_up, is_fist, left_hand_modifier, pinch
from .keyboard import VirtualKeyboard
from .tracker import Hand, HandTracker, choose_hand


@dataclass(slots=True)
class TickResult:
    front_frame: object | None
    top_frame: object | None
    status: str
    event: str | None = None


class GhostyEngine:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.front = Camera(config.front_camera)
        self.top: Camera | None = None
        self.front_tracker = HandTracker(max_hands=2)
        self.top_tracker: HandTracker | None = None
        self.input = InputController(smoothing=config.smoothing)
        self.calibration = DeskCalibration(config.calibration_points.copy())
        self.keyboard = VirtualKeyboard(config.keyboard_cooldown_ms)

        self.left_click_edge = EdgeTrigger()
        self.right_click_edge = EdgeTrigger()
        self.modifier_edge = EdgeTrigger()
        self.paused = False
        self._fist_since: float | None = None
        self._fist_latched = False
        self._last_scroll_y: float | None = None

    def start(self) -> None:
        self.front.open()
        if self.config.dual_camera and self.config.top_camera != self.config.front_camera:
            self.top = Camera(self.config.top_camera)
            self.top.open()
            self.top_tracker = HandTracker(max_hands=2)

    def set_calibration(self, points: list[list[float]]) -> None:
        self.calibration = DeskCalibration(points)

    def _process_mouse(self, hand: Hand | None) -> str | None:
        if hand is None:
            self._fist_since = None
            self.left_click_edge.rising(False)
            self.right_click_edge.rising(False)
            if self.input.state.dragging:
                self.input.drag_end()
            return None

        now = monotonic()
        if is_fist(hand):
            if self._fist_since is None:
                self._fist_since = now
            if now - self._fist_since > 0.75 and not self._fist_latched:
                self.paused = not self.paused
                self._fist_latched = True
                return "Mouse paused" if self.paused else "Mouse resumed"
        else:
            self._fist_since = None
            self._fist_latched = False

        if self.paused:
            return None

        index = hand.point(8)
        # A small dead margin reduces accidental screen-edge jumps.
        x = (index[0] - 0.06) / 0.88
        y = (index[1] - 0.06) / 0.88
        self.input.move_normalized(x, y)

        threshold = self.config.pinch_threshold
        left = pinch(hand, 8) < threshold
        right = pinch(hand, 12) < threshold
        drag = pinch(hand, 16) < threshold

        if self.left_click_edge.rising(left):
            self.input.click("left")
            return "Left click"
        if self.right_click_edge.rising(right):
            self.input.click("right")
            return "Right click"

        if drag:
            self.input.drag_start()
        else:
            self.input.drag_end()

        up = fingers_up(hand)
        scrolling = up[1] and up[2] and not up[3] and not up[4] and not left and not right
        if scrolling:
            y_now = hand.point(8)[1]
            if self._last_scroll_y is not None:
                delta = self._last_scroll_y - y_now
                amount = int(delta * 100 * self.config.scroll_sensitivity)
                if amount:
                    self.input.scroll(amount)
                    self._last_scroll_y = y_now
                    return f"Scroll {amount:+d}"
            self._last_scroll_y = y_now
        else:
            self._last_scroll_y = None
        return None

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

        right = choose_hand([h for h in hands if h.label.lower() == "right"], "Right")
        left = choose_hand([h for h in hands if h.label.lower() == "left"], "Left")

        event = None
        active_value = None
        if right is not None:
            index = right.point(8)
            xy = (index[0], index[1])
            if self.calibration.contains(xy):
                kx, ky = self.calibration.map(xy)
                key = self.keyboard.key_at(kx, ky)
                active_value = key.value if key else None
                value = self.keyboard.trigger(
                    key,
                    pinching=pinch(right, 8) < self.config.pinch_threshold,
                )
                if value:
                    event = self._apply_key(value)

        if left is not None:
            modifier = left_hand_modifier(left)
            fired = self.modifier_edge.rising(modifier is not None)
            if fired and modifier:
                event = self._apply_key(modifier)
        else:
            self.modifier_edge.rising(False)

        overlay = frame.copy()
        self.keyboard.render(overlay, active_value)
        cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)
        return event

    def tick(self) -> TickResult:
        try:
            front_frame = self.front.read()
            if self.config.mirror_front:
                front_frame = cv2.flip(front_frame, 1)

            front_hands = self.front_tracker.process(
                front_frame,
                draw=self.config.draw_landmarks,
            )
            mouse_hand = choose_hand(front_hands, "Right")
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
            return TickResult(front_frame, top_frame, status, event)
        except CameraError as exc:
            return TickResult(None, None, "Camera error", str(exc))
        except Exception as exc:
            return TickResult(None, None, "Runtime error", f"{type(exc).__name__}: {exc}")

    def close(self) -> None:
        self.input.close()
        self.front.release()
        if self.top is not None:
            self.top.release()
        self.front_tracker.close()
        if self.top_tracker is not None:
            self.top_tracker.close()

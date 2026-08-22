from __future__ import annotations

from dataclasses import dataclass

import pyautogui


@dataclass(slots=True)
class PointerState:
    x: float | None = None
    y: float | None = None
    dragging: bool = False


class InputController:
    def __init__(self, *, smoothing: float = 0.35) -> None:
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0
        self.smoothing = smoothing
        self.state = PointerState()

    @property
    def screen_size(self) -> tuple[int, int]:
        size = pyautogui.size()
        return int(size.width), int(size.height)

    def move_normalized(self, x: float, y: float) -> None:
        width, height = self.screen_size
        target_x = max(0.0, min(1.0, x)) * (width - 1)
        target_y = max(0.0, min(1.0, y)) * (height - 1)
        if self.state.x is None or self.state.y is None:
            smooth_x, smooth_y = target_x, target_y
        else:
            alpha = self.smoothing
            smooth_x = self.state.x + alpha * (target_x - self.state.x)
            smooth_y = self.state.y + alpha * (target_y - self.state.y)
        self.state.x, self.state.y = smooth_x, smooth_y
        pyautogui.moveTo(int(smooth_x), int(smooth_y), duration=0)

    def click(self, button: str = "left") -> None:
        pyautogui.click(button=button)

    def drag_start(self) -> None:
        if not self.state.dragging:
            pyautogui.mouseDown(button="left")
            self.state.dragging = True

    def drag_end(self) -> None:
        if self.state.dragging:
            pyautogui.mouseUp(button="left")
            self.state.dragging = False

    def scroll(self, amount: int) -> None:
        if amount:
            pyautogui.scroll(amount)

    def press(self, key: str) -> None:
        pyautogui.press(key)

    def hotkey(self, *keys: str) -> None:
        pyautogui.hotkey(*keys)

    def close(self) -> None:
        self.drag_end()

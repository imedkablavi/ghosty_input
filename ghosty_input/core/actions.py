from __future__ import annotations

from dataclasses import dataclass
from math import hypot, pi
from time import monotonic

from .input_backends import InputBackend, create_input_backend


@dataclass(slots=True)
class PointerState:
    x: float | None = None
    y: float | None = None
    dragging: bool = False


class LowPass:
    def __init__(self) -> None:
        self.value: float | None = None

    def apply(self, value: float, alpha: float) -> float:
        if self.value is None:
            self.value = value
        else:
            self.value = alpha * value + (1.0 - alpha) * self.value
        return self.value

    def reset(self) -> None:
        self.value = None


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2.0 * pi * max(1e-4, cutoff))
    return 1.0 / (1.0 + tau / max(1e-4, dt))


class OneEuroAxis:
    """Adaptive low-pass filter: stable at rest, responsive during fast motion."""

    def __init__(
        self,
        min_cutoff: float = 1.25,
        beta: float = 0.045,
        d_cutoff: float = 1.0,
    ) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x = LowPass()
        self._dx = LowPass()
        self._last_raw: float | None = None
        self._last_time: float | None = None

    def apply(self, value: float, now: float) -> float:
        if self._last_time is None or self._last_raw is None:
            self._last_time = now
            self._last_raw = value
            return self._x.apply(value, 1.0)
        dt = max(1e-4, min(0.1, now - self._last_time))
        derivative = (value - self._last_raw) / dt
        filtered_derivative = self._dx.apply(derivative, _alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(filtered_derivative)
        result = self._x.apply(value, _alpha(cutoff, dt))
        self._last_time = now
        self._last_raw = value
        return result

    def reset(self) -> None:
        self._x.reset()
        self._dx.reset()
        self._last_raw = None
        self._last_time = None


class InputController:
    def __init__(
        self,
        *,
        smoothing: float = 0.28,
        deadzone_px: float = 1.5,
        backend: str = "auto",
        screen_size: tuple[int, int] | None = None,
        backend_instance: InputBackend | None = None,
    ) -> None:
        min_cutoff = 0.8 + (1.0 - smoothing) * 1.7
        beta = 0.025 + (1.0 - smoothing) * 0.055
        self._filter_x = OneEuroAxis(min_cutoff=min_cutoff, beta=beta)
        self._filter_y = OneEuroAxis(min_cutoff=min_cutoff, beta=beta)
        self.deadzone_px = deadzone_px
        self.state = PointerState()
        self.backend = backend_instance or create_input_backend(backend, screen_size=screen_size)

    @property
    def backend_name(self) -> str:
        return self.backend.name

    @property
    def screen_size(self) -> tuple[int, int]:
        return self.backend.screen_size

    def reset_pointer_filter(self) -> None:
        self._filter_x.reset()
        self._filter_y.reset()
        self.state.x = None
        self.state.y = None

    def move_normalized(self, x: float, y: float) -> None:
        width, height = self.screen_size
        nx = max(0.0, min(1.0, x))
        ny = max(0.0, min(1.0, y))
        now = monotonic()
        target_x = self._filter_x.apply(nx, now) * (width - 1)
        target_y = self._filter_y.apply(ny, now) * (height - 1)
        if self.state.x is not None and self.state.y is not None:
            if hypot(target_x - self.state.x, target_y - self.state.y) < self.deadzone_px:
                return
        self.state.x, self.state.y = target_x, target_y
        self.backend.move_to(int(target_x), int(target_y))

    def click(self, button: str = "left") -> None:
        self.backend.click(button)

    def drag_start(self) -> None:
        if not self.state.dragging:
            self.backend.mouse_down("left")
            self.state.dragging = True

    def drag_end(self) -> None:
        if self.state.dragging:
            self.backend.mouse_up("left")
            self.state.dragging = False

    def scroll(self, amount: int) -> None:
        if amount:
            self.backend.scroll(amount)

    def press(self, key: str) -> None:
        self.backend.press(key)

    def hotkey(self, *keys: str) -> None:
        self.backend.hotkey(*keys)

    def close(self) -> None:
        errors: list[Exception] = []
        if self.state.dragging:
            try:
                self.backend.mouse_up("left")
            except Exception as exc:
                errors.append(exc)
            finally:
                self.state.dragging = False
        try:
            self.backend.close()
        except Exception as exc:
            errors.append(exc)
        if errors:
            summary = "; ".join(f"{type(exc).__name__}: {exc}" for exc in errors)
            raise RuntimeError(f"Input controller cleanup failed: {summary}") from errors[0]

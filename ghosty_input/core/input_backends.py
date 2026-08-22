from __future__ import annotations

import importlib.util
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from string import ascii_lowercase
from time import sleep
from typing import Protocol


class InputBackendError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class InputEnvironment:
    system: str
    session_type: str
    desktop: str
    uinput_exists: bool
    uinput_writable: bool
    pyautogui_available: bool

    @property
    def wayland(self) -> bool:
        return self.session_type == "wayland"


def detect_session_type() -> str:
    explicit = os.environ.get("XDG_SESSION_TYPE", "").strip().lower()
    if explicit:
        return explicit
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def inspect_input_environment(
    *,
    system_name: str | None = None,
    uinput_path: Path = Path("/dev/uinput"),
) -> InputEnvironment:
    system = system_name or platform.system()
    exists = system == "Linux" and uinput_path.exists()
    writable = exists and os.access(uinput_path, os.W_OK)
    return InputEnvironment(
        system=system,
        session_type=detect_session_type(),
        desktop=os.environ.get("XDG_CURRENT_DESKTOP", "unknown") or "unknown",
        uinput_exists=exists,
        uinput_writable=writable,
        pyautogui_available=importlib.util.find_spec("pyautogui") is not None,
    )


def select_backend_name(
    requested: str,
    *,
    environment: InputEnvironment | None = None,
) -> str:
    if requested not in {"auto", "uinput", "pyautogui"}:
        raise InputBackendError(f"Unknown input backend: {requested}")
    if requested != "auto":
        return requested

    env = environment or inspect_input_environment()
    if env.system == "Linux" and env.uinput_writable:
        return "uinput"
    return "pyautogui"


class InputBackend(Protocol):
    name: str

    @property
    def screen_size(self) -> tuple[int, int]: ...

    def move_to(self, x: int, y: int) -> None: ...

    def click(self, button: str = "left") -> None: ...

    def mouse_down(self, button: str = "left") -> None: ...

    def mouse_up(self, button: str = "left") -> None: ...

    def scroll(self, amount: int) -> None: ...

    def press(self, key: str) -> None: ...

    def hotkey(self, *keys: str) -> None: ...

    def close(self) -> None: ...


class PyAutoGUIBackend:
    name = "PyAutoGUI"

    def __init__(self, screen_size: tuple[int, int] | None = None) -> None:
        try:
            import pyautogui
        except Exception as exc:
            raise InputBackendError(
                "PyAutoGUI could not initialize. On Wayland, enable the native "
                "uinput backend using the Linux setup script."
            ) from exc
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0
        self._pyautogui = pyautogui
        self._screen_size = screen_size

    @property
    def screen_size(self) -> tuple[int, int]:
        if self._screen_size and all(self._screen_size):
            return self._screen_size
        size = self._pyautogui.size()
        return int(size.width), int(size.height)

    def move_to(self, x: int, y: int) -> None:
        self._pyautogui.moveTo(x, y, duration=0)

    def click(self, button: str = "left") -> None:
        self._pyautogui.click(button=button)

    def mouse_down(self, button: str = "left") -> None:
        self._pyautogui.mouseDown(button=button)

    def mouse_up(self, button: str = "left") -> None:
        self._pyautogui.mouseUp(button=button)

    def scroll(self, amount: int) -> None:
        self._pyautogui.scroll(amount)

    def press(self, key: str) -> None:
        self._pyautogui.press(key)

    def hotkey(self, *keys: str) -> None:
        self._pyautogui.hotkey(*keys)

    def close(self) -> None:
        return None


class UInputBackend:
    """Linux-native keyboard/mouse injection through the kernel uinput API."""

    name = "Linux uinput"

    def __init__(self, screen_size: tuple[int, int] | None = None) -> None:
        if platform.system() != "Linux":
            raise InputBackendError("uinput is available only on Linux.")
        if not Path("/dev/uinput").exists():
            raise InputBackendError(
                "/dev/uinput is missing. Load the uinput kernel module and run "
                "the bundled ghosty-input-linux-setup.sh helper."
            )
        if not os.access("/dev/uinput", os.W_OK):
            raise InputBackendError(
                "/dev/uinput is not writable by this user. Run the bundled "
                "ghosty-input-linux-setup.sh helper, then sign out and back in."
            )

        try:
            from evdev import AbsInfo, UInput, ecodes as e
        except Exception as exc:
            raise InputBackendError("python-evdev is unavailable in this build.") from exc

        self._e = e
        self._screen_size = screen_size if screen_size and all(screen_size) else (1920, 1080)
        width, height = self._screen_size

        key_codes = self._keyboard_codes(e)
        capabilities = {
            e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE, *sorted(set(key_codes.values()))],
            e.EV_ABS: [
                (e.ABS_X, AbsInfo(0, 0, max(1, width - 1), 0, 0, 1)),
                (e.ABS_Y, AbsInfo(0, 0, max(1, height - 1), 0, 0, 1)),
            ],
            e.EV_REL: [e.REL_WHEEL],
        }
        try:
            self._device = UInput(
                capabilities,
                name="Ghosty Input Virtual Controller",
                vendor=0x1209,
                product=0x4748,
                version=0x0400,
                input_props=[e.INPUT_PROP_POINTER],
            )
        except Exception as exc:
            raise InputBackendError(f"Unable to create uinput device: {exc}") from exc
        self._keys = key_codes
        sleep(0.18)

    @staticmethod
    def _keyboard_codes(e) -> dict[str, int]:
        mapping: dict[str, int] = {
            "space": e.KEY_SPACE,
            "enter": e.KEY_ENTER,
            "backspace": e.KEY_BACKSPACE,
            "shift": e.KEY_LEFTSHIFT,
            "ctrl": e.KEY_LEFTCTRL,
            "alt": e.KEY_LEFTALT,
            "tab": e.KEY_TAB,
            "esc": e.KEY_ESC,
            "escape": e.KEY_ESC,
            "up": e.KEY_UP,
            "down": e.KEY_DOWN,
            "left": e.KEY_LEFT,
            "right": e.KEY_RIGHT,
        }
        for char in ascii_lowercase:
            mapping[char] = getattr(e, f"KEY_{char.upper()}")
        for digit in "0123456789":
            mapping[digit] = getattr(e, f"KEY_{digit}")
        return mapping

    @property
    def screen_size(self) -> tuple[int, int]:
        return self._screen_size

    def _button_code(self, button: str) -> int:
        buttons = {
            "left": self._e.BTN_LEFT,
            "right": self._e.BTN_RIGHT,
            "middle": self._e.BTN_MIDDLE,
        }
        if button not in buttons:
            raise InputBackendError(f"Unsupported mouse button: {button}")
        return buttons[button]

    def move_to(self, x: int, y: int) -> None:
        width, height = self._screen_size
        x = max(0, min(width - 1, int(x)))
        y = max(0, min(height - 1, int(y)))
        self._device.write(self._e.EV_ABS, self._e.ABS_X, x)
        self._device.write(self._e.EV_ABS, self._e.ABS_Y, y)
        self._device.syn()

    def click(self, button: str = "left") -> None:
        code = self._button_code(button)
        self._device.write(self._e.EV_KEY, code, 1)
        self._device.write(self._e.EV_KEY, code, 0)
        self._device.syn()

    def mouse_down(self, button: str = "left") -> None:
        self._device.write(self._e.EV_KEY, self._button_code(button), 1)
        self._device.syn()

    def mouse_up(self, button: str = "left") -> None:
        self._device.write(self._e.EV_KEY, self._button_code(button), 0)
        self._device.syn()

    def scroll(self, amount: int) -> None:
        value = max(-15, min(15, int(amount)))
        if value:
            self._device.write(self._e.EV_REL, self._e.REL_WHEEL, value)
            self._device.syn()

    def _key_code(self, key: str) -> int:
        normalized = key.lower()
        if normalized not in self._keys:
            raise InputBackendError(f"Unsupported uinput key: {key}")
        return self._keys[normalized]

    def press(self, key: str) -> None:
        code = self._key_code(key)
        self._device.write(self._e.EV_KEY, code, 1)
        self._device.write(self._e.EV_KEY, code, 0)
        self._device.syn()

    def hotkey(self, *keys: str) -> None:
        codes = [self._key_code(key) for key in keys]
        for code in codes:
            self._device.write(self._e.EV_KEY, code, 1)
        for code in reversed(codes):
            self._device.write(self._e.EV_KEY, code, 0)
        self._device.syn()

    def close(self) -> None:
        self._device.close()


def create_input_backend(
    requested: str = "auto",
    *,
    screen_size: tuple[int, int] | None = None,
) -> InputBackend:
    selected = select_backend_name(requested)
    if selected == "uinput":
        return UInputBackend(screen_size)
    if selected == "pyautogui":
        return PyAutoGUIBackend(screen_size)
    raise InputBackendError(f"No implementation for backend: {selected}")

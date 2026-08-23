import pytest

from ghosty_input.core.input_backends import (
    InputBackendError,
    InputEnvironment,
    select_backend_name,
    validate_backend_for_environment,
)


def make_env(*, linux=True, wayland=True, uinput=False):
    return InputEnvironment(
        system="Linux" if linux else "Windows",
        session_type="wayland" if wayland else "x11",
        desktop="KDE",
        uinput_exists=uinput,
        uinput_writable=uinput,
        pyautogui_available=True,
    )


def test_auto_prefers_uinput_when_linux_permissions_are_ready():
    assert select_backend_name("auto", environment=make_env(uinput=True)) == "uinput"


def test_auto_x11_falls_back_to_pyautogui_without_uinput_access():
    assert select_backend_name(
        "auto", environment=make_env(wayland=False, uinput=False)
    ) == "pyautogui"


def test_auto_wayland_remains_on_uinput_when_permissions_are_missing():
    assert select_backend_name("auto", environment=make_env(uinput=False)) == "uinput"


def test_explicit_pyautogui_is_rejected_on_wayland_fail_closed():
    env = make_env(uinput=False)
    with pytest.raises(InputBackendError, match="fail-closed"):
        validate_backend_for_environment("pyautogui", env)


def test_explicit_pyautogui_is_allowed_on_x11():
    validate_backend_for_environment("pyautogui", make_env(wayland=False, uinput=False))


def test_explicit_backend_is_respected_by_selection():
    assert select_backend_name(
        "pyautogui", environment=make_env(wayland=False, uinput=True)
    ) == "pyautogui"

from ghosty_input.core.input_backends import InputEnvironment, select_backend_name


def make_env(*, linux=True, wayland=True, uinput=False):
    return InputEnvironment(system="Linux" if linux else "Windows", session_type="wayland" if wayland else "x11", desktop="KDE", uinput_exists=uinput, uinput_writable=uinput, pyautogui_available=True)


def test_auto_prefers_uinput_when_linux_permissions_are_ready():
    assert select_backend_name("auto", environment=make_env(uinput=True)) == "uinput"


def test_auto_falls_back_to_pyautogui_without_uinput_access():
    assert select_backend_name("auto", environment=make_env(uinput=False)) == "pyautogui"


def test_explicit_backend_is_respected():
    assert select_backend_name("pyautogui", environment=make_env(uinput=True)) == "pyautogui"

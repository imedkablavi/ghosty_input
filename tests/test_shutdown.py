from ghosty_input.core.actions import InputController


class FailingReleaseBackend:
    name = "test"

    def __init__(self) -> None:
        self.closed = False
        self.mouse_up_calls = 0

    @property
    def screen_size(self) -> tuple[int, int]:
        return (1920, 1080)

    def move_to(self, x: int, y: int) -> None:
        return None

    def click(self, button: str = "left") -> None:
        return None

    def mouse_down(self, button: str = "left") -> None:
        return None

    def mouse_up(self, button: str = "left") -> None:
        self.mouse_up_calls += 1
        raise OSError("synthetic mouse-up failure")

    def scroll(self, amount: int) -> None:
        return None

    def press(self, key: str) -> None:
        return None

    def hotkey(self, *keys: str) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def test_input_close_attempts_backend_close_after_mouse_up_failure():
    backend = FailingReleaseBackend()
    controller = InputController(backend_instance=backend)
    controller.state.dragging = True

    try:
        controller.close()
    except RuntimeError as exc:
        assert "synthetic mouse-up failure" in str(exc)
    else:
        raise AssertionError("cleanup error should remain visible to the caller")

    assert backend.mouse_up_calls == 1
    assert backend.closed is True
    assert controller.state.dragging is False

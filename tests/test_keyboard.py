from ghosty_input.core.keyboard import VirtualKeyboard


def test_key_lookup():
    keyboard = VirtualKeyboard()
    q = next(key for key in keyboard.keys if key.value == "q")
    key = keyboard.key_at(q.x + q.w / 2, q.y + q.h / 2)
    assert key is not None
    assert key.value == "q"


def test_outside_layout_returns_none():
    keyboard = VirtualKeyboard()
    assert keyboard.key_at(-1, -1) is None

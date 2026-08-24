from ghosty_input.core.keyboard import VirtualKeyboard


def test_key_lookup_uses_safe_inset():
    keyboard = VirtualKeyboard(edge_inset=0.01)
    q = next(key for key in keyboard.keys if key.value == "q")
    assert keyboard.key_at(q.x + q.w / 2, q.y + q.h / 2).value == "q"
    assert keyboard.key_at(q.x + 0.001, q.y + q.h / 2) is None


def test_dwell_and_release_gate_prevent_duplicate_keys():
    keyboard = VirtualKeyboard(cooldown_ms=60, dwell_ms=80, release_ms=50, edge_inset=0)
    q = next(key for key in keyboard.keys if key.value == "q")
    assert keyboard.trigger(q, False, now=0.00) is None
    assert keyboard.trigger(q, False, now=0.10) is None
    assert keyboard.trigger(q, True, now=0.11) == "q"
    assert keyboard.trigger(q, True, now=0.30) is None
    assert keyboard.trigger(q, False, now=0.31) is None
    assert keyboard.trigger(q, False, now=0.37) is None
    assert keyboard.trigger(q, True, now=0.38) == "q"


def test_hover_mode_fires_once_per_key_visit():
    keyboard = VirtualKeyboard(cooldown_ms=60, hover_dwell_ms=500, edge_inset=0)
    q = next(key for key in keyboard.keys if key.value == "q")
    w = next(key for key in keyboard.keys if key.value == "w")
    assert keyboard.trigger_hover(q, now=0.0) is None
    assert keyboard.trigger_hover(q, now=0.49) is None
    assert keyboard.trigger_hover(q, now=0.51) == "q"
    assert keyboard.trigger_hover(q, now=1.2) is None
    assert keyboard.trigger_hover(w, now=1.3) is None
    assert keyboard.trigger_hover(w, now=1.81) == "w"


def test_outside_layout_returns_none():
    assert VirtualKeyboard().key_at(-1, -1) is None

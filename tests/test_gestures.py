import pytest

from ghosty_input.core.gestures import DwellPointTrigger, HysteresisGate, normalized_pinch


class FakeHand:
    def __init__(self, points):
        self.points = points
        self.label = "Right"

    def point(self, index):
        return self.points[index]


def make_hand(scale: float) -> FakeHand:
    points = [(0.5, 0.5, 0.0) for _ in range(21)]
    points[0] = (0.50, 0.70, 0.0)
    points[9] = (0.50, 0.70 - 0.20 * scale, 0.0)
    points[5] = (0.50 - 0.10 * scale, 0.58, 0.0)
    points[17] = (0.50 + 0.10 * scale, 0.58, 0.0)
    points[4] = (0.50 - 0.025 * scale, 0.45, 0.0)
    points[8] = (0.50 + 0.025 * scale, 0.45, 0.0)
    return FakeHand(points)


def test_normalized_pinch_is_scale_invariant():
    near = normalized_pinch(make_hand(1.0), 8)
    far = normalized_pinch(make_hand(0.5), 8)
    assert near == pytest.approx(far, rel=1e-6)


def test_hysteresis_prevents_threshold_chatter():
    gate = HysteresisGate(0.30, 0.42)
    assert gate.update(0.50) is False
    assert gate.update(0.29) is True
    assert gate.update(0.34) is True
    assert gate.update(0.41) is True
    assert gate.update(0.43) is False


def test_dwell_trigger_fires_once_until_pointer_moves_away():
    dwell = DwellPointTrigger(0.5, radius=0.02, release_radius=0.04)
    assert dwell.update((0.5, 0.5), now=0.0) is False
    assert dwell.update((0.505, 0.5), now=0.49) is False
    assert dwell.update((0.505, 0.5), now=0.51) is True
    assert dwell.update((0.506, 0.5), now=1.0) is False
    assert dwell.update((0.56, 0.5), now=1.1) is False
    assert dwell.update((0.56, 0.5), now=1.61) is True

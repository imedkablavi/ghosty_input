import pytest

from ghosty_input.core.calibration import DeskCalibration


def test_corner_mapping():
    calibration = DeskCalibration(
        [[0.10, 0.20], [0.90, 0.20], [0.90, 0.80], [0.10, 0.80]]
    )
    assert calibration.map((0.10, 0.20)) == pytest.approx((0.0, 0.0), abs=1e-5)
    assert calibration.map((0.90, 0.80)) == pytest.approx((1.0, 1.0), abs=1e-5)
    assert calibration.map((0.50, 0.50)) == pytest.approx((0.5, 0.5), abs=1e-5)


def test_requires_four_points():
    with pytest.raises(ValueError):
        DeskCalibration([[0.0, 0.0]])

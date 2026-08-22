import pytest

from ghosty_input.core.calibration import DeskCalibration


def test_corner_mapping_and_inverse():
    calibration = DeskCalibration([[0.10, 0.20], [0.90, 0.20], [0.90, 0.80], [0.10, 0.80]])
    assert calibration.map((0.10, 0.20)) == pytest.approx((0.0, 0.0), abs=1e-5)
    assert calibration.map((0.90, 0.80)) == pytest.approx((1.0, 1.0), abs=1e-5)
    assert calibration.unmap((0.5, 0.5)) == pytest.approx((0.5, 0.5), abs=1e-5)


def test_rejects_crossed_quad():
    with pytest.raises(ValueError):
        DeskCalibration([[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]])

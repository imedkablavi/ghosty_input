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


def test_independent_center_reprojection_error_is_near_zero_for_good_mapping():
    calibration = DeskCalibration([[0.10, 0.20], [0.90, 0.20], [0.90, 0.80], [0.10, 0.80]])
    error = calibration.reprojection_error([[0.50, 0.50, 0.50, 0.50]])
    assert error == pytest.approx(0.0, abs=1e-5)
    assert calibration.quality_with_validation([[0.50, 0.50, 0.50, 0.50]]) >= 90


def test_holdout_error_penalizes_misaligned_calibration_quality():
    calibration = DeskCalibration([[0.10, 0.20], [0.90, 0.20], [0.90, 0.80], [0.10, 0.80]])
    validation = [[0.58, 0.50, 0.50, 0.50]]
    error = calibration.reprojection_error(validation)
    assert error == pytest.approx(0.10, abs=1e-4)
    assert calibration.quality_with_validation(validation) < calibration.quality_score

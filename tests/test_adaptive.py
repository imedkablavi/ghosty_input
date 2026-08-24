import pytest

from ghosty_input.core.adaptive import AdaptivePinchCalibrator


def test_adaptive_pinch_profile_separates_open_and_pinched_samples():
    calibrator = AdaptivePinchCalibrator(samples_per_phase=10)
    for value in [0.78, 0.80, 0.82, 0.79, 0.81] * 2:
        calibrator.add(value)
    assert calibrator.phase == "pinch"

    for value in [0.18, 0.20, 0.19, 0.21, 0.17] * 2:
        calibrator.add(value)

    assert calibrator.complete is True
    profile = calibrator.profile
    assert profile is not None
    assert 0.20 < profile.engage_ratio < 0.50
    assert profile.release_ratio > profile.engage_ratio
    assert profile.separation > 0.5
    assert profile.sample_count == 20


def test_adaptive_calibration_rejects_overlapping_user_samples():
    calibrator = AdaptivePinchCalibrator(samples_per_phase=10)
    for _ in range(10):
        calibrator.add(0.40)
    for _ in range(10):
        calibrator.add(0.35)

    assert calibrator.complete is False
    assert calibrator.phase == "failed"
    assert "overlap" in calibrator.error.lower()


def test_adaptive_calibrator_rejects_too_few_requested_samples():
    with pytest.raises(ValueError):
        AdaptivePinchCalibrator(samples_per_phase=5)

import json

from ghosty_input.config import AppConfig, save_config


def test_persisted_config_contains_no_frame_or_typed_payload_fields(tmp_path):
    path = tmp_path / "config.json"
    config = AppConfig(
        gesture_calibrated=True,
        pinch_engage_ratio=0.28,
        pinch_release_ratio=0.41,
        calibration_points=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
        calibration_validation_points=[[0.5, 0.5, 0.5, 0.5]],
        onboarding_complete=True,
    )
    save_config(config, path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    keys = {str(key).lower() for key in payload}
    forbidden = {"frame", "frames", "typed", "typed_data", "keystrokes", "image", "images"}
    assert keys.isdisjoint(forbidden)
    assert payload["gesture_calibrated"] is True
    assert payload["pinch_engage_ratio"] == 0.28
    assert "gesture_samples" not in payload
    assert "pinch_samples" not in payload

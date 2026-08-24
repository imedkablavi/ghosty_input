from pathlib import Path

import pytest

from ghosty_input.config import AppConfig, load_config, load_config_state, save_config


def test_config_roundtrip(tmp_path: Path):
    path = tmp_path / "config.json"
    cfg = AppConfig(
        front_camera=2,
        front_camera_id="/dev/v4l/by-id/front",
        top_camera_id="/dev/v4l/by-id/desk",
        dual_camera=True,
        top_camera_autofocus=False,
        camera_reconnect_ms=1200,
        camera_width=1920,
        camera_height=1080,
        keyboard_dwell_ms=110,
        input_backend="uinput",
        pointer_activation_mode="hover",
        keyboard_activation_mode="hover",
        screen_width=2560,
        screen_height=1440,
        calibration_points=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
    )
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.front_camera == 2
    assert loaded.front_camera_id == "/dev/v4l/by-id/front"
    assert loaded.top_camera_id == "/dev/v4l/by-id/desk"
    assert loaded.dual_camera is True
    assert loaded.top_camera_autofocus is False
    assert loaded.camera_reconnect_ms == 1200
    assert loaded.camera_width == 1920
    assert loaded.keyboard_dwell_ms == 110
    assert loaded.input_backend == "uinput"
    assert loaded.pointer_activation_mode == "hover"
    assert loaded.keyboard_activation_mode == "hover"
    assert loaded.screen_width == 2560
    assert len(loaded.calibration_points) == 4


def test_old_smoothing_setting_migrates():
    cfg = AppConfig.from_dict({"smoothing": 0.44})
    assert cfg.pointer_smoothing == 0.44
    assert cfg.smoothing is None


def test_old_absolute_pinch_threshold_is_discarded():
    cfg = AppConfig.from_dict({"pinch_threshold": 0.055})
    assert cfg.pinch_threshold is None
    assert cfg.pinch_engage_ratio == AppConfig().pinch_engage_ratio


def test_invalid_config_is_quarantined_instead_of_silently_lost(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text('{"camera_fps": "broken"', encoding="utf-8")

    state = load_config_state(path)

    assert state.recovered is True
    assert state.config == AppConfig()
    assert state.backup_path is not None
    assert state.backup_path.exists()
    assert not path.exists()
    assert state.backup_path.read_text(encoding="utf-8") == '{"camera_fps": "broken"'
    assert "JSONDecodeError" in state.error


def test_non_object_config_is_quarantined(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("[]", encoding="utf-8")

    state = load_config_state(path)

    assert state.recovered is True
    assert state.backup_path is not None
    assert "TypeError" in state.error


def test_invalid_activation_mode_is_rejected():
    with pytest.raises(ValueError):
        AppConfig(pointer_activation_mode="magic").validate()

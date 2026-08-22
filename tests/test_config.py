from pathlib import Path

import pytest

from ghosty_input.config import AppConfig, load_config, save_config


def test_config_roundtrip(tmp_path: Path):
    path = tmp_path / "config.json"
    cfg = AppConfig(front_camera=2, dual_camera=True, camera_width=1920, camera_height=1080, keyboard_dwell_ms=110, input_backend="uinput", pointer_activation_mode="hover", keyboard_activation_mode="hover", screen_width=2560, screen_height=1440, calibration_points=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]])
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.front_camera == 2
    assert loaded.dual_camera is True
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


def test_invalid_activation_mode_is_rejected():
    with pytest.raises(ValueError):
        AppConfig(pointer_activation_mode="magic").validate()

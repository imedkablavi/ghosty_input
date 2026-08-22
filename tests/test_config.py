from pathlib import Path

from ghosty_input.config import AppConfig, load_config, save_config


def test_config_roundtrip(tmp_path: Path):
    path = tmp_path / "config.json"
    cfg = AppConfig(front_camera=2, dual_camera=True, calibration_points=[
        [0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]
    ])
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.front_camera == 2
    assert loaded.dual_camera is True
    assert len(loaded.calibration_points) == 4

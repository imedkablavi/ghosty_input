from __future__ import annotations

import json
import os
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


APP_NAME = "GhostyInput"


def app_data_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_NAME


@dataclass(slots=True)
class AppConfig:
    front_camera: int = 0
    top_camera: int = 1
    dual_camera: bool = False
    keyboard_enabled: bool = True
    mirror_front: bool = True
    draw_landmarks: bool = True
    smoothing: float = 0.35
    pinch_threshold: float = 0.055
    scroll_sensitivity: float = 5.0
    keyboard_cooldown_ms: int = 350
    calibration_points: list[list[float]] = field(default_factory=list)

    def validate(self) -> None:
        if self.front_camera < 0 or self.top_camera < 0:
            raise ValueError("Camera indices must be non-negative.")
        if not 0.05 <= self.smoothing <= 1.0:
            raise ValueError("Smoothing must be between 0.05 and 1.0.")
        if not 0.02 <= self.pinch_threshold <= 0.15:
            raise ValueError("Pinch threshold must be between 0.02 and 0.15.")
        if self.keyboard_cooldown_ms < 100:
            raise ValueError("Keyboard cooldown must be at least 100 ms.")
        if self.calibration_points and len(self.calibration_points) != 4:
            raise ValueError("Calibration requires exactly four points.")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AppConfig":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        cfg = cls(**{k: v for k, v in payload.items() if k in known})
        cfg.validate()
        return cfg


def config_path() -> Path:
    return app_data_dir() / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    target = path or config_path()
    if not target.exists():
        return AppConfig()
    try:
        return AppConfig.from_dict(json.loads(target.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return AppConfig()


def save_config(config: AppConfig, path: Path | None = None) -> None:
    config.validate()
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    temp.replace(target)

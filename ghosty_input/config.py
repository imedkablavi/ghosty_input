from __future__ import annotations

import json
import os
import platform
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_NAME = "GhostyInput"
INPUT_BACKENDS = {"auto", "uinput", "pyautogui"}
ACTIVATION_MODES = {"pinch", "hover"}


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
    front_camera_id: str = ""
    top_camera_id: str = ""
    dual_camera: bool = False

    camera_width: int = 1920
    camera_height: int = 1080
    camera_fps: int = 30
    camera_autofocus: bool = True
    top_camera_autofocus: bool = False
    camera_exposure: float | None = None
    camera_reconnect_ms: int = 900

    keyboard_enabled: bool = True
    mirror_front: bool = True
    draw_landmarks: bool = True

    detection_confidence: float = 0.65
    tracking_confidence: float = 0.65

    input_backend: str = "auto"
    screen_width: int = 0
    screen_height: int = 0
    linux_close_to_tray: bool = False
    linux_start_minimized: bool = False

    pointer_smoothing: float = 0.28
    pointer_deadzone_px: float = 1.5
    pointer_active_margin: float = 0.055
    pointer_activation_mode: str = "pinch"
    pointer_dwell_ms: int = 700
    pointer_dwell_radius: float = 0.018

    pinch_engage_ratio: float = 0.31
    pinch_release_ratio: float = 0.42
    scroll_sensitivity: float = 4.0

    keyboard_activation_mode: str = "pinch"
    keyboard_hover_ms: int = 650
    keyboard_dwell_ms: int = 90
    keyboard_release_ms: int = 70
    keyboard_cooldown_ms: int = 180
    keyboard_edge_inset: float = 0.012

    calibration_points: list[list[float]] = field(default_factory=list)

    # Compatibility with v0.2 config files. New code uses pointer_smoothing.
    # The old pinch_threshold was an absolute landmark distance and cannot be
    # safely mapped to the new palm-normalized pinch ratio, so it is discarded.
    smoothing: float | None = None
    pinch_threshold: float | None = None

    def __post_init__(self) -> None:
        if self.smoothing is not None:
            self.pointer_smoothing = float(self.smoothing)
            self.smoothing = None
        if self.pinch_threshold is not None:
            self.pinch_threshold = None

    def validate(self) -> None:
        if self.front_camera < 0 or self.top_camera < 0:
            raise ValueError("Camera indices must be non-negative.")
        if self.camera_width < 640 or self.camera_height < 480:
            raise ValueError("Camera resolution must be at least 640x480.")
        if not 15 <= self.camera_fps <= 120:
            raise ValueError("Camera FPS must be between 15 and 120.")
        if not 250 <= self.camera_reconnect_ms <= 10000:
            raise ValueError("Camera reconnect interval must be between 250 and 10000 ms.")
        if not 0.3 <= self.detection_confidence <= 0.95:
            raise ValueError("Detection confidence must be between 0.3 and 0.95.")
        if not 0.3 <= self.tracking_confidence <= 0.95:
            raise ValueError("Tracking confidence must be between 0.3 and 0.95.")
        if self.input_backend not in INPUT_BACKENDS:
            raise ValueError(f"Unsupported input backend: {self.input_backend}.")
        if bool(self.screen_width) != bool(self.screen_height):
            raise ValueError("Screen width and height must both be set or both be zero.")
        if self.screen_width and (self.screen_width < 640 or self.screen_height < 480):
            raise ValueError("Detected screen size is unexpectedly small.")
        if not 0.05 <= self.pointer_smoothing <= 0.95:
            raise ValueError("Pointer smoothing must be between 0.05 and 0.95.")
        if not 0.0 <= self.pointer_deadzone_px <= 20:
            raise ValueError("Pointer deadzone must be between 0 and 20 pixels.")
        if not 0.0 <= self.pointer_active_margin <= 0.2:
            raise ValueError("Pointer active margin must be between 0 and 0.2.")
        if self.pointer_activation_mode not in ACTIVATION_MODES:
            raise ValueError("Pointer activation mode must be 'pinch' or 'hover'.")
        if not 250 <= self.pointer_dwell_ms <= 2500:
            raise ValueError("Pointer dwell must be between 250 and 2500 ms.")
        if not 0.005 <= self.pointer_dwell_radius <= 0.08:
            raise ValueError("Pointer dwell radius must be between 0.005 and 0.08.")
        if not 0.12 <= self.pinch_engage_ratio <= 0.8:
            raise ValueError("Pinch engage ratio must be between 0.12 and 0.8.")
        if not self.pinch_engage_ratio + 0.03 <= self.pinch_release_ratio <= 1.2:
            raise ValueError("Pinch release ratio must be at least 0.03 above engage ratio.")
        if self.keyboard_activation_mode not in ACTIVATION_MODES:
            raise ValueError("Keyboard activation mode must be 'pinch' or 'hover'.")
        if not 250 <= self.keyboard_hover_ms <= 2500:
            raise ValueError("Keyboard hover activation must be between 250 and 2500 ms.")
        if not 20 <= self.keyboard_dwell_ms <= 800:
            raise ValueError("Keyboard dwell must be between 20 and 800 ms.")
        if not 20 <= self.keyboard_release_ms <= 800:
            raise ValueError("Keyboard release must be between 20 and 800 ms.")
        if not 60 <= self.keyboard_cooldown_ms <= 2000:
            raise ValueError("Keyboard cooldown must be between 60 and 2000 ms.")
        if not 0.0 <= self.keyboard_edge_inset <= 0.08:
            raise ValueError("Keyboard edge inset must be between 0 and 0.08.")
        if self.calibration_points and len(self.calibration_points) != 4:
            raise ValueError("Calibration requires exactly four points.")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AppConfig":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        cfg = cls(**{k: v for k, v in payload.items() if k in known})
        cfg.validate()
        return cfg


@dataclass(frozen=True, slots=True)
class ConfigLoadState:
    config: AppConfig
    recovered: bool = False
    backup_path: Path | None = None
    error: str = ""


def config_path() -> Path:
    return app_data_dir() / "config.json"


def _quarantine_invalid_config(target: Path) -> Path | None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = target.with_name(f"{target.stem}.invalid-{stamp}{target.suffix}")
    try:
        target.replace(backup)
    except OSError:
        return None
    return backup


def load_config_state(path: Path | None = None) -> ConfigLoadState:
    target = path or config_path()
    if not target.exists():
        return ConfigLoadState(AppConfig())
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("config root must be a JSON object")
        return ConfigLoadState(AppConfig.from_dict(payload))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        backup = _quarantine_invalid_config(target)
        return ConfigLoadState(
            AppConfig(),
            recovered=True,
            backup_path=backup,
            error=f"{type(exc).__name__}: {exc}",
        )


def load_config(path: Path | None = None) -> AppConfig:
    return load_config_state(path).config


def save_config(config: AppConfig, path: Path | None = None) -> None:
    config.validate()
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(config)
    payload.pop("smoothing", None)
    payload.pop("pinch_threshold", None)
    temp = target.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    if platform.system() != "Windows":
        try:
            temp.chmod(0o600)
        except OSError:
            pass
    temp.replace(target)

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from ghosty_input.config import AppConfig

from .calibration import DeskCalibration
from .camera import CameraDevice, CameraProbeResult, discover_cameras, probe_camera_stream
from .input_backends import InputEnvironment, inspect_input_environment, select_backend_name


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    code: str
    status: str
    title: str
    detail: str

    @property
    def blocking(self) -> bool:
        return self.status == "FAIL"


@dataclass(frozen=True, slots=True)
class PreflightReport:
    checks: tuple[PreflightCheck, ...]

    @property
    def ready(self) -> bool:
        return not any(check.blocking for check in self.checks)

    @property
    def failure_count(self) -> int:
        return sum(check.status == "FAIL" for check in self.checks)

    @property
    def warning_count(self) -> int:
        return sum(check.status == "WARN" for check in self.checks)

    def render(self) -> str:
        heading = (
            "ALPHA READY"
            if self.ready and not self.warning_count
            else "ALPHA READY WITH WARNINGS"
            if self.ready
            else "ALPHA BLOCKED"
        )
        lines = [
            "Ghosty Input Alpha Preflight",
            heading,
            f"Failures: {self.failure_count} · Warnings: {self.warning_count}",
        ]
        for check in self.checks:
            lines.append(f"[{check.status}] {check.title}: {check.detail}")
        return "\n".join(lines)


def _selected_camera(
    config_index: int,
    stable_id: str,
    cameras: list[CameraDevice],
) -> CameraDevice | None:
    if stable_id:
        for camera in cameras:
            if stable_id in {camera.stable_id, camera.path}:
                return camera
    return next((camera for camera in cameras if camera.index == config_index), None)


def _camera_identity(camera: CameraDevice | None) -> str:
    if camera is None:
        return "unavailable"
    return f"{camera.name} ({camera.path})"


def _camera_check(
    code: str,
    title: str,
    camera: CameraDevice | None,
    *,
    probe_streams: bool,
    stream_probe: Callable[[CameraDevice], CameraProbeResult],
) -> PreflightCheck:
    if camera is None:
        return PreflightCheck(code, "FAIL", title, "saved camera is not currently available")
    if not camera.accessible:
        return PreflightCheck(
            code,
            "FAIL",
            title,
            f"{_camera_identity(camera)} is not readable/writable by this user",
        )
    if camera.capture_capable is False:
        return PreflightCheck(
            code,
            "FAIL",
            title,
            f"{_camera_identity(camera)} is not a V4L2 video-capture node",
        )
    if probe_streams:
        result = stream_probe(camera)
        if not result.ok:
            return PreflightCheck(code, "FAIL", title, result.status)
        return PreflightCheck(
            code,
            "PASS",
            title,
            f"{_camera_identity(camera)} · {result.backend} · {result.resolution}",
        )
    capability = "capture" if camera.capture_capable is True else "capture capability unknown"
    return PreflightCheck(code, "PASS", title, f"{_camera_identity(camera)} · {capability}")


def run_preflight(
    config: AppConfig,
    *,
    cameras: list[CameraDevice] | None = None,
    environment: InputEnvironment | None = None,
    probe_streams: bool = False,
    stream_probe: Callable[[CameraDevice], CameraProbeResult] = probe_camera_stream,
    effective_uid: int | None = None,
) -> PreflightReport:
    """Evaluate whether the current configuration is safe to start for alpha testing."""

    env = environment or inspect_input_environment()
    checks: list[PreflightCheck] = []

    if env.system == "Linux":
        uid = (
            effective_uid
            if effective_uid is not None
            else getattr(os, "geteuid", lambda: -1)()
        )
        checks.append(
            PreflightCheck(
                "user.root",
                "FAIL" if uid == 0 else "PASS",
                "Desktop user",
                "do not run Ghosty Input as root" if uid == 0 else "running as a normal user",
            )
        )

        available = cameras if cameras is not None else discover_cameras()
        front = _selected_camera(config.front_camera, config.front_camera_id, available)
        checks.append(
            _camera_check(
                "camera.front",
                "Front camera",
                front,
                probe_streams=probe_streams,
                stream_probe=stream_probe,
            )
        )

        if config.dual_camera:
            top = _selected_camera(config.top_camera, config.top_camera_id, available)
            checks.append(
                _camera_check(
                    "camera.desk",
                    "Desk camera",
                    top,
                    probe_streams=probe_streams,
                    stream_probe=stream_probe,
                )
            )
            if front is not None and top is not None:
                same_stable = bool(front.stable_id) and front.stable_id == top.stable_id
                same_path = front.path == top.path
                if same_stable or same_path:
                    checks.append(
                        PreflightCheck(
                            "camera.distinct",
                            "FAIL",
                            "Dual-camera routing",
                            "front and desk camera resolve to the same physical device",
                        )
                    )
                else:
                    checks.append(
                        PreflightCheck(
                            "camera.distinct",
                            "PASS",
                            "Dual-camera routing",
                            "front and desk cameras are distinct",
                        )
                    )
    else:
        checks.append(
            PreflightCheck(
                "camera.platform",
                "WARN",
                "Camera preflight",
                "structured device preflight is currently Linux-first; runtime will validate the camera",
            )
        )

    selected_backend = select_backend_name(config.input_backend, environment=env)
    if env.system == "Linux" and env.wayland and not env.uinput_writable:
        checks.append(
            PreflightCheck(
                "input.wayland",
                "FAIL",
                "Wayland input",
                "/dev/uinput is not writable; run the bundled Linux setup helper and sign in again",
            )
        )
    elif selected_backend == "uinput" and not env.uinput_writable:
        checks.append(
            PreflightCheck(
                "input.backend",
                "FAIL",
                "Input backend",
                "native uinput was selected but /dev/uinput is unavailable or not writable",
            )
        )
    elif selected_backend == "pyautogui" and not env.pyautogui_available:
        checks.append(
            PreflightCheck(
                "input.backend",
                "FAIL",
                "Input backend",
                "PyAutoGUI is selected but the package cannot be imported",
            )
        )
    else:
        checks.append(
            PreflightCheck(
                "input.backend",
                "PASS",
                "Input backend",
                f"{selected_backend} is available for this session",
            )
        )

    if config.keyboard_enabled:
        if len(config.calibration_points) != 4:
            checks.append(
                PreflightCheck(
                    "keyboard.calibration",
                    "WARN",
                    "Desk keyboard calibration",
                    "mouse control can start, but the desk keyboard needs a 4-point calibration",
                )
            )
        else:
            try:
                quality = DeskCalibration(config.calibration_points).quality_score
            except ValueError as exc:
                checks.append(
                    PreflightCheck(
                        "keyboard.calibration",
                        "FAIL",
                        "Desk keyboard calibration",
                        f"saved calibration is invalid: {exc}",
                    )
                )
            else:
                checks.append(
                    PreflightCheck(
                        "keyboard.calibration",
                        "PASS" if quality >= 70 else "WARN",
                        "Desk keyboard calibration",
                        f"quality {quality}/100" + ("" if quality >= 70 else "; recalibration recommended"),
                    )
                )

    return PreflightReport(tuple(checks))

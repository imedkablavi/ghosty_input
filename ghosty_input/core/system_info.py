from __future__ import annotations

import os
import platform

from .camera import discover_cameras
from .input_backends import inspect_input_environment, select_backend_name


def diagnostic_report() -> str:
    env = inspect_input_environment()
    cameras = discover_cameras()
    selected = select_backend_name("auto", environment=env)
    uinput_state = (
        "ready"
        if env.uinput_writable
        else "present but permission denied"
        if env.uinput_exists
        else "not available"
    )
    warnings: list[str] = []
    if env.system == "Linux" and env.wayland and not env.uinput_writable:
        warnings.append(
            "Wayland detected without writable /dev/uinput; pointer injection may be limited "
            "until the Linux permissions helper is run."
        )
    if not cameras:
        warnings.append("No camera devices were discovered.")

    lines = [
        "Ghosty Input diagnostics",
        f"OS: {platform.platform()}",
        f"Session: {env.session_type}",
        f"Desktop: {env.desktop}",
        f"DISPLAY: {'set' if os.environ.get('DISPLAY') else 'not set'}",
        f"WAYLAND_DISPLAY: {'set' if os.environ.get('WAYLAND_DISPLAY') else 'not set'}",
        f"uinput: {uinput_state}",
        f"PyAutoGUI package: {'available' if env.pyautogui_available else 'missing'}",
        f"Recommended input backend: {selected}",
        f"Camera devices: {len(cameras)}",
    ]
    for camera in cameras[:12]:
        lines.append(f"  - {camera.index}: {camera.name} ({camera.path})")
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in warnings)
    return "\n".join(lines)

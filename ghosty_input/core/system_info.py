from __future__ import annotations

import os
import platform
from pathlib import Path

from .camera import discover_cameras
from .input_backends import inspect_input_environment, select_backend_name
from .linux_desktop import autostart_enabled, desktop_entry_installed


def _linux_distribution(path: Path = Path("/etc/os-release")) -> str:
    if platform.system() != "Linux" or not path.is_file():
        return "—"
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    except OSError:
        return "unknown"
    return values.get("PRETTY_NAME") or values.get("NAME") or "unknown"


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
            "Wayland detected without writable /dev/uinput; reliable system-wide input "
            "requires the bundled Linux permissions helper."
        )
    if env.system == "Linux" and os.geteuid() == 0:
        warnings.append("Ghosty Input is running as root. Run the application as your desktop user.")
    if not cameras:
        warnings.append("No camera devices were discovered.")
    inaccessible = [camera.path for camera in cameras if not camera.accessible]
    if inaccessible:
        warnings.append("Camera access is denied for: " + ", ".join(inaccessible[:6]))

    lines = [
        "Ghosty Input diagnostics",
        f"OS: {platform.platform()}",
        f"Distribution: {_linux_distribution()}",
        f"Kernel: {platform.release()}",
        f"Session: {env.session_type}",
        f"Desktop: {env.desktop}",
        f"DISPLAY: {'set' if os.environ.get('DISPLAY') else 'not set'}",
        f"WAYLAND_DISPLAY: {'set' if os.environ.get('WAYLAND_DISPLAY') else 'not set'}",
        f"uinput: {uinput_state}",
        f"PyAutoGUI package: {'available' if env.pyautogui_available else 'missing'}",
        f"Recommended input backend: {selected}",
        f"Desktop entry: {'installed' if desktop_entry_installed() else 'not installed'}",
        f"Autostart: {'enabled' if autostart_enabled() else 'disabled'}",
        f"Camera devices: {len(cameras)}",
    ]
    for camera in cameras[:12]:
        persistent = camera.stable_id if camera.stable_id != camera.path else "no persistent alias"
        access = "rw" if camera.accessible else "denied"
        lines.append(
            f"  - {camera.index}: {camera.name} ({camera.path}) · {access} · {persistent}"
        )
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in warnings)
    return "\n".join(lines)

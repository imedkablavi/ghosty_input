from __future__ import annotations

import os
import platform
from pathlib import Path

from .camera import discover_cameras, inspect_linux_video_nodes
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


def _linux_video_nodes(dev_root: Path = Path("/dev")) -> list[str]:
    if platform.system() != "Linux":
        return []
    try:
        return sorted(
            str(path)
            for path in dev_root.glob("video*")
            if path.name.removeprefix("video").isdigit()
        )
    except OSError:
        return []


def _opencv_videoio_backends() -> str:
    try:
        import cv2

        registry = getattr(cv2, "videoio_registry", None)
        if registry is None:
            return "unknown"
        names: list[str] = []
        for backend in registry.getBackends():
            try:
                name = registry.getBackendName(backend)
            except Exception:
                name = str(backend)
            if name not in names:
                names.append(name)
        return ", ".join(names) if names else "none"
    except Exception:
        return "unavailable"


def diagnostic_report() -> str:
    env = inspect_input_environment()
    cameras = discover_cameras()
    selected = select_backend_name("auto", environment=env)
    video_nodes = _linux_video_nodes()
    sysfs_v4l = Path("/sys/class/video4linux").exists() if env.system == "Linux" else False
    inspected_nodes = inspect_linux_video_nodes() if env.system == "Linux" else []
    capture_nodes = [node for node in inspected_nodes if node.capture_capable is True]
    non_capture_nodes = [node for node in inspected_nodes if node.capture_capable is False]
    unknown_nodes = [node for node in inspected_nodes if node.capture_capable is None]

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
        if env.system == "Linux" and not video_nodes:
            warnings.append(
                "No /dev/video* V4L2 devices are visible. If the camera works only through "
                "PipeWire/libcamera, a non-V4L2 capture backend is required."
            )
        elif inspected_nodes and all(node.capture_capable is False for node in inspected_nodes):
            warnings.append(
                "Video nodes exist, but VIDIOC_QUERYCAP reports no video-capture-capable node. "
                "The visible nodes appear to be metadata/output devices."
            )
        else:
            warnings.append(
                "No selectable camera was discovered. Run --camera-diagnose for a real stream probe."
            )

    inaccessible = [camera.path for camera in cameras if not camera.accessible]
    if inaccessible:
        warnings.append("Camera access is denied for: " + ", ".join(inaccessible[:6]))
    if env.system == "Linux" and video_nodes and not sysfs_v4l:
        warnings.append(
            "V4L2 device nodes are visible but /sys/class/video4linux is unavailable; direct "
            "/dev/video* fallback discovery is active."
        )
    if non_capture_nodes:
        warnings.append(
            f"Filtered {len(non_capture_nodes)} non-capture V4L2 node(s) from the camera selector."
        )

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
        f"OpenCV video backends: {_opencv_videoio_backends()}",
        f"V4L sysfs class: {'present' if sysfs_v4l else 'missing'}",
        f"V4L device nodes: {', '.join(video_nodes) if video_nodes else 'none'}",
        (
            "V4L capabilities: "
            f"capture={len(capture_nodes)}, non-capture={len(non_capture_nodes)}, "
            f"unknown={len(unknown_nodes)}"
        ),
        f"Camera devices: {len(cameras)}",
    ]
    for camera in cameras[:12]:
        persistent = camera.stable_id if camera.stable_id != camera.path else "no persistent alias"
        access = "rw" if camera.accessible else "denied"
        source = camera.discovery_source or "default"
        capability = (
            "capture"
            if camera.capture_capable is True
            else "unknown-capability"
        )
        driver = camera.driver or "unknown-driver"
        lines.append(
            f"  - {camera.index}: {camera.name} ({camera.path}) · {access} · {capability} · "
            f"{driver} · {source} · {persistent}"
        )
        if camera.bus_info:
            lines.append(f"      bus: {camera.bus_info}")
        if camera.capability_error:
            lines.append(f"      capability note: {camera.capability_error}")
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in warnings)
    return "\n".join(lines)

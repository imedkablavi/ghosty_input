from __future__ import annotations

from dataclasses import dataclass

from .camera import Camera, CameraDevice, discover_cameras


DEFAULT_MODE_CANDIDATES: tuple[tuple[int, int, int], ...] = (
    (640, 480, 30),
    (1280, 720, 30),
    (1280, 720, 60),
    (1920, 1080, 30),
    (1920, 1080, 60),
)


@dataclass(frozen=True, slots=True)
class CameraModeProbe:
    requested_width: int
    requested_height: int
    requested_fps: int
    ok: bool
    actual_width: int = 0
    actual_height: int = 0
    actual_fps: float = 0.0
    backend: str = ""
    exact: bool = False
    status: str = ""

    @property
    def requested(self) -> str:
        return f"{self.requested_width}x{self.requested_height}@{self.requested_fps}"

    @property
    def actual(self) -> str:
        if not self.ok:
            return "unavailable"
        return f"{self.actual_width}x{self.actual_height}@{self.actual_fps:.1f}"


def probe_camera_modes(
    device: CameraDevice,
    candidates: tuple[tuple[int, int, int], ...] = DEFAULT_MODE_CANDIDATES,
) -> list[CameraModeProbe]:
    results: list[CameraModeProbe] = []
    if device.capture_capable is False:
        return [
            CameraModeProbe(w, h, fps, False, status="not a video-capture node")
            for w, h, fps in candidates
        ]
    if not device.accessible:
        return [
            CameraModeProbe(w, h, fps, False, status="device is not accessible")
            for w, h, fps in candidates
        ]

    for width, height, fps in candidates:
        camera = Camera(
            device.index,
            width=width,
            height=height,
            fps=fps,
            device_id=device.stable_id,
            reconnect_interval=0.25,
        )
        try:
            camera.open()
            frame = camera.read()
            del frame
            info = camera.info
            fps_ok = info.fps <= 0.0 or info.fps >= fps * 0.85
            exact = info.width == width and info.height == height and fps_ok
            results.append(
                CameraModeProbe(
                    width,
                    height,
                    fps,
                    True,
                    actual_width=info.width,
                    actual_height=info.height,
                    actual_fps=info.fps,
                    backend=info.backend,
                    exact=exact,
                    status="exact" if exact else "backend negotiated fallback",
                )
            )
        except Exception as exc:
            results.append(
                CameraModeProbe(
                    width,
                    height,
                    fps,
                    False,
                    status=f"{type(exc).__name__}: {exc}",
                )
            )
        finally:
            camera.release()
    return results


def camera_mode_report(index: int) -> str:
    devices = discover_cameras()
    device = next((item for item in devices if item.index == index), None)
    if device is None:
        return f"Ghosty Input Camera Mode Probe\nCamera {index}: not discovered"

    lines = [
        "Ghosty Input Camera Mode Probe",
        f"Camera: {device.name} ({device.path})",
        "Each mode is opened independently and one real frame is discarded after inspection.",
    ]
    for result in probe_camera_modes(device):
        if result.ok:
            marker = "PASS" if result.exact else "WARN"
            lines.append(
                f"[{marker}] {result.requested} -> {result.actual} · {result.backend} · {result.status}"
            )
        else:
            lines.append(f"[FAIL] {result.requested} · {result.status}")
    return "\n".join(lines)

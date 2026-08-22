from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

import cv2


class CameraError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CameraDevice:
    index: int
    name: str
    path: str
    stable_id: str = ""
    accessible: bool = True

    @property
    def label(self) -> str:
        access = "" if self.accessible else " · permission denied"
        if self.stable_id and self.stable_id != self.path:
            persistent = Path(self.stable_id).name
            return f"{self.name} · {self.path} · {persistent}{access}"
        return f"{self.name} · {self.path}{access}"


@dataclass(frozen=True, slots=True)
class CameraInfo:
    index: int
    width: int
    height: int
    fps: float
    backend: str
    path: str = ""

    @property
    def resolution(self) -> str:
        return f"{self.width}×{self.height}"


def _persistent_video_links(
    *,
    dev_root: Path,
    by_id_root: Path,
    by_path_root: Path,
) -> dict[str, str]:
    """Map video node names to persistent Linux device links.

    Prefer /dev/v4l/by-id because it follows the physical camera across reboot.
    Fall back to by-path for devices that do not expose a serial-backed by-id link.
    """

    mapping: dict[str, str] = {}
    for directory in (by_id_root, by_path_root):
        if not directory.exists():
            continue
        try:
            links = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError:
            continue
        for link in links:
            try:
                resolved = link.resolve(strict=False)
            except OSError:
                continue
            name = resolved.name
            if not name.startswith("video"):
                continue
            # The first directory wins, so by-id is preferred over by-path.
            mapping.setdefault(name, str(link))
    return mapping


def discover_linux_cameras(
    root: Path = Path("/sys/class/video4linux"),
    *,
    dev_root: Path = Path("/dev"),
    by_id_root: Path = Path("/dev/v4l/by-id"),
    by_path_root: Path = Path("/dev/v4l/by-path"),
) -> list[CameraDevice]:
    devices: list[CameraDevice] = []
    if not root.exists():
        return devices

    persistent = _persistent_video_links(
        dev_root=dev_root,
        by_id_root=by_id_root,
        by_path_root=by_path_root,
    )

    for entry in sorted(root.glob("video*"), key=lambda p: p.name):
        suffix = entry.name.removeprefix("video")
        if not suffix.isdigit():
            continue
        index = int(suffix)
        try:
            name = (entry / "name").read_text(encoding="utf-8").strip()
        except OSError:
            name = f"Camera {index}"

        node = dev_root / entry.name
        path = str(node)
        stable_id = persistent.get(entry.name, path)
        # VideoCapture generally needs read/write access to a V4L2 node.
        accessible = node.exists() and os.access(node, os.R_OK | os.W_OK)
        devices.append(
            CameraDevice(
                index=index,
                name=name or f"Camera {index}",
                path=path,
                stable_id=stable_id,
                accessible=accessible,
            )
        )
    return sorted(devices, key=lambda device: device.index)


def discover_cameras(max_index: int = 10) -> list[CameraDevice]:
    if platform.system() == "Linux":
        return discover_linux_cameras()
    return [
        CameraDevice(index=i, name=f"Camera {i}", path=str(i), stable_id=str(i))
        for i in range(max_index)
    ]


def resolve_camera_index(
    stable_id: str,
    fallback_index: int,
    *,
    devices: list[CameraDevice] | None = None,
) -> int:
    """Resolve a saved persistent camera identity back to its current video index."""

    if not stable_id:
        return fallback_index
    candidates = devices if devices is not None else discover_cameras()
    for device in candidates:
        if stable_id in {device.stable_id, device.path}:
            return device.index
    return fallback_index


class Camera:
    def __init__(
        self,
        index: int,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        *,
        autofocus: bool = True,
        exposure: float | None = None,
        device_id: str = "",
        reconnect_interval: float = 0.9,
    ) -> None:
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self.autofocus = autofocus
        self.exposure = exposure
        self.device_id = device_id
        self.reconnect_interval = max(0.25, float(reconnect_interval))
        self._capture: cv2.VideoCapture | None = None
        self._last_frame_at: float | None = None
        self._measured_fps = 0.0
        self._reconnect_after = 0.0

    def _resolve_linux_index(self) -> None:
        if platform.system() == "Linux" and self.device_id:
            self.index = resolve_camera_index(self.device_id, self.index)

    def _open_with_backend(self, backend: int) -> cv2.VideoCapture:
        capture = cv2.VideoCapture(self.index, backend)
        if capture.isOpened():
            return capture
        capture.release()
        return cv2.VideoCapture()

    def _drop_capture(self) -> None:
        if self._capture is not None:
            self._capture.release()
        self._capture = None
        self._last_frame_at = None
        self._measured_fps = 0.0

    def open(self) -> None:
        if self._capture is not None and self._capture.isOpened():
            return

        now = monotonic()
        if now < self._reconnect_after:
            remaining = self._reconnect_after - now
            raise CameraError(f"Camera {self.index} reconnecting in {remaining:.1f}s.")

        self._resolve_linux_index()
        if platform.system() == "Windows":
            capture = self._open_with_backend(cv2.CAP_DSHOW)
            if not capture.isOpened():
                capture = self._open_with_backend(cv2.CAP_MSMF)
        elif platform.system() == "Linux":
            capture = self._open_with_backend(cv2.CAP_V4L2)
            if not capture.isOpened():
                capture = self._open_with_backend(cv2.CAP_ANY)
        else:
            capture = self._open_with_backend(cv2.CAP_ANY)

        if not capture.isOpened():
            capture.release()
            self._reconnect_after = monotonic() + self.reconnect_interval
            identity = self.device_id or str(self.index)
            raise CameraError(f"Unable to open camera {identity}; reconnect will be retried.")

        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_FPS, self.fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        capture.set(cv2.CAP_PROP_AUTOFOCUS, 1 if self.autofocus else 0)
        if self.exposure is not None:
            capture.set(cv2.CAP_PROP_EXPOSURE, float(self.exposure))

        for _ in range(3):
            capture.grab()

        self._capture = capture
        self._last_frame_at = None
        self._measured_fps = 0.0
        self._reconnect_after = 0.0

    @property
    def info(self) -> CameraInfo:
        path = f"/dev/video{self.index}" if platform.system() == "Linux" else str(self.index)
        if self._capture is None or not self._capture.isOpened():
            return CameraInfo(self.index, self.width, self.height, 0.0, "closed", path)
        width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH) or self.width)
        height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or self.height)
        reported_fps = float(self._capture.get(cv2.CAP_PROP_FPS) or 0.0)
        fps = self._measured_fps or reported_fps
        try:
            backend = self._capture.getBackendName()
        except Exception:
            backend = "unknown"
        return CameraInfo(self.index, width, height, fps, backend, path)

    def read(self):
        if self._capture is None or not self._capture.isOpened():
            self.open()
        assert self._capture is not None
        ok, frame = self._capture.read()
        if not ok or frame is None:
            current = self.index
            self._drop_capture()
            self._reconnect_after = monotonic() + self.reconnect_interval
            raise CameraError(f"Camera {current} lost its frame; attempting automatic reconnect.")

        now = monotonic()
        if self._last_frame_at is not None:
            dt = max(1e-4, now - self._last_frame_at)
            instant = 1.0 / dt
            self._measured_fps = (
                instant
                if self._measured_fps == 0
                else self._measured_fps * 0.9 + instant * 0.1
            )
        self._last_frame_at = now
        return frame

    def release(self) -> None:
        self._drop_capture()
        self._reconnect_after = 0.0

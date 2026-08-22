from __future__ import annotations

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

    @property
    def label(self) -> str:
        return f"{self.name} · {self.path}"


@dataclass(frozen=True, slots=True)
class CameraInfo:
    index: int
    width: int
    height: int
    fps: float
    backend: str

    @property
    def resolution(self) -> str:
        return f"{self.width}×{self.height}"


def discover_linux_cameras(root: Path = Path("/sys/class/video4linux")) -> list[CameraDevice]:
    devices: list[CameraDevice] = []
    if not root.exists():
        return devices
    for entry in sorted(root.glob("video*"), key=lambda p: p.name):
        suffix = entry.name.removeprefix("video")
        if not suffix.isdigit():
            continue
        index = int(suffix)
        try:
            name = (entry / "name").read_text(encoding="utf-8").strip()
        except OSError:
            name = f"Camera {index}"
        devices.append(CameraDevice(index=index, name=name or f"Camera {index}", path=f"/dev/video{index}"))
    return sorted(devices, key=lambda device: device.index)


def discover_cameras(max_index: int = 10) -> list[CameraDevice]:
    if platform.system() == "Linux":
        devices = discover_linux_cameras()
        if devices:
            return devices
    return [CameraDevice(index=i, name=f"Camera {i}", path=str(i)) for i in range(max_index)]


class Camera:
    def __init__(self, index: int, width: int = 1920, height: int = 1080, fps: int = 30, *, autofocus: bool = True, exposure: float | None = None) -> None:
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self.autofocus = autofocus
        self.exposure = exposure
        self._capture: cv2.VideoCapture | None = None
        self._last_frame_at: float | None = None
        self._measured_fps = 0.0

    def _open_with_backend(self, backend: int) -> cv2.VideoCapture:
        capture = cv2.VideoCapture(self.index, backend)
        if capture.isOpened():
            return capture
        capture.release()
        return cv2.VideoCapture()

    def open(self) -> None:
        if self._capture is not None and self._capture.isOpened():
            return
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
            raise CameraError(f"Unable to open camera {self.index}.")
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

    @property
    def info(self) -> CameraInfo:
        if self._capture is None or not self._capture.isOpened():
            return CameraInfo(self.index, self.width, self.height, 0.0, "closed")
        width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH) or self.width)
        height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or self.height)
        reported_fps = float(self._capture.get(cv2.CAP_PROP_FPS) or 0.0)
        fps = self._measured_fps or reported_fps
        try:
            backend = self._capture.getBackendName()
        except Exception:
            backend = "unknown"
        return CameraInfo(self.index, width, height, fps, backend)

    def read(self):
        if self._capture is None or not self._capture.isOpened():
            raise CameraError(f"Camera {self.index} is not open.")
        ok, frame = self._capture.read()
        if not ok or frame is None:
            raise CameraError(f"Camera {self.index} did not return a frame.")
        now = monotonic()
        if self._last_frame_at is not None:
            dt = max(1e-4, now - self._last_frame_at)
            instant = 1.0 / dt
            self._measured_fps = instant if self._measured_fps == 0 else self._measured_fps * 0.9 + instant * 0.1
        self._last_frame_at = now
        return frame

    def release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._last_frame_at = None
        self._measured_fps = 0.0

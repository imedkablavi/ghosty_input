from __future__ import annotations

import errno
import os
import platform
import struct
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Callable

import cv2


class CameraError(RuntimeError):
    pass


V4L2_CAP_VIDEO_CAPTURE = 0x00000001
V4L2_CAP_VIDEO_CAPTURE_MPLANE = 0x00001000
V4L2_CAP_META_CAPTURE = 0x00800000
V4L2_CAP_STREAMING = 0x04000000
V4L2_CAP_DEVICE_CAPS = 0x80000000
VIDIOC_QUERYCAP = 0x80685600
V4L2_CAPABILITY_SIZE = 104


@dataclass(frozen=True, slots=True)
class V4L2NodeCapabilities:
    capture_capable: bool | None
    card: str = ""
    driver: str = ""
    bus_info: str = ""
    effective_caps: int = 0
    error: str = ""

    @property
    def metadata_only(self) -> bool:
        return self.capture_capable is False and bool(self.effective_caps & V4L2_CAP_META_CAPTURE)


@dataclass(frozen=True, slots=True)
class CameraDevice:
    index: int
    name: str
    path: str
    stable_id: str = ""
    accessible: bool = True
    discovery_source: str = ""
    capture_capable: bool | None = None
    driver: str = ""
    bus_info: str = ""
    capability_error: str = ""

    @property
    def label(self) -> str:
        access = "" if self.accessible else " · permission denied"
        source = f" · {self.discovery_source}" if self.discovery_source else ""
        if self.stable_id and self.stable_id != self.path:
            persistent = Path(self.stable_id).name
            return f"{self.name} · {self.path} · {persistent}{source}{access}"
        return f"{self.name} · {self.path}{source}{access}"


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


@dataclass(frozen=True, slots=True)
class CameraProbeResult:
    index: int
    ok: bool
    status: str
    backend: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0

    @property
    def resolution(self) -> str:
        return f"{self.width}×{self.height}" if self.width and self.height else "—"


def _video_index(name: str) -> int | None:
    if not name.startswith("video"):
        return None
    suffix = name.removeprefix("video")
    return int(suffix) if suffix.isdigit() else None


def _decode_c_string(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("utf-8", errors="replace").strip()


def _parse_v4l2_capability_buffer(buffer: bytes | bytearray) -> V4L2NodeCapabilities:
    if len(buffer) < V4L2_CAPABILITY_SIZE:
        return V4L2NodeCapabilities(None, error="short VIDIOC_QUERYCAP response")
    driver = _decode_c_string(bytes(buffer[0:16]))
    card = _decode_c_string(bytes(buffer[16:48]))
    bus_info = _decode_c_string(bytes(buffer[48:80]))
    _version, capabilities, device_caps = struct.unpack_from("<III", buffer, 80)
    effective = device_caps if capabilities & V4L2_CAP_DEVICE_CAPS else capabilities
    capture = bool(effective & (V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_VIDEO_CAPTURE_MPLANE))
    return V4L2NodeCapabilities(
        capture_capable=capture,
        card=card,
        driver=driver,
        bus_info=bus_info,
        effective_caps=effective,
    )


def query_v4l2_capabilities(path: Path) -> V4L2NodeCapabilities:
    if platform.system() != "Linux":
        return V4L2NodeCapabilities(None, error="VIDIOC_QUERYCAP is Linux-only")
    try:
        import fcntl
    except ImportError:
        return V4L2NodeCapabilities(None, error="fcntl unavailable")

    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        message = os.strerror(exc.errno) if exc.errno else str(exc)
        return V4L2NodeCapabilities(None, error=message)

    try:
        buffer = bytearray(V4L2_CAPABILITY_SIZE)
        try:
            fcntl.ioctl(fd, VIDIOC_QUERYCAP, buffer, True)
        except OSError as exc:
            if exc.errno in {errno.ENOTTY, errno.EINVAL}:
                return V4L2NodeCapabilities(None, error="not a V4L2 capture-capability node")
            message = os.strerror(exc.errno) if exc.errno else str(exc)
            return V4L2NodeCapabilities(None, error=message)
        return _parse_v4l2_capability_buffer(buffer)
    finally:
        os.close(fd)


def _persistent_video_links(*, dev_root: Path, by_id_root: Path, by_path_root: Path) -> dict[str, str]:
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
            if _video_index(name) is None:
                continue
            mapping.setdefault(name, str(link))
    return mapping


def _sysfs_video_names(root: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    if not root.exists():
        return names
    try:
        entries = list(root.glob("video*"))
    except OSError:
        return names
    for entry in entries:
        if _video_index(entry.name) is None:
            continue
        try:
            name = (entry / "name").read_text(encoding="utf-8").strip()
        except OSError:
            name = ""
        names[entry.name] = name
    return names


def _direct_video_nodes(dev_root: Path) -> dict[str, Path]:
    nodes: dict[str, Path] = {}
    try:
        candidates = list(dev_root.glob("video*"))
    except OSError:
        return nodes
    for node in candidates:
        if _video_index(node.name) is not None:
            nodes[node.name] = node
    return nodes


CapabilityProbe = Callable[[Path], V4L2NodeCapabilities]


def inspect_linux_video_nodes(
    root: Path = Path("/sys/class/video4linux"),
    *,
    dev_root: Path = Path("/dev"),
    by_id_root: Path = Path("/dev/v4l/by-id"),
    by_path_root: Path = Path("/dev/v4l/by-path"),
    capability_probe: CapabilityProbe | None = None,
) -> list[CameraDevice]:
    sysfs_names = _sysfs_video_names(root)
    direct_nodes = _direct_video_nodes(dev_root)
    node_names = set(sysfs_names) | set(direct_nodes)
    if not node_names:
        return []

    persistent = _persistent_video_links(
        dev_root=dev_root,
        by_id_root=by_id_root,
        by_path_root=by_path_root,
    )
    probe = capability_probe or query_v4l2_capabilities

    devices: list[CameraDevice] = []
    for node_name in sorted(node_names, key=lambda name: _video_index(name) or 0):
        index = _video_index(node_name)
        if index is None:
            continue
        node = direct_nodes.get(node_name, dev_root / node_name)
        path = str(node)
        stable_id = persistent.get(node_name, path)
        accessible = node.exists() and os.access(node, os.R_OK | os.W_OK)
        source = (
            "sysfs+v4l"
            if node_name in sysfs_names and node_name in direct_nodes
            else "sysfs"
            if node_name in sysfs_names
            else "v4l"
        )
        caps = probe(node) if node.exists() else V4L2NodeCapabilities(None, error="device node missing")
        friendly_name = sysfs_names.get(node_name, "") or caps.card or f"Camera {index}"
        devices.append(
            CameraDevice(
                index=index,
                name=friendly_name,
                path=path,
                stable_id=stable_id,
                accessible=accessible,
                discovery_source=source,
                capture_capable=caps.capture_capable,
                driver=caps.driver,
                bus_info=caps.bus_info,
                capability_error=caps.error,
            )
        )
    return devices


def discover_linux_cameras(
    root: Path = Path("/sys/class/video4linux"),
    *,
    dev_root: Path = Path("/dev"),
    by_id_root: Path = Path("/dev/v4l/by-id"),
    by_path_root: Path = Path("/dev/v4l/by-path"),
    capability_probe: CapabilityProbe | None = None,
) -> list[CameraDevice]:
    devices = inspect_linux_video_nodes(
        root,
        dev_root=dev_root,
        by_id_root=by_id_root,
        by_path_root=by_path_root,
        capability_probe=capability_probe,
    )
    return [device for device in devices if device.capture_capable is not False]


def discover_cameras(max_index: int = 10) -> list[CameraDevice]:
    if platform.system() == "Linux":
        return discover_linux_cameras()
    return [
        CameraDevice(index=i, name=f"Camera {i}", path=str(i), stable_id=str(i))
        for i in range(max_index)
    ]


def resolve_camera_index(stable_id: str, fallback_index: int, *, devices: list[CameraDevice] | None = None) -> int:
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
        self._primed_frame = None

    def _resolve_linux_index(self) -> None:
        if platform.system() == "Linux" and self.device_id:
            self.index = resolve_camera_index(self.device_id, self.index)

    @staticmethod
    def _open_with_backend(index: int, backend: int) -> cv2.VideoCapture:
        capture = cv2.VideoCapture(index, backend)
        if capture.isOpened():
            return capture
        capture.release()
        return cv2.VideoCapture()

    def _drop_capture(self) -> None:
        if self._capture is not None:
            self._capture.release()
        self._capture = None
        self._primed_frame = None
        self._last_frame_at = None
        self._measured_fps = 0.0

    def _candidate_modes(self) -> list[tuple[int, int]]:
        modes = [(self.width, self.height), (1280, 720), (640, 480)]
        result: list[tuple[int, int]] = []
        for mode in modes:
            if mode not in result:
                result.append(mode)
        return result

    def _configure_capture(self, capture: cv2.VideoCapture, *, width: int, height: int, prefer_mjpg: bool) -> None:
        if prefer_mjpg:
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        capture.set(cv2.CAP_PROP_FPS, self.fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        capture.set(cv2.CAP_PROP_AUTOFOCUS, 1 if self.autofocus else 0)
        if self.exposure is not None:
            capture.set(cv2.CAP_PROP_EXPOSURE, float(self.exposure))

    @staticmethod
    def _prime(capture: cv2.VideoCapture):
        for _ in range(2):
            capture.grab()
        ok, frame = capture.read()
        return frame if ok and frame is not None and getattr(frame, "size", 0) else None

    def open(self) -> None:
        if self._capture is not None and self._capture.isOpened():
            return

        now = monotonic()
        if now < self._reconnect_after:
            remaining = self._reconnect_after - now
            raise CameraError(f"Camera {self.index} reconnecting in {remaining:.1f}s.")

        self._resolve_linux_index()
        if platform.system() == "Windows":
            backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
        elif platform.system() == "Linux":
            backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
        else:
            backends = [cv2.CAP_ANY]

        attempted: list[str] = []
        for backend in backends:
            for width, height in self._candidate_modes():
                for prefer_mjpg in ((True, False) if platform.system() == "Linux" else (False,)):
                    capture = self._open_with_backend(self.index, backend)
                    if not capture.isOpened():
                        attempted.append(f"backend={backend}:open-failed")
                        capture.release()
                        continue
                    self._configure_capture(capture, width=width, height=height, prefer_mjpg=prefer_mjpg)
                    frame = self._prime(capture)
                    if frame is not None:
                        self._capture = capture
                        self._primed_frame = frame
                        self._last_frame_at = None
                        self._measured_fps = 0.0
                        self._reconnect_after = 0.0
                        return
                    attempted.append(
                        f"backend={backend}:{width}x{height}:{'mjpg' if prefer_mjpg else 'default'}:no-frame"
                    )
                    capture.release()

        self._reconnect_after = monotonic() + self.reconnect_interval
        identity = self.device_id or str(self.index)
        summary = ", ".join(attempted[-4:]) if attempted else "no backend accepted the device"
        raise CameraError(f"Unable to read frames from camera {identity}. Tried V4L/OpenCV modes; {summary}.")

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

        if self._primed_frame is not None:
            frame = self._primed_frame
            self._primed_frame = None
        else:
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
            self._measured_fps = instant if self._measured_fps == 0 else self._measured_fps * 0.9 + instant * 0.1
        self._last_frame_at = now
        return frame

    def release(self) -> None:
        self._drop_capture()
        self._reconnect_after = 0.0


def probe_camera_stream(
    device: CameraDevice,
    *,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
) -> CameraProbeResult:
    if device.capture_capable is False:
        return CameraProbeResult(device.index, False, "not a video-capture node")
    if not device.accessible:
        return CameraProbeResult(device.index, False, "permission denied or device node missing")

    camera = Camera(device.index, width=width, height=height, fps=fps, device_id=device.stable_id, reconnect_interval=0.25)
    try:
        camera.open()
        frame = camera.read()
        if frame is None:
            return CameraProbeResult(device.index, False, "opened but returned no frame")
        info = camera.info
        return CameraProbeResult(device.index, True, "frame capture ok", info.backend, info.width, info.height, info.fps)
    except Exception as exc:
        return CameraProbeResult(device.index, False, f"{type(exc).__name__}: {exc}")
    finally:
        camera.release()


def camera_diagnostic_report(*, probe_streams: bool = True) -> str:
    if platform.system() != "Linux":
        return "Camera Doctor currently provides V4L2 diagnostics on Linux."

    nodes = inspect_linux_video_nodes()
    capture_nodes = [node for node in nodes if node.capture_capable is not False]
    lines = [
        "Ghosty Input Camera Doctor",
        f"V4L2 nodes: {len(nodes)}",
        f"Selectable capture nodes: {len(capture_nodes)}",
    ]
    if not nodes:
        lines.append("No /dev/video* nodes detected. Check kernel/libcamera/PipeWire exposure before Ghosty.")
        return "\n".join(lines)

    for node in nodes:
        capability = "capture" if node.capture_capable is True else "non-capture" if node.capture_capable is False else "unknown"
        access = "rw" if node.accessible else "denied"
        driver = node.driver or "unknown-driver"
        lines.append(f"- {node.path}: {node.name} · {capability} · {access} · {driver}")
        if node.bus_info:
            lines.append(f"    bus: {node.bus_info}")
        if node.capability_error:
            lines.append(f"    capability note: {node.capability_error}")
        if probe_streams and node.capture_capable is not False and node.accessible:
            result = probe_camera_stream(node)
            if result.ok:
                lines.append(f"    stream: OK · {result.backend} · {result.resolution} · {result.fps:.1f} FPS")
            else:
                lines.append(f"    stream: FAILED · {result.status}")
    return "\n".join(lines)

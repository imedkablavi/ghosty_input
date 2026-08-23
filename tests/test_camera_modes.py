from ghosty_input.core import camera_modes
from ghosty_input.core.camera import CameraDevice, CameraInfo


class FakeCamera:
    def __init__(
        self,
        index,
        width,
        height,
        fps,
        *,
        device_id="",
        reconnect_interval=0.25,
    ) -> None:
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self.device_id = device_id
        self.reconnect_interval = reconnect_interval
        self.released = False

    def open(self) -> None:
        return None

    def read(self):
        return object()

    @property
    def info(self) -> CameraInfo:
        # Simulate a backend that accepts 720p30 exactly but negotiates
        # 1080p60 down to 1080p30.
        actual_fps = 30.0 if self.fps >= 60 else float(self.fps)
        return CameraInfo(
            self.index,
            self.width,
            self.height,
            actual_fps,
            "FAKE",
            str(self.index),
        )

    def release(self) -> None:
        self.released = True


def _device(*, accessible=True, capture=True) -> CameraDevice:
    return CameraDevice(
        index=2,
        name="Synthetic Camera",
        path="2",
        stable_id="synthetic-camera-2",
        accessible=accessible,
        capture_capable=capture,
    )


def test_camera_mode_probe_distinguishes_exact_and_backend_fallback(monkeypatch):
    monkeypatch.setattr(camera_modes, "Camera", FakeCamera)

    results = camera_modes.probe_camera_modes(
        _device(),
        candidates=((1280, 720, 30), (1920, 1080, 60)),
    )

    assert len(results) == 2
    assert results[0].ok is True
    assert results[0].exact is True
    assert results[0].backend == "FAKE"
    assert results[0].actual == "1280x720@30.0"

    assert results[1].ok is True
    assert results[1].exact is False
    assert results[1].actual == "1920x1080@30.0"
    assert results[1].status == "backend negotiated fallback"


def test_camera_mode_probe_rejects_non_capture_and_inaccessible_nodes():
    non_capture = camera_modes.probe_camera_modes(
        _device(capture=False),
        candidates=((1280, 720, 30),),
    )
    denied = camera_modes.probe_camera_modes(
        _device(accessible=False),
        candidates=((1280, 720, 30),),
    )

    assert non_capture[0].ok is False
    assert "not a video-capture node" in non_capture[0].status
    assert denied[0].ok is False
    assert "not accessible" in denied[0].status

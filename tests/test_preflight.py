from ghosty_input.config import AppConfig
from ghosty_input.core.camera import CameraDevice, CameraProbeResult
from ghosty_input.core.input_backends import InputEnvironment
from ghosty_input.core.preflight import run_preflight


def _env(*, wayland: bool = True, uinput: bool = True) -> InputEnvironment:
    return InputEnvironment(
        system="Linux",
        session_type="wayland" if wayland else "x11",
        desktop="KDE",
        uinput_exists=uinput,
        uinput_writable=uinput,
        pyautogui_available=True,
    )


def _camera(index: int = 0, stable: str = "/dev/v4l/by-id/front") -> CameraDevice:
    return CameraDevice(
        index=index,
        name="USB Camera",
        path=f"/dev/video{index}",
        stable_id=stable,
        accessible=True,
        capture_capable=True,
        discovery_source="sysfs+v4l",
    )


def test_preflight_ready_with_camera_and_uinput():
    cfg = AppConfig(keyboard_enabled=False, front_camera_id="/dev/v4l/by-id/front")
    report = run_preflight(
        cfg,
        cameras=[_camera()],
        environment=_env(),
        effective_uid=1000,
    )
    assert report.ready is True
    assert report.failure_count == 0


def test_preflight_blocks_wayland_without_uinput():
    cfg = AppConfig(keyboard_enabled=False, front_camera_id="/dev/v4l/by-id/front")
    report = run_preflight(
        cfg,
        cameras=[_camera()],
        environment=_env(uinput=False),
        effective_uid=1000,
    )
    assert report.ready is False
    assert any(check.code == "input.wayland" and check.blocking for check in report.checks)


def test_preflight_blocks_missing_saved_camera():
    cfg = AppConfig(keyboard_enabled=False, front_camera=4, front_camera_id="/dev/v4l/by-id/missing")
    report = run_preflight(
        cfg,
        cameras=[_camera()],
        environment=_env(),
        effective_uid=1000,
    )
    assert report.ready is False
    assert any(check.code == "camera.front" and check.blocking for check in report.checks)


def test_preflight_blocks_same_physical_camera_in_dual_mode():
    front = _camera(0, "/dev/v4l/by-id/same")
    cfg = AppConfig(
        keyboard_enabled=False,
        dual_camera=True,
        front_camera=0,
        top_camera=0,
        front_camera_id=front.stable_id,
        top_camera_id=front.stable_id,
    )
    report = run_preflight(
        cfg,
        cameras=[front],
        environment=_env(),
        effective_uid=1000,
    )
    assert report.ready is False
    assert any(check.code == "camera.distinct" and check.blocking for check in report.checks)


def test_preflight_keyboard_without_calibration_is_warning_only():
    cfg = AppConfig(front_camera_id="/dev/v4l/by-id/front", keyboard_enabled=True)
    report = run_preflight(
        cfg,
        cameras=[_camera()],
        environment=_env(),
        effective_uid=1000,
    )
    assert report.ready is True
    assert report.warning_count == 1


def test_preflight_stream_probe_failure_blocks_startup():
    cfg = AppConfig(keyboard_enabled=False, front_camera_id="/dev/v4l/by-id/front")

    def fail_probe(device: CameraDevice) -> CameraProbeResult:
        return CameraProbeResult(device.index, False, "camera busy")

    report = run_preflight(
        cfg,
        cameras=[_camera()],
        environment=_env(),
        effective_uid=1000,
        probe_streams=True,
        stream_probe=fail_probe,
    )
    assert report.ready is False
    assert "camera busy" in report.render()

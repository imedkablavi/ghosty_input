import struct
from pathlib import Path

from ghosty_input.core.camera import (
    V4L2_CAP_DEVICE_CAPS,
    V4L2_CAP_META_CAPTURE,
    V4L2_CAP_STREAMING,
    V4L2_CAP_VIDEO_CAPTURE,
    V4L2NodeCapabilities,
    _parse_v4l2_capability_buffer,
    discover_linux_cameras,
    inspect_linux_video_nodes,
    resolve_camera_index,
)


def _fake_video_node(dev_root: Path, index: int) -> Path:
    node = dev_root / f"video{index}"
    node.parent.mkdir(parents=True, exist_ok=True)
    node.write_bytes(b"")
    node.chmod(0o666)
    return node


def _cap(*, capture: bool, card: str = "Camera") -> V4L2NodeCapabilities:
    flags = V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_STREAMING if capture else V4L2_CAP_META_CAPTURE
    return V4L2NodeCapabilities(
        capture,
        card=card,
        driver="uvcvideo",
        effective_caps=flags,
    )


def test_parse_v4l2_querycap_uses_device_caps():
    raw = bytearray(104)
    raw[0:8] = b"uvcvideo"
    raw[16:26] = b"USB Camera"
    raw[48:57] = b"usb-1-2.3"
    struct.pack_into(
        "<III",
        raw,
        80,
        0,
        V4L2_CAP_DEVICE_CAPS | V4L2_CAP_META_CAPTURE,
        V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_STREAMING,
    )

    caps = _parse_v4l2_capability_buffer(raw)

    assert caps.capture_capable is True
    assert caps.driver == "uvcvideo"
    assert caps.card == "USB Camera"
    assert caps.bus_info == "usb-1-2.3"


def test_linux_camera_discovery_uses_sysfs_names(tmp_path):
    sys_root = tmp_path / "sys"
    dev_root = tmp_path / "dev"
    first = sys_root / "video0"
    second = sys_root / "video2"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "name").write_text("Integrated Camera\n", encoding="utf-8")
    (second / "name").write_text("USB Desk Cam\n", encoding="utf-8")
    _fake_video_node(dev_root, 0)
    _fake_video_node(dev_root, 2)

    cameras = discover_linux_cameras(
        sys_root,
        dev_root=dev_root,
        by_id_root=tmp_path / "missing-by-id",
        by_path_root=tmp_path / "missing-by-path",
        capability_probe=lambda _path: _cap(capture=True),
    )
    assert [(camera.index, camera.name) for camera in cameras] == [
        (0, "Integrated Camera"),
        (2, "USB Desk Cam"),
    ]
    assert cameras[1].path == str(dev_root / "video2")
    assert cameras[0].discovery_source == "sysfs+v4l"


def test_linux_camera_discovery_falls_back_to_direct_dev_nodes(tmp_path):
    dev_root = tmp_path / "dev"
    _fake_video_node(dev_root, 1)
    _fake_video_node(dev_root, 4)

    cameras = discover_linux_cameras(
        tmp_path / "missing-sysfs",
        dev_root=dev_root,
        by_id_root=tmp_path / "missing-by-id",
        by_path_root=tmp_path / "missing-by-path",
        capability_probe=lambda path: _cap(capture=True, card=f"Card {path.name}"),
    )

    assert [(camera.index, camera.name) for camera in cameras] == [
        (1, "Card video1"),
        (4, "Card video4"),
    ]
    assert all(camera.discovery_source == "v4l" for camera in cameras)


def test_linux_camera_discovery_filters_metadata_only_nodes(tmp_path):
    dev_root = tmp_path / "dev"
    _fake_video_node(dev_root, 0)
    _fake_video_node(dev_root, 1)

    def probe(path: Path) -> V4L2NodeCapabilities:
        return _cap(capture=path.name == "video0")

    cameras = discover_linux_cameras(
        tmp_path / "missing-sysfs",
        dev_root=dev_root,
        by_id_root=tmp_path / "missing-by-id",
        by_path_root=tmp_path / "missing-by-path",
        capability_probe=probe,
    )
    all_nodes = inspect_linux_video_nodes(
        tmp_path / "missing-sysfs",
        dev_root=dev_root,
        by_id_root=tmp_path / "missing-by-id",
        by_path_root=tmp_path / "missing-by-path",
        capability_probe=probe,
    )

    assert [camera.index for camera in cameras] == [0]
    assert [camera.index for camera in all_nodes] == [0, 1]
    assert all_nodes[1].capture_capable is False


def test_linux_camera_discovery_keeps_unknown_capability_node(tmp_path):
    dev_root = tmp_path / "dev"
    _fake_video_node(dev_root, 5)

    cameras = discover_linux_cameras(
        tmp_path / "missing-sysfs",
        dev_root=dev_root,
        by_id_root=tmp_path / "missing-by-id",
        by_path_root=tmp_path / "missing-by-path",
        capability_probe=lambda _path: V4L2NodeCapabilities(
            None,
            error="permission denied",
        ),
    )

    assert [camera.index for camera in cameras] == [5]
    assert cameras[0].capability_error == "permission denied"


def test_linux_camera_discovery_keeps_sysfs_device_when_node_is_missing(tmp_path):
    sys_root = tmp_path / "sys"
    camera_sys = sys_root / "video3"
    camera_sys.mkdir(parents=True)
    (camera_sys / "name").write_text("Integrated Camera\n", encoding="utf-8")

    cameras = discover_linux_cameras(
        sys_root,
        dev_root=tmp_path / "dev",
        by_id_root=tmp_path / "missing-by-id",
        by_path_root=tmp_path / "missing-by-path",
    )

    assert len(cameras) == 1
    assert cameras[0].index == 3
    assert cameras[0].accessible is False
    assert cameras[0].discovery_source == "sysfs"


def test_linux_camera_discovery_prefers_persistent_by_id(tmp_path):
    sys_root = tmp_path / "sys"
    dev_root = tmp_path / "dev"
    by_id = dev_root / "v4l" / "by-id"
    by_id.mkdir(parents=True)
    camera_sys = sys_root / "video4"
    camera_sys.mkdir(parents=True)
    (camera_sys / "name").write_text("Desk Camera\n", encoding="utf-8")
    node = _fake_video_node(dev_root, 4)
    persistent = by_id / "usb-Ghosty_Desk_Cam-video-index0"
    persistent.symlink_to(node)

    cameras = discover_linux_cameras(
        sys_root,
        dev_root=dev_root,
        by_id_root=by_id,
        by_path_root=tmp_path / "missing-by-path",
        capability_probe=lambda _path: _cap(capture=True),
    )
    assert cameras[0].stable_id == str(persistent)
    assert resolve_camera_index(str(persistent), 0, devices=cameras) == 4


def test_resolve_camera_index_falls_back_when_camera_is_unplugged():
    assert resolve_camera_index("/dev/v4l/by-id/missing", 7, devices=[]) == 7

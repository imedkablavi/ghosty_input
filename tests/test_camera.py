from pathlib import Path

from ghosty_input.core.camera import discover_linux_cameras, resolve_camera_index


def _fake_video_node(dev_root: Path, index: int) -> Path:
    node = dev_root / f"video{index}"
    node.parent.mkdir(parents=True, exist_ok=True)
    node.write_bytes(b"")
    node.chmod(0o666)
    return node


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
    )
    assert [(camera.index, camera.name) for camera in cameras] == [
        (0, "Integrated Camera"),
        (2, "USB Desk Cam"),
    ]
    assert cameras[1].path == str(dev_root / "video2")


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
    )
    assert cameras[0].stable_id == str(persistent)
    assert resolve_camera_index(str(persistent), 0, devices=cameras) == 4


def test_resolve_camera_index_falls_back_when_camera_is_unplugged():
    assert resolve_camera_index("/dev/v4l/by-id/missing", 7, devices=[]) == 7

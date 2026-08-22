from ghosty_input.core.camera import discover_linux_cameras


def test_linux_camera_discovery_uses_sysfs_names(tmp_path):
    first = tmp_path / "video0"
    second = tmp_path / "video2"
    first.mkdir()
    second.mkdir()
    (first / "name").write_text("Integrated Camera\n", encoding="utf-8")
    (second / "name").write_text("USB Desk Cam\n", encoding="utf-8")

    cameras = discover_linux_cameras(tmp_path)
    assert [(camera.index, camera.name) for camera in cameras] == [
        (0, "Integrated Camera"),
        (2, "USB Desk Cam"),
    ]
    assert cameras[1].path == "/dev/video2"

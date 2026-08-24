from ghosty_input.core.performance import run_camera_soak


class FakeCamera:
    def __init__(self) -> None:
        self.opened = False
        self.released = False
        self.frames = 0

    def open(self) -> None:
        self.opened = True

    def read(self):
        self.frames += 1
        return object()

    def release(self) -> None:
        self.released = True


def test_camera_soak_runs_many_frames_without_persisting_payloads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    camera = FakeCamera()
    result = run_camera_soak(
        camera,
        seconds=30,
        expected_fps=30,
        max_frames=5000,
    )

    assert camera.opened is True
    assert camera.released is True
    assert result.frames == 5000
    assert result.reliability.frames == 5000
    assert result.rss_peak_bytes >= 0
    assert result.cpu_percent >= 0
    assert list(tmp_path.iterdir()) == []

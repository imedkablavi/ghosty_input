from ghosty_input.ui.instance_lock import acquire_instance_lock, instance_lock_path


def test_second_instance_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    first, first_error = acquire_instance_lock()
    assert first is not None
    assert first_error == ""
    assert instance_lock_path().parent == tmp_path / "GhostyInput"

    try:
        second, second_error = acquire_instance_lock()
        assert second is None
        assert "already running" in second_error.lower()
    finally:
        first.unlock()


def test_instance_lock_can_be_reacquired_after_unlock(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    first, _ = acquire_instance_lock()
    assert first is not None
    first.unlock()

    second, error = acquire_instance_lock()
    assert second is not None
    assert error == ""
    second.unlock()

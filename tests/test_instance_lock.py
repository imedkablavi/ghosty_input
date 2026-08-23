import ghosty_input.ui.instance_lock as instance_lock


def _use_test_data_dir(monkeypatch, tmp_path):
    data_dir = tmp_path / "GhostyInput"
    monkeypatch.setattr(instance_lock, "app_data_dir", lambda: data_dir)
    return data_dir


def test_second_instance_is_rejected(monkeypatch, tmp_path):
    data_dir = _use_test_data_dir(monkeypatch, tmp_path)
    first, first_error = instance_lock.acquire_instance_lock()
    assert first is not None
    assert first_error == ""
    assert instance_lock.instance_lock_path().parent == data_dir

    try:
        second, second_error = instance_lock.acquire_instance_lock()
        assert second is None
        assert "already running" in second_error.lower()
    finally:
        first.unlock()


def test_instance_lock_can_be_reacquired_after_unlock(monkeypatch, tmp_path):
    _use_test_data_dir(monkeypatch, tmp_path)
    first, _ = instance_lock.acquire_instance_lock()
    assert first is not None
    first.unlock()

    second, error = instance_lock.acquire_instance_lock()
    assert second is not None
    assert error == ""
    second.unlock()

import json
from pathlib import Path

from ghosty_input.core import update_state


def test_auto_update_check_runs_when_state_is_missing(tmp_path: Path):
    path = tmp_path / "update-state.json"
    assert update_state.should_auto_check(now=1000, path=path) is True


def test_auto_update_check_is_rate_limited(tmp_path: Path):
    path = tmp_path / "update-state.json"
    update_state.mark_auto_check_attempt(now=1000, path=path)
    assert update_state.should_auto_check(now=1001, path=path) is False
    assert (
        update_state.should_auto_check(
            now=1000 + update_state.AUTO_CHECK_INTERVAL_SECONDS,
            path=path,
        )
        is True
    )


def test_corrupt_update_state_does_not_block_checks(tmp_path: Path):
    path = tmp_path / "update-state.json"
    path.write_text("not-json", encoding="utf-8")
    assert update_state.should_auto_check(now=1000, path=path) is True


def test_update_state_write_is_valid_json(tmp_path: Path):
    path = tmp_path / "update-state.json"
    update_state.mark_auto_check_attempt(now=1234.5, path=path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["last_check_attempt"] == 1234.5

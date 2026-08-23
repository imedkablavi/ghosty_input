from __future__ import annotations

import json
import os
import time
from pathlib import Path

from ghosty_input.config import app_data_dir


AUTO_CHECK_INTERVAL_SECONDS = 6 * 60 * 60


def update_state_path() -> Path:
    return app_data_dir() / "update-state.json"


def _last_attempt(path: Path) -> float:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = float(payload.get("last_check_attempt", 0.0))
        return max(0.0, value)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, AttributeError):
        return 0.0


def should_auto_check(*, now: float | None = None, path: Path | None = None) -> bool:
    current = time.time() if now is None else float(now)
    target = path or update_state_path()
    last = _last_attempt(target)
    if last <= 0 or current < last:
        return True
    return current - last >= AUTO_CHECK_INTERVAL_SECONDS


def mark_auto_check_attempt(*, now: float | None = None, path: Path | None = None) -> None:
    current = time.time() if now is None else float(now)
    target = path or update_state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump({"last_check_attempt": current}, handle, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    if os.name != "nt":
        try:
            temp.chmod(0o600)
        except OSError:
            pass
    temp.replace(target)

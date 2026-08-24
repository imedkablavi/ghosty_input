from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLockFile

from ghosty_input.config import app_data_dir


def instance_lock_path() -> Path:
    return app_data_dir() / "ghosty-input.instance.lock"


def acquire_instance_lock() -> tuple[QLockFile | None, str]:
    """Acquire a long-lived desktop instance lock."""

    path = instance_lock_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return None, f"Cannot create the Ghosty Input data directory: {exc}"

    lock = QLockFile(str(path))
    lock.setStaleLockTime(0)
    if lock.tryLock(50):
        return lock, ""

    error = lock.error()
    if error == QLockFile.LockError.PermissionError:
        return None, f"Cannot create the instance lock at {path}. Check directory permissions."
    if error == QLockFile.LockError.UnknownError:
        return None, f"Cannot acquire the Ghosty Input instance lock at {path}."

    try:
        pid, hostname, appname = lock.getLockInfo()
    except Exception:
        return None, "Another Ghosty Input instance is already running."
    owner = appname or "Ghosty Input"
    location = f" on {hostname}" if hostname else ""
    return None, f"{owner} is already running (PID {pid}{location})."

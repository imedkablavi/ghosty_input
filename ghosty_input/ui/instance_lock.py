from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLockFile

from ghosty_input.config import app_data_dir


def instance_lock_path() -> Path:
    return app_data_dir() / "ghosty-input.instance.lock"


def acquire_instance_lock() -> tuple[QLockFile | None, str]:
    """Acquire a long-lived desktop instance lock.

    A second Ghosty Input process can otherwise race for the same V4L2 camera
    and uinput device, producing confusing camera-busy failures during alpha
    testing.
    """

    path = instance_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(path))
    lock.setStaleLockTime(0)
    if lock.tryLock(50):
        return lock, ""

    try:
        pid, hostname, appname = lock.getLockInfo()
    except Exception:
        return None, "another Ghosty Input instance is already running"
    owner = appname or "Ghosty Input"
    location = f" on {hostname}" if hostname else ""
    return None, f"{owner} is already running (PID {pid}{location})"

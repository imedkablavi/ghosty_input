from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_ID = "ghosty-input"


def _xdg_home(env_name: str, fallback: Path) -> Path:
    value = os.environ.get(env_name, "").strip()
    return Path(value).expanduser() if value else fallback


def config_home() -> Path:
    return _xdg_home("XDG_CONFIG_HOME", Path.home() / ".config")


def data_home() -> Path:
    return _xdg_home("XDG_DATA_HOME", Path.home() / ".local" / "share")


def desktop_entry_path() -> Path:
    return data_home() / "applications" / f"{APP_ID}.desktop"


def autostart_entry_path() -> Path:
    return config_home() / "autostart" / f"{APP_ID}.desktop"


def icon_install_path() -> Path:
    return data_home() / "icons" / "hicolor" / "256x256" / "apps" / f"{APP_ID}.png"


def application_executable() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return Path(sys.argv[0]).resolve()


def bundled_icon_path() -> Path | None:
    roots = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    roots.extend(
        [
            Path(__file__).resolve().parents[2],
            application_executable().parent,
        ]
    )
    for root in roots:
        candidate = root / "assets" / "logo.png"
        if candidate.is_file():
            return candidate
    return None


def _quote_exec(path: Path) -> str:
    return '"' + path.as_posix().replace('"', '\\"') + '"'


def desktop_entry(*, executable: Path | None = None, minimized: bool = False) -> str:
    exe = executable or application_executable()
    args = " --minimized" if minimized else ""
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            "Version=1.0",
            "Name=Ghosty Input",
            "Comment=Camera-based hand gesture mouse and desk keyboard",
            f"Exec={_quote_exec(exe)}{args}",
            "Icon=ghosty-input",
            "Terminal=false",
            "Categories=Utility;Accessibility;",
            "StartupNotify=true",
            "X-GNOME-Autostart-enabled=true",
            "",
        ]
    )


def _install_icon() -> None:
    source = bundled_icon_path()
    if source is None:
        return
    target = icon_install_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def install_desktop_entry(*, executable: Path | None = None) -> Path:
    if sys.platform != "linux":
        raise RuntimeError("Desktop integration is available only on Linux.")
    target = desktop_entry_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(desktop_entry(executable=executable), encoding="utf-8")
    target.chmod(0o644)
    _install_icon()
    return target


def remove_desktop_entry() -> None:
    desktop_entry_path().unlink(missing_ok=True)
    icon_install_path().unlink(missing_ok=True)


def set_autostart(enabled: bool, *, executable: Path | None = None) -> Path | None:
    if sys.platform != "linux":
        raise RuntimeError("Autostart is available only on Linux.")
    target = autostart_entry_path()
    if not enabled:
        target.unlink(missing_ok=True)
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(desktop_entry(executable=executable, minimized=True), encoding="utf-8")
    target.chmod(0o644)
    _install_icon()
    return target


def autostart_enabled() -> bool:
    return autostart_entry_path().is_file()


def desktop_entry_installed() -> bool:
    return desktop_entry_path().is_file()

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from ghosty_input.config import AppConfig
from ghosty_input.core.logging_setup import get_logger
from ghosty_input.core.update_manager import UpdateInfo, installation_kind, launch_installer
from ghosty_input.ui.update_controller import UpdateController


logger = get_logger("updates")


def _release_summary(info: UpdateInfo) -> str:
    notes = " ".join(info.body.strip().split())
    if len(notes) > 900:
        notes = notes[:897] + "..."
    kind = "Alpha / prerelease" if info.prerelease else "Stable"
    parts = [
        f"Ghosty Input {info.version} is available.",
        f"Channel: {kind}",
        f"Package: {info.asset.name}",
        "The package will be downloaded from the official GitHub Release and verified with SHA-256 before installation.",
    ]
    if notes:
        parts.extend(["", notes])
    return "\n".join(parts)


def _wait_for_check(controller: UpdateController, channel: str) -> tuple[UpdateInfo | None, str]:
    loop = QEventLoop()
    result: dict[str, object] = {"info": None, "error": ""}

    def checked(info: object) -> None:
        result["info"] = info
        loop.quit()

    def failed(message: str) -> None:
        result["error"] = message
        loop.quit()

    controller.checked.connect(checked)
    controller.failed.connect(failed)
    controller.check(channel)
    loop.exec()
    controller.checked.disconnect(checked)
    controller.failed.disconnect(failed)
    return result["info"], str(result["error"])  # type: ignore[return-value]


def _wait_for_download(
    controller: UpdateController, info: UpdateInfo
) -> tuple[Path | None, str]:
    loop = QEventLoop()
    result: dict[str, object] = {"path": None, "error": ""}
    progress = QProgressDialog(
        f"Downloading Ghosty Input {info.version} and verifying SHA-256…",
        "",
        0,
        0,
    )
    progress.setWindowTitle("Ghosty Input Update")
    progress.setCancelButton(None)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)
    progress.show()

    def downloaded(_info: object, path: str) -> None:
        result["path"] = Path(path)
        loop.quit()

    def failed(message: str) -> None:
        result["error"] = message
        loop.quit()

    controller.downloaded.connect(downloaded)
    controller.failed.connect(failed)
    controller.download(info)
    loop.exec()
    progress.close()
    controller.downloaded.disconnect(downloaded)
    controller.failed.disconnect(failed)
    return result["path"], str(result["error"])  # type: ignore[return-value]


def maybe_run_startup_update(config: AppConfig) -> bool:
    """Offer a verified one-click update for packaged builds.

    Returns True when an installer/updater was launched and the current process
    should exit instead of opening the normal control center.
    """

    kind = installation_kind()
    if not config.auto_check_updates or kind in {"source", "unsupported"}:
        return False

    app = QApplication.instance() or QApplication([])
    controller = UpdateController(app)
    info, error = _wait_for_check(controller, config.update_channel)
    if error:
        logger.warning("automatic update check failed: %s", error)
        return False
    if info is None:
        return False

    answer = QMessageBox.question(
        None,
        "Ghosty Input update available",
        _release_summary(info) + "\n\nDownload and install this update now?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if answer != QMessageBox.StandardButton.Yes:
        logger.info("update %s deferred by user", info.version)
        return False

    package, error = _wait_for_download(controller, info)
    if error or package is None:
        QMessageBox.critical(
            None,
            "Ghosty Input update failed",
            error or "The update package could not be downloaded.",
        )
        return False

    try:
        launch_installer(package, version=info.version)
    except Exception as exc:
        logger.exception("unable to launch verified update")
        QMessageBox.critical(None, "Ghosty Input update failed", str(exc))
        return False

    logger.info("verified update %s launched via %s", info.version, kind)
    return True

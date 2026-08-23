from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from ghosty_input.core.update_manager import UpdateInfo, check_for_update, download_verified_update


class _CheckThread(QThread):
    def __init__(self, channel: str) -> None:
        super().__init__()
        self.channel = channel
        self.result: UpdateInfo | None = None
        self.error = ""

    def run(self) -> None:
        try:
            self.result = check_for_update(channel=self.channel)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"


class _DownloadThread(QThread):
    def __init__(self, info: UpdateInfo) -> None:
        super().__init__()
        self.info = info
        self.path = ""
        self.error = ""

    def run(self) -> None:
        try:
            self.path = str(download_verified_update(self.info))
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"


class UpdateController(QObject):
    checked = Signal(object)
    downloaded = Signal(object, str)
    failed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._check: _CheckThread | None = None
        self._download: _DownloadThread | None = None

    @property
    def busy(self) -> bool:
        return bool(
            (self._check and self._check.isRunning())
            or (self._download and self._download.isRunning())
        )

    def check(self, channel: str) -> None:
        if self.busy:
            return
        self.busy_changed.emit(True)
        worker = _CheckThread(channel)
        worker.finished.connect(self._check_finished)
        self._check = worker
        worker.start()

    def download(self, info: UpdateInfo) -> None:
        if self.busy:
            return
        self.busy_changed.emit(True)
        worker = _DownloadThread(info)
        worker.finished.connect(self._download_finished)
        self._download = worker
        worker.start()

    def _check_finished(self) -> None:
        worker = self._check
        if worker is None:
            return
        error = worker.error
        result = worker.result
        self._check = None
        self.busy_changed.emit(False)
        if error:
            self.failed.emit(error)
        else:
            self.checked.emit(result)
        worker.deleteLater()

    def _download_finished(self) -> None:
        worker = self._download
        if worker is None:
            return
        error = worker.error
        info = worker.info
        path = worker.path
        self._download = None
        self.busy_changed.emit(False)
        if error:
            self.failed.emit(error)
        elif path:
            self.downloaded.emit(info, path)
        else:
            self.failed.emit("Update download finished without producing a package.")
        worker.deleteLater()

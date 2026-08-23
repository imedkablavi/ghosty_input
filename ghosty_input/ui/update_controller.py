from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from ghosty_input.core.update_manager import UpdateInfo, check_for_update, download_verified_update


class _CheckThread(QThread):
    found = Signal(object)
    failed = Signal(str)

    def __init__(self, channel: str) -> None:
        super().__init__()
        self.channel = channel

    def run(self) -> None:
        try:
            self.found.emit(check_for_update(channel=self.channel))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _DownloadThread(QThread):
    ready = Signal(object, str)
    failed = Signal(str)

    def __init__(self, info: UpdateInfo) -> None:
        super().__init__()
        self.info = info

    def run(self) -> None:
        try:
            package = download_verified_update(self.info)
            self.ready.emit(self.info, str(package))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


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
        worker.found.connect(self._check_done)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._check_finished)
        self._check = worker
        worker.start()

    def download(self, info: UpdateInfo) -> None:
        if self.busy:
            return
        self.busy_changed.emit(True)
        worker = _DownloadThread(info)
        worker.ready.connect(self.downloaded)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._download_finished)
        self._download = worker
        worker.start()

    def _check_done(self, info: object) -> None:
        self.checked.emit(info)

    def _failed(self, message: str) -> None:
        self.failed.emit(message)

    def _check_finished(self) -> None:
        self._check = None
        if not self.busy:
            self.busy_changed.emit(False)

    def _download_finished(self) -> None:
        self._download = None
        if not self.busy:
            self.busy_changed.emit(False)

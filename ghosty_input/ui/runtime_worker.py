from __future__ import annotations

from dataclasses import asdict
from queue import Empty, SimpleQueue

from PySide6.QtCore import QThread, Signal

from ghosty_input.config import AppConfig
from ghosty_input.core.engine import GhostyEngine


class RuntimeThread(QThread):
    """Run camera capture + MediaPipe inference away from the Qt UI thread."""

    result_ready = Signal(object)
    engine_ready = Signal(object)
    start_failed = Signal(str)
    calibration_applied = Signal(int)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        # Snapshot settings at engine start. UI changes are applied on the next
        # restart, while calibration updates use the command queue below.
        self.config = AppConfig.from_dict(asdict(config))
        self._commands: SimpleQueue[tuple[str, object]] = SimpleQueue()

    def request_calibration(self, points: list[list[float]]) -> None:
        self._commands.put(("calibration", [point[:] for point in points]))

    def _drain_commands(self, engine: GhostyEngine) -> None:
        while True:
            try:
                command, payload = self._commands.get_nowait()
            except Empty:
                return
            if command == "calibration":
                engine.set_calibration(payload)
                self.calibration_applied.emit(engine.calibration.quality_score)

    def run(self) -> None:
        engine: GhostyEngine | None = None
        try:
            engine = GhostyEngine(self.config)
            engine.start()
            self.engine_ready.emit(engine.front.info)
        except Exception as exc:
            if engine is not None:
                engine.close()
            self.start_failed.emit(f"{type(exc).__name__}: {exc}")
            return

        try:
            while not self.isInterruptionRequested():
                self._drain_commands(engine)
                result = engine.tick()
                self.result_ready.emit(result)
                if "error" in result.status.lower():
                    self.msleep(80)
        finally:
            engine.close()

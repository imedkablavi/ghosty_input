from __future__ import annotations

from dataclasses import asdict
from queue import Empty, SimpleQueue

from PySide6.QtCore import QThread, Signal

from ghosty_input.config import AppConfig
from ghosty_input.core.logging_setup import get_logger
from ghosty_input.core.product_engine import ProductGhostyEngine


logger = get_logger("runtime_worker")


class RuntimeThread(QThread):
    """Run camera capture + MediaPipe inference away from the Qt UI thread."""

    result_ready = Signal(object)
    engine_ready = Signal(object)
    start_failed = Signal(str)
    runtime_failed = Signal(str)
    calibration_applied = Signal(int)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        # Snapshot settings at engine start. UI changes are applied on the next
        # restart, while calibration updates use the command queue below.
        self.config = AppConfig.from_dict(asdict(config))
        self._commands: SimpleQueue[tuple[str, object]] = SimpleQueue()

    def request_calibration(self, points: list[list[float]]) -> None:
        self._commands.put(("calibration", [point[:] for point in points]))

    def stop(self, timeout_ms: int = 3000) -> bool:
        """Request cooperative shutdown and report whether the thread stopped."""

        self.requestInterruption()
        return self.wait(max(0, int(timeout_ms)))

    def _drain_commands(self, engine: ProductGhostyEngine) -> None:
        while True:
            try:
                command, payload = self._commands.get_nowait()
            except Empty:
                return
            if command == "calibration":
                engine.set_calibration(payload)
                quality = engine.calibration.quality_with_validation(
                    engine.config.calibration_validation_points
                )
                self.calibration_applied.emit(quality)

    def run(self) -> None:
        engine: ProductGhostyEngine | None = None
        try:
            engine = ProductGhostyEngine(self.config)
            engine.start()
            logger.info(
                "runtime started camera=%s backend=%s",
                engine.front.info.index,
                engine.input.backend_name,
            )
            self.engine_ready.emit(engine.front.info)
        except Exception as exc:
            if engine is not None:
                try:
                    engine.close()
                except Exception:
                    logger.exception("runtime cleanup failed after startup error")
            logger.exception("runtime startup failed")
            self.start_failed.emit(f"{type(exc).__name__}: {exc}")
            return

        runtime_error_streak = 0
        try:
            while not self.isInterruptionRequested():
                self._drain_commands(engine)
                result = engine.tick()
                self.result_ready.emit(result)

                if result.status.lower() == "runtime error":
                    runtime_error_streak += 1
                    if runtime_error_streak >= 5:
                        message = result.event or "Repeated runtime failure"
                        logger.error(
                            "runtime stopped after %d consecutive errors: %s",
                            runtime_error_streak,
                            message,
                        )
                        self.runtime_failed.emit(message)
                        break
                    self.msleep(80)
                else:
                    runtime_error_streak = 0
                    if "camera error" in result.status.lower():
                        self.msleep(80)
        except Exception as exc:
            logger.exception("runtime thread failed outside the engine tick guard")
            self.runtime_failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            try:
                engine.close()
            except Exception:
                logger.exception("runtime cleanup failed")
            logger.info("runtime stopped")

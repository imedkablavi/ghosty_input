from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ghosty_input.config import save_config
from ghosty_input.core.adaptive import AdaptivePinchCalibrator
from ghosty_input.core.calibration import DeskCalibration
from ghosty_input.core.input_backends import inspect_input_environment, select_backend_name
from ghosty_input.ui.instance_lock import acquire_instance_lock
from ghosty_input.ui.linux_window import LinuxWindow
from ghosty_input.ui.main_window import MainWindow
from ghosty_input.ui.onboarding import run_first_run_onboarding


class ProductReliabilityMixin:
    def _install_reliability_tab(self) -> None:
        self._pinch_calibrator: AdaptivePinchCalibrator | None = None
        self._validating_center = False

        page = QWidget()
        root = QVBoxLayout(page)

        environment = inspect_input_environment()
        backend = select_backend_name("auto", environment=environment)
        session = QGroupBox("Session and input safety")
        session_layout = QVBoxLayout(session)
        self.reliability_session = QLabel(
            f"Session: {environment.session_type} · desktop: {environment.desktop} · "
            f"recommended backend: {backend}"
        )
        self.reliability_session.setWordWrap(True)
        session_layout.addWidget(self.reliability_session)
        if environment.system == "Linux" and environment.wayland and not environment.uinput_writable:
            warning = QLabel(
                "BLOCKED: Wayland is fail-closed until /dev/uinput is writable. "
                "PyAutoGUI fallback is intentionally disabled for this session."
            )
            warning.setWordWrap(True)
            session_layout.addWidget(warning)
        root.addWidget(session)

        live = QGroupBox("Live reliability metrics")
        live_grid = QGridLayout(live)
        self.capture_metric = QLabel("Capture latency —")
        self.tick_metric = QLabel("Tick latency —")
        self.drop_metric = QLabel("Dropped —")
        self.reconnect_metric = QLabel("Reconnects —")
        live_grid.addWidget(self.capture_metric, 0, 0)
        live_grid.addWidget(self.tick_metric, 0, 1)
        live_grid.addWidget(self.drop_metric, 1, 0)
        live_grid.addWidget(self.reconnect_metric, 1, 1)
        root.addWidget(live)

        gesture = QGroupBox("Per-user gesture calibration")
        gesture_layout = QVBoxLayout(gesture)
        self.gesture_state = QLabel()
        self.gesture_state.setWordWrap(True)
        self.gesture_button = QPushButton("Calibrate pinch for this user")
        self.gesture_button.clicked.connect(self._start_pinch_calibration)
        gesture_layout.addWidget(self.gesture_state)
        gesture_layout.addWidget(self.gesture_button)
        root.addWidget(gesture)

        calibration = QGroupBox("Desk calibration validation")
        calibration_layout = QVBoxLayout(calibration)
        self.reprojection_state = QLabel()
        self.reprojection_state.setWordWrap(True)
        self.center_validation_button = QPushButton("Validate physical center point")
        self.center_validation_button.clicked.connect(self._start_center_validation)
        calibration_layout.addWidget(self.reprojection_state)
        calibration_layout.addWidget(self.center_validation_button)
        root.addWidget(calibration)
        root.addStretch()

        self.tabs.addTab(page, "Reliability")
        self._refresh_gesture_state()
        self._refresh_reprojection_state()

    def _refresh_gesture_state(self) -> None:
        calibrated = "yes" if self.config.gesture_calibrated else "no"
        self.gesture_state.setText(
            f"Adaptive profile: {calibrated} · engage {self.config.pinch_engage_ratio:.3f} · "
            f"release {self.config.pinch_release_ratio:.3f}. Raw samples are not persisted."
        )

    def _desk_calibration(self) -> DeskCalibration | None:
        if len(self.config.calibration_points) != 4:
            return None
        try:
            return DeskCalibration(self.config.calibration_points)
        except ValueError:
            return None

    def _refresh_reprojection_state(self) -> None:
        if len(self.config.calibration_points) != 4:
            self.reprojection_state.setText("Desk plane is not calibrated.")
            return
        try:
            calibration = DeskCalibration(self.config.calibration_points)
        except ValueError as exc:
            self.reprojection_state.setText(
                f"INVALID saved desk calibration · {exc} · run a new 4-point calibration."
            )
            return
        error = calibration.reprojection_error(self.config.calibration_validation_points)
        if error is None:
            self.reprojection_state.setText(
                f"Geometry quality {calibration.quality_score}/100 · independent center validation needed."
            )
            return
        quality = calibration.quality_with_validation(self.config.calibration_validation_points)
        level = "PASS" if error <= 0.04 else "WARN" if error <= 0.08 else "FAIL"
        self.reprojection_state.setText(
            f"{level} · hold-out reprojection error {error * 100:.2f}% of normalized plane · "
            f"validated quality {quality}/100."
        )

    def _running(self) -> bool:
        return bool(self.worker is not None and self.worker.isRunning())

    def _start_pinch_calibration(self) -> None:
        if not self._running():
            QMessageBox.information(
                self,
                "Adaptive pinch calibration",
                "Start the engine first so the right hand can be sampled locally.",
            )
            return
        self._pinch_calibrator = AdaptivePinchCalibrator(samples_per_phase=45)
        self.gesture_state.setText(
            "Step 1/2: keep the right hand OPEN and steady at the normal operating distance."
        )

    def _consume_adaptive_sample(self, ratio: float | None) -> None:
        calibrator = self._pinch_calibrator
        if calibrator is None or ratio is None:
            return
        previous = calibrator.phase
        phase = calibrator.add(ratio)
        if previous == "open" and phase == "pinch":
            self.gesture_state.setText(
                "Step 2/2: hold a normal thumb-index PINCH at the same camera distance."
            )
            return
        if phase == "failed":
            self.gesture_state.setText(f"Calibration failed: {calibrator.error}")
            self._pinch_calibrator = None
            return
        if not calibrator.complete:
            return

        profile = calibrator.profile
        assert profile is not None
        self.config.pinch_engage_ratio = profile.engage_ratio
        self.config.pinch_release_ratio = profile.release_ratio
        self.config.gesture_calibrated = True
        save_config(self.config)
        if hasattr(self, "pinch") and hasattr(self.pinch, "slider"):
            self.pinch.slider.setValue(int(round(profile.engage_ratio * 100)))
        self.gesture_state.setText(
            f"Saved per-user profile from {profile.sample_count} samples · "
            f"engage {profile.engage_ratio:.3f} · release {profile.release_ratio:.3f}. "
            "Restart the engine to apply the new gates. Raw samples were discarded."
        )
        self._pinch_calibrator = None

    def _start_center_validation(self) -> None:
        if not self._running():
            QMessageBox.information(
                self,
                "Calibration validation",
                "Start the engine first so the desk preview is live.",
            )
            return
        if len(self.config.calibration_points) != 4:
            QMessageBox.information(
                self,
                "Calibration validation",
                "Complete the four-corner desk calibration first.",
            )
            return
        try:
            DeskCalibration(self.config.calibration_points)
        except ValueError as exc:
            self._refresh_reprojection_state()
            QMessageBox.warning(
                self,
                "Calibration validation",
                f"The saved desk calibration is invalid: {exc}\n\nRun a new 4-point calibration first.",
            )
            return
        self._validating_center = True
        self.reprojection_state.setText(
            "Click the PHYSICAL CENTER of the calibrated keyboard plane in the desk preview."
        )

    def _capture_validation_point(self, x: float, y: float) -> None:
        if not self._validating_center:
            return
        self._validating_center = False
        try:
            calibration = DeskCalibration(self.config.calibration_points)
        except ValueError as exc:
            self._refresh_reprojection_state()
            if hasattr(self, "log"):
                self.log.appendPlainText(f"Calibration validation rejected: {exc}")
            return
        validation = [[float(x), float(y), 0.5, 0.5]]
        error = calibration.reprojection_error(validation)
        assert error is not None
        self.config.calibration_validation_points = validation
        save_config(self.config)
        if self._running():
            self.worker.request_calibration(
                self.config.calibration_points,
                self.config.calibration_validation_points,
            )
        self._refresh_reprojection_state()
        if hasattr(self, "log"):
            self.log.appendPlainText(
                f"Calibration center hold-out error: {error * 100:.2f}% of normalized plane."
            )

    def _consume_reliability_metrics(self, metrics) -> None:
        capture = float(getattr(metrics, "front_capture_ms", 0.0))
        maximum = float(getattr(metrics, "max_capture_ms", 0.0))
        tick = float(getattr(metrics, "tick_latency_ms", 0.0))
        dropped = int(getattr(metrics, "estimated_dropped_frames", 0))
        errors = int(getattr(metrics, "camera_errors", 0))
        reconnects = int(getattr(metrics, "reconnects", 0))
        self.capture_metric.setText(f"Capture EMA {capture:.2f} ms · max {maximum:.2f} ms")
        self.tick_metric.setText(f"Engine tick {tick:.2f} ms")
        self.drop_metric.setText(f"Estimated dropped frames {dropped} · camera errors {errors}")
        self.reconnect_metric.setText(f"Recovered reconnects {reconnects}")
        self._consume_adaptive_sample(getattr(metrics, "pinch_ratio", None))


class ProductMainWindow(ProductReliabilityMixin, MainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._install_reliability_tab()
        self.top_preview.clicked.connect(self._capture_validation_point)

    def begin_calibration(self) -> None:
        self.config.calibration_validation_points = []
        self._refresh_reprojection_state()
        super().begin_calibration()

    def _on_result(self, result) -> None:
        super()._on_result(result)
        self._consume_reliability_metrics(result.metrics)


class ProductLinuxWindow(ProductReliabilityMixin, LinuxWindow):
    def __init__(self) -> None:
        super().__init__()
        self._install_reliability_tab()
        self.desk_preview.clicked.connect(self._capture_validation_point)

    def begin_calibration(self) -> None:
        self.config.calibration_validation_points = []
        self._refresh_reprojection_state()
        super().begin_calibration()

    def _result(self, result) -> None:
        super()._result(result)
        self._consume_reliability_metrics(result.metrics)


def run_product_ui() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Ghosty Input")
    app.setOrganizationName("Ghosty Input")
    if not run_first_run_onboarding():
        return 0
    window = ProductMainWindow()
    window.show()
    return app.exec()


def run_product_linux_ui(*, start_minimized: bool = False) -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Ghosty Input")
    app.setOrganizationName("Ghosty Input")

    instance_lock, lock_error = acquire_instance_lock()
    if instance_lock is None:
        QMessageBox.information(None, "Ghosty Input is already running", lock_error)
        return 2

    try:
        if not run_first_run_onboarding():
            return 0
        window = ProductLinuxWindow()
        minimized = start_minimized or window.config.linux_start_minimized
        if minimized and window.tray:
            window.hide()
        elif minimized:
            window.showMinimized()
        else:
            window.show()
        return app.exec()
    finally:
        instance_lock.unlock()

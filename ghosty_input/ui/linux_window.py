from __future__ import annotations

import cv2
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ghosty_input.config import AppConfig, load_config, save_config
from ghosty_input.core.calibration import DeskCalibration
from ghosty_input.core.camera import CameraDevice, discover_cameras
from ghosty_input.core.engine import RuntimeMetrics, TickResult
from ghosty_input.core.system_info import diagnostic_report
from ghosty_input.ui.runtime_worker import RuntimeThread

STYLE = """
* { font-family: "Inter","Noto Sans","Segoe UI",sans-serif; font-size:13px; }
QMainWindow,QWidget { background:#090d13; color:#edf2f8; }
QFrame#card,QGroupBox { background:#111821; border:1px solid #243041; border-radius:12px; }
QGroupBox { margin-top:10px; padding:12px; font-weight:700; }
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; }
QLabel#brand { font-size:24px; font-weight:800; }
QLabel#muted { color:#8795a8; }
QLabel#preview { background:#05080c; border:1px solid #263447; border-radius:10px; }
QPushButton { min-height:34px; border:1px solid #30415a; border-radius:8px; background:#192435; padding:3px 12px; font-weight:700; }
QPushButton#primary { background:#6757ec; border-color:#8275ff; }
QPushButton#danger { background:#2a171d; border-color:#63313f; color:#ff9aac; }
QPushButton:disabled { color:#637083; background:#111720; border-color:#202a38; }
QComboBox { min-height:31px; border:1px solid #2a394d; border-radius:7px; background:#0b1119; padding:2px 7px; }
QSlider::groove:horizontal { height:5px; background:#273347; border-radius:2px; }
QSlider::handle:horizontal { width:16px; margin:-6px 0; background:#7768ff; border-radius:8px; }
QPlainTextEdit { background:#070a0f; border:1px solid #253144; border-radius:9px; color:#bec9d8; }
QTabWidget::pane { border:0; }
QTabBar::tab { background:#111821; border:1px solid #243041; border-radius:7px; padding:8px 14px; margin-right:4px; color:#8b98aa; }
QTabBar::tab:selected { color:white; background:#1b2432; }
"""


class Preview(QLabel):
    clicked = Signal(float, float)

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setObjectName("preview")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(390, 270)
        self._shown: tuple[int, int] | None = None

    def show_pixmap(self, pixmap: QPixmap) -> None:
        pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._shown = pixmap.width(), pixmap.height()
        self.setPixmap(pixmap)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._shown:
            pw, ph = self._shown
            x = (event.position().x() - (self.width() - pw) / 2) / max(1, pw)
            y = (event.position().y() - (self.height() - ph) / 2) / max(1, ph)
            if 0 <= x <= 1 and 0 <= y <= 1:
                self.clicked.emit(float(x), float(y))
        super().mousePressEvent(event)


class SliderRow(QWidget):
    def __init__(self, low: int, high: int, value: int, suffix: str = "") -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(low, high)
        self.slider.setValue(value)
        self.value = QLabel()
        self.value.setFixedWidth(62)
        row.addWidget(self.slider, 1)
        row.addWidget(self.value)
        self.suffix = suffix
        self.slider.valueChanged.connect(self._sync)
        self._sync(value)

    def _sync(self, value: int) -> None:
        self.value.setText(f"{value}{self.suffix}")


class LinuxWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.worker: RuntimeThread | None = None
        self.calibrating = False
        self.points: list[list[float]] = []
        self.setWindowTitle("Ghosty Input · Linux Preview")
        self.resize(1420, 850)
        self.setMinimumSize(1080, 690)
        self.setStyleSheet(STYLE)

        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        root = QVBoxLayout(root_widget)
        header = QHBoxLayout()
        brand = QLabel("GHOSTY INPUT")
        brand.setObjectName("brand")
        self.status = QLabel("STOPPED")
        self.status.setObjectName("muted")
        header.addWidget(brand)
        header.addWidget(QLabel("Linux precision preview · local processing"))
        header.addStretch()
        header.addWidget(self.status)
        root.addLayout(header)

        body = QHBoxLayout()
        root.addLayout(body, 1)
        body.addWidget(self._controls())
        self.tabs = QTabWidget()
        self.tabs.addTab(self._live_tab(), "Live")
        self.tabs.addTab(self._precision_tab(), "Precision")
        self.tabs.addTab(self._diagnostics_tab(), "Diagnostics")
        body.addWidget(self.tabs, 1)

        self.start.clicked.connect(self.start_engine)
        self.stop.clicked.connect(self.stop_engine)
        self.calibrate.clicked.connect(self.begin_calibration)
        self.save.clicked.connect(self.save_settings)
        self.refresh_cameras.clicked.connect(self.populate_cameras)
        self.refresh_diag.clicked.connect(self.refresh_diagnostics)
        self.desk_preview.clicked.connect(self.capture_calibration_point)
        self.populate_cameras()
        self.refresh_diagnostics()

    def _controls(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedWidth(295)
        layout = QVBoxLayout(frame)
        cameras = QGroupBox("Cameras")
        form = QFormLayout(cameras)
        self.front_camera = QComboBox()
        self.top_camera = QComboBox()
        self.refresh_cameras = QPushButton("Refresh cameras")
        self.dual = QCheckBox("Dedicated desk camera")
        self.dual.setChecked(self.config.dual_camera)
        form.addRow("Front", self.front_camera)
        form.addRow("Desk", self.top_camera)
        form.addRow(self.dual)
        form.addRow(self.refresh_cameras)
        layout.addWidget(cameras)

        modules = QGroupBox("Modules")
        modules_layout = QVBoxLayout(modules)
        self.keyboard = QCheckBox("Desk keyboard")
        self.keyboard.setChecked(self.config.keyboard_enabled)
        self.landmarks = QCheckBox("Tracking overlay")
        self.landmarks.setChecked(self.config.draw_landmarks)
        modules_layout.addWidget(self.keyboard)
        modules_layout.addWidget(self.landmarks)
        layout.addWidget(modules)

        self.start = QPushButton("Start engine")
        self.start.setObjectName("primary")
        self.stop = QPushButton("Stop engine")
        self.stop.setObjectName("danger")
        self.stop.setEnabled(False)
        self.calibrate = QPushButton("Calibrate desk plane")
        self.calibrate.setEnabled(False)
        layout.addWidget(self.start)
        layout.addWidget(self.stop)
        layout.addWidget(self.calibrate)
        hint = QLabel("On Wayland, Auto prefers the native uinput backend. Run Diagnostics first.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        return frame

    def _live_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        metrics = QGridLayout()
        self.metric_fps = QLabel("FPS —")
        self.metric_res = QLabel("Camera —")
        self.metric_hand = QLabel("Hand —")
        self.metric_backend = QLabel("Input —")
        for i, widget in enumerate((self.metric_fps, self.metric_res, self.metric_hand, self.metric_backend)):
            card = QFrame()
            card.setObjectName("card")
            box = QVBoxLayout(card)
            box.addWidget(widget)
            metrics.addWidget(card, 0, i)
        layout.addLayout(metrics)
        previews = QHBoxLayout()
        self.front_preview = Preview("Front camera")
        self.desk_preview = Preview("Desk camera / calibration")
        previews.addWidget(self.front_preview, 1)
        previews.addWidget(self.desk_preview, 1)
        layout.addLayout(previews, 1)
        return page

    def _precision_tab(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        camera = QGroupBox("Camera")
        form = QFormLayout(camera)
        self.resolution = QComboBox()
        self.resolution.addItems(["1280×720", "1920×1080", "2560×1440"])
        current = f"{self.config.camera_width}×{self.config.camera_height}"
        self.resolution.setCurrentText(current if self.resolution.findText(current) >= 0 else "1920×1080")
        self.fps = QComboBox()
        self.fps.addItems(["30", "60"])
        self.fps.setCurrentText(str(self.config.camera_fps))
        form.addRow("Requested", self.resolution)
        form.addRow("FPS", self.fps)

        input_box = QGroupBox("Linux input")
        form2 = QFormLayout(input_box)
        self.backend = QComboBox()
        self.backend.addItem("Auto (recommended)", "auto")
        self.backend.addItem("Native uinput", "uinput")
        self.backend.addItem("PyAutoGUI fallback", "pyautogui")
        self.pointer_mode = QComboBox()
        self.pointer_mode.addItem("Pinch", "pinch")
        self.pointer_mode.addItem("Hover dwell", "hover")
        self.pointer_dwell = SliderRow(300, 1600, self.config.pointer_dwell_ms, "ms")
        form2.addRow("Backend", self.backend)
        form2.addRow("Left click", self.pointer_mode)
        form2.addRow("Dwell", self.pointer_dwell)

        key_box = QGroupBox("Keyboard activation")
        form3 = QFormLayout(key_box)
        self.keyboard_mode = QComboBox()
        self.keyboard_mode.addItem("Pinch", "pinch")
        self.keyboard_mode.addItem("Hover dwell", "hover")
        self.keyboard_hover = SliderRow(300, 1600, self.config.keyboard_hover_ms, "ms")
        self.pinch = SliderRow(18, 60, int(self.config.pinch_engage_ratio * 100), "%")
        form3.addRow("Activation", self.keyboard_mode)
        form3.addRow("Hover dwell", self.keyboard_hover)
        form3.addRow("Pinch threshold", self.pinch)

        tracking = QGroupBox("Tracking")
        form4 = QFormLayout(tracking)
        self.smoothing = SliderRow(5, 95, int(self.config.pointer_smoothing * 100), "%")
        self.detection = SliderRow(30, 95, int(self.config.detection_confidence * 100), "%")
        self.tracking = SliderRow(30, 95, int(self.config.tracking_confidence * 100), "%")
        form4.addRow("Pointer smoothing", self.smoothing)
        form4.addRow("Detection", self.detection)
        form4.addRow("Tracking", self.tracking)

        grid.addWidget(camera, 0, 0)
        grid.addWidget(input_box, 0, 1)
        grid.addWidget(key_box, 1, 0)
        grid.addWidget(tracking, 1, 1)
        self.save = QPushButton("Save precision settings")
        self.save.setObjectName("primary")
        grid.addWidget(self.save, 2, 0, 1, 2)
        grid.setRowStretch(3, 1)
        self._select_data(self.backend, self.config.input_backend)
        self._select_data(self.pointer_mode, self.config.pointer_activation_mode)
        self._select_data(self.keyboard_mode, self.config.keyboard_activation_mode)
        return page

    def _diagnostics_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.refresh_diag = QPushButton("Refresh system diagnostics")
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.refresh_diag)
        layout.addWidget(self.diagnostics, 1)
        layout.addWidget(QLabel("Runtime events"))
        layout.addWidget(self.log, 1)
        return page

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def populate_cameras(self) -> None:
        devices = discover_cameras()
        self._fill_camera(self.front_camera, devices, self.config.front_camera)
        self._fill_camera(self.top_camera, devices, self.config.top_camera)

    @staticmethod
    def _fill_camera(combo: QComboBox, devices: list[CameraDevice], selected: int) -> None:
        combo.clear()
        for device in devices:
            combo.addItem(device.label, device.index)
        if combo.findData(selected) < 0:
            combo.addItem(f"Camera {selected}", selected)
        combo.setCurrentIndex(max(0, combo.findData(selected)))

    def _collect(self) -> AppConfig:
        cfg = self.config
        cfg.front_camera = int(self.front_camera.currentData())
        cfg.top_camera = int(self.top_camera.currentData())
        cfg.dual_camera = self.dual.isChecked()
        cfg.keyboard_enabled = self.keyboard.isChecked()
        cfg.draw_landmarks = self.landmarks.isChecked()
        width, height = self.resolution.currentText().split("×")
        cfg.camera_width, cfg.camera_height = int(width), int(height)
        cfg.camera_fps = int(self.fps.currentText())
        cfg.input_backend = str(self.backend.currentData())
        cfg.pointer_activation_mode = str(self.pointer_mode.currentData())
        cfg.pointer_dwell_ms = self.pointer_dwell.slider.value()
        cfg.keyboard_activation_mode = str(self.keyboard_mode.currentData())
        cfg.keyboard_hover_ms = self.keyboard_hover.slider.value()
        cfg.pointer_smoothing = self.smoothing.slider.value() / 100
        cfg.detection_confidence = self.detection.slider.value() / 100
        cfg.tracking_confidence = self.tracking.slider.value() / 100
        cfg.pinch_engage_ratio = self.pinch.slider.value() / 100
        cfg.pinch_release_ratio = min(1.2, cfg.pinch_engage_ratio + 0.11)
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.virtualGeometry()
            cfg.screen_width, cfg.screen_height = geometry.width(), geometry.height()
        cfg.validate()
        return cfg

    def save_settings(self) -> None:
        try:
            self.config = self._collect()
            save_config(self.config)
            self.log.appendPlainText("Settings saved. Restart the engine to apply runtime changes.")
            self.refresh_diagnostics()
        except Exception as exc:
            QMessageBox.warning(self, "Ghosty Input", str(exc))

    def start_engine(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        try:
            self.config = self._collect()
            save_config(self.config)
        except Exception as exc:
            QMessageBox.critical(self, "Ghosty Input", str(exc))
            return
        worker = RuntimeThread(self.config)
        worker.engine_ready.connect(self._engine_ready)
        worker.start_failed.connect(self._start_failed)
        worker.result_ready.connect(self._result)
        worker.calibration_applied.connect(lambda _: None)
        worker.finished.connect(self._worker_finished)
        self.worker = worker
        self.start.setEnabled(False)
        self.stop.setEnabled(True)
        self.status.setText("STARTING")
        worker.start()

    def _engine_ready(self, info) -> None:
        self.status.setText("RUNNING")
        self.calibrate.setEnabled(self.config.keyboard_enabled)
        self.log.appendPlainText(f"Camera {info.index} · {info.resolution} · {info.backend}")

    def _start_failed(self, message: str) -> None:
        self.status.setText("RUNTIME ERROR")
        self.log.appendPlainText(message)
        self.refresh_diagnostics()
        self.tabs.setCurrentIndex(2)
        QMessageBox.critical(self, "Ghosty Input", message)

    def _worker_finished(self) -> None:
        self.start.setEnabled(True)
        self.stop.setEnabled(False)
        self.calibrate.setEnabled(False)
        self.worker = None

    def stop_engine(self) -> None:
        if self.worker:
            self.worker.requestInterruption()
            self.worker.wait(2200)
            if not self.worker.isRunning():
                self.worker = None
        self.start.setEnabled(True)
        self.stop.setEnabled(False)
        self.calibrate.setEnabled(False)
        self.status.setText("STOPPED")

    def begin_calibration(self) -> None:
        if not self.worker or not self.worker.isRunning():
            QMessageBox.information(self, "Calibration", "Start the engine first.")
            return
        self.points = []
        self.calibrating = True
        self.tabs.setCurrentIndex(0)
        self.status.setText("CALIBRATION · TOP LEFT")

    def capture_calibration_point(self, x: float, y: float) -> None:
        if not self.calibrating or not self.worker:
            return
        self.points.append([x, y])
        labels = ("TOP RIGHT", "BOTTOM RIGHT", "BOTTOM LEFT")
        if len(self.points) < 4:
            self.status.setText(f"CALIBRATION · {labels[len(self.points) - 1]}")
            return
        try:
            calibration = DeskCalibration(self.points)
        except ValueError as exc:
            self.calibrating = False
            self.status.setText("RUNNING")
            QMessageBox.warning(self, "Calibration rejected", str(exc))
            return
        self.calibrating = False
        self.config.calibration_points = [point[:] for point in self.points]
        save_config(self.config)
        self.worker.request_calibration(self.config.calibration_points)
        self.status.setText("RUNNING")
        self.log.appendPlainText(f"Calibration quality: {calibration.quality_score}/100")

    def refresh_diagnostics(self) -> None:
        self.diagnostics.setPlainText(diagnostic_report())

    def _update_metrics(self, metrics: RuntimeMetrics) -> None:
        self.metric_fps.setText(f"FPS {metrics.front_fps:.0f}")
        self.metric_res.setText(f"Camera {metrics.camera_resolution}")
        self.metric_hand.setText(f"Hand {metrics.hand_confidence * 100:.0f}%" if metrics.hand_count else "Hand —")
        self.metric_backend.setText(f"Input {metrics.input_backend}")

    @staticmethod
    def _pixmap(frame) -> QPixmap:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888).copy()
        return QPixmap.fromImage(image)

    def _result(self, result: TickResult) -> None:
        self.status.setText(result.status.upper())
        self._update_metrics(result.metrics)
        if result.event:
            self.log.appendPlainText(result.event)
        if result.front_frame is not None:
            self.front_preview.show_pixmap(self._pixmap(result.front_frame))
        if result.top_frame is not None:
            self.desk_preview.show_pixmap(self._pixmap(result.top_frame))

    def closeEvent(self, event) -> None:  # noqa: N802
        self.stop_engine()
        event.accept()


def run_linux_ui() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Ghosty Input")
    app.setOrganizationName("Ghosty Input")
    window = LinuxWindow()
    window.show()
    return app.exec()

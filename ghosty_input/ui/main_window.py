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
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ghosty_input.config import AppConfig, load_config, save_config
from ghosty_input.core.calibration import DeskCalibration
from ghosty_input.core.engine import RuntimeMetrics, TickResult
from ghosty_input.ui.runtime_worker import RuntimeThread


STYLE = """
* { font-family: "Segoe UI","Inter",Arial; font-size: 13px; }
QMainWindow,QWidget { background:#090c12; color:#e8edf7; }
QFrame#header,QFrame#card,QGroupBox {
  background:#101620; border:1px solid #202b3a; border-radius:14px;
}
QFrame#header { background:#0d121b; }
QGroupBox { margin-top:12px; padding:14px 10px 10px; font-weight:700; }
QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 5px; }
QLabel#brand { font-size:25px; font-weight:800; letter-spacing:1px; }
QLabel#muted,QLabel#metricTitle { color:#8491a5; }
QLabel#metricTitle { font-size:11px; font-weight:650; }
QLabel#metricValue { font-size:21px; font-weight:750; }
QLabel#preview {
  background:#05070b; border:1px solid #263347; border-radius:12px; color:#738096;
}
QPushButton {
  min-height:34px; border-radius:9px; padding:4px 13px; font-weight:700;
  background:#182232; border:1px solid #2a384c; color:#dce6f5;
}
QPushButton:hover { background:#202d40; border-color:#3a4c66; }
QPushButton#primary { background:#6d5dfc; border-color:#8376ff; color:white; }
QPushButton#danger { background:#2a171d; border-color:#60313f; color:#ff9aae; }
QPushButton:disabled { color:#5e6878; background:#111720; border-color:#1c2532; }
QComboBox,QSpinBox {
  min-height:31px; background:#0b1018; border:1px solid #263347;
  border-radius:8px; padding:2px 8px;
}
QSlider::groove:horizontal { height:5px; border-radius:2px; background:#263143; }
QSlider::handle:horizontal {
  width:16px; margin:-6px 0; border-radius:8px; background:#7b6cff;
}
QSlider::sub-page:horizontal { background:#6d5dfc; border-radius:2px; }
QTabWidget::pane { border:0; }
QTabBar::tab {
  background:#101620; border:1px solid #202b3a; padding:9px 16px;
  margin-right:5px; border-radius:8px; color:#8794a8; font-weight:650;
}
QTabBar::tab:selected { background:#1b2231; color:#f2f5fa; border-color:#3c4760; }
QPlainTextEdit {
  background:#070a0f; border:1px solid #202b3a; border-radius:12px;
  color:#b5c0d1; padding:8px;
}
"""


class PreviewLabel(QLabel):
    clicked = Signal(float, float)

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setObjectName("preview")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(390, 270)
        self._pixmap_size: tuple[int, int] | None = None

    def set_frame_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._pixmap_size = (scaled.width(), scaled.height())
        self.setPixmap(scaled)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._pixmap_size is None:
            return super().mousePressEvent(event)
        pw, ph = self._pixmap_size
        x = (event.position().x() - (self.width() - pw) / 2) / max(1, pw)
        y = (event.position().y() - (self.height() - ph) / 2) / max(1, ph)
        if 0 <= x <= 1 and 0 <= y <= 1:
            self.clicked.emit(float(x), float(y))
        return super().mousePressEvent(event)


class MetricCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 10, 13, 10)
        heading = QLabel(title.upper())
        heading.setObjectName("metricTitle")
        self.value = QLabel("—")
        self.value.setObjectName("metricValue")
        layout.addWidget(heading)
        layout.addWidget(self.value)


class SliderControl(QWidget):
    def __init__(self, minimum: int, maximum: int, value: int, suffix: str = "") -> None:
        super().__init__()
        self.suffix = suffix
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.label = QLabel()
        self.label.setFixedWidth(55)
        self.label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.label)
        self.slider.valueChanged.connect(self._show_value)
        self._show_value(value)

    def _show_value(self, value: int) -> None:
        self.label.setText(f"{value}{self.suffix}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.worker: RuntimeThread | None = None
        self.calibration_points: list[list[float]] = []
        self.calibrating = False

        self.setWindowTitle("Ghosty Input Control Center")
        self.resize(1440, 860)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(10)
        root.addWidget(self._header())

        body = QHBoxLayout()
        body.setSpacing(10)
        root.addLayout(body, 1)
        body.addWidget(self._sidebar())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._live_page(), "Live")
        self.tabs.addTab(self._precision_page(), "Precision")
        self.tabs.addTab(self._calibration_page(), "Calibration")
        self.tabs.addTab(self._diagnostics_page(), "Diagnostics")
        body.addWidget(self.tabs, 1)

        self.start_button.clicked.connect(self.start_engine)
        self.stop_button.clicked.connect(self.stop_engine)
        self.calibrate_button.clicked.connect(self.begin_calibration)
        self.calibration_start.clicked.connect(self.begin_calibration)
        self.save_button.clicked.connect(self.save_tuning_config)
        self.apply_preset.clicked.connect(self.apply_selected_preset)
        self.top_preview.clicked.connect(self.capture_calibration_point)
        self._update_calibration_summary()

    def _header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("header")
        layout = QHBoxLayout(frame)
        brand = QVBoxLayout()
        name = QLabel("GHOSTY INPUT")
        name.setObjectName("brand")
        sub = QLabel("Vision input control center · fully local runtime")
        sub.setObjectName("muted")
        brand.addWidget(name)
        brand.addWidget(sub)
        layout.addLayout(brand)
        layout.addStretch()
        self.status_pill = QLabel()
        layout.addWidget(self.status_pill)
        self._set_status("Stopped")
        return frame

    def _sidebar(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(275)
        layout = QVBoxLayout(card)

        self.preset = QComboBox()
        self.preset.addItems(["Balanced", "Precision", "Performance"])
        self.apply_preset = QPushButton("Apply profile")
        layout.addWidget(QLabel("Operating profile"))
        layout.addWidget(self.preset)
        layout.addWidget(self.apply_preset)

        routing = QGroupBox("Camera routing")
        form = QFormLayout(routing)
        self.front_camera = QSpinBox()
        self.top_camera = QSpinBox()
        for spin in (self.front_camera, self.top_camera):
            spin.setRange(0, 20)
        self.front_camera.setValue(self.config.front_camera)
        self.top_camera.setValue(self.config.top_camera)
        self.dual_camera = QCheckBox("Dedicated desk camera")
        self.dual_camera.setChecked(self.config.dual_camera)
        form.addRow("Front", self.front_camera)
        form.addRow("Desk", self.top_camera)
        form.addRow(self.dual_camera)
        layout.addWidget(routing)

        modules = QGroupBox("Input modules")
        modules_layout = QVBoxLayout(modules)
        self.keyboard_enabled = QCheckBox("Desk keyboard")
        self.keyboard_enabled.setChecked(self.config.keyboard_enabled)
        self.landmarks = QCheckBox("Tracking overlay")
        self.landmarks.setChecked(self.config.draw_landmarks)
        modules_layout.addWidget(self.keyboard_enabled)
        modules_layout.addWidget(self.landmarks)
        layout.addWidget(modules)

        self.start_button = QPushButton("Start engine")
        self.start_button.setObjectName("primary")
        self.stop_button = QPushButton("Stop engine")
        self.stop_button.setObjectName("danger")
        self.stop_button.setEnabled(False)
        self.calibrate_button = QPushButton("Calibrate keyboard plane")
        self.calibrate_button.setEnabled(False)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.calibrate_button)

        hint = QLabel(
            "Typing works best with a fixed top-down camera and a calibration "
            "covering the full keyboard plane."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        return card

    def _live_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        metrics = QGridLayout()
        self.metric_fps = MetricCard("Tracking FPS")
        self.metric_resolution = MetricCard("Actual camera")
        self.metric_confidence = MetricCard("Hand confidence")
        self.metric_calibration = MetricCard("Calibration")
        for col, card in enumerate(
            (
                self.metric_fps,
                self.metric_resolution,
                self.metric_confidence,
                self.metric_calibration,
            )
        ):
            metrics.addWidget(card, 0, col)
        layout.addLayout(metrics)

        previews = QHBoxLayout()
        self.front_preview = PreviewLabel("Front tracking camera")
        self.top_preview = PreviewLabel("Desk keyboard camera")
        previews.addWidget(self.front_preview, 1)
        previews.addWidget(self.top_preview, 1)
        layout.addLayout(previews, 1)
        return page

    def _precision_page(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)

        camera = QGroupBox("Camera quality")
        camera_form = QFormLayout(camera)
        self.resolution = QComboBox()
        self.resolution.addItems(["1280×720", "1920×1080", "2560×1440"])
        current = f"{self.config.camera_width}×{self.config.camera_height}"
        self.resolution.setCurrentText(
            current if self.resolution.findText(current) >= 0 else "1920×1080"
        )
        self.fps = QComboBox()
        self.fps.addItems(["30", "60"])
        self.fps.setCurrentText(str(self.config.camera_fps))
        self.autofocus = QCheckBox("Use autofocus")
        self.autofocus.setChecked(self.config.camera_autofocus)
        camera_form.addRow("Requested mode", self.resolution)
        camera_form.addRow("Requested FPS", self.fps)
        camera_form.addRow(self.autofocus)

        tracking = QGroupBox("Hand tracking")
        tracking_form = QFormLayout(tracking)
        self.detection = SliderControl(30, 95, int(self.config.detection_confidence * 100), "%")
        self.tracking = SliderControl(30, 95, int(self.config.tracking_confidence * 100), "%")
        tracking_form.addRow("Detection", self.detection)
        tracking_form.addRow("Tracking", self.tracking)

        pointer = QGroupBox("Pointer")
        pointer_form = QFormLayout(pointer)
        self.pointer_smoothing = SliderControl(5, 95, int(self.config.pointer_smoothing * 100), "%")
        self.pinch = SliderControl(18, 60, int(self.config.pinch_engage_ratio * 100), "%")
        pointer_form.addRow("Smoothing", self.pointer_smoothing)
        pointer_form.addRow("Pinch threshold", self.pinch)

        keyboard = QGroupBox("Keyboard precision")
        keyboard_form = QFormLayout(keyboard)
        self.keyboard_dwell = SliderControl(20, 300, self.config.keyboard_dwell_ms, "ms")
        self.keyboard_release = SliderControl(20, 250, self.config.keyboard_release_ms, "ms")
        keyboard_form.addRow("Stable-key dwell", self.keyboard_dwell)
        keyboard_form.addRow("Release guard", self.keyboard_release)

        layout.addWidget(camera, 0, 0)
        layout.addWidget(tracking, 0, 1)
        layout.addWidget(pointer, 1, 0)
        layout.addWidget(keyboard, 1, 1)

        self.save_button = QPushButton("Save precision settings")
        self.save_button.setObjectName("primary")
        layout.addWidget(self.save_button, 2, 0, 1, 2)
        layout.setRowStretch(3, 1)
        return page

    def _calibration_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel(
            "Select the physical keyboard-plane corners in this order: "
            "top-left → top-right → bottom-right → bottom-left."
        )
        title.setWordWrap(True)
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("card")
        row = QHBoxLayout(card)
        summary = QVBoxLayout()
        self.calibration_state = QLabel("Not calibrated")
        self.calibration_state.setObjectName("metricValue")
        self.calibration_quality = QLabel("Quality: —")
        self.calibration_quality.setObjectName("muted")
        summary.addWidget(self.calibration_state)
        summary.addWidget(self.calibration_quality)
        row.addLayout(summary)
        row.addStretch()
        self.calibration_start = QPushButton("Start 4-point calibration")
        self.calibration_start.setObjectName("primary")
        row.addWidget(self.calibration_start)
        layout.addWidget(card)

        note = QLabel(
            "A score of 70/100 or higher is a useful target. After calibration, "
            "verify that the projected key outlines follow the physical plane. "
            "Moving either camera requires recalibration."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        return page

    def _diagnostics_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.log)
        return page

    def _set_status(self, text: str) -> None:
        upper = text.upper()
        if "ERROR" in upper:
            bg, border, fg = "#30171c", "#743441", "#ff9bad"
        elif "PAUSED" in upper:
            bg, border, fg = "#302a15", "#6e5e28", "#f6d87c"
        elif "RUNNING" in upper:
            bg, border, fg = "#10291f", "#245b44", "#80e3b3"
        elif "CALIBRATION" in upper:
            bg, border, fg = "#1b2340", "#415592", "#aabaff"
        else:
            bg, border, fg = "#171d27", "#2b3748", "#97a3b7"
        self.status_pill.setText(upper)
        self.status_pill.setStyleSheet(
            f"background:{bg}; border:1px solid {border}; color:{fg}; "
            "padding:7px 12px; border-radius:12px; font-weight:800;"
        )

    def apply_selected_preset(self) -> None:
        values = {
            "Precision": ("1920×1080", "30", 72, 72, 38, 31, 110, 80),
            "Performance": ("1280×720", "60", 58, 58, 20, 34, 65, 55),
            "Balanced": ("1920×1080", "30", 65, 65, 28, 31, 90, 70),
        }[self.preset.currentText()]
        resolution, fps, detection, tracking, smoothing, pinch, dwell, release = values
        self.resolution.setCurrentText(resolution)
        self.fps.setCurrentText(fps)
        self.detection.slider.setValue(detection)
        self.tracking.slider.setValue(tracking)
        self.pointer_smoothing.slider.setValue(smoothing)
        self.pinch.slider.setValue(pinch)
        self.keyboard_dwell.slider.setValue(dwell)
        self.keyboard_release.slider.setValue(release)
        self.log.appendPlainText(f"Applied {self.preset.currentText()} profile.")

    def _collect_config(self) -> AppConfig:
        cfg = self.config
        cfg.front_camera = self.front_camera.value()
        cfg.top_camera = self.top_camera.value()
        cfg.dual_camera = self.dual_camera.isChecked()
        cfg.keyboard_enabled = self.keyboard_enabled.isChecked()
        cfg.draw_landmarks = self.landmarks.isChecked()

        width, height = self.resolution.currentText().split("×")
        cfg.camera_width, cfg.camera_height = int(width), int(height)
        cfg.camera_fps = int(self.fps.currentText())
        cfg.camera_autofocus = self.autofocus.isChecked()
        cfg.detection_confidence = self.detection.slider.value() / 100
        cfg.tracking_confidence = self.tracking.slider.value() / 100
        cfg.pointer_smoothing = self.pointer_smoothing.slider.value() / 100
        cfg.pinch_engage_ratio = self.pinch.slider.value() / 100
        cfg.pinch_release_ratio = min(1.2, cfg.pinch_engage_ratio + 0.11)
        cfg.keyboard_dwell_ms = self.keyboard_dwell.slider.value()
        cfg.keyboard_release_ms = self.keyboard_release.slider.value()
        cfg.validate()
        return cfg

    def save_tuning_config(self) -> None:
        try:
            self.config = self._collect_config()
            save_config(self.config)
        except Exception as exc:
            QMessageBox.warning(self, "Ghosty Input", str(exc))
            return
        self.log.appendPlainText("Precision settings saved.")
        if self.worker is not None and self.worker.isRunning():
            self.log.appendPlainText("Restart the engine to apply tracking changes.")

    def start_engine(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        try:
            self.config = self._collect_config()
            save_config(self.config)
        except Exception as exc:
            QMessageBox.critical(self, "Ghosty Input", str(exc))
            return

        worker = RuntimeThread(self.config)
        worker.engine_ready.connect(self._on_engine_ready)
        worker.start_failed.connect(self._on_start_failed)
        worker.result_ready.connect(self._on_result)
        worker.calibration_applied.connect(self._update_calibration_summary)
        worker.finished.connect(self._on_worker_finished)
        self.worker = worker
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.calibrate_button.setEnabled(False)
        self._set_status("Starting")
        worker.start()

    def _on_engine_ready(self, info) -> None:
        self.calibrate_button.setEnabled(self.config.keyboard_enabled)
        self._set_status("Running")
        self.log.appendPlainText(
            f"Runtime started · camera {info.index} · {info.resolution} · {info.backend}"
        )

    def _on_start_failed(self, message: str) -> None:
        self._set_status("Runtime error")
        self.log.appendPlainText(f"Runtime failed: {message}")
        QMessageBox.critical(self, "Ghosty Input", message)

    def _on_worker_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.calibrate_button.setEnabled(False)
        if self.worker is not None and not self.worker.isRunning():
            self.worker = None

    def stop_engine(self) -> None:
        if self.worker is not None:
            self.worker.requestInterruption()
            self.worker.wait(1800)
            if not self.worker.isRunning():
                self.worker = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.calibrate_button.setEnabled(False)
        self._set_status("Stopped")
        if hasattr(self, "log"):
            self.log.appendPlainText("Runtime stopped.")

    def begin_calibration(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            QMessageBox.information(self, "Calibration", "Start the engine first.")
            return
        self.calibration_points = []
        self.calibrating = True
        self.tabs.setCurrentIndex(0)
        self._set_status("Calibration: top-left")
        self.log.appendPlainText("Calibration: click TL → TR → BR → BL on desk preview.")

    def capture_calibration_point(self, x: float, y: float) -> None:
        if not self.calibrating or self.worker is None or not self.worker.isRunning():
            return
        self.calibration_points.append([x, y])
        index = len(self.calibration_points)
        self.log.appendPlainText(f"Calibration point {index}: ({x:.4f}, {y:.4f})")
        if index < 4:
            next_label = ("top-right", "bottom-right", "bottom-left")[index - 1]
            self._set_status(f"Calibration: {next_label}")
            return

        try:
            calibration = DeskCalibration(self.calibration_points)
        except ValueError as exc:
            self.calibrating = False
            self.calibration_points = []
            self._set_status("Running")
            QMessageBox.warning(self, "Calibration rejected", str(exc))
            return

        self.calibrating = False
        self.config.calibration_points = self.calibration_points.copy()
        save_config(self.config)
        self.worker.request_calibration(self.config.calibration_points)
        self._set_status("Running")
        self._update_calibration_summary(calibration.quality_score)
        self.log.appendPlainText(
            f"Calibration saved · quality {calibration.quality_score}/100."
        )

    def _update_calibration_summary(self, quality: int | None = None) -> None:
        if not hasattr(self, "calibration_state"):
            return
        if len(self.config.calibration_points) == 4:
            if quality is None:
                try:
                    quality = DeskCalibration(self.config.calibration_points).quality_score
                except ValueError:
                    quality = 0
            self.calibration_state.setText("Calibrated")
            self.calibration_quality.setText(f"Quality: {quality}/100")
        else:
            self.calibration_state.setText("Not calibrated")
            self.calibration_quality.setText("Quality: —")

    def _update_metrics(self, metrics: RuntimeMetrics) -> None:
        self.metric_fps.value.setText(f"{metrics.front_fps:.0f} FPS")
        self.metric_resolution.value.setText(metrics.camera_resolution)
        self.metric_confidence.value.setText(
            f"{metrics.hand_confidence * 100:.0f}%" if metrics.hand_count else "No hand"
        )
        self.metric_calibration.value.setText(
            f"{metrics.calibration_quality}/100" if metrics.calibration_quality else "Not set"
        )

    @staticmethod
    def _to_pixmap(frame) -> QPixmap:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(
            rgb.data, width, height, channels * width, QImage.Format_RGB888
        ).copy()
        return QPixmap.fromImage(image)

    def _on_result(self, result: TickResult) -> None:
        self._set_status(result.status)
        self._update_metrics(result.metrics)
        if result.event:
            self.log.appendPlainText(result.event)
        if result.front_frame is not None:
            self.front_preview.set_frame_pixmap(self._to_pixmap(result.front_frame))
        if result.top_frame is not None:
            self.top_preview.set_frame_pixmap(self._to_pixmap(result.top_frame))

    def closeEvent(self, event) -> None:  # noqa: N802
        self.stop_engine()
        event.accept()


def run_ui() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Ghosty Input")
    app.setOrganizationName("Ghosty Input")
    window = MainWindow()
    window.show()
    return app.exec()

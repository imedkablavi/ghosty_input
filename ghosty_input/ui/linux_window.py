from __future__ import annotations

import cv2
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QImage, QPixmap
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
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ghosty_input.config import AppConfig, ConfigLoadState, load_config_state, save_config
from ghosty_input.core.calibration import DeskCalibration
from ghosty_input.core.camera import CameraDevice, camera_diagnostic_report, discover_cameras
from ghosty_input.core.engine import RuntimeMetrics, TickResult
from ghosty_input.core.linux_desktop import (
    autostart_enabled,
    desktop_entry_installed,
    install_desktop_entry,
    remove_desktop_entry,
    set_autostart,
)
from ghosty_input.core.logging_setup import log_path
from ghosty_input.core.preflight import PreflightReport, run_preflight
from ghosty_input.core.system_info import diagnostic_report
from ghosty_input.ui.instance_lock import acquire_instance_lock
from ghosty_input.ui.runtime_worker import RuntimeThread


STYLE = """
* { font-family:"Inter","Noto Sans","Segoe UI",sans-serif; font-size:13px; }
QMainWindow,QWidget { background:#090d13; color:#edf2f8; }
QFrame#card,QGroupBox { background:#111821; border:1px solid #243041; border-radius:12px; }
QGroupBox { margin-top:10px; padding:12px; font-weight:700; }
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; }
QLabel#brand { font-size:24px; font-weight:800; }
QLabel#muted { color:#8795a8; }
QLabel#ready { color:#80e3b3; font-weight:800; font-size:16px; }
QLabel#blocked { color:#ff9aac; font-weight:800; font-size:16px; }
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

    def show_frame(self, pixmap: QPixmap) -> None:
        image = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._shown = (image.width(), image.height())
        self.setPixmap(image)

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
        self.config_state: ConfigLoadState = load_config_state()
        self.config = self.config_state.config
        self.worker: RuntimeThread | None = None
        self.calibrating = False
        self.points: list[list[float]] = []
        self._quitting = False
        self._tray_notice = False
        self.tray: QSystemTrayIcon | None = None

        self.setWindowTitle("Ghosty Input Alpha · Linux Control Center")
        self.resize(1420, 850)
        self.setMinimumSize(1080, 690)
        self.setStyleSheet(STYLE)

        center = QWidget()
        self.setCentralWidget(center)
        root = QVBoxLayout(center)

        header = QHBoxLayout()
        brand = QLabel("GHOSTY INPUT")
        brand.setObjectName("brand")
        self.status = QLabel("STOPPED")
        self.status.setObjectName("muted")
        header.addWidget(brand)
        header.addWidget(QLabel("Alpha · Linux native input · persistent cameras · local processing"))
        header.addStretch()
        header.addWidget(self.status)
        root.addLayout(header)

        body = QHBoxLayout()
        root.addLayout(body, 1)
        body.addWidget(self._sidebar())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._live(), "Live")
        self.tabs.addTab(self._precision(), "Precision")
        self.tabs.addTab(self._alpha(), "Alpha")
        self.tabs.addTab(self._linux(), "Linux")
        body.addWidget(self.tabs, 1)

        self.start.clicked.connect(self.start_engine)
        self.stop.clicked.connect(self.stop_engine)
        self.calibrate.clicked.connect(self.begin_calibration)
        self.save.clicked.connect(self.save_settings)
        self.refresh_cameras.clicked.connect(self.populate_cameras)
        self.refresh_diag.clicked.connect(self.refresh_diagnostics)
        self.preflight_button.clicked.connect(self.refresh_preflight)
        self.camera_doctor_button.clicked.connect(self.run_camera_doctor)
        self.desktop_button.clicked.connect(self.toggle_desktop)
        self.autostart_button.clicked.connect(self.toggle_autostart)
        self.desk_preview.clicked.connect(self.capture_calibration_point)

        self._setup_tray()
        self.populate_cameras()
        self.refresh_diagnostics()
        self.refresh_preflight()
        if self.config_state.recovered:
            backup = str(self.config_state.backup_path) if self.config_state.backup_path else "backup unavailable"
            self.log.appendPlainText(
                f"Recovered from an invalid config · backup: {backup} · {self.config_state.error}"
            )

    def _sidebar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedWidth(305)
        layout = QVBoxLayout(frame)

        cameras = QGroupBox("Cameras")
        form = QFormLayout(cameras)
        self.front_camera = QComboBox()
        self.top_camera = QComboBox()
        self.dual = QCheckBox("Dedicated desk camera")
        self.dual.setChecked(self.config.dual_camera)
        self.refresh_cameras = QPushButton("Refresh cameras")
        form.addRow("Front", self.front_camera)
        form.addRow("Desk", self.top_camera)
        form.addRow(self.dual)
        form.addRow(self.refresh_cameras)
        layout.addWidget(cameras)

        modules = QGroupBox("Modules")
        box = QVBoxLayout(modules)
        self.keyboard = QCheckBox("Desk keyboard")
        self.keyboard.setChecked(self.config.keyboard_enabled)
        self.landmarks = QCheckBox("Tracking overlay")
        self.landmarks.setChecked(self.config.draw_landmarks)
        self.close_to_tray = QCheckBox("Keep running when window closes")
        self.close_to_tray.setChecked(self.config.linux_close_to_tray)
        self.close_to_tray.setEnabled(QSystemTrayIcon.isSystemTrayAvailable())
        box.addWidget(self.keyboard)
        box.addWidget(self.landmarks)
        box.addWidget(self.close_to_tray)
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

        hint = QLabel(
            "Start runs the Alpha preflight first. Wayland requires writable /dev/uinput. "
            "Camera routing uses persistent /dev/v4l aliases when available."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        return frame

    def _live(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        grid = QGridLayout()
        self.metric_fps = QLabel("FPS —")
        self.metric_res = QLabel("Camera —")
        self.metric_hand = QLabel("Hand —")
        self.metric_backend = QLabel("Input —")
        for i, widget in enumerate(
            (self.metric_fps, self.metric_res, self.metric_hand, self.metric_backend)
        ):
            card = QFrame()
            card.setObjectName("card")
            box = QVBoxLayout(card)
            box.addWidget(widget)
            grid.addWidget(card, 0, i)
        layout.addLayout(grid)

        previews = QHBoxLayout()
        self.front_preview = Preview("Front camera")
        self.desk_preview = Preview("Desk camera / calibration")
        previews.addWidget(self.front_preview, 1)
        previews.addWidget(self.desk_preview, 1)
        layout.addLayout(previews, 1)
        return page

    def _precision(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)

        camera = QGroupBox("Camera")
        f1 = QFormLayout(camera)
        self.resolution = QComboBox()
        self.resolution.addItems(["1280×720", "1920×1080", "2560×1440"])
        current = f"{self.config.camera_width}×{self.config.camera_height}"
        self.resolution.setCurrentText(
            current if self.resolution.findText(current) >= 0 else "1920×1080"
        )
        self.fps = QComboBox()
        self.fps.addItems(["30", "60"])
        self.fps.setCurrentText(str(self.config.camera_fps))
        self.front_autofocus = QCheckBox("Front autofocus")
        self.front_autofocus.setChecked(self.config.camera_autofocus)
        self.desk_autofocus = QCheckBox("Desk autofocus")
        self.desk_autofocus.setChecked(self.config.top_camera_autofocus)
        f1.addRow("Mode", self.resolution)
        f1.addRow("FPS", self.fps)
        f1.addRow(self.front_autofocus)
        f1.addRow(self.desk_autofocus)

        input_box = QGroupBox("Linux input")
        f2 = QFormLayout(input_box)
        self.backend = QComboBox()
        self.backend.addItem("Auto (recommended)", "auto")
        self.backend.addItem("Native uinput", "uinput")
        self.backend.addItem("PyAutoGUI fallback", "pyautogui")
        self.pointer_mode = QComboBox()
        self.pointer_mode.addItem("Pinch", "pinch")
        self.pointer_mode.addItem("Hover dwell", "hover")
        self.pointer_dwell = SliderRow(300, 1600, self.config.pointer_dwell_ms, "ms")
        f2.addRow("Backend", self.backend)
        f2.addRow("Left click", self.pointer_mode)
        f2.addRow("Dwell", self.pointer_dwell)

        keyboard = QGroupBox("Keyboard activation")
        f3 = QFormLayout(keyboard)
        self.keyboard_mode = QComboBox()
        self.keyboard_mode.addItem("Pinch", "pinch")
        self.keyboard_mode.addItem("Hover dwell", "hover")
        self.keyboard_hover = SliderRow(300, 1600, self.config.keyboard_hover_ms, "ms")
        self.pinch = SliderRow(18, 60, int(self.config.pinch_engage_ratio * 100), "%")
        f3.addRow("Activation", self.keyboard_mode)
        f3.addRow("Hover dwell", self.keyboard_hover)
        f3.addRow("Pinch threshold", self.pinch)

        tracking = QGroupBox("Tracking")
        f4 = QFormLayout(tracking)
        self.smoothing = SliderRow(5, 95, int(self.config.pointer_smoothing * 100), "%")
        self.detection = SliderRow(30, 95, int(self.config.detection_confidence * 100), "%")
        self.tracking = SliderRow(30, 95, int(self.config.tracking_confidence * 100), "%")
        f4.addRow("Pointer smoothing", self.smoothing)
        f4.addRow("Detection", self.detection)
        f4.addRow("Tracking", self.tracking)

        grid.addWidget(camera, 0, 0)
        grid.addWidget(input_box, 0, 1)
        grid.addWidget(keyboard, 1, 0)
        grid.addWidget(tracking, 1, 1)
        self.save = QPushButton("Save Linux precision settings")
        self.save.setObjectName("primary")
        grid.addWidget(self.save, 2, 0, 1, 2)
        grid.setRowStretch(3, 1)
        self._select(self.backend, self.config.input_backend)
        self._select(self.pointer_mode, self.config.pointer_activation_mode)
        self._select(self.keyboard_mode, self.config.keyboard_activation_mode)
        return page

    def _alpha(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        gate = QGroupBox("Alpha preflight")
        gate_layout = QVBoxLayout(gate)
        row = QHBoxLayout()
        self.preflight_status = QLabel("NOT CHECKED")
        self.preflight_status.setObjectName("blocked")
        self.preflight_button = QPushButton("Run preflight")
        self.camera_doctor_button = QPushButton("Run Camera Doctor")
        row.addWidget(self.preflight_status)
        row.addStretch()
        row.addWidget(self.preflight_button)
        row.addWidget(self.camera_doctor_button)
        gate_layout.addLayout(row)
        self.preflight_output = QPlainTextEdit()
        self.preflight_output.setReadOnly(True)
        gate_layout.addWidget(self.preflight_output)
        layout.addWidget(gate, 2)

        log_group = QGroupBox("Alpha runtime log")
        log_layout = QVBoxLayout(log_group)
        log_location = QLabel(str(log_path()))
        log_location.setObjectName("muted")
        log_location.setWordWrap(True)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        log_layout.addWidget(log_location)
        log_layout.addWidget(self.log, 1)
        layout.addWidget(log_group, 1)
        return page

    def _linux(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox("Desktop integration")
        row = QHBoxLayout(group)
        self.desktop_button = QPushButton()
        self.autostart_button = QPushButton()
        row.addWidget(self.desktop_button)
        row.addWidget(self.autostart_button)
        row.addStretch()
        layout.addWidget(group)

        self.refresh_diag = QPushButton("Refresh system diagnostics")
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        layout.addWidget(self.refresh_diag)
        layout.addWidget(self.diagnostics, 1)
        return page

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(
            QApplication.style().standardIcon(QStyle.SP_ComputerIcon), self
        )
        self.tray.setToolTip("Ghosty Input Alpha")
        menu = QMenu(self)
        show = QAction("Show Control Center", self)
        toggle = QAction("Start / Stop Engine", self)
        quit_action = QAction("Quit Ghosty Input", self)
        show.triggered.connect(self._show)
        toggle.triggered.connect(self._toggle_engine)
        quit_action.triggered.connect(self._quit)
        menu.addAction(show)
        menu.addAction(toggle)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_clicked)
        self.tray.show()

    def _tray_clicked(self, reason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self._show()

    def _show(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _toggle_engine(self) -> None:
        if self.worker and self.worker.isRunning():
            self.stop_engine()
        else:
            self.start_engine()

    def _quit(self) -> None:
        self._quitting = True
        if not self.stop_engine():
            self._quitting = False
            QMessageBox.warning(
                self,
                "Ghosty Input",
                "The camera worker is still stopping. Close Ghosty Input again after it finishes.",
            )
            return
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    @staticmethod
    def _select(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def populate_cameras(self) -> None:
        devices = discover_cameras()
        self._fill_camera(
            self.front_camera,
            devices,
            self.config.front_camera,
            self.config.front_camera_id,
        )
        self._fill_camera(
            self.top_camera,
            devices,
            self.config.top_camera,
            self.config.top_camera_id,
        )
        if hasattr(self, "log"):
            self.log.appendPlainText(
                f"Camera discovery refreshed · {len(devices)} selectable device(s)."
            )
        if hasattr(self, "preflight_output"):
            self.refresh_preflight()

    @staticmethod
    def _fill_camera(
        combo: QComboBox,
        devices: list[CameraDevice],
        selected: int,
        stable_id: str,
    ) -> None:
        combo.clear()
        target = -1
        for device in devices:
            combo.addItem(device.label, (device.index, device.stable_id))
            row = combo.count() - 1
            if stable_id and device.stable_id == stable_id:
                target = row
            elif target < 0 and device.index == selected:
                target = row
        if target < 0:
            combo.addItem(
                f"Camera {selected} · currently unavailable",
                (selected, stable_id),
            )
            target = combo.count() - 1
        combo.setCurrentIndex(target)

    @staticmethod
    def _camera(combo: QComboBox) -> tuple[int, str]:
        data = combo.currentData()
        if isinstance(data, (tuple, list)) and len(data) == 2:
            return int(data[0]), str(data[1])
        return int(data), ""

    def _collect(self) -> AppConfig:
        cfg = self.config
        cfg.front_camera, cfg.front_camera_id = self._camera(self.front_camera)
        cfg.top_camera, cfg.top_camera_id = self._camera(self.top_camera)
        cfg.dual_camera = self.dual.isChecked()
        cfg.keyboard_enabled = self.keyboard.isChecked()
        cfg.draw_landmarks = self.landmarks.isChecked()
        cfg.linux_close_to_tray = self.close_to_tray.isChecked()
        width, height = self.resolution.currentText().split("×")
        cfg.camera_width, cfg.camera_height = int(width), int(height)
        cfg.camera_fps = int(self.fps.currentText())
        cfg.camera_autofocus = self.front_autofocus.isChecked()
        cfg.top_camera_autofocus = self.desk_autofocus.isChecked()
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
            self.refresh_preflight()
        except Exception as exc:
            QMessageBox.warning(self, "Ghosty Input", str(exc))

    def _show_preflight(self, report: PreflightReport) -> None:
        text = report.render()
        if self.config_state.recovered:
            backup = str(self.config_state.backup_path) if self.config_state.backup_path else "unavailable"
            text += f"\n[WARN] Config recovery: invalid config was quarantined at {backup}"
        self.preflight_output.setPlainText(text)
        if report.ready:
            self.preflight_status.setText(
                "READY WITH WARNINGS" if report.warning_count else "READY"
            )
            self.preflight_status.setObjectName("ready")
        else:
            self.preflight_status.setText("BLOCKED")
            self.preflight_status.setObjectName("blocked")
        self.preflight_status.style().unpolish(self.preflight_status)
        self.preflight_status.style().polish(self.preflight_status)

    def refresh_preflight(self, *, probe_streams: bool = False) -> PreflightReport:
        try:
            cfg = self._collect()
            report = run_preflight(cfg, probe_streams=probe_streams)
        except Exception as exc:
            self.preflight_status.setText("BLOCKED")
            self.preflight_output.setPlainText(f"Preflight failed: {type(exc).__name__}: {exc}")
            return PreflightReport(())
        self._show_preflight(report)
        return report

    def run_camera_doctor(self) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(
                self,
                "Camera Doctor",
                "Stop the engine before probing camera streams.",
            )
            return
        self.status.setText("CAMERA DOCTOR")
        self.preflight_output.setPlainText("Camera Doctor is probing V4L2 devices and real frames…")
        QApplication.processEvents()
        try:
            report = camera_diagnostic_report(probe_streams=True)
        except Exception as exc:
            report = f"Camera Doctor failed: {type(exc).__name__}: {exc}"
        self.preflight_output.setPlainText(report)
        self.status.setText("STOPPED")

    def start_engine(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        try:
            self.config = self._collect()
            report = run_preflight(self.config)
            self._show_preflight(report)
            if not report.ready:
                self.status.setText("ALPHA BLOCKED")
                self.tabs.setCurrentIndex(2)
                QMessageBox.warning(
                    self,
                    "Alpha preflight blocked startup",
                    "Fix the FAIL items in the Alpha tab before starting the engine.",
                )
                return
            save_config(self.config)
        except Exception as exc:
            QMessageBox.critical(self, "Ghosty Input", str(exc))
            return

        worker = RuntimeThread(self.config)
        worker.engine_ready.connect(self._engine_ready)
        worker.start_failed.connect(self._start_failed)
        worker.runtime_failed.connect(self._runtime_failed)
        worker.result_ready.connect(self._result)
        worker.finished.connect(self._worker_finished)
        self.worker = worker
        self.start.setEnabled(False)
        self.stop.setEnabled(True)
        self.status.setText("STARTING")
        worker.start()

    def _engine_ready(self, info) -> None:
        self.status.setText("RUNNING")
        self.calibrate.setEnabled(self.config.keyboard_enabled)
        self.log.appendPlainText(
            f"Runtime started · camera {info.index} · {info.resolution} · {info.backend} · {info.path}"
        )

    def _start_failed(self, message: str) -> None:
        self.status.setText("RUNTIME ERROR")
        self.log.appendPlainText(f"Runtime startup failed · {message}")
        self.refresh_diagnostics()
        self.tabs.setCurrentIndex(2)
        QMessageBox.critical(self, "Ghosty Input", message)

    def _runtime_failed(self, message: str) -> None:
        self.status.setText("RUNTIME ERROR")
        self.log.appendPlainText(f"Runtime stopped after repeated internal errors · {message}")
        self.tabs.setCurrentIndex(2)
        QMessageBox.warning(
            self,
            "Ghosty Input runtime stopped",
            f"The runtime stopped after repeated errors.\n\n{message}\n\nLog: {log_path()}",
        )

    def _worker_finished(self) -> None:
        self.start.setEnabled(True)
        self.stop.setEnabled(False)
        self.calibrate.setEnabled(False)
        self.worker = None
        if not self._quitting and "ERROR" not in self.status.text().upper():
            self.status.setText("STOPPED")

    def stop_engine(self) -> bool:
        if self.worker:
            worker = self.worker
            self.status.setText("STOPPING")
            self.stop.setEnabled(False)
            if not worker.stop(3000):
                self.start.setEnabled(False)
                self.log.appendPlainText(
                    "Runtime stop is still pending; waiting for the current camera read to return."
                )
                return False
            self.worker = None

        self.start.setEnabled(True)
        self.stop.setEnabled(False)
        self.calibrate.setEnabled(False)
        self.status.setText("STOPPED")
        return True

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
        self.config.calibration_points = [p[:] for p in self.points]
        save_config(self.config)
        self.worker.request_calibration(self.config.calibration_points)
        self.status.setText("RUNNING")
        self.log.appendPlainText(f"Calibration quality: {calibration.quality_score}/100")
        self.refresh_preflight()

    def _sync_desktop(self) -> None:
        self.desktop_button.setText(
            "Remove app launcher" if desktop_entry_installed() else "Install app launcher"
        )
        self.autostart_button.setText(
            "Disable autostart" if autostart_enabled() else "Enable autostart"
        )

    def toggle_desktop(self) -> None:
        try:
            if desktop_entry_installed():
                remove_desktop_entry()
                self.log.appendPlainText("Linux application launcher removed.")
            else:
                self.log.appendPlainText(
                    f"Linux application launcher installed: {install_desktop_entry()}"
                )
            self.refresh_diagnostics()
        except Exception as exc:
            QMessageBox.warning(self, "Desktop integration", str(exc))

    def toggle_autostart(self) -> None:
        try:
            enabled = not autostart_enabled()
            set_autostart(enabled)
            self.log.appendPlainText(
                "Desktop-session autostart enabled." if enabled else "Autostart disabled."
            )
            self.refresh_diagnostics()
        except Exception as exc:
            QMessageBox.warning(self, "Autostart", str(exc))

    def refresh_diagnostics(self) -> None:
        self.diagnostics.setPlainText(
            diagnostic_report() + f"\nPersistent log: {log_path()}"
        )
        self._sync_desktop()

    def _update_metrics(self, metrics: RuntimeMetrics) -> None:
        self.metric_fps.setText(f"FPS {metrics.front_fps:.0f}")
        self.metric_res.setText(f"Camera {metrics.camera_resolution}")
        self.metric_hand.setText(
            f"Hand {metrics.hand_confidence * 100:.0f}%" if metrics.hand_count else "Hand —"
        )
        self.metric_backend.setText(f"Input {metrics.input_backend}")

    @staticmethod
    def _pixmap(frame) -> QPixmap:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        return QPixmap.fromImage(
            QImage(
                rgb.data,
                width,
                height,
                channels * width,
                QImage.Format_RGB888,
            ).copy()
        )

    def _result(self, result: TickResult) -> None:
        self.status.setText(result.status.upper())
        self._update_metrics(result.metrics)
        if result.event:
            self.log.appendPlainText(result.event)
        if result.front_frame is not None:
            self.front_preview.show_frame(self._pixmap(result.front_frame))
        if result.top_frame is not None:
            self.desk_preview.show_frame(self._pixmap(result.top_frame))

    def closeEvent(self, event) -> None:  # noqa: N802
        if (
            not self._quitting
            and self.config.linux_close_to_tray
            and self.tray
            and self.tray.isVisible()
        ):
            event.ignore()
            self.hide()
            if not self._tray_notice:
                self.tray.showMessage(
                    "Ghosty Input",
                    "Ghosty Input is still running. Use the tray menu to quit.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3500,
                )
                self._tray_notice = True
            return

        self._quitting = True
        if not self.stop_engine():
            self._quitting = False
            event.ignore()
            QMessageBox.warning(
                self,
                "Ghosty Input",
                "The runtime is still stopping. Close the window again after it finishes.",
            )
            return
        if self.tray:
            self.tray.hide()
        event.accept()


def run_linux_ui(*, start_minimized: bool = False) -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Ghosty Input")
    app.setOrganizationName("Ghosty Input")

    instance_lock, lock_error = acquire_instance_lock()
    if instance_lock is None:
        QMessageBox.information(
            None,
            "Ghosty Input is already running",
            lock_error,
        )
        return 2

    window = LinuxWindow()
    minimized = start_minimized or window.config.linux_start_minimized
    if minimized and window.tray:
        window.hide()
    elif minimized:
        window.showMinimized()
    else:
        window.show()

    try:
        return app.exec()
    finally:
        instance_lock.unlock()

from __future__ import annotations

import cv2
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ghosty_input.config import AppConfig, load_config, save_config
from ghosty_input.core.engine import GhostyEngine


STYLE = """
QMainWindow, QWidget {
    background: #0b0f14;
    color: #e8edf2;
    font-family: Inter, Segoe UI, Arial;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #263241;
    border-radius: 12px;
    margin-top: 10px;
    padding: 12px;
    background: #111821;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #9ecbff;
}
QPushButton {
    background: #17375e;
    border: 1px solid #2f6faf;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
}
QPushButton:hover { background: #204b7c; }
QPushButton:disabled { color: #697481; background: #161b21; border-color: #252d36; }
QSpinBox {
    background: #0d131b;
    border: 1px solid #2b3948;
    border-radius: 6px;
    padding: 6px;
}
QPlainTextEdit {
    background: #080c11;
    border: 1px solid #263241;
    border-radius: 8px;
    color: #b9c7d5;
}
QLabel#preview {
    background: #05080c;
    border: 1px solid #263241;
    border-radius: 10px;
}
QLabel#status {
    color: #9ecbff;
    font-weight: 600;
}
"""


class PreviewLabel(QLabel):
    clicked = Signal(float, float)

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setObjectName("preview")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(420, 260)
        self.setScaledContents(False)
        self._pixmap_size: tuple[int, int] | None = None

    def set_frame_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._pixmap_size = (scaled.width(), scaled.height())
        self.setPixmap(scaled)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._pixmap_size is None:
            return super().mousePressEvent(event)
        pw, ph = self._pixmap_size
        ox = (self.width() - pw) / 2
        oy = (self.height() - ph) / 2
        x = (event.position().x() - ox) / max(1, pw)
        y = (event.position().y() - oy) / max(1, ph)
        if 0 <= x <= 1 and 0 <= y <= 1:
            self.clicked.emit(float(x), float(y))
        return super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.engine: GhostyEngine | None = None
        self.calibration_points: list[list[float]] = []
        self.calibrating = False

        self.setWindowTitle("Ghosty Input")
        self.resize(1220, 780)
        self.setStyleSheet(STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        title_row = QHBoxLayout()
        title = QLabel("GHOSTY INPUT")
        title.setStyleSheet("font-size: 26px; font-weight: 800; letter-spacing: 2px;")
        subtitle = QLabel("Offline hand-gesture input")
        subtitle.setStyleSheet("color: #7f8c99;")
        self.status = QLabel("Stopped")
        self.status.setObjectName("status")
        title_row.addWidget(title)
        title_row.addWidget(subtitle)
        title_row.addStretch(1)
        title_row.addWidget(self.status)
        root.addLayout(title_row)

        content = QHBoxLayout()
        root.addLayout(content, 1)

        sidebar = QVBoxLayout()
        content.addLayout(sidebar, 0)

        camera_box = QGroupBox("Cameras")
        camera_layout = QGridLayout(camera_box)
        self.front_camera = QSpinBox()
        self.top_camera = QSpinBox()
        self.front_camera.setRange(0, 20)
        self.top_camera.setRange(0, 20)
        self.front_camera.setValue(self.config.front_camera)
        self.top_camera.setValue(self.config.top_camera)
        self.dual_camera = QCheckBox("Use separate top camera")
        self.dual_camera.setChecked(self.config.dual_camera)
        camera_layout.addWidget(QLabel("Front"), 0, 0)
        camera_layout.addWidget(self.front_camera, 0, 1)
        camera_layout.addWidget(QLabel("Top"), 1, 0)
        camera_layout.addWidget(self.top_camera, 1, 1)
        camera_layout.addWidget(self.dual_camera, 2, 0, 1, 2)
        sidebar.addWidget(camera_box)

        feature_box = QGroupBox("Features")
        feature_layout = QVBoxLayout(feature_box)
        self.keyboard_enabled = QCheckBox("Desk keyboard")
        self.keyboard_enabled.setChecked(self.config.keyboard_enabled)
        self.landmarks = QCheckBox("Show hand landmarks")
        self.landmarks.setChecked(self.config.draw_landmarks)
        feature_layout.addWidget(self.keyboard_enabled)
        feature_layout.addWidget(self.landmarks)
        sidebar.addWidget(feature_box)

        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.calibrate_button = QPushButton("Calibrate desk")
        self.calibrate_button.setEnabled(False)
        sidebar.addWidget(self.start_button)
        sidebar.addWidget(self.stop_button)
        sidebar.addWidget(self.calibrate_button)

        help_label = QLabel(
            "Mouse: right-hand index moves pointer.\n"
            "Pinch thumb+index = left click.\n"
            "Pinch thumb+middle = right click.\n"
            "Pinch thumb+ring = drag.\n"
            "Hold fist 0.75s = pause/resume.\n\n"
            "Desk keyboard: calibrate 4 corners\n"
            "clockwise from top-left, then hover\n"
            "a key and pinch thumb+index."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #8d9aa7;")
        sidebar.addWidget(help_label)
        sidebar.addStretch(1)

        right = QVBoxLayout()
        content.addLayout(right, 1)
        previews = QHBoxLayout()
        self.front_preview = PreviewLabel("Front camera preview")
        self.top_preview = PreviewLabel("Desk keyboard preview")
        previews.addWidget(self.front_preview, 1)
        previews.addWidget(self.top_preview, 1)
        right.addLayout(previews, 1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(250)
        self.log.setFixedHeight(150)
        right.addWidget(self.log)

        self.timer = QTimer(self)
        self.timer.setInterval(33)

        self.start_button.clicked.connect(self.start_engine)
        self.stop_button.clicked.connect(self.stop_engine)
        self.calibrate_button.clicked.connect(self.begin_calibration)
        self.top_preview.clicked.connect(self.capture_calibration_point)
        self.timer.timeout.connect(self.tick)

    def _collect_config(self) -> AppConfig:
        cfg = self.config
        cfg.front_camera = self.front_camera.value()
        cfg.top_camera = self.top_camera.value()
        cfg.dual_camera = self.dual_camera.isChecked()
        cfg.keyboard_enabled = self.keyboard_enabled.isChecked()
        cfg.draw_landmarks = self.landmarks.isChecked()
        cfg.validate()
        return cfg

    def start_engine(self) -> None:
        if self.engine is not None:
            return
        try:
            self.config = self._collect_config()
            save_config(self.config)
            engine = GhostyEngine(self.config)
            engine.start()
            self.engine = engine
        except Exception as exc:
            QMessageBox.critical(self, "Ghosty Input", str(exc))
            return

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.calibrate_button.setEnabled(self.config.keyboard_enabled)
        self.timer.start()
        self.status.setText("Running")
        self.log.appendPlainText("Runtime started.")

    def stop_engine(self) -> None:
        self.timer.stop()
        if self.engine is not None:
            self.engine.close()
            self.engine = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.calibrate_button.setEnabled(False)
        self.status.setText("Stopped")
        self.log.appendPlainText("Runtime stopped.")

    def begin_calibration(self) -> None:
        self.calibration_points = []
        self.calibrating = True
        self.status.setText("Calibration: click top-left corner")
        self.log.appendPlainText(
            "Calibration started. Click TL → TR → BR → BL on the desk preview."
        )

    def capture_calibration_point(self, x: float, y: float) -> None:
        if not self.calibrating or self.engine is None:
            return
        self.calibration_points.append([x, y])
        labels = ["top-right", "bottom-right", "bottom-left", "done"]
        idx = len(self.calibration_points)
        self.status.setText(f"Calibration: {labels[min(idx - 1, 3)]}")
        self.log.appendPlainText(f"Calibration point {idx}: ({x:.3f}, {y:.3f})")

        if idx == 4:
            self.calibrating = False
            self.config.calibration_points = self.calibration_points.copy()
            self.engine.set_calibration(self.config.calibration_points)
            save_config(self.config)
            self.status.setText("Running · keyboard calibrated")
            self.log.appendPlainText("Desk calibration saved.")

    @staticmethod
    def _to_pixmap(frame) -> QPixmap:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QImage.Format_RGB888,
        ).copy()
        return QPixmap.fromImage(image)

    def tick(self) -> None:
        if self.engine is None:
            return
        result = self.engine.tick()
        self.status.setText(result.status)
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
    window = MainWindow()
    window.show()
    return app.exec()

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from ghosty_input.config import AppConfig, load_config, save_config
from ghosty_input.core.camera import discover_cameras
from ghosty_input.core.input_backends import inspect_input_environment, select_backend_name


def _page(title: str, text: str) -> QWizardPage:
    page = QWizardPage()
    page.setTitle(title)
    layout = QVBoxLayout(page)
    label = QLabel(text)
    label.setWordWrap(True)
    layout.addWidget(label)
    layout.addStretch()
    return page


class FirstRunWizard(QWizard):
    """Local-only first-run setup. It never opens or records a camera stream."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.setWindowTitle("Ghosty Input · First-run setup")
        self.resize(680, 470)

        self.addPage(
            _page(
                "Welcome",
                "Ghosty Input Alpha controls the pointer and optional desk keyboard from local "
                "camera processing. Reliability checks run before input injection. No camera "
                "frame or typed content is intentionally persisted.",
            )
        )

        environment = inspect_input_environment()
        selected = select_backend_name("auto", environment=environment)
        if environment.system == "Linux" and environment.wayland:
            input_note = (
                "Wayland is fail-closed. Writable /dev/uinput is required; Ghosty Input will "
                "not silently downgrade to PyAutoGUI."
            )
        else:
            input_note = f"Automatic input backend: {selected}."
        self.addPage(
            _page(
                "Desktop session",
                f"Detected session: {environment.session_type}\n"
                f"Desktop: {environment.desktop}\n"
                f"uinput writable: {'yes' if environment.uinput_writable else 'no'}\n\n"
                f"{input_note}",
            )
        )

        camera_page = QWizardPage()
        camera_page.setTitle("Front camera")
        camera_layout = QVBoxLayout(camera_page)
        camera_layout.addWidget(
            QLabel(
                "Choose the primary tracking camera. This step enumerates devices only; "
                "the camera stream is not opened until you start the engine."
            )
        )
        self.camera = QComboBox()
        devices = discover_cameras()
        selected_row = -1
        for device in devices:
            self.camera.addItem(device.label, (device.index, device.stable_id))
            row = self.camera.count() - 1
            if config.front_camera_id and device.stable_id == config.front_camera_id:
                selected_row = row
            elif selected_row < 0 and device.index == config.front_camera:
                selected_row = row
        if not devices:
            self.camera.addItem(
                f"Camera {config.front_camera} · not currently discovered",
                (config.front_camera, config.front_camera_id),
            )
            selected_row = 0
        if selected_row >= 0:
            self.camera.setCurrentIndex(selected_row)
        camera_layout.addWidget(self.camera)
        camera_layout.addStretch()
        self.addPage(camera_page)

        self.addPage(
            _page(
                "Calibration and privacy",
                "After startup, calibrate the desk plane using four corners and then run the "
                "independent center validation. For adaptive pinch calibration, Ghosty samples "
                "open-hand and pinched distances in memory and stores only the resulting "
                "engage/release thresholds. Frames and raw gesture samples are not saved.",
            )
        )

    def apply(self) -> None:
        data = self.camera.currentData()
        if isinstance(data, (tuple, list)) and len(data) == 2:
            self.config.front_camera = int(data[0])
            self.config.front_camera_id = str(data[1])
        self.config.onboarding_complete = True
        save_config(self.config)


def run_first_run_onboarding() -> bool:
    config = load_config()
    if config.onboarding_complete:
        return True
    wizard = FirstRunWizard(config)
    if wizard.exec() != QDialog.DialogCode.Accepted:
        return False
    wizard.apply()
    return True

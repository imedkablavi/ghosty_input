from __future__ import annotations

import platform

import cv2


class CameraError(RuntimeError):
    pass


class Camera:
    def __init__(self, index: int, width: int = 1280, height: int = 720) -> None:
        self.index = index
        self.width = width
        self.height = height
        self._capture: cv2.VideoCapture | None = None

    def open(self) -> None:
        if self._capture is not None and self._capture.isOpened():
            return

        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
        capture = cv2.VideoCapture(self.index, backend)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not capture.isOpened():
            capture.release()
            raise CameraError(f"Unable to open camera {self.index}.")
        self._capture = capture

    def read(self):
        if self._capture is None or not self._capture.isOpened():
            raise CameraError(f"Camera {self.index} is not open.")
        ok, frame = self._capture.read()
        if not ok or frame is None:
            raise CameraError(f"Camera {self.index} did not return a frame.")
        return frame

    def release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

# Ghosty Input Architecture

## Runtime flow

1. `Camera` acquires frames from the front camera and, optionally, a second top camera.
2. `HandTracker` detects up to two hands with MediaPipe.
3. `GhostyEngine` routes the preferred right hand to mouse control.
4. Mouse gestures are translated by `InputController` to local OS input through PyAutoGUI.
5. Desk keyboard input is enabled only after a four-corner perspective calibration.
6. The index fingertip is projected into keyboard coordinates with a homography.
7. A thumb/index pinch commits the hovered key.
8. The Qt UI shows previews, calibration state and runtime events.

## Safety and privacy

- No network calls are made by the application.
- Camera frames are processed in memory and are not written to disk.
- PyAutoGUI fail-safe remains enabled. Moving the pointer to the top-left corner can abort PyAutoGUI operations.
- A 0.75 second closed-fist hold toggles pointer control.
- Calibration and settings are stored in the user's application-data directory.

## Camera modes

### Single camera

The front camera stream is reused for mouse control and keyboard tracking. This is useful for testing but requires the desk plane to be visible in the same image.

### Dual camera

The front camera controls the pointer while a top-down camera observes the desk keyboard. This is the recommended setup.

## Calibration order

Click the keyboard/desk corners in this order:

1. top-left
2. top-right
3. bottom-right
4. bottom-left

The points are stored as normalized image coordinates, so camera resolution changes do not invalidate the calibration as long as the physical camera position does not move.

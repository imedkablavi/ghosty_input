# Ghosty Input Architecture

## Runtime model

Ghosty Input separates the Qt control surface from the real-time vision pipeline. Camera capture, MediaPipe inference, gesture classification, calibration mapping, and local input execution run on a dedicated `RuntimeThread`. The Qt main thread receives immutable runtime results and renders previews/metrics without performing vision inference itself.

## Runtime flow

1. `RuntimeThread` owns a `GhostyEngine` for the active session.
2. `Camera` requests the configured resolution/FPS and reports the actual negotiated mode and measured FPS.
3. `HandTracker` detects up to two hands with MediaPipe and applies temporal landmark stabilization.
4. `GhostyEngine` selects the highest-confidence matching hand for each role.
5. Pointer coordinates pass through adaptive One Euro filtering plus a small pixel dead-zone before `InputController` emits local OS events through PyAutoGUI.
6. Pinch distances are normalized against palm size and interpreted through hysteresis gates rather than a single raw threshold.
7. Desk typing is enabled only after validated four-corner perspective calibration.
8. The right index/pinch center is transformed into normalized keyboard coordinates with a homography.
9. `VirtualKeyboard` applies safe edge insets, hover dwell, release gating, and cooldown before committing a key.
10. Key polygons are inverse-projected back into the calibrated camera quadrilateral so the preview reflects the real desk geometry.
11. `RuntimeMetrics` reports measured FPS, actual camera resolution, hand confidence, and calibration quality to the Control Center.

## Threading

- **Qt main thread:** widgets, settings, preview rendering, user interaction.
- **RuntimeThread:** camera I/O, MediaPipe, gesture logic, keyboard logic, PyAutoGUI actions.
- UI-to-runtime mutations use a small command queue. Calibration updates are applied by the runtime thread instead of modifying the engine concurrently.

This keeps the interface responsive when higher camera resolutions or slower inference frames are used.

## Precision layers

### Camera

The application requests an operating mode, but camera drivers and OpenCV backends may negotiate another mode. The dashboard therefore exposes the actual width/height and measured FPS instead of assuming the requested values were applied.

### Hand landmarks

Raw MediaPipe landmark locations are temporally stabilized. The smoother increases responsiveness when wrist motion is large and applies more damping when movement is small.

### Pointer

The pointer uses adaptive One Euro filtering. This provides stronger low-speed jitter suppression while allowing faster motion to respond with less lag. A configurable dead-zone removes tiny screen-space updates.

### Gesture activation

Raw thumb-to-fingertip distance varies with hand distance from the camera. Ghosty Input divides this distance by a palm-size reference before comparing it with engage/release thresholds. Separate hysteresis thresholds prevent rapid activation/deactivation around a noisy boundary.

### Desk keyboard

A key press is not accepted from a threshold crossing alone. The target key must be stable for the configured dwell period, the pinch must be armed, and a completed press must be followed by a release period before another character can fire. A small inset around key borders reduces adjacent-key errors.

## Camera modes

### Single camera

The front camera stream is reused for pointer and keyboard tracking. This remains useful for development and demonstrations but requires the desk plane to be visible in the same frame.

### Dual camera

The front camera controls the pointer while a fixed top-down camera observes the desk keyboard. This is the recommended configuration for typing accuracy.

## Calibration

Corner order:

1. top-left
2. top-right
3. bottom-right
4. bottom-left

Calibration points are normalized image coordinates. Geometry checks reject crossed, non-convex, out-of-range, and unusably small quadrilaterals. The UI reports a heuristic 0–100 quality score and the keyboard overlay is projected into the selected quadrilateral.

A camera position change requires recalibration. Resolution changes alone do not invalidate normalized coordinates if the camera framing and aspect ratio remain equivalent, but the projected overlay should always be visually rechecked after changing a camera mode.

## Safety and privacy

- No network calls are required by the runtime.
- Camera frames are processed in memory and are not intentionally written to disk.
- PyAutoGUI fail-safe remains enabled.
- A 0.75 second closed-fist hold toggles pointer control.
- Losing hand tracking ends any active drag and resets pointer filtering.
- Calibration and settings are stored in the user's application-data directory.
- Public releases should pass both automated CI and the real-camera quality gate in `docs/QUALITY.md`.

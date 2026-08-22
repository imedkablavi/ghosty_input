# Ghosty Input Release Quality Gate

This checklist separates automated correctness from real-camera acceptance testing. A release should not be labelled production-ready until both sections pass.

## Automated gate

- `ruff check .` passes.
- `pytest` passes on Python 3.10 and 3.11.
- CI passes on Ubuntu and Windows.
- Windows portable ZIP and installer build completes.
- Linux portable archive and Debian package build completes.
- Linux source UI and packaged UI smoke tests pass with Qt's offscreen platform.
- The extracted `.deb` payload runs `--version`, `--diagnose`, and the UI smoke test before publication.
- The Debian desktop entry passes `desktop-file-validate`.
- The Debian `/usr/bin/ghosty-input` launcher resolves to the packaged runtime.
- Linux distribution size stays within the current release budget: portable <= 230 MiB and `.deb` <= 180 MiB.
- SHA-256 checksum files are generated for distribution artifacts.
- Linux build and dependency manifests are generated and bundled with the runtime.
- No config migration regression from a previous user config.
- Calibration geometry rejects crossed or unusably small quadrilaterals.
- Pinch hysteresis and keyboard release-gating tests pass.

## Camera acceptance gate

Test each supported webcam configuration in the Control Center.

- Confirm the dashboard's **actual** resolution, not only the requested mode.
- Minimum target: 1280×720 at a measured 24 FPS during hand tracking.
- Preferred precision target: 1920×1080 at a measured 24–30 FPS.
- Verify the hand confidence remains stable under normal indoor lighting.
- Verify autofocus does not continuously hunt when the hand is over the keyboard.
- If autofocus hunts, disable it in the control panel and retest with a fixed camera setup.
- On Linux, reboot or reconnect USB cameras and confirm saved front/desk routing follows the same physical devices when persistent V4L aliases are available.
- On Linux, disconnect and reconnect a camera while the runtime is active and confirm the reconnect loop recovers without restarting the application.

## Pointer acceptance test

Run for at least 5 minutes.

- Hold the index finger stationary over five different screen positions; cursor jitter should remain visually contained.
- Traverse all four corners and the center without pointer jumps.
- Perform 50 left clicks and verify no unintended double-clicks.
- Perform 25 right clicks and 25 drag operations.
- Pause/resume with a fist 10 times and verify no stuck mouse-down state.
- On Wayland, verify the native `uinput` backend is active before scoring pointer accuracy.

## Keyboard accuracy test

Use a fixed top-down camera and a fresh four-point calibration.

1. Type a known 200-character sample containing every alphabet row, spaces, backspace, shift, and enter.
2. Count wrong, missing, and duplicated characters.
3. Recalibrate and repeat once.

Release target:

- No duplicated character caused by a held pinch.
- At least 97% raw key-selection accuracy in stable indoor lighting after calibration.
- No neighboring-key error pattern caused by a visibly misaligned projected overlay.

If accuracy is below target, tune keyboard dwell, release guard, camera position, and calibration before changing global pinch thresholds.

## Calibration acceptance test

- Quality score should normally be 70/100 or higher.
- The projected key polygons must visually stay inside the selected keyboard plane.
- Moving any camera after calibration requires recalibration.
- Crossed corner order must be rejected.

## Soak test

Run the application continuously for 30 minutes.

- Control Center remains responsive.
- Runtime worker stops cleanly and can restart.
- No continuously growing diagnostic spam.
- No stuck drag state after losing hand tracking.
- Camera can recover after stop/start without restarting the process.
- On Linux, tray show/hide, close-to-tray, autostart, and launcher actions do not leave duplicate processes.

## Offline/privacy check

With network access disabled:

- Application starts and runs.
- Camera processing, mouse control, keyboard input, config loading, and calibration all work.
- No frame or typed-content files are created by the application.

## Release decision

A green CI run is necessary but not sufficient. Real-hardware camera and typing acceptance results should be recorded in the release notes for any build described as production-ready.

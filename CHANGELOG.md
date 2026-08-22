# Changelog

## 0.4.0

### Linux input
- Add a native Linux `uinput` keyboard/mouse backend through python-evdev.
- Auto-select `uinput` when the current user has access and keep PyAutoGUI as a fallback.
- Add Wayland/X11 session diagnostics and an explicit backend selector.
- Add a least-privilege Linux setup helper using a dedicated `ghosty-input` group and udev rule.

### Interaction engine
- Add hands-free hover/dwell activation for pointer left-click and desk-keyboard input.
- Re-arm dwell actions only after the pointer/key target is left, preventing repeated clicks or characters.
- Keep normalized pinch, hysteresis, temporal hand stabilization, and One Euro pointer filtering.

### Cameras and diagnostics
- Discover Linux cameras from `/sys/class/video4linux` with human-readable device names.
- Add `ghosty-input --diagnose` for session, camera, and input-backend health checks.
- Show the active OS input backend in live runtime metrics.

### Distribution
- Add an Ubuntu 22.04 x86_64 Linux preview build.
- Package a self-contained tarball, launch helper, Linux setup helper, README, and SHA-256 checksum.

## 0.3.0

### Precision
- Normalize pinch distance by palm size.
- Add hysteresis to noisy pinch states.
- Add temporal landmark stabilization.
- Replace simple pointer EMA with adaptive One Euro filtering and a dead-zone.
- Add keyboard dwell, release guard, cooldown, and safe key-edge inset.
- Validate calibration geometry and expose a calibration quality score.
- Project keyboard keys into the calibrated camera quadrilateral.

### Camera
- Default to a 1080p/30 request.
- Add requested resolution/FPS/autofocus controls.
- Report actual camera resolution, backend, and measured FPS.

### Desktop UI
- New Control Center with live metrics, camera previews, tuning profiles, calibration workflow, and diagnostics.
- Move capture and MediaPipe processing to a worker thread to keep the Qt UI responsive.

### Quality
- Expand unit coverage and add a real-hardware release quality gate.

### Distribution
- Build Windows portable and Inno Setup installer artifacts with SHA-256 checksums.

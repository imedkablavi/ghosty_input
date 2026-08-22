# Changelog

## 0.5.1 - Linux camera reliability hotfix

### Camera discovery
- Added direct `/dev/video*` discovery when `/sys/class/video4linux` is unavailable or incomplete.
- Added native `VIDIOC_QUERYCAP` inspection without requiring `v4l-utils`.
- Filters V4L2 metadata/output-only nodes from the user camera selector while keeping them visible in diagnostics.
- Uses the V4L2 `card`, driver, and bus information when sysfs does not provide a friendly camera name.
- Keeps unknown/permission-blocked nodes visible instead of silently dropping them.

### Camera opening
- Verifies a real frame during camera open instead of treating `VideoCapture.isOpened()` as sufficient.
- Adds adaptive capture negotiation: requested resolution, then 1280×720, then 640×480.
- On Linux, tries MJPG and the camera's default pixel format before falling back from V4L2 to OpenCV auto-selection.
- Keeps the first validated frame so startup verification does not discard a good frame.

### Diagnostics and packaging
- Added `--camera-diagnose` (Camera Doctor) to report V4L2 capability, access, driver, bus, backend, negotiated resolution, FPS, and real-frame probe result.
- Expanded `--diagnose` with capture/non-capture/unknown V4L2 counts and OpenCV video backends.
- Linux source, packaged binary, and extracted `.deb` now run Camera Doctor as a packaging gate.
- Linux packaging now uses a single release-version variable to keep archive, Debian metadata, and artifact names consistent.

## 0.5.0 - Linux commercial track

### Linux runtime
- Added persistent V4L camera identities using `/dev/v4l/by-id` with `by-path` fallback.
- Added automatic camera reconnect with persistent-ID re-resolution after USB re-enumeration.
- Added separate autofocus settings for front and desk cameras.
- Hardened Auto input backend fallback when native uinput creation fails.
- Expanded Linux diagnostics with distribution, kernel, camera permissions, persistent IDs, desktop launcher state, and autostart state.

### Linux desktop
- Added an optional system tray with Show, Start/Stop Engine, and Quit actions.
- Added optional close-to-tray behavior; disabled by default.
- Added per-user application-menu integration without root.
- Added per-user desktop-session autostart and minimized startup.
- Added CLI desktop integration commands.

### Distribution
- Added a Debian/Ubuntu `.deb` package in addition to the portable tarball.
- Added a packaged Qt offscreen UI smoke test so CLI-only packaging success cannot hide missing Qt plugins.
- Removed blanket `--collect-all PySide6` from the Linux build and rely on PyInstaller's Qt hooks to reduce package size while retaining explicit UI verification.
- Added checksums and package-size reporting.
- Improved the uinput setup helper with boot-time module loading, status, and removal commands.

### Quality
- Expanded unit coverage for persistent camera IDs and Linux desktop-entry generation.
- 20 local unit tests pass before CI.

## 0.4.0 - Linux precision preview

- Added native Linux uinput input injection.
- Added Wayland/X11 diagnostics and camera discovery.
- Added Linux Control Center and hover/dwell interaction modes.
- Added portable Ubuntu 22.04 x86_64 preview packaging.

## 0.3.0 - Precision control center

- Added normalized pinch, hysteresis, One Euro pointer filtering, calibrated projected keyboard rendering, runtime threading, camera metrics, and Windows distribution workflows.

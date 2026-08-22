# Changelog

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

# Changelog

## 0.6.0a1 - Alpha 1

### Alpha readiness
- Added `--preflight` with a structured PASS/WARN/FAIL readiness report.
- Added optional real-camera validation with `--preflight --preflight-probe-camera`.
- Added an **Alpha** tab to the Linux Control Center with readiness status, Camera Doctor, and runtime-log location.
- Added a local first-run onboarding wizard for desktop-session/input safety, camera selection, calibration guidance, and privacy guidance without opening a camera stream.
- Added a product **Reliability** view with live capture/tick latency, drop/error/reconnect counters, adaptive pinch calibration, and independent center validation.
- Engine startup is blocked when required camera/input checks fail; desk-keyboard calibration can remain a warning while mouse testing proceeds.
- Added single-instance desktop locking so two Ghosty Input processes cannot race for the same camera or uinput device.

### Camera, input, and calibration reliability
- Added X11/Wayland session detection with environment fallbacks and fail-closed Wayland input behavior: automatic selection remains on native `uinput`, and runtime PyAutoGUI downgrade is rejected on Wayland.
- Added persistent Linux `/dev/v4l/by-id` routing with `by-path` fallback and reconnect/re-enumeration recovery.
- Added `--camera-modes` to verify common requested modes against real negotiated resolution/FPS/backend; unknown backend FPS is reported as unverified instead of exact.
- Added runtime measured FPS, capture-read EMA/max latency, estimated dropped-frame timing gaps, camera errors, and successful reconnect counters.
- Added independent center hold-out reprojection error for desk calibration and a validated quality indicator instead of relying only on calibration points used to fit the transform.
- Added per-user adaptive pinch calibration that derives engage/release hysteresis thresholds from temporary open/pinch samples and discards the raw samples after derivation.
- Added stationary-jitter smoothing and threshold-jitter/false-click QA coverage.
- Invalid saved four-point desk calibration now fails safely in the Reliability UI and requests recalibration instead of crashing validation.

### Recovery and stability
- Invalid `config.json` files are quarantined with a timestamped backup instead of being silently discarded.
- Config writes are flushed, fsynced, permission-hardened on Unix, and atomically replaced.
- Added a small rotating persistent runtime log for startup, shutdown, device/backend failures, and crash tracebacks.
- Persistent logs intentionally exclude camera frames and typed content.
- Runtime workers stop after repeated unexpected internal errors instead of producing an unbounded error loop.
- Window shutdown no longer claims the engine is stopped while the camera worker is still alive.
- Input/backend and engine shutdown now use best-effort resource cleanup so one release failure does not prevent remaining cameras, trackers, or virtual-input resources from being closed.
- Camera-only soak diagnostics explicitly drop frame references, never write image payloads, and report CPU/RSS/drop/latency metrics; Linux RSS probes explicitly close `/proc/self/statm` on every sample.
- Old absolute `pinch_threshold` configuration is intentionally discarded because it cannot be safely converted to the newer palm-normalized pinch ratio.

### Verified updates
- Added automatic packaged-build update checks against the official GitHub Releases feed.
- Added `auto`, `stable`, and `alpha` release channels. Alpha builds on `auto` receive newer Alpha releases and future stable releases.
- Added `--check-update`, `--update`, and `--update-channel` CLI controls.
- Update packages are restricted to this repository's Release download path and verified against platform SHA-256 manifests before installation.
- Linux `.deb` installs use a PolicyKit privilege prompt while the application remains a normal desktop-user process.
- Linux portable builds can replace themselves after exit using a verified archive, temporary staging directory, and rollback copy.
- Windows builds launch the verified Inno Setup installer and exit cleanly for replacement.
- Added archive path/special-file validation for portable Linux updates.
- Added a release publisher workflow that creates/updates a GitHub Release only for accepted `v*` tags and uploads successful Linux/Windows distribution artifacts.
- The updater ignores newly created Releases until the package and checksum required by the current platform are both present.
- Windows Alpha artifacts are integrity-checked with SHA-256; Authenticode signing is not claimed until a real signing certificate is configured.

### Distribution
- Alpha version is consistent as `0.6.0a1` across Python metadata, Linux packages, Windows installer metadata, and artifact names.
- Debian package declares the Linux/X11/XCB runtime libraries required by the packaged Qt application.
- Linux CI validates `libqxcb.so` with `ldd` and fails on unresolved shared libraries.
- Source, packaged portable runtime, and extracted Debian payload validate `--preflight`, `--diagnose`, `--camera-diagnose`, `--log-path`, version output, updater package smoke, and Qt offscreen startup.
- The generated portable archive is passed through the same archive-safety validator used by the self-updater before it can be published.
- Alpha testing instructions ship inside the portable and Debian packages as `README-ALPHA.md`.
- Windows packaging now runs the actual source/product UI smoke before building and the packaged product UI/onboarding smoke after PyInstaller.
- Windows artifacts now have explicit per-file/combined size budgets plus dependency and build-size manifests to catch accidental package growth.

### Tests
- Added coverage for config quarantine/recovery and legacy pinch migration.
- Added Alpha preflight tests for missing cameras, Wayland/uinput readiness, dual-camera conflicts, calibration warnings, and real-stream probe failures.
- Added duplicate-instance lock/reacquire tests.
- Added updater tests for semantic Alpha/stable ordering, channel selection, incomplete releases, package-type detection, SHA-256 rejection, and portable archive traversal rejection.
- Added Wayland fail-closed runtime policy, camera mode exact/fallback/unknown-FPS reporting, calibration hold-out error, adaptive threshold derivation/overlap rejection, drop/reconnect counters, stationary jitter, and false-click regression coverage.
- Added a 5,000-frame synthetic camera soak regression that verifies no payload files are created.
- Added persistence privacy regression checks for camera-frame, typed-data, and raw gesture-sample fields.
- Package smoke now constructs the actual first-run wizard and Product UI reliability controls instead of only legacy/base window classes.

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
- Added `--camera-diagnose` (Camera Doctor) to report V4L2 capability, access, driver, bus, backend, negotiated resolution, FPS, and real frame probe result.
- Expanded `--diagnose` with capture/non-capture/unknown V4L2 counts and OpenCV video backends.
- Linux source, packaged binary, and extracted `.deb` run Camera Doctor as a packaging gate.
- Linux packaging uses a single release-version variable to keep archive, Debian metadata, and artifact names consistent.

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

## 0.4.0 - Linux precision preview

- Added native Linux uinput input injection.
- Added Wayland/X11 diagnostics and camera discovery.
- Added Linux Control Center and hover/dwell interaction modes.
- Added portable Ubuntu 22.04 x86_64 preview packaging.

## 0.3.0 - Precision control center

- Added normalized pinch, hysteresis, One Euro pointer filtering, calibrated projected keyboard rendering, runtime threading, camera metrics, and Windows distribution workflows.

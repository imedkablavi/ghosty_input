<div align="center">

<img src="assets/logo.png" alt="Ghosty Input logo" width="130"/>

# Ghosty Input

**Precision offline hand-gesture mouse control and desk-surface virtual keyboard**

**Current test build: `0.6.0a1` · Alpha 1 · Windows + Linux**

[Alpha testing](docs/ALPHA.md) · [Reliability report](docs/ALPHA_RELIABILITY_REPORT.md) · [Linux](docs/LINUX.md) · [Quality](docs/QUALITY.md) · [Architecture](docs/ARCHITECTURE.md) · [Privacy](PRIVACY.md)

</div>

Ghosty Input turns one or two ordinary cameras into a local computer-vision input system. A front camera tracks the hand for pointer control, while an optional top-down camera maps a calibrated physical area to a projected QWERTY keyboard.

The current Alpha focuses on **real-machine reliability**: camera capability/stream diagnostics, X11/Wayland input safety, reconnect recovery, calibration quality, per-user gesture calibration, first-run onboarding, privacy regression checks, safe shutdown, long-run instrumentation, and testable Windows/Linux packages.

## Alpha 1 readiness layer

Alpha 1 adds:

- structured `PASS / WARN / FAIL` preflight before the engine starts;
- optional real-frame camera preflight;
- V4L2 **Camera Doctor** with kernel capability and stream probing on Linux;
- `--camera-modes` verification of requested versus negotiated resolution/FPS/backend;
- persistent `/dev/v4l/by-id` / `by-path` Linux camera routing and automatic reconnect;
- measured runtime FPS plus capture latency/drop/error/reconnect diagnostics;
- native `uinput` for Wayland with fail-closed behavior instead of unsafe silent PyAutoGUI downgrade;
- per-user adaptive pinch thresholds with raw calibration samples discarded after derivation;
- four-point desk calibration quality plus independent center reprojection validation;
- first-run local onboarding and a Reliability view for hardware/gesture qualification;
- duplicate-process protection, invalid-config quarantine, atomic config writes, and bounded runtime failures;
- rotating operational logs that do not store camera frames or typed-content payloads;
- `--camera-soak` CPU/RAM/drop/latency diagnostics that discard frames in memory;
- Debian/portable Linux and Windows portable/installer distributions with packaged Product UI smoke, checksums, dependency manifests, and package-size gates.

Useful Alpha diagnostics:

```bash
ghosty-input --preflight
ghosty-input --camera-diagnose
ghosty-input --camera-modes
ghosty-input --log-path
ghosty-input --camera-soak 120
```

See [docs/ALPHA.md](docs/ALPHA.md) and [docs/ALPHA_RELIABILITY_REPORT.md](docs/ALPHA_RELIABILITY_REPORT.md) for the real-hardware acceptance sequence and the distinction between automated evidence and manual hardware claims.

## Precision system

- 1080p/30 requested by default with adaptive fallback to 720p and 480p when required
- Actual camera resolution and measured FPS shown live
- Temporal landmark stabilization
- Adaptive One Euro pointer filtering
- Pointer dead-zone to reduce cursor chatter
- Pinch distance normalized by palm size
- Hysteresis for click/drag/typing states
- Per-user adaptive pinch calibration
- Hover-dwell activation modes
- Keyboard dwell/release protection against duplicate characters
- Four-point perspective calibration with geometry validation and a 0–100 quality score
- Independent desk-center reprojection validation for calibration accuracy
- Keyboard overlay projected into the calibrated quadrilateral
- Camera + MediaPipe runtime isolated from the Qt UI thread

## Mouse gestures

| Gesture | Action |
|---|---|
| Move right index fingertip | Move pointer |
| Thumb + index pinch | Left click |
| Thumb + middle pinch | Right click |
| Thumb + ring pinch/hold | Drag |
| Index + middle raised, vertical motion | Scroll |
| Closed fist held 0.75s | Pause/resume |

## Desk keyboard

For best typing accuracy, use a dedicated top-down camera with the full keyboard plane visible.

1. Start the engine after Alpha preflight passes.
2. Enable the dedicated desk camera when using two cameras.
3. Calibrate top-left → top-right → bottom-right → bottom-left.
4. Target calibration quality of at least 70/100.
5. Run independent center validation; use `<= 4%` reprojection error as the Alpha precision target.
6. Verify projected key outlines follow the physical surface.
7. Test with a known 200-character sample and record wrong, missed, or duplicated keys.

## Requirements

### Linux Alpha

- x86_64 Linux
- Debian/Ubuntu-family for the `.deb`, or another recent distribution for the portable archive
- one V4L2 webcam minimum; two are recommended for desk typing
- writable camera device nodes
- on Wayland, writable `/dev/uinput` configured using the bundled helper

### Windows Alpha

- Windows 11 x64 is the current manual qualification target
- one integrated or USB UVC-compatible webcam minimum; two are recommended for desk typing
- packaged builds are available as portable ZIP and Inno Setup installer
- Alpha packages are SHA-256 verified by the updater; Authenticode signing is not claimed until a real code-signing certificate is configured

### Development from source

- Python 3.10 or 3.11
- Windows or Linux

```bash
git clone https://github.com/imedkablavi/ghosty_input.git
cd ghosty_input
python -m venv .venv
```

Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python run.py --preflight
python run.py
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

## Local data and privacy

Settings and Alpha operational logs are stored outside the repository:

- Windows: `%APPDATA%\GhostyInput\`
- Linux: `~/.local/share/GhostyInput/`

Camera frames are processed in memory. Ghosty Input does not include analytics, telemetry, cloud inference, or runtime network APIs. Persistent operational logs are for lifecycle/device diagnostics and are not intended to store frames or typed content. Adaptive calibration persists derived thresholds, not raw gesture samples. See [PRIVACY.md](PRIVACY.md).

## Development and CI

```bash
pip install -r requirements-ci.txt
ruff check .
pytest
```

CI runs linting and unit tests on Python 3.10 and 3.11 on Ubuntu and Windows. Distribution workflows additionally verify packaged version/product UI startup, onboarding/reliability controls, Linux preflight/diagnostics and Qt/XCB linkage, Windows installer/portable packaging, SHA-256 manifests, dependency manifests, and package-size budgets.

## Release status

`0.6.0a1` is an **Alpha**, not a production-certified release. Green CI means the source and packages are ready for real-hardware qualification. Physical camera mode/latency behavior, compositor/input behavior, disconnect/reconnect recovery, pointer/typing accuracy, and long-running full-runtime stability still need to pass the target hardware matrix before Beta promotion.

## Author

iEmmAd / cybrex — [@imedkablavi](https://github.com/imedkablavi)

## Support

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/imed_kablavi)

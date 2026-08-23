<div align="center">

<img src="assets/logo.png" alt="Ghosty Input logo" width="130"/>

# Ghosty Input

**Precision offline hand-gesture mouse control and desk-surface virtual keyboard**

**Current test build: `0.6.0a1` · Linux Alpha 1**

[Alpha testing](docs/ALPHA.md) · [Linux](docs/LINUX.md) · [Quality](docs/QUALITY.md) · [Architecture](docs/ARCHITECTURE.md) · [Privacy](PRIVACY.md)

</div>

Ghosty Input turns one or two ordinary cameras into a local computer-vision input system. A front camera tracks the hand for pointer control, while an optional top-down camera maps a calibrated physical area to a projected QWERTY keyboard.

The current Alpha focuses on **real-machine reliability**: camera discovery, Wayland/uinput readiness, first-run diagnostics, config recovery, safe shutdown, and packages that can be tested without a Python development environment.

## Alpha 1 readiness layer

Linux Alpha 1 adds:

- structured `PASS / WARN / FAIL` preflight before the engine starts;
- optional real-frame camera preflight;
- V4L2 **Camera Doctor** with kernel capability and stream probing;
- persistent `/dev/v4l/by-id` / `by-path` camera routing;
- adaptive camera mode negotiation and automatic reconnect;
- native `uinput` for reliable Wayland input with PyAutoGUI fallback where appropriate;
- duplicate-process protection so two app instances cannot fight over the same camera/input device;
- invalid-config quarantine and atomic config writes;
- bounded runtime failure handling and safer worker shutdown;
- rotating operational logs that do not store camera frames or typed-content payloads;
- Debian and portable Linux distributions with package/linkage checks in CI.

Before testing on Linux:

```bash
ghosty-input --preflight
ghosty-input --camera-diagnose
ghosty-input --log-path
```

See [docs/ALPHA.md](docs/ALPHA.md) for the hardware acceptance sequence.

## Precision system

- 1080p/30 requested by default with adaptive fallback to 720p and 480p when required
- Actual camera resolution and measured FPS shown live
- Temporal landmark stabilization
- Adaptive One Euro pointer filtering
- Pointer dead-zone to reduce cursor chatter
- Pinch distance normalized by palm size
- Hysteresis for click/drag/typing states
- Hover-dwell activation modes
- Keyboard dwell/release protection against duplicate characters
- Four-point perspective calibration with geometry validation and a 0–100 quality score
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
5. Verify projected key outlines follow the physical surface.
6. Test with a known 200-character sample and record wrong, missed, or duplicated keys.

## Requirements

### Linux Alpha

- x86_64 Linux
- Debian/Ubuntu-family for the `.deb`, or another recent distribution for the portable archive
- one V4L2 webcam minimum; two are recommended for desk typing
- writable camera device nodes
- on Wayland, writable `/dev/uinput` configured using the bundled helper

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

Camera frames are processed in memory. Ghosty Input does not include analytics, telemetry, cloud inference, or runtime network APIs. Persistent operational logs are for lifecycle/device diagnostics and are not intended to store frames or typed content. See [PRIVACY.md](PRIVACY.md).

## Development and CI

```bash
pip install -r requirements-ci.txt
ruff check .
pytest
```

CI runs linting and unit tests on Python 3.10 and 3.11 on Ubuntu and Windows. Distribution workflows additionally verify packaged version output, diagnostics, Alpha preflight behavior, Qt startup, Debian metadata, checksums, and Linux Qt/XCB shared-library linkage.

## Release status

`0.6.0a1` is an **Alpha**, not a production-certified release. Green CI means the package is ready for real-hardware testing. Camera/compositor accuracy, reconnect behavior, pointer/typing accuracy, shutdown behavior, and a 30-minute soak still need to pass on target hardware before Beta promotion.

## Author

iEmmAd / cybrex — [@imedkablavi](https://github.com/imedkablavi)

## Support

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/imed_kablavi)

<div align="center">

<img src="assets/logo.png" alt="Ghosty Input logo" width="130"/>

# Ghosty Input

**Precision offline hand-gesture mouse control and desk-surface virtual keyboard**

[العربية](README.ar.md) · [Türkçe](README.tr.md) · [Architecture](docs/ARCHITECTURE.md) · [Quality](docs/QUALITY.md) · [Privacy](PRIVACY.md)

</div>

Ghosty Input turns one or two ordinary cameras into a local computer-vision input system. A front camera tracks the right hand for pointer control, while an optional top-down camera maps a calibrated physical area to a projected QWERTY keyboard.

Version 0.3 focuses on precision, stability, operator feedback, and a control panel that can be tuned for different cameras instead of relying on fixed demo thresholds.

## Precision system

- 1080p/30 requested by default with 720p, 1080p and 1440p control-panel profiles
- Actual camera resolution and measured FPS shown live
- Temporal landmark stabilization
- Adaptive One Euro pointer filtering: strong jitter reduction at rest with lower lag during fast movement
- Pointer dead-zone to eliminate sub-pixel cursor chatter
- Pinch distance normalized by palm size, reducing sensitivity changes when the hand moves closer to or farther from the camera
- Hysteresis for click/drag/typing pinch states to prevent threshold chatter
- Keyboard hover dwell before a key can fire
- Release guard so one pinch cannot generate repeated characters
- Safe key-edge inset to reduce accidental neighboring-key presses
- Four-point perspective calibration with geometry validation and a 0–100 calibration quality score
- Keyboard overlay projected back into the calibrated quadrilateral instead of being drawn as a flat screen overlay
- Camera + MediaPipe runtime moved off the Qt UI thread so the control center stays responsive under heavier video modes

## Control Center

The PySide6 desktop control center includes:

- Live front/desk camera previews
- Tracking FPS, actual camera mode, hand confidence, and calibration quality metrics
- Balanced, Precision, and Performance profiles
- Requested resolution and FPS controls
- Detection and tracking confidence controls
- Pointer smoothing and normalized pinch sensitivity tuning
- Keyboard dwell and release-guard tuning
- Four-point calibration workflow
- Runtime diagnostics log
- Local settings persistence

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

For best typing accuracy, use a dedicated top-down camera with the full keyboard plane visible. Calibration is performed on the exact rectangle where the projected keyboard should live.

1. Start the engine.
2. Enable the dedicated desk camera when using two cameras.
3. Open **Calibration** and start the 4-point flow.
4. On the Live desk preview, click top-left → top-right → bottom-right → bottom-left.
5. Check the calibration score and the projected key outlines.
6. Hover a key with the right index finger, then pinch thumb + index to press it.

A key must remain stable for a short dwell period before a press is accepted. After a press, the pinch must release before another character can fire.

## Requirements

- Python 3.10 or 3.11
- Windows or Linux
- One webcam minimum; two are strongly recommended for desk typing
- Camera permission
- On Linux, a desktop session where PyAutoGUI can generate input events

Camera drivers may negotiate a lower mode than requested. Ghosty Input reports the actual mode in the Live dashboard.

## Install from source

```bash
git clone https://github.com/imedkablavi/ghosty_input.git
cd ghosty_input
python -m venv .venv
```

Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

## Local data and privacy

Settings are stored outside the repository:

- Windows: `%APPDATA%\GhostyInput\config.json`
- Linux: `~/.local/share/GhostyInput/config.json`

Camera frames are processed in memory. Ghosty Input does not include analytics, telemetry, cloud inference, or runtime network APIs. See [PRIVACY.md](PRIVACY.md).

## Development

```bash
pip install -r requirements-ci.txt
ruff check .
pytest
```

CI runs linting and unit tests on Python 3.10 and 3.11 on Ubuntu and Windows.

## Quality gate before a public release

The software logic and CI can be tested automatically, but camera precision must also pass real-hardware acceptance testing. See [docs/QUALITY.md](docs/QUALITY.md) for the release checklist, typing accuracy test, soak test, and camera-mode verification.

## Windows distribution

The **Build Windows Distribution** workflow validates packaging on relevant pull requests and also runs manually or for version tags. It produces:

- `GhostyInput-Windows-x64.zip` portable package
- `GhostyInputSetup.exe` per-user Windows installer
- `SHA256SUMS.txt` integrity hashes

Push a release tag such as `v0.3.0` only after CI, distribution build, and the real-hardware quality gate pass.

## Author

iEmmAd / cybrex — [@imedkablavi](https://github.com/imedkablavi)

## Support

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/imed_kablavi)

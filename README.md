<div align="center">

<img src="assets/logo.jpg" alt="Ghosty Input Logo" width="140"/>

# Ghosty Input

**Hand-gesture mouse control and desk-surface virtual keyboard**

Local, offline hand-tracking system for mouse control and desk-based typing using computer vision.

[Website](https://imedkablavi.info) ·
[Releases](https://github.com/imedkablavi/ghosty_input/releases) ·
[Issues](https://github.com/imedkablavi/ghosty_input/issues) ·
[Docs](docs/)

<br/>

<img src="https://img.shields.io/github/v/release/imedkablavi/ghosty_input?label=release"/>
<img src="https://img.shields.io/github/license/imedkablavi/ghosty_input"/>
<img src="https://img.shields.io/github/issues/imedkablavi/ghosty_input"/>
<img src="https://img.shields.io/github/stars/imedkablavi/ghosty_input"/>
<img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey"/>
<img src="https://img.shields.io/badge/python-3.10%20%7C%203.11-blue"/>

<br/><br/>

**Language**  
[English](README.md) · [العربية](README.ar.md) · [Türkçe](README.tr.md)

</div>

---

## Overview

**Ghosty Input** is a desktop application that allows users to control the mouse and type on a desk-surface virtual keyboard using hand gestures.

- Front camera controls the mouse  
- Top-down camera maps a physical desk keyboard  
- One-camera or two-camera setups are supported  
- All processing runs locally (offline)

---

## Features

- Dual-camera architecture  
  - Front camera → mouse control  
  - Top camera → desk keyboard
- Automatic single-camera fallback (shared stream)
- Desk-plane calibration using four corner points
- Gesture-based mouse interaction (move, click, drag, scroll, pause)
- Desk-surface virtual keyboard with optional overlay
- Left-hand modifier gestures (Space, Backspace, Shift, Enter)
- Local profiles and configuration

---

## Gesture Guide

<div align="center">
  <img src="assets/screenshots/gesture-guide.png"
       alt="Ghosty Input Gesture Guide"
       width="100%"/>
</div>

**Notes**
- Front camera is used for mouse control
- Top-down camera is used for desk-surface keyboard input
- Keyboard typing requires desk-plane calibration (4 points)

---

## Screenshots

### Main Dashboard
<div align="center">
  <img src="assets/screenshots/dashboard.png" width="100%"/>
</div>

### Desk Plane Calibration
<div align="center">
  <img src="assets/screenshots/calibration.png" width="100%"/>
</div>

### Virtual Keyboard Overlay
<div align="center">
  <img src="assets/screenshots/keyboard-overlay.png" width="100%"/>
</div>

---

## Installation

### For Regular Users (Recommended)

#### Windows Installer
1. Open the **Releases** page
2. Download **GhostyInputSetup.exe**
3. Install and launch the application

No Python or development tools are required.

#### Windows Portable
- Download the portable ZIP
- Extract and run `GhostyInput.exe`

---

### For Developers

Clone the repository and run from source:

```bash
git clone https://github.com/imedkablavi/ghosty_input.git
cd ghosty_input
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
python run.py
Python 3.10 or 3.11 is required.

Camera Modes
Single camera: one shared stream for mouse and keyboard

Two cameras: front camera for mouse, top camera for keyboard

If only one camera preview is visible, this is expected behavior.

Profiles & Logs
User data is stored outside the installation directory.

Windows: %APPDATA%\GhostyInput

Linux: ~/.local/share/GhostyInput

Troubleshooting
Black camera preview: camera ID may be incorrect or blocked by OS privacy settings

Second camera preview hidden: expected in single-camera mode

Keyboard not typing: desk-plane calibration is required

MediaPipe errors: use Python 3.10 or 3.11 only

Privacy
Ghosty Input works fully offline.
No camera data or user input is transmitted or collected.

See PRIVACY.md

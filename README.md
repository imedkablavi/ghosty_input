<div align="center">

<img src="assets/logo.png" alt="Ghosty Input Logo" width="140"/>

# Ghosty Input

**Hand-gesture mouse control and desk-surface virtual keyboard**

Local, offline hand-tracking system for mouse control and desk-based typing using computer vision.

[Website](https://imedkablavi.info) ·
[Releases](https://github.com/ghosty_input/releases) ·
[Issues](https://github.com/ghosty_input/issues) ·
[Documentation](docs/)

<br/>

<!-- Badges -->
<img src="https://img.shields.io/github/v/release/YOUR_REPO?label=release"/>
<img src="https://img.shields.io/github/license/YOUR_REPO"/>
<img src="https://img.shields.io/github/issues/YOUR_REPO"/>
<img src="https://img.shields.io/github/stars/YOUR_REPO"/>
<img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey"/>
<img src="https://img.shields.io/badge/python-3.10%20%7C%203.11-blue"/>

<br/><br/>

**Language:**  
[English](README.md) · [العربية](README.ar.md) · [Türkçe](README.tr.md)

</div>

---

## Overview

**Ghosty Input** is a desktop application that allows users to control the mouse and type on a desk-surface virtual keyboard using hand gestures.

The system supports one or two cameras and automatically optimizes camera usage to avoid duplicated streams and performance issues.

All processing is performed locally. No network connection is required.

---

## Features

- Dual-camera architecture  
  - Front camera for mouse control  
  - Top-down camera for desk-plane keyboard
- Automatic single-camera fallback (shared stream)
- Desk-plane calibration using four points (homography)
- Gesture-based mouse interaction: move, click, drag, scroll, pause
- Desk-surface virtual keyboard with optional overlay
- Left-hand modifier gestures (Space, Backspace, Shift, Enter)
- Local user profiles and configuration

---

## Screenshots

### Main Dashboard
<img src="assets/screenshots/dashboard.png" width="100%"/>

### Desk Plane Calibration
<img src="assets/screenshots/calibration.png" width="100%"/>

### Virtual Keyboard Overlay
<img src="assets/screenshots/keyboard-overlay.png" width="100%"/>

---

## Installation

### For Regular Users (Recommended)

#### Windows Installer
1. Go to **Releases**
2. Download **GhostyInputSetup.exe**
3. Run the installer and launch the application

This option does not require Python or development tools.

#### Windows Portable
- Download the portable ZIP
- Extract and run `GhostyInput.exe`

---

### For Developers

Clone the repository and run from source:

```bash
git clone https://github.com/YOUR_REPO.git
cd GhostyInput
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
python run.py

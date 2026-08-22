# Ghosty Input on Linux

The Linux preview is packaged as a self-contained PyInstaller directory archive. Camera frames and input processing remain local.

## Start

```bash
tar -xzf GhostyInput-Linux-x86_64.tar.gz
cd GhostyInput
./GhostyInput --diagnose
./run-ghosty.sh
```

The diagnostic command reports the desktop session, discovered cameras, `/dev/uinput` state, and the selected input backend.

## Wayland and native input

Ghosty Input v0.4 includes a Linux-native `uinput` backend. It is preferred automatically when `/dev/uinput` is available to your normal desktop user. This avoids relying on X11-only pointer injection for the main input path.

If diagnostics show `uinput: present but permission denied` or `uinput: not available`, run the bundled helper once:

```bash
./ghosty-input-linux-setup.sh
```

The helper loads the `uinput` kernel module, creates a dedicated `ghosty-input` group, and installs a narrow udev rule granting that group read/write access to `/dev/uinput`. Sign out and back in (or reboot), then run diagnostics again.

**Do not run Ghosty Input as root.** The application itself should always run as your normal desktop user.

## X11 fallback

When native `uinput` is unavailable, Auto mode falls back to PyAutoGUI. This is most reliable in X11/XWayland environments. The Control Center shows the active backend so you can see which path is in use.

## Cameras

The Control Center discovers Linux video devices from `/sys/class/video4linux` and shows names such as integrated/USB cameras rather than requiring only numeric indices. You can refresh the list without restarting the application.

A dedicated fixed top-down desk camera is recommended for keyboard testing.

## Test sequence

1. Run `./GhostyInput --diagnose`.
2. Start the Control Center and confirm the live camera FPS and actual camera resolution.
3. Test pointer movement before enabling clicking.
4. Try both **Pinch** and **Hover dwell** left-click modes.
5. For desk typing, calibrate all four corners and verify the projected keyboard aligns with the physical plane.
6. Try **Pinch** and **Hover dwell** keyboard activation separately.
7. Record any error from the Diagnostics tab together with your desktop session (`wayland` or `x11`).

## Packaging compatibility

The preview is built on Ubuntu 22.04 x86_64 to reduce glibc compatibility problems on newer Linux distributions. Linux desktop libraries and GPU/camera drivers still vary by distribution, so real-device acceptance testing is required before calling a specific distro fully supported.

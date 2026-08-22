# Ghosty Input on Linux

Ghosty Input v0.5 treats Linux as a first-class target rather than a PyAutoGUI fallback. The Linux build uses native `uinput` when available, keeps camera selection stable across reboots when V4L persistent links exist, and ships both a portable archive and a Debian package.

## Recommended installation

### Debian / Ubuntu / Linux Mint / Pop!_OS

Install the `.deb` build:

```bash
sudo apt install ./ghosty-input_0.5.0_amd64.deb
ghosty-input --diagnose
ghosty-input
```

The application is installed under `/opt/ghosty-input` and a desktop launcher is registered system-wide.

### Portable build

```bash
tar -xzf GhostyInput-Linux-x86_64-v0.5.0.tar.gz
cd GhostyInput
./GhostyInput --diagnose
./run-ghosty.sh
```

The portable build does not require Python to be installed.

## Wayland and native input

For reliable global mouse and keyboard injection on Wayland, use the native Linux `uinput` backend. Run the bundled setup helper as your normal user:

```bash
./ghosty-input-linux-setup.sh install
```

For a `.deb` installation:

```bash
/opt/ghosty-input/ghosty-input-linux-setup.sh install
```

The helper:

- loads the `uinput` kernel module;
- configures it to load on boot;
- creates a dedicated `ghosty-input` group;
- grants that group access only to `/dev/uinput`;
- does not run Ghosty Input itself as root.

Sign out and back in, or reboot, then verify:

```bash
ghosty-input --diagnose
```

Expected result:

```text
uinput: ready
Recommended input backend: uinput
```

Check or remove the system configuration later with:

```bash
/opt/ghosty-input/ghosty-input-linux-setup.sh status
/opt/ghosty-input/ghosty-input-linux-setup.sh remove
```

## Persistent camera routing

Linux can reorder `/dev/video0`, `/dev/video1`, and other V4L device numbers after reboot or USB reconnect. Ghosty Input v0.5 stores `/dev/v4l/by-id/...` when the camera exposes a persistent device alias and resolves the current numeric index at runtime.

This means a saved **Desk Camera** should continue to be selected even if the kernel assigns it a different `/dev/videoN` number later.

When no `by-id` alias exists, Ghosty Input falls back to `by-path`, then finally to the numeric V4L node.

## Camera reconnect

If a camera stops returning frames, the runtime releases the failed V4L handle and retries opening the camera. When a persistent camera ID is available, the current `/dev/videoN` assignment is resolved again during reconnect.

A reconnect is intentionally rate-limited so a disconnected camera does not produce a tight reopen loop.

## Desk camera focus

The front camera and dedicated desk camera have separate autofocus controls. A fixed top-down desk camera often produces more stable fingertip geometry with autofocus disabled after the keyboard plane is in focus.

## Desktop launcher and autostart

The Linux Control Center can install/remove a per-user application launcher and enable/disable desktop-session autostart without root.

The same operations are available from the CLI:

```bash
./GhostyInput --install-desktop
./GhostyInput --remove-desktop
./GhostyInput --enable-autostart
./GhostyInput --disable-autostart
```

Autostart launches the application minimized. If a system tray is available, Ghosty Input stays there until opened or quit. **Keep running when window closes** is optional and disabled by default.

## X11 fallback

Auto mode prefers `uinput` when it is usable. If native input is unavailable, Ghosty Input can fall back to PyAutoGUI on X11/XWayland. The active backend is shown in the Control Center.

## Diagnostics

Run:

```bash
ghosty-input --diagnose
```

The report includes:

- Linux distribution and kernel;
- Wayland/X11 session;
- desktop environment;
- `/dev/uinput` availability and permissions;
- recommended input backend;
- application launcher and autostart state;
- V4L cameras, access state, and persistent aliases.

## Hardware acceptance sequence

1. Run `--diagnose` and fix any `uinput` or camera permission warning.
2. Start with the front camera only and verify pointer movement.
3. Test Pinch and Hover Dwell separately.
4. Connect the desk camera, select it by name, save settings, reboot, and verify that the same physical camera remains selected.
5. Disconnect and reconnect the USB camera while Ghosty Input is running and verify automatic recovery.
6. Calibrate the desk plane and verify projected keys follow the physical surface.
7. Type a 200-character sample and record wrong keys, duplicates, and missed presses.
8. Test a 30-minute session for camera stalls, input lockups, and memory growth.

## Packaging compatibility

The x86_64 portable and `.deb` builds are produced on Ubuntu 22.04 to reduce glibc compatibility issues on newer distributions. Debian-family distributions receive the best installation experience from the `.deb` package. Fedora/openSUSE/Arch should use the portable archive for now.

Real hardware testing is still required before marking a particular distribution/compositor/camera combination as certified.

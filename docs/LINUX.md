# Ghosty Input on Linux — Alpha 1

Ghosty Input `0.6.0a1` is the first Linux Alpha intended for real-machine testing. Linux is treated as a first-class target with native `uinput`, V4L2 camera diagnostics, persistent camera routing, preflight checks, and both portable and Debian packages.

## Recommended installation

### Debian / Ubuntu / Linux Mint / Pop!_OS

```bash
sudo apt install ./ghosty-input_0.6.0a1_amd64.deb
ghosty-input --preflight
ghosty-input --diagnose
ghosty-input --camera-diagnose
ghosty-input
```

The application is installed under `/opt/ghosty-input` and a desktop launcher is registered system-wide.

### Portable build

```bash
tar -xzf GhostyInput-Linux-x86_64-v0.6.0a1.tar.gz
cd GhostyInput
./GhostyInput --preflight
./GhostyInput --diagnose
./GhostyInput --camera-diagnose
./run-ghosty.sh
```

The portable build does not require Python to be installed.

## Alpha preflight

Before starting the engine, Ghosty Input evaluates the current machine and saved settings:

```bash
ghosty-input --preflight
```

The report uses `PASS`, `WARN`, and `FAIL` items and ends as:

- `ALPHA READY` — required checks passed;
- `ALPHA READY WITH WARNINGS` — safe to test, but optional setup such as desk-keyboard calibration needs attention;
- `ALPHA BLOCKED` — fix every `FAIL` before starting the engine.

To require a real camera frame during the CLI check:

```bash
ghosty-input --preflight --preflight-probe-camera
```

The Linux Control Center exposes the same readiness information in the **Alpha** tab. Engine startup is blocked when required camera or input checks fail.

## Single-instance protection

Only one desktop Ghosty Input instance should run at a time. Alpha 1 uses a process lock to reject a second instance before it can compete for a V4L2 camera or `/dev/uinput`.

## Config recovery and logs

If `config.json` becomes invalid, Alpha 1 moves it to a timestamped `config.invalid-*.json` backup and starts from safe defaults instead of silently losing the broken file.

The persistent runtime log path is available with:

```bash
ghosty-input --log-path
```

The rotating log is intended for startup, shutdown, backend/device failures, and crash tracebacks. Ghosty Input does not write camera frames or typed content to the persistent log.

## Camera Doctor

```bash
ghosty-input --camera-diagnose
```

Camera Doctor reports every visible `/dev/videoN` node, whether the kernel marks it as a real video-capture node, access state, V4L2 driver and bus information, and a real OpenCV frame-capture test for selectable cameras.

Typical outcomes:

- `capture · rw` plus `stream: OK` means Ghosty can read the camera.
- `non-capture` means the node is metadata/output-only and is intentionally hidden from the selector.
- `denied` means the device exists but the current desktop user cannot access it.
- `stream: FAILED` means the node is a capture device but Ghosty could not obtain a frame; close other camera applications and inspect the reported backend/mode.
- no `/dev/video*` nodes means the camera is not exposed as V4L2 to Ghosty. A PipeWire/libcamera-only device still needs a future capture backend.

Ghosty reads `VIDIOC_QUERYCAP` directly, so `v4l2-ctl` is not required merely to distinguish capture nodes from metadata nodes.

## Adaptive camera opening

Linux cameras do not all accept the same format/resolution combination. Ghosty verifies a real frame during startup and negotiates progressively:

1. requested resolution;
2. 1280×720;
3. 640×480;
4. MJPG and default pixel format;
5. V4L2 backend, then OpenCV auto backend.

The Control Center shows the actual negotiated resolution and backend instead of assuming the requested mode succeeded.

## Wayland and native input

For reliable global mouse and keyboard injection on Wayland, use the native Linux `uinput` backend. Run the bundled helper as your normal desktop user:

```bash
/opt/ghosty-input/ghosty-input-linux-setup.sh install
```

For the portable build:

```bash
./ghosty-input-linux-setup.sh install
```

The helper:

- loads the `uinput` kernel module;
- configures it to load on boot;
- creates a dedicated `ghosty-input` group;
- grants that group access only to `/dev/uinput`;
- does not run Ghosty Input itself as root.

Sign out and back in, or reboot, then verify:

```bash
ghosty-input --preflight
ghosty-input --diagnose
```

A Wayland session without writable `/dev/uinput` is an Alpha startup blocker.

Check or remove the system configuration later with:

```bash
/opt/ghosty-input/ghosty-input-linux-setup.sh status
/opt/ghosty-input/ghosty-input-linux-setup.sh remove
```

## Persistent camera routing

Linux can reorder `/dev/video0`, `/dev/video1`, and other V4L nodes after reboot or USB reconnect. Ghosty stores `/dev/v4l/by-id/...` when the camera exposes a persistent alias and resolves the current numeric index at runtime.

When no `by-id` alias exists, Ghosty falls back to `by-path`, then finally to the numeric V4L node.

In dual-camera mode, Alpha preflight rejects front and desk selections that resolve to the same physical device.

## Camera reconnect

If a camera stops returning frames, the runtime releases the failed V4L handle and retries. With a persistent ID, the current `/dev/videoN` assignment is resolved again during reconnect.

Camera errors remain reconnectable. Repeated non-camera internal runtime errors are bounded so the Alpha does not enter an endless error loop.

## Desk camera focus

The front camera and dedicated desk camera have separate autofocus controls. A fixed top-down desk camera often produces more stable fingertip geometry with autofocus disabled after the keyboard plane is in focus.

## Desktop launcher and autostart

The Linux Control Center can install/remove a per-user application launcher and enable/disable desktop-session autostart without root.

CLI equivalents:

```bash
./GhostyInput --install-desktop
./GhostyInput --remove-desktop
./GhostyInput --enable-autostart
./GhostyInput --disable-autostart
```

Autostart launches the application minimized. If a system tray is available, Ghosty Input stays there until opened or quit. **Keep running when window closes** remains optional and disabled by default.

## X11 / XWayland packaging

The Debian package declares the common Qt/X11/XCB runtime dependencies used by the packaged desktop UI. CI also runs `ldd` against the packaged Qt `libqxcb.so` and rejects unresolved shared libraries before the artifact is published.

## Diagnostics

```bash
ghosty-input --diagnose
ghosty-input --camera-diagnose
ghosty-input --log-path
```

The normal report includes distribution/kernel, Wayland/X11 session, desktop environment, `/dev/uinput` status, recommended input backend, OpenCV backends, V4L node counts, desktop integration state, camera access/driver/bus data, and persistent aliases.

## Alpha hardware acceptance

Use `README-ALPHA.md` shipped with the package for the full checklist. The minimum sequence is:

1. run `--preflight` and fix every `FAIL`;
2. confirm a second app instance is rejected;
3. test front-camera preview and pointer input;
4. disconnect/reconnect the USB camera and confirm recovery;
5. test 50 left clicks, 20 right clicks, and 20 drags;
6. calibrate the desk plane and target quality 70/100 or higher;
7. type a known 200-character sample;
8. run a 30-minute soak and restart the engine at least three times;
9. close the application while the engine is active and confirm clean shutdown/no stuck drag.

## Packaging compatibility

The x86_64 portable and `.deb` builds are produced on Ubuntu 22.04 to reduce glibc compatibility issues on newer distributions. Debian-family distributions receive the best install experience from the `.deb`; Fedora/openSUSE/Arch should use the portable archive for Alpha testing.

Real hardware testing is still required before marking any distribution/compositor/camera combination as certified.

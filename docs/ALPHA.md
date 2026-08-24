# Ghosty Input 0.6.0a1 — Alpha 1

This build is intended for real-machine testing. It is not a production certification.

The application reports version `0.6.0a1`. The Debian package internally uses `0.6.0~a1` so Debian correctly sorts the Alpha before the future stable `0.6.0` package.

## Before starting the engine

Run the lightweight readiness check:

```bash
ghosty-input --preflight
```

On Linux, a healthy Wayland setup should show a selectable front camera and writable `/dev/uinput`. Warnings about desk-keyboard calibration do not block mouse testing.

For a real camera stream probe:

```bash
ghosty-input --preflight --preflight-probe-camera
```

For detailed V4L2 information:

```bash
ghosty-input --camera-diagnose
```

The persistent runtime log path is available with:

```bash
ghosty-input --log-path
```

Ghosty Input does not write camera frames or typed text to the runtime log.

## Verified updates

Packaged Alpha builds can check the official GitHub Releases channel:

```bash
ghosty-input --check-update
ghosty-input --update
```

Startup update checks are enabled by default. Alpha builds on the `auto` channel accept newer Alpha builds and future stable releases. Ghosty asks before downloading/installing and verifies the release package with SHA-256 first.

Update installation supports:

- Linux `.deb` through a PolicyKit privilege prompt;
- Linux portable packages through a verified self-replacement helper with rollback during the swap;
- Windows through the verified Inno Setup installer.

See `docs/UPDATES.md` for the trust model and publishing flow.

## Alpha acceptance sequence

1. Launch Ghosty Input once. Launch it a second time and confirm the second instance is rejected.
2. Check the **Alpha** tab. Fix every `FAIL` before starting the engine.
3. Start with only the front camera enabled.
4. Confirm the preview is live and the displayed resolution/FPS are plausible.
5. Move the pointer for five minutes and test 50 left clicks, 20 right clicks, and 20 drags.
6. Pause/resume with the fist gesture 10 times and confirm no mouse button remains held.
7. Disconnect the front USB camera while the engine is running, reconnect it, and verify automatic recovery.
8. If using a desk camera, enable dual-camera mode and confirm the preflight rejects selecting the same physical device twice.
9. Calibrate the desk plane. A quality score of 70/100 or higher is the target.
10. Type a known 200-character sample and record wrong, missing, or duplicated characters.
11. Run continuously for 30 minutes. Stop and restart the engine at least three times.
12. Close the application while the engine is active and confirm it does not crash or leave a stuck drag state.
13. After a newer Alpha release exists, run `--check-update`, confirm the correct package is selected, complete one update, and confirm the application restarts on the new version.

## What to report

When reporting an Alpha issue, include:

- Linux distribution and desktop environment;
- Wayland or X11;
- camera model;
- output of `ghosty-input --diagnose`;
- output of `ghosty-input --camera-diagnose` for camera failures;
- the last relevant section of the persistent runtime log;
- exact steps that reproduce the problem.

Do not attach private camera frames or typed content unless you intentionally choose to share them.

## Current Alpha limits

- Linux camera capture is V4L2/OpenCV-first. Native PipeWire/libcamera capture is not yet a fallback backend.
- Linux packages are x86_64 only.
- Debian-family systems receive the `.deb`; other distributions should use the portable archive.
- Multi-compositor and broad webcam certification still requires real hardware results.

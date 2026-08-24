# Ghosty Input Alpha Reliability Report

This document is the acceptance report for the Alpha reliability/productization pass. It deliberately separates automated evidence from hardware claims. GitHub-hosted CI has no representative webcam, compositor, desk geometry, or user hand, so real-camera latency and accuracy numbers must be recorded on target hardware rather than invented from CI.

## Reliability controls implemented

### Desktop input

- Session detection uses `XDG_SESSION_TYPE`, then Wayland/X11 display variables as fallback.
- Linux Wayland is fail-closed: automatic selection stays on native `uinput`, and explicit/automatic PyAutoGUI downgrade is rejected in the runtime backend layer.
- X11 may use PyAutoGUI when native `uinput` is unavailable.
- Alpha preflight independently blocks Wayland startup without writable `/dev/uinput`.

### Camera

- Linux V4L2 discovery includes direct `/dev/video*`, sysfs names, persistent `/dev/v4l/by-id`/`by-path`, and `VIDIOC_QUERYCAP` filtering.
- Runtime camera open negotiates requested mode with 720p/480p fallbacks, backend fallback, and a real-frame prime.
- Frame loss releases the capture handle and retries the persistent camera identity after a bounded reconnect interval.
- `ghosty-input --camera-modes` independently opens common modes and reports requested vs actual resolution/FPS/backend.
- Runtime instrumentation records measured FPS, capture-read latency EMA/max, estimated timing drops, camera errors, and successful reconnects without retaining frames.

### Calibration and gesture quality

- Four-corner desk calibration validates area and convex geometry.
- Independent center hold-out validation measures real homography reprojection error instead of evaluating the four points used to fit the transform.
- Validated calibration quality blends geometry and hold-out error.
- Adaptive pinch calibration collects short open-hand and pinched samples in memory, derives per-user engage/release hysteresis thresholds, persists only those derived thresholds, and clears raw samples.
- Pointer QA covers One Euro smoothing, deadzone behavior, pinch hysteresis, and false-click resistance around the threshold.

### Recovery, packaging, updates, and privacy

- Runtime camera recovery does not require an application restart when the device returns.
- Linux and Windows package workflows build installable/portable artifacts and run package smoke gates.
- Packaged updates use the official repository release feed, compatible release assets, SHA-256 verification, and platform-specific staged install/rollback behavior.
- The camera soak harness explicitly drops each frame reference and never writes frame contents.
- Persisted config contains calibration geometry and derived thresholds only; no camera frames, raw gesture samples, or typed-content buffer is part of the persistence schema.

## Automated QA gate

The Alpha automated gate must include all existing tests plus these reliability regressions:

- Wayland auto-selection remains on `uinput` even when permissions are missing.
- Explicit PyAutoGUI is rejected on Wayland but remains allowed on X11.
- Calibration hold-out error detects a deliberately shifted validation point.
- Adaptive pinch calibration derives separated hysteresis thresholds and rejects overlapping samples.
- Timing gaps increment estimated dropped frames and recovery increments reconnect count.
- Stationary synthetic jitter is reduced by the pointer filter.
- Threshold jitter produces one click edge, not repeated false clicks.
- A 5,000-frame synthetic camera soak completes without creating payload files.
- Persisted config is checked for absence of frame/typed-data/raw-gesture payload fields.

## Performance and latency instrumentation

### Real camera mode matrix

Run with the engine stopped:

```bash
ghosty-input --camera-modes
```

Record every `PASS`, `WARN`, and `FAIL`. A `WARN` means the backend opened a real frame but negotiated a different resolution/FPS than requested.

### Camera-only soak

A short diagnostic run:

```bash
ghosty-input --camera-soak 120
```

Release acceptance run:

```bash
ghosty-input --camera-soak 1800
```

The report records:

- elapsed duration and successful frames;
- measured camera-only FPS;
- capture-read EMA and maximum latency;
- estimated dropped frames;
- camera read errors and recovered reconnects;
- process CPU as a percentage of one logical core;
- RSS start/end/peak/growth;
- explicit privacy statement that frames were discarded in memory.

### Alpha goals, not CI claims

Use these as investigation thresholds on target hardware:

- 720p target: at least 24 measured runtime FPS under normal hand tracking.
- 1080p precision target: 24-30 measured runtime FPS where the camera/backend supports it.
- Capture-read EMA should normally stay below one frame interval for the selected mode.
- Engine tick latency should not show sustained growth over a 30-minute run.
- RSS must not show monotonic unbounded growth. Investigate growth greater than 50 MiB over a stable 30-minute camera-only run.
- A temporary RSS increase during backend/model warm-up is acceptable if it plateaus.

Do not promote these goals to certified numbers until results are recorded for the target hardware matrix.

## Manual camera and hardware acceptance checklist

### Required platform coverage

- Windows 11 with an integrated laptop webcam.
- Windows 11 with a USB UVC 1080p webcam.
- KDE Plasma Wayland on a current Linux distribution.
- GNOME Wayland on a current Linux distribution.
- At least one X11 session to verify the fallback path.
- One dual-camera setup with two distinct physical UVC devices.
- One multi-monitor setup, including fractional scaling if available.

### Camera and reconnect

- Run `--camera-diagnose` and `--camera-modes` with the engine stopped.
- Confirm the UI reports actual rather than requested resolution/FPS.
- Disconnect the active USB camera while running, keep it disconnected for at least five seconds, reconnect it, and confirm recovery without restarting Ghosty Input.
- On Linux, reconnect in a way that changes `/dev/videoN` where possible and confirm persistent by-id/by-path routing returns to the same physical camera.
- Repeat stop/start at least ten times and confirm the camera is released every time.

### Pointer and false-click QA

- Hold the index finger stationary at center and four screen quadrants for 30 seconds each; record visible jitter.
- Perform 100 intentional left clicks and count misses, duplicates, and unintended clicks.
- Perform 50 right clicks and 50 drags; confirm no stuck mouse-down state.
- Move near the pinch threshold without intending to click for one minute; record false clicks.
- Pause/resume ten times and verify pointer state resets cleanly.

### Adaptive gesture calibration

- Calibrate one user at normal camera distance.
- Record derived engage/release ratios.
- Restart the engine and repeat the 100-click test.
- Repeat with a second user or materially different hand-to-camera distance to confirm the profile changes without saving raw samples.

### Desk calibration and keyboard

- Calibrate four corners, then validate the physical center point.
- Target center hold-out reprojection error: <= 4% of normalized keyboard plane.
- 4-8% is a warning; recalibrate before precision scoring.
- > 8% is a failed precision setup and should not be used for keyboard acceptance.
- Type a known 200-character sample containing all letter rows, spaces, backspace, shift, and enter.
- Target at least 97% raw key-selection accuracy with no duplicated character caused by a held pinch.

### Long-running stability

- Run `ghosty-input --camera-soak 1800` and save the numeric report.
- Run the full Control Center for at least 30 minutes with tracking enabled.
- Perform at least three engine stop/restart cycles after the soak.
- Check CPU, RSS, camera error/reconnect counters, and runtime responsiveness.
- Close while active and confirm no stuck drag, orphan worker, or camera handle.

### Update cycle

After a newer Alpha release exists:

- run `ghosty-input --check-update`;
- verify the selected asset belongs to the official repository release;
- complete one verified Alpha-to-newer-Alpha update;
- verify version after restart;
- on portable Linux, exercise rollback by intentionally failing package validation in a controlled test build, not by corrupting a production install.

## Release decision

A green CI + Linux package + Windows package run means the source and distribution gates are ready for real-machine Alpha testing. It does **not** certify webcam models, compositor behavior, pointer accuracy, keyboard accuracy, latency, or leak-free long-running behavior until the manual matrix above is completed and its measured results are recorded.

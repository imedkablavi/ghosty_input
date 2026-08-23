# Privacy

Ghosty Input is designed to keep vision and input processing local.

- Camera frames are processed in memory.
- The application does not upload frames, hand landmarks, typed keys, mouse activity, calibration points, or application settings.
- No analytics, telemetry, remote logging, advertising SDK, or cloud inference API is included.
- Settings, calibration data, logs, and updater state are stored locally in the user's application-data directory.

## Update checks

Packaged builds can contact the official `imedkablavi/ghosty_input` GitHub Releases API to check for a newer version. Automatic checks are rate-limited to at most one attempt every six hours and can be disabled with the local `auto_check_updates` setting.

When the user accepts an update, Ghosty Input downloads the selected package and its SHA-256 manifest from that repository's GitHub Release assets. Camera frames, gestures, typed content, and local configuration are not included in update requests.

Ghosty Input continues to work without an internet connection. Failure to reach the update service does not block the local camera/input runtime.

Third-party Python packages are downloaded separately when installing the project from source with `pip`.

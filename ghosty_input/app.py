from __future__ import annotations

import argparse
import platform
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ghosty-input",
        description="Offline hand-gesture mouse and desk-keyboard controller.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="print the application version and exit",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="print camera, desktop-session, and input-backend diagnostics and exit",
    )
    parser.add_argument(
        "--camera-diagnose",
        action="store_true",
        help="probe Linux V4L2 camera capabilities and attempt a real frame capture",
    )
    parser.add_argument(
        "--camera-modes",
        action="store_true",
        help="probe common resolution/FPS modes on the saved front camera",
    )
    parser.add_argument(
        "--camera-soak",
        type=float,
        metavar="SECONDS",
        help="run a camera-only CPU/RAM/drop/latency soak test without input injection",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="check whether the saved configuration is ready for alpha runtime testing",
    )
    parser.add_argument(
        "--preflight-probe-camera",
        action="store_true",
        help="with --preflight, also open the selected camera and require a real frame",
    )
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="check GitHub Releases for a newer compatible Ghosty Input build",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="download, verify, and launch the newest compatible update",
    )
    parser.add_argument(
        "--update-channel",
        choices=("auto", "stable", "alpha"),
        help="override the saved update channel for --check-update or --update",
    )
    parser.add_argument(
        "--set-update-channel",
        choices=("auto", "stable", "alpha"),
        help="save the automatic update channel and exit",
    )
    update_checks = parser.add_mutually_exclusive_group()
    update_checks.add_argument(
        "--enable-auto-update-check",
        action="store_true",
        help="enable packaged-build startup update checks and exit",
    )
    update_checks.add_argument(
        "--disable-auto-update-check",
        action="store_true",
        help="disable packaged-build startup update checks and exit",
    )
    parser.add_argument(
        "--log-path",
        action="store_true",
        help="print the persistent alpha runtime log path and exit",
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="start the Linux Control Center minimized to the system tray when available",
    )
    parser.add_argument(
        "--ui-smoke-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--package-smoke-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    desktop = parser.add_mutually_exclusive_group()
    desktop.add_argument(
        "--install-desktop",
        action="store_true",
        help="install a per-user Linux application-menu entry",
    )
    desktop.add_argument(
        "--remove-desktop",
        action="store_true",
        help="remove a per-user Linux application-menu entry",
    )
    autostart = parser.add_mutually_exclusive_group()
    autostart.add_argument(
        "--enable-autostart",
        action="store_true",
        help="start Ghosty Input with the Linux desktop session",
    )
    autostart.add_argument(
        "--disable-autostart",
        action="store_true",
        help="disable Linux desktop-session autostart",
    )
    return parser


def _handle_linux_desktop_actions(args: argparse.Namespace) -> bool:
    if not any(
        (
            args.install_desktop,
            args.remove_desktop,
            args.enable_autostart,
            args.disable_autostart,
        )
    ):
        return False
    if platform.system() != "Linux":
        raise RuntimeError("Desktop integration commands are available only on Linux.")

    from ghosty_input.core.linux_desktop import (
        install_desktop_entry,
        remove_desktop_entry,
        set_autostart,
    )

    if args.install_desktop:
        path = install_desktop_entry()
        print(f"Desktop entry installed: {path}")
    elif args.remove_desktop:
        remove_desktop_entry()
        print("Desktop entry removed.")
    elif args.enable_autostart:
        path = set_autostart(True)
        print(f"Autostart enabled: {path}")
    elif args.disable_autostart:
        set_autostart(False)
        print("Autostart disabled.")
    return True


def _run_linux_ui_smoke_test() -> int:
    import os
    from pathlib import Path
    from tempfile import TemporaryDirectory

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    import ghosty_input.ui.instance_lock as instance_lock
    from ghosty_input.config import AppConfig
    from ghosty_input.ui.onboarding import FirstRunWizard
    from ghosty_input.ui.product_window import ProductLinuxWindow

    app = QApplication.instance() or QApplication([])
    with TemporaryDirectory(prefix="ghosty-alpha-smoke-") as temp:
        data_dir = Path(temp) / "GhostyInput"
        original_data_dir = instance_lock.app_data_dir
        instance_lock.app_data_dir = lambda: data_dir
        first = None
        try:
            first, first_error = instance_lock.acquire_instance_lock()
            if first is None:
                raise RuntimeError(f"instance lock smoke failed: {first_error}")
            second, second_error = instance_lock.acquire_instance_lock()
            if second is not None:
                second.unlock()
                raise RuntimeError("instance lock smoke failed: duplicate lock was acquired")
            if "already running" not in second_error.lower():
                raise RuntimeError(f"unexpected duplicate-instance message: {second_error}")
        finally:
            if first is not None:
                first.unlock()
            instance_lock.app_data_dir = original_data_dir

    wizard = FirstRunWizard(AppConfig())
    if wizard.camera.count() < 1:
        raise RuntimeError("first-run wizard did not render a camera choice")
    wizard.close()

    window = ProductLinuxWindow()
    window.config.linux_close_to_tray = False
    if not hasattr(window, "capture_metric") or not hasattr(window, "gesture_button"):
        raise RuntimeError("product reliability controls were not constructed")
    window.close()
    app.processEvents()
    print("Linux product UI + onboarding + instance lock smoke test: ok")
    return 0


def _run_package_smoke_test() -> int:
    """Validate the actual packaged product UI using only its process exit code."""

    import os

    from ghosty_input import __version__
    from ghosty_input.config import AppConfig
    from ghosty_input.core.update_manager import _normalize_tag, installation_kind

    expected = os.environ.get("GHOSTY_EXPECTED_VERSION", "").strip()
    if expected and __version__ != expected:
        return 3
    if _normalize_tag("v0.6.0-alpha.2") != "0.6.0a2":
        return 4
    if installation_kind() == "unsupported":
        return 5

    AppConfig().validate()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from ghosty_input.ui.onboarding import FirstRunWizard
    from ghosty_input.ui.startup_update import maybe_run_startup_update

    if not callable(maybe_run_startup_update):
        return 6

    app = QApplication.instance() or QApplication([])

    # Exercise first-run construction without executing the modal dialog. Device
    # enumeration is allowed here, but the wizard deliberately never opens a
    # camera stream.
    wizard = FirstRunWizard(AppConfig())
    if wizard.camera.count() < 1:
        wizard.close()
        return 7
    wizard.close()

    if platform.system() == "Linux":
        from ghosty_input.ui.product_window import ProductLinuxWindow

        window = ProductLinuxWindow()
        window.config.linux_close_to_tray = False
    else:
        from ghosty_input.ui.product_window import ProductMainWindow

        window = ProductMainWindow()

    if not hasattr(window, "capture_metric") or not hasattr(window, "gesture_button"):
        window.close()
        return 8
    window.close()
    app.processEvents()
    return 0


def _handle_update_preferences(args: argparse.Namespace) -> bool:
    if not any(
        (
            args.set_update_channel,
            args.enable_auto_update_check,
            args.disable_auto_update_check,
        )
    ):
        return False

    from ghosty_input.config import load_config, save_config

    config = load_config()
    if args.set_update_channel:
        config.update_channel = args.set_update_channel
    if args.enable_auto_update_check:
        config.auto_check_updates = True
    elif args.disable_auto_update_check:
        config.auto_check_updates = False
    save_config(config)
    state = "enabled" if config.auto_check_updates else "disabled"
    print(f"Automatic update checks: {state} · channel={config.update_channel}")
    return True


def _handle_update_command(args: argparse.Namespace) -> int | None:
    if not args.check_update and not args.update:
        return None

    from ghosty_input.config import load_config
    from ghosty_input.core.update_manager import (
        check_for_update,
        download_verified_update,
        launch_installer,
        updater_environment,
    )

    config = load_config()
    channel = args.update_channel or config.update_channel
    info = check_for_update(channel=channel)
    if info is None:
        print(f"Ghosty Input is up to date · channel={channel} · {updater_environment()}")
        return 0

    print(
        f"Update available: {info.current_version} -> {info.version} · "
        f"{info.asset.name} · channel={channel}"
    )
    if not args.update:
        return 0

    package = download_verified_update(info)
    print(f"Verified update: {package}")
    launch_installer(package, version=info.version)
    print("Update installer launched. Ghosty Input will exit now.")
    return 0


def _schedule_automatic_update_check() -> None:
    """Schedule updater work after the control center enters its event loop."""

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from ghosty_input.config import load_config
    from ghosty_input.ui.startup_update import maybe_run_startup_update

    app = QApplication.instance() or QApplication([])
    config = load_config()
    # Do not let a startup network check interrupt the first-run local setup
    # wizard. Automatic checks resume normally from the next launch.
    if not config.onboarding_complete:
        return

    def run_check() -> None:
        if maybe_run_startup_update(config):
            app.quit()

    QTimer.singleShot(1200, run_check)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        from ghosty_input import __version__

        print(__version__)
        return 0

    from ghosty_input.core.logging_setup import configure_logging, get_logger, log_path

    configure_logging()
    logger = get_logger("app")

    if args.package_smoke_test:
        return _run_package_smoke_test()

    if args.log_path:
        print(log_path())
        return 0

    if args.diagnose:
        from ghosty_input.core.system_info import diagnostic_report

        print(diagnostic_report())
        return 0

    if args.camera_diagnose:
        from ghosty_input.core.camera import camera_diagnostic_report

        print(camera_diagnostic_report(probe_streams=True))
        return 0

    if args.camera_modes:
        from ghosty_input.config import load_config
        from ghosty_input.core.camera_modes import camera_mode_report

        config = load_config()
        print(camera_mode_report(config.front_camera))
        return 0

    if args.camera_soak is not None:
        if args.camera_soak <= 0:
            print("--camera-soak must be greater than zero seconds", file=sys.stderr)
            return 2
        from ghosty_input.config import load_config
        from ghosty_input.core.performance import camera_soak_report

        try:
            print(camera_soak_report(load_config(), args.camera_soak))
            return 0
        except Exception as exc:
            print(f"Camera soak failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2

    if args.preflight:
        from ghosty_input.config import load_config_state
        from ghosty_input.core.preflight import run_preflight

        state = load_config_state()
        report = run_preflight(
            state.config,
            probe_streams=args.preflight_probe_camera,
        )
        if state.recovered:
            backup = str(state.backup_path) if state.backup_path else "backup unavailable"
            print(f"Config recovery: invalid config quarantined ({backup})")
        print(report.render())
        return 0 if report.ready else 2

    try:
        if _handle_update_preferences(args):
            return 0

        update_result = _handle_update_command(args)
        if update_result is not None:
            return update_result

        if _handle_linux_desktop_actions(args):
            return 0

        if args.ui_smoke_test:
            if platform.system() != "Linux":
                return 0
            return _run_linux_ui_smoke_test()

        _schedule_automatic_update_check()

        if platform.system() == "Linux":
            from ghosty_input.ui.product_window import run_product_linux_ui

            return run_product_linux_ui(start_minimized=args.minimized)

        from ghosty_input.ui.product_window import run_product_ui

        return run_product_ui()
    except KeyboardInterrupt:
        logger.info("application interrupted by user")
        return 130
    except Exception as exc:
        logger.exception("application failed to start")
        print(f"Ghosty Input failed to start: {exc}", file=sys.stderr)
        print(f"Runtime log: {log_path()}", file=sys.stderr)
        return 1

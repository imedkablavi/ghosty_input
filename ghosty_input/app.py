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
        help="remove the per-user Linux application-menu entry",
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
    from ghosty_input.ui.linux_window import LinuxWindow

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

    window = LinuxWindow()
    window.config.linux_close_to_tray = False
    window.close()
    app.processEvents()
    print("Linux UI + instance lock smoke test: ok")
    return 0


def _run_package_smoke_test() -> int:
    """Validate a frozen GUI executable using only its process exit code.

    Windows ``--windowed`` PyInstaller executables do not have a console stdout,
    so distribution CI cannot reliably validate them by capturing ``--version``.
    The optional expected version is supplied by the build environment and a
    small offscreen Qt construction verifies that the packaged GUI imports.
    """

    import os

    from ghosty_input import __version__
    from ghosty_input.config import AppConfig

    expected = os.environ.get("GHOSTY_EXPECTED_VERSION", "").strip()
    if expected and __version__ != expected:
        return 3

    AppConfig().validate()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    if platform.system() == "Linux":
        from ghosty_input.ui.linux_window import LinuxWindow

        window = LinuxWindow()
        window.config.linux_close_to_tray = False
    else:
        from ghosty_input.ui.main_window import MainWindow

        window = MainWindow()
    window.close()
    app.processEvents()
    return 0


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
        if _handle_linux_desktop_actions(args):
            return 0

        if args.ui_smoke_test:
            if platform.system() != "Linux":
                return 0
            return _run_linux_ui_smoke_test()

        if platform.system() == "Linux":
            from ghosty_input.ui.linux_window import run_linux_ui

            return run_linux_ui(start_minimized=args.minimized)

        from ghosty_input.ui.main_window import run_ui

        return run_ui()
    except KeyboardInterrupt:
        logger.info("application interrupted by user")
        return 130
    except Exception as exc:
        logger.exception("application failed to start")
        print(f"Ghosty Input failed to start: {exc}", file=sys.stderr)
        print(f"Runtime log: {log_path()}", file=sys.stderr)
        return 1

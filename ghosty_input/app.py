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
        "--minimized",
        action="store_true",
        help="start the Linux Control Center minimized to the system tray when available",
    )
    parser.add_argument(
        "--ui-smoke-test",
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        from ghosty_input import __version__

        print(__version__)
        return 0

    if args.diagnose:
        from ghosty_input.core.system_info import diagnostic_report

        print(diagnostic_report())
        return 0

    if args.camera_diagnose:
        from ghosty_input.core.camera import camera_diagnostic_report

        print(camera_diagnostic_report(probe_streams=True))
        return 0

    try:
        if _handle_linux_desktop_actions(args):
            return 0

        if args.ui_smoke_test:
            if platform.system() != "Linux":
                return 0
            import os

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            from PySide6.QtWidgets import QApplication

            from ghosty_input.ui.linux_window import LinuxWindow

            app = QApplication.instance() or QApplication([])
            window = LinuxWindow()
            window.config.linux_close_to_tray = False
            window.close()
            app.processEvents()
            print("Linux UI smoke test: ok")
            return 0

        if platform.system() == "Linux":
            from ghosty_input.ui.linux_window import run_linux_ui

            return run_linux_ui(start_minimized=args.minimized)

        from ghosty_input.ui.main_window import run_ui

        return run_ui()
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Ghosty Input failed to start: {exc}", file=sys.stderr)
        return 1

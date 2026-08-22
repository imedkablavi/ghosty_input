from __future__ import annotations

import argparse
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        from ghosty_input import __version__

        print(__version__)
        return 0

    try:
        from ghosty_input.ui.main_window import run_ui

        return run_ui()
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Ghosty Input failed to start: {exc}", file=sys.stderr)
        return 1

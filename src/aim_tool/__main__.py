"""Command-line entry point for the desktop application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from aim_tool import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aim-tool")
    parser.add_argument("--gps-only", action="store_true", help="Open the standalone GPS preview")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--self-test", action="store_true", help="Run an offline GPS GUI smoke test"
    )
    parser.add_argument(
        "--self-test-jpg", action="store_true", help="Run an offline full JPG GUI smoke test"
    )
    parser.add_argument("--report", type=Path, help="Write the self-test result as JSON")
    args = parser.parse_args(argv)
    if args.self_test_jpg:
        if args.report is None or args.self_test or args.gps_only:
            parser.error("--self-test-jpg requires --report and the full JPG edition")
        from aim_tool.self_test_jpg import run_self_test as run_jpg_self_test

        return run_jpg_self_test(args.report)
    if args.self_test:
        if args.report is None:
            parser.error("--self-test requires --report")
        from aim_tool.self_test import run_self_test

        return run_self_test(args.report)
    if args.report is not None:
        parser.error("--report requires --self-test or --self-test-jpg")

    from aim_tool.app import run_gui

    return run_gui(gps_only=args.gps_only)


if __name__ == "__main__":
    raise SystemExit(main())

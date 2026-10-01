"""Command-line entry point for the desktop application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from aim_tool import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aim-tool")
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args(argv)

    from aim_tool.app import run_gui

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())

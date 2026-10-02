"""Retain the GPS-only launcher while the default app develops JPG watermarks."""

import sys

from aim_tool.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["--gps-only", *sys.argv[1:]]))

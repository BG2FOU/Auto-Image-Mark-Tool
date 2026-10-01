"""Shared pytest options for required external acceptance assets."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-real-assets",
        action="store_true",
        help="fail rather than skip tests that require real photos",
    )
    parser.addoption(
        "--require-visual-assets",
        action="store_true",
        help="fail rather than skip tests that require approved visual baselines",
    )

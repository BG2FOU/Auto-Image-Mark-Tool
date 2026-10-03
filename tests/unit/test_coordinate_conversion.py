"""Pinned upstream examples, inverse residuals and strict batch interpretation."""

import pytest

from aim_tool.services.coordinate_conversion import (
    CoordinateRow,
    convert_row,
    coordinate_csv,
    gcj02_to_wgs84,
    parse_coordinate_rows,
    wgs84_to_gcj02,
)


# Public test vectors from eviltransform/python/test.py at 03ba58d92dfd.
@pytest.mark.parametrize(
    "wgs,gcj",
    (
        ((31.1774276, 121.5272106), (31.17530398364597, 121.531541859215)),
        ((22.543847, 113.912316), (22.540796131694766, 113.9171764808363)),
        ((39.911954, 116.377817), (39.91334545536069, 116.38404722455657)),
    ),
)
def test_published_vectors_and_inverse(wgs, gcj) -> None:
    assert wgs84_to_gcj02(*wgs) == pytest.approx(gcj, abs=1e-6)
    recovered = gcj02_to_wgs84(*gcj)
    assert recovered == pytest.approx(wgs, abs=2e-7)
    assert wgs84_to_gcj02(*recovered) == pytest.approx(gcj, abs=1e-8)


@pytest.mark.parametrize("point", ((48.85, 2.35), (0, 0), (-45, 170), (90, 180)))
def test_outside_rectangle_keeps_input(point) -> None:
    assert wgs84_to_gcj02(*point) == point
    assert gcj02_to_wgs84(*point) == point


def test_batch_names_altitude_and_coordinate_system_are_explicit() -> None:
    rows = parse_coordinate_rows(
        "名称\t纬度\t经度\t海拔\nA\t39.91334545536069\t116.38404722455657\t-12.5\nB\t48.85\t2.35\t\n",
        "gcj_to_wgs",
    )
    assert rows[0].altitude == -12.5 and rows[1].altitude == 0
    converted = tuple(convert_row(row, "gcj_to_wgs") for row in rows)
    assert converted[0].name == "A" and converted[0].altitude == -12.5
    assert converted[1] == rows[1]
    text = coordinate_csv(converted, "gcj_to_wgs")
    with pytest.raises(ValueError, match="坐标系"):
        parse_coordinate_rows(text, "gcj_to_wgs")
    assert parse_coordinate_rows(text, "wgs_to_gcj")[0].altitude == -12.5
    assert parse_coordinate_rows("39.9,116.3", "gcj_to_wgs")[0].name == "转换地点1"


@pytest.mark.parametrize(
    "text",
    (
        "名称,纬度,经度\nA,nan,2",
        "纬度,经度\n91,2",
        "名称,纬度,经度,海拔\nA,1,2,inf",
        "name,latitude,latitude\nA,1,2",
        "name,latitude,longitude\nA,1,2,3",
        "",
    ),
)
def test_invalid_batch_is_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        parse_coordinate_rows(text, "gcj_to_wgs")


def test_converter_rejects_invalid_coordinate_and_preserves_height() -> None:
    with pytest.raises(ValueError):
        gcj02_to_wgs84(float("nan"), 118)
    assert convert_row(CoordinateRow("A", 0, 0, 12.5), "gcj_to_wgs").altitude == 12.5


@pytest.mark.parametrize(
    "wgs,current",
    (
        ((31.1774276, 121.5272106), (31.175303947687105, 121.53154193255554)),
        ((22.543847, 113.912316), (22.54079608003489, 113.91717656313807)),
        ((39.911954, 116.377817), (39.91334547892198, 116.38404733005198)),
    ),
)
def test_matches_pinned_python_formula(wgs, current) -> None:
    # Evaluated independently from the pinned, checksum-verified upstream archive.
    assert wgs84_to_gcj02(*wgs) == pytest.approx(current, abs=1e-12)
    assert gcj02_to_wgs84(*current) == pytest.approx(wgs, abs=2e-8)

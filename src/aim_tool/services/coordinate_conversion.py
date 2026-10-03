"""Offline WGS84/GCJ-02 conversion and explicit CSV/TSV batch parsing.

Formula adapted from googollee/eviltransform at
03ba58d92dfda57f8a1635f3805483c8fc10bd77 (BSD-2-Clause).
Copyright (c) 2015, Googol Lee and contributors; see
packaging/EVILTRANSFORM_LICENSE.txt and bundled licenses/eviltransform/LICENSE.
Modifications: typed interface, input validation, bounded inverse with failure,
batch parsing and altitude preservation. This is an approximate public formula,
not an official transformation or a guarantee of surveyed ground accuracy.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from io import StringIO
from typing import Literal

from aim_tool.domain.validation import validate_altitude, validate_coordinates

Direction = Literal["gcj_to_wgs", "wgs_to_gcj"]
MAX_ROWS = 10000
HEADERS = {
    "name": "name",
    "名称": "name",
    "地点": "name",
    "latitude": "latitude",
    "纬度": "latitude",
    "longitude": "longitude",
    "经度": "longitude",
    "altitude": "altitude",
    "海拔": "altitude",
    "海拔（米）": "altitude",
    "coordinate_system": "coordinate_system",
    "坐标系": "coordinate_system",
}


def outside_formula_region(latitude: float, longitude: float) -> bool:
    return not (72.004 <= longitude <= 137.8347 and 0.8293 <= latitude <= 55.8271)


def _offset(latitude: float, longitude: float) -> tuple[float, float]:
    x, y = longitude - 105.0, latitude - 35.0
    shared = 20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)
    latitude_wave = (
        shared
        + 20 * math.sin(y * math.pi)
        + 40 * math.sin(y * math.pi / 3)
        + 160 * math.sin(y * math.pi / 12)
        + 320 * math.sin(y * math.pi / 30)
    )
    longitude_wave = (
        shared
        + 20 * math.sin(x * math.pi)
        + 40 * math.sin(x * math.pi / 3)
        + 150 * math.sin(x * math.pi / 12)
        + 300 * math.sin(x * math.pi / 30)
    )
    dlat = (
        latitude_wave * 2 / 3
        - 100
        + 2 * x
        + 3 * y
        + 0.2 * y * y
        + 0.1 * x * y
        + 0.2 * math.sqrt(abs(x))
    )
    dlon = (
        longitude_wave * 2 / 3
        + 300
        + x
        + 2 * y
        + 0.1 * x * x
        + 0.1 * x * y
        + 0.1 * math.sqrt(abs(x))
    )
    radian = math.radians(latitude)
    eccentricity = 0.00669342162296594323
    magic = 1 - eccentricity * math.sin(radian) ** 2
    root = math.sqrt(magic)
    radius = 6378137.0
    return (
        dlat * 180 / (radius * (1 - eccentricity) / (magic * root) * math.pi),
        dlon * 180 / (radius / root * math.cos(radian) * math.pi),
    )


def wgs84_to_gcj02(latitude: float, longitude: float) -> tuple[float, float]:
    validate_coordinates(latitude, longitude)
    if outside_formula_region(latitude, longitude):
        return latitude, longitude
    dlat, dlon = _offset(latitude, longitude)
    return latitude + dlat, longitude + dlon


def gcj02_to_wgs84(latitude: float, longitude: float) -> tuple[float, float]:
    validate_coordinates(latitude, longitude)
    if outside_formula_region(latitude, longitude):
        return latitude, longitude
    low_lat, high_lat = latitude - 0.01, latitude + 0.01
    low_lon, high_lon = longitude - 0.01, longitude + 0.01
    for _ in range(40):
        candidate = ((low_lat + high_lat) / 2, (low_lon + high_lon) / 2)
        forward = wgs84_to_gcj02(*candidate)
        lat_error, lon_error = forward[0] - latitude, forward[1] - longitude
        if abs(lat_error) <= 1e-8 and abs(lon_error) <= 1e-8:
            return candidate
        if lat_error > 0:
            high_lat = candidate[0]
        else:
            low_lat = candidate[0]
        if lon_error > 0:
            high_lon = candidate[1]
        else:
            low_lon = candidate[1]
    raise ValueError("逆解未收敛，请核对算法边界附近的坐标")


@dataclass(frozen=True)
class CoordinateRow:
    name: str
    latitude: float
    longitude: float
    altitude: float = 0.0


def parse_coordinate_rows(text: str, direction: Direction) -> tuple[CoordinateRow, ...]:
    if direction not in {"gcj_to_wgs", "wgs_to_gcj"}:
        raise ValueError("未知转换方向")
    if len(text) > 5_000_000:
        raise ValueError("输入超过 5 MB，请拆分批次")
    text = text.lstrip("\ufeff")
    rows = [
        row
        for row in csv.reader(StringIO(text), delimiter="\t" if "\t" in text else ",")
        if any(cell.strip() for cell in row)
    ]
    if not rows:
        raise ValueError("请粘贴或导入坐标")
    first = [cell.strip() for cell in rows[0]]
    if any(cell in HEADERS for cell in first):
        if any(cell not in HEADERS for cell in first):
            raise ValueError("表头仅支持名称、纬度、经度、海拔、坐标系")
        fields = tuple(HEADERS[cell] for cell in first)
        rows = rows[1:]
        start = 2
    else:
        fields = {
            2: ("latitude", "longitude"),
            3: ("name", "latitude", "longitude"),
            4: ("name", "latitude", "longitude", "altitude"),
        }.get(len(first), ())
        start = 1
    if (
        not fields
        or len(set(fields)) != len(fields)
        or not {"latitude", "longitude"} <= set(fields)
    ):
        raise ValueError("必须提供纬度、经度；可选名称和海拔，纬度在经度前")
    if not rows or len(rows) > MAX_ROWS:
        raise ValueError(f"每批需要 1 至 {MAX_ROWS} 行")
    parsed = []
    system = "GCJ-02" if direction == "gcj_to_wgs" else "WGS84"
    for line, row in enumerate(rows, start):
        if len(row) != len(fields):
            raise ValueError(f"第 {line} 行列数不一致")
        values = dict(zip(fields, (cell.strip() for cell in row), strict=True))
        if values.get("coordinate_system", system) != system:
            raise ValueError(f"第 {line} 行坐标系与输入方向不一致")
        try:
            latitude, longitude = float(values["latitude"]), float(values["longitude"])
            altitude = float(values.get("altitude", "") or "0")
            validate_coordinates(latitude, longitude)
            validate_altitude(altitude)
        except ValueError as error:
            raise ValueError(f"第 {line} 行坐标或海拔无效") from error
        parsed.append(
            CoordinateRow(
                values.get("name") or f"转换地点{line - start + 1}", latitude, longitude, altitude
            )
        )
    return tuple(parsed)


def convert_row(row: CoordinateRow, direction: Direction) -> CoordinateRow:
    if direction not in {"gcj_to_wgs", "wgs_to_gcj"}:
        raise ValueError("未知转换方向")
    validate_altitude(row.altitude)
    converter = gcj02_to_wgs84 if direction == "gcj_to_wgs" else wgs84_to_gcj02
    latitude, longitude = converter(row.latitude, row.longitude)
    return CoordinateRow(row.name, latitude, longitude, row.altitude)


def coordinate_csv(rows: tuple[CoordinateRow, ...], direction: Direction) -> str:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("name", "latitude", "longitude", "altitude", "coordinate_system"))
    system = "WGS84" if direction == "gcj_to_wgs" else "GCJ-02"
    for row in rows:
        writer.writerow(
            (row.name, f"{row.latitude:.8f}", f"{row.longitude:.8f}", f"{row.altitude:g}", system)
        )
    return output.getvalue()

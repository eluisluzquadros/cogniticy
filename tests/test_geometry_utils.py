import pytest
from shapely.geometry import Polygon
from core.geometry_utils import (
    clean_geometry, apply_setbacks, calculate_usable_area,
    combine_geometries, compact_geometry
)


def test_clean_geometry():
    bad_poly = Polygon([(0,0), (1,1), (1,0), (0,1), (0,0)])  # self-intersecting
    cleaned = clean_geometry(bad_poly)
    assert cleaned.is_valid


def test_apply_setbacks():
    poly = Polygon([(0,0), (0,10), (10,10), (10,0), (0,0)])
    reduced = apply_setbacks(poly, front=1, back=1, sides=1)
    assert reduced.area < poly.area


def test_calculate_usable_area():
    poly = Polygon([(0,0), (0,10), (10,10), (10,0), (0,0)])
    area = calculate_usable_area(poly)
    assert area == 100.0


def test_combine_geometries():
    p1 = Polygon([(0,0), (0,5), (5,5), (5,0), (0,0)])
    p2 = Polygon([(4,4), (4,9), (9,9), (9,4), (4,4)])
    unioned = combine_geometries([p1, p2])
    assert unioned.area > p1.area


def test_compact_geometry():
    poly = Polygon([(0,0), (0,10), (10,10), (10,0), (0,0)])
    compacted = compact_geometry(poly, factor=0.9)
    assert compacted.area < poly.area

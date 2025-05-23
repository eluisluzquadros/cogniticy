import pytest
from shapely.geometry import Polygon
from io.validator import GeometryValidator

def test_valid_polygon():
    poly = Polygon([(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)])
    validator = GeometryValidator(poly)
    result = validator.validate()

    assert result["is_valid"] is True
    assert result["is_simple"] is True
    assert result["is_polygonal"] is True


def test_invalid_polygon():
    # Self-intersecting polygon (bowtie)
    poly = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
    validator = GeometryValidator(poly)
    result = validator.validate()

    assert result["is_valid"] is False
    assert "Self-intersection" in result["explanation"]


def test_raise_if_invalid():
    poly = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
    validator = GeometryValidator(poly)

    with pytest.raises(ValueError) as exc:
        validator.raise_if_invalid()

    assert "Geometria inválida" in str(exc.value)
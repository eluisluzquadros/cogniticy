from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid
from shapely.affinity import scale


def clean_geometry(geom: Polygon) -> Polygon:
    """
    Corrige geometrias inválidas usando buffer ou make_valid.
    """
    if not geom.is_valid:
        geom = make_valid(geom)
    return geom


def apply_setbacks(geom: Polygon, front: float = 0, back: float = 0, sides: float = 0) -> Polygon:
    """
    Aplica recuos básicos via buffer negativo. (Atenção: é simplificado)
    """
    reduced = geom.buffer(-min(front, back, sides))
    return clean_geometry(reduced)


def calculate_usable_area(geom: Polygon) -> float:
    """
    Calcula a área utilizável da geometria.
    """
    return geom.area


def combine_geometries(geoms: list) -> Polygon:
    """
    Realiza a união espacial de múltiplas geometrias.
    """
    unioned = unary_union(geoms)
    return clean_geometry(unioned)


def compact_geometry(geom: Polygon, factor: float = 0.95) -> Polygon:
    """
    Aplica compactação proporcional em x e y.
    """
    return scale(geom, xfact=factor, yfact=factor)

import hashlib
import json
from shapely.geometry import Polygon
from shapely import wkt


def hash_geometry(geom: Polygon) -> str:
    """
    Gera um hash único a partir da geometria para caching ou identificação.
    """
    wkt_str = geom.wkt
    return hashlib.md5(wkt_str.encode('utf-8')).hexdigest()


def geometry_to_json(geom: Polygon) -> dict:
    """
    Converte um objeto shapely Polygon para GeoJSON dict.
    """
    return json.loads(json.dumps(geom.__geo_interface__))


def json_to_geometry(geojson_obj: dict) -> Polygon:
    """
    Converte um dict GeoJSON para shapely Polygon.
    """
    from shapely.geometry import shape
    return shape(geojson_obj)


def generate_prompt_from_geometry(geom: Polygon, context: str = "") -> str:
    """
    Gera um prompt textual para agentes ou LLMs com base na geometria.
    """
    coords = list(geom.exterior.coords)
    return f"{context}\n\nGeometria com {len(coords)} vértices e área de {geom.area:.2f} m²."

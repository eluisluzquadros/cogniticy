from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import explain_validity

class GeometryValidator:
    """
    Classe utilitária para validar integridade e conformidade de geometrias shapely.
    """

    def __init__(self, geom):
        self.geom = geom

    def is_valid(self) -> bool:
        return self.geom.is_valid

    def is_simple(self) -> bool:
        return self.geom.is_simple

    def is_polygonal(self) -> bool:
        return isinstance(self.geom, (Polygon, MultiPolygon))

    def validate(self) -> dict:
        """
        Retorna um dicionário com diagnóstico completo da geometria.
        """
        return {
            "is_valid": self.is_valid(),
            "is_simple": self.is_simple(),
            "is_polygonal": self.is_polygonal(),
            "explanation": explain_validity(self.geom)
        }

    def raise_if_invalid(self):
        """
        Lança uma exceção se a geometria for inválida.
        """
        if not self.is_valid():
            raise ValueError(f"Geometria inválida: {explain_validity(self.geom)}")

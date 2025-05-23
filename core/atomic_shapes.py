# cogniticy/core/atomic_shapes.py

from typing import Union
from shapely.geometry import Point, LineString, Polygon
import logging

logger = logging.getLogger(__name__)

class AtomicShape:
    """
    Classe base para formas atômicas usadas na modelagem generativa.
    """
    def __init__(self, geometry: Union[Point, LineString, Polygon], shape_type: str):
        self.geometry = geometry
        self.shape_type = shape_type

    def __repr__(self) -> str:
        geom_wkt = "N/A"
        if self.geometry:
            try:
                geom_wkt = self.geometry.wkt[:50] + "..." if len(self.geometry.wkt) > 50 else self.geometry.wkt
            except Exception: # Em caso de geometria inválida que não tem wkt
                geom_wkt = "[Geometria Inválida]"
        return f"{self.shape_type}({geom_wkt})"

class Slab(AtomicShape):
    """
    Representa um 'Slab', uma forma linear ou uma área retangular estreita.
    """
    def __init__(self, geometry: Union[LineString, Polygon]):
        super().__init__(geometry, "Slab")
        if not isinstance(geometry, (LineString, Polygon)):
            raise ValueError("A geometria do Slab deve ser LineString ou Polygon.")

    @property
    def length(self) -> float:
        if isinstance(self.geometry, LineString):
            return self.geometry.length
        elif isinstance(self.geometry, Polygon) and self.geometry.exterior:
            # Para um polígono, pode ser o comprimento da borda mais longa ou perímetro/2.
            # Usando perímetro/2 como uma aproximação genérica de "comprimento".
            return self.geometry.exterior.length / 2 
        return 0.0

class Corner(AtomicShape):
    """
    Representa um 'Corner', um ponto ou vértice significativo na modelagem.
    """
    def __init__(self, geometry: Point):
        super().__init__(geometry, "Corner")
        if not isinstance(geometry, Point):
            raise ValueError("A geometria do Corner deve ser um Point.")

    @property
    def x(self) -> float:
        return self.geometry.x if isinstance(self.geometry, Point) else 0.0

    @property
    def y(self) -> float:
        return self.geometry.y if isinstance(self.geometry, Point) else 0.0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("--- Testando Formas Atômicas ---")
    my_corner = Corner(Point(10, 20))
    logger.info(f"Corner criado: {my_corner}, Coords: ({my_corner.x}, {my_corner.y})")
    my_slab_line = Slab(LineString([(0, 0), (0, 50)]))
    logger.info(f"Slab (linha) criado: {my_slab_line}, Comprimento: {my_slab_line.length}")
    my_slab_poly = Slab(Polygon([(0,0), (1,0), (1,10), (0,10)]))
    logger.info(f"Slab (polígono) criado: {my_slab_poly}, Comprimento (aprox): {my_slab_poly.length}")
    logger.info("--- Testes de Formas Atômicas Concluídos ---")

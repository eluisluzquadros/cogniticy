from shapely.geometry import Polygon
from shapely.ops import unary_union

class Slab:
    """
    Representa um retângulo simples (Slab) definido por comprimento e largura.
    """
    def __init__(self, length: float, width: float):
        self.length = length
        self.width = width

    def to_polygon(self) -> Polygon:
        """
        Converte os parâmetros do Slab em um polígono Shapely.
        """
        coords = [
            (0.0, 0.0),
            (self.length, 0.0),
            (self.length, self.width),
            (0.0, self.width)
        ]
        return Polygon(coords)


class Corner:
    """
    Representa uma forma em 'L' (Corner) definida por side_length e thickness.
    """
    def __init__(self, side_length: float, thickness: float):
        self.side_length = side_length
        self.thickness = thickness

    def to_polygon(self) -> Polygon:
        """
        Gera um polígono Shapely em formato de 'L', unindo dois retângulos.
        """
        # Braço horizontal
        rect1 = Polygon([
            (0.0, 0.0),
            (self.side_length, 0.0),
            (self.side_length, self.thickness),
            (0.0, self.thickness)
        ])
        # Braço vertical
        rect2 = Polygon([
            (0.0, 0.0),
            (self.thickness, 0.0),
            (self.thickness, self.side_length),
            (0.0, self.side_length)
        ])
        return unary_union([rect1, rect2])


def compose_shapes(shapes: list) -> Polygon:
    """
    Compoe diversas formas atômicas (Slab, Corner) unindo-as em um único polígono.
    """
    polygons = [shape.to_polygon() for shape in shapes]
    return unary_union(polygons)

from abc import ABC, abstractmethod
from shapely.geometry import Polygon
from core.params import BuildingParameters

class IShapeGenerator(ABC):
    """
    Interface base para geradores de formas morfológicas.
    Todos os geradores devem implementar esta interface.
    """

    def __init__(self, parameters: BuildingParameters):
        self.params = parameters

    @abstractmethod
    def generate_footprint(self) -> Polygon:
        """
        Gera o polígono representando o footprint da edificação.
        """
        pass

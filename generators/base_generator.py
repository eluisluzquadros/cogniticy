# cogniticy/generators/base_generator.py

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Dict, Any
from shapely.geometry import Polygon
import logging # Importa logging

from cogniticy.core.model import Building # Importa Building
from cogniticy.core.params import AppParams # Importa AppParams

logger = logging.getLogger(__name__) # Configura logger

class GeneratedShape:
    """
    Representa uma forma gerada, incluindo seu footprint e metadados.
    """
    def __init__(self,
                 footprint: Polygon,
                 shape_name: str,
                 morphology_type: str,
                 generation_params: Optional[Dict[str, Any]] = None,
                 parent_footprint: Optional[Polygon] = None):
        self.footprint = footprint 
        self.shape_name = shape_name 
        self.morphology_type = morphology_type 
        self.generation_params = generation_params if generation_params else {} 
        self.parent_footprint = parent_footprint 

    def __repr__(self):
        return f"GeneratedShape(name='{self.shape_name}', type='{self.morphology_type}', area={self.footprint.area:.2f})"

class BaseGenerator(ABC):
    """
    Classe base abstrata para geradores de formas de edificações.
    """
    def __init__(self, params_manager: AppParams, building_model: Building):
        self.params_manager = params_manager
        self.building_model = building_model 
        self.base_footprint = building_model.footprint_polygon 

    @abstractmethod
    def generate_shapes(self) -> List[GeneratedShape]:
        """
        Método abstrato para gerar uma ou mais formas (footprints) candidatas.
        """
        pass

    def generate_building_from_shape(self, generated_shape: GeneratedShape) -> Building:
        """
        Gera um modelo de edificação completo a partir de um GeneratedShape.
        """
        # Cria uma nova instância de Building para esta forma específica
        specific_building = Building(
            lot_polygon=self.building_model.lot_polygon_original,
            params_manager=self.params_manager, # Usa os mesmos parâmetros do lote atual
            lot_crs=self.building_model.lot_crs,
            shape_name=generated_shape.shape_name,
            morphology_type=generated_shape.morphology_type,
            identified_faces=self.building_model.identified_faces # Propaga as faces identificadas
        )
        
        # Gera pavimentos usando o footprint da forma gerada
        specific_building.generate_floors(custom_footprint=generated_shape.footprint)
        
        return specific_building

if __name__ == "__main__":
    # Exemplo de estrutura, não funcional diretamente sem mocks completos
    logging.basicConfig(level=logging.INFO)
    logger.info("BaseGenerator e GeneratedShape definidos.")

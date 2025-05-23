# cogniticy/generators/orthogonal_generator.py

from typing import List, Optional
from shapely.geometry import Polygon
import logging # Importa logging

from .base_generator import BaseGenerator, GeneratedShape # Importa BaseGenerator e GeneratedShape
from cogniticy.core.params import AppParams # Importa AppParams
from cogniticy.core.model import Building # Importa Building
from cogniticy.core.geometry_utils import get_oriented_bounding_box, make_geometry_valid # Importa utilitários

logger = logging.getLogger(__name__) # Configura logger

class OrthogonalGenerator(BaseGenerator):
    """
    Gera uma forma ortogonal (retangular) para a edificação.
    """
    SHAPE_NAME = "Ortogonal"
    MORPHOLOGY_TYPE = "O" 

    def __init__(self, params_manager: AppParams, building_model: Building):
        super().__init__(params_manager, building_model)

    def generate_shapes(self) -> List[GeneratedShape]:
        """
        Gera a forma ortogonal baseada no OBB do footprint inicial.
        """
        if not self.base_footprint or self.base_footprint.is_empty:
            logger.warning(f"Lote {self.building_model.numlote} (OrthogonalGenerator): Footprint base inválido. Não pode gerar forma ortogonal.")
            return []

        orthogonal_footprint = get_oriented_bounding_box(self.base_footprint)
        orthogonal_footprint = make_geometry_valid(orthogonal_footprint)

        if not isinstance(orthogonal_footprint, Polygon) or orthogonal_footprint.is_empty:
            logger.warning(f"Lote {self.building_model.numlote} (OrthogonalGenerator): OBB resultou inválido. Usando base_footprint como fallback.")
            if self.base_footprint and isinstance(self.base_footprint, Polygon) and not self.base_footprint.is_empty:
                 orthogonal_footprint = self.base_footprint
            else:
                return []

        generated_shape = GeneratedShape(
            footprint=orthogonal_footprint,
            shape_name=self.SHAPE_NAME,
            morphology_type=self.MORPHOLOGY_TYPE,
            generation_params={"source": "OBB of base_footprint"},
            parent_footprint=self.base_footprint
        )
        return [generated_shape]

if __name__ == "__main__":
    # Exemplo de uso (como definido anteriormente)
    from cogniticy.core.params import AppParams
    from cogniticy.core.model import Building
    from shapely.geometry import Polygon
    logging.basicConfig(level=logging.INFO)
    logger.info("--- Testando OrthogonalGenerator ---")
    class MockAppParamsOrthogonal: # Mock simplificado
        def __init__(self):
            self.zoning = {"numlote": "LOTETESTE_ORTHO"}
            self.normative = {"min_front_setback": 1.0, "min_back_setback": 1.0, "min_side_setback": 1.0, "gf_floor_height":3, "uf_floor_height":3, "max_height":30, "max_far":2}
            self.architectural = {}
            self.simulation = {}
    mock_params_ortho = MockAppParamsOrthogonal()
    lot_geom_irregular = Polygon([(0,0), (40,10), (35,50), (5,40), (0,0)])
    base_building_model = Building(lot_polygon=lot_geom_irregular, params_manager=mock_params_ortho, lot_crs="EPSG:32722")
    if base_building_model.footprint_polygon and not base_building_model.footprint_polygon.is_empty:
        ortho_generator = OrthogonalGenerator(params_manager=mock_params_ortho, building_model=base_building_model)
        generated_shapes_list = ortho_generator.generate_shapes()
        if generated_shapes_list:
            logger.info(f"Forma Ortogonal Gerada: {generated_shapes_list[0]}")
    else:
        logger.warning("Footprint base inválido para teste do OrthogonalGenerator.")
    logger.info("--- Testes de OrthogonalGenerator Concluídos ---")

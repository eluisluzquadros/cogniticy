# cogniticy/generators/composite_generator.py

import logging
from typing import List, Optional, Dict, Any
from shapely.geometry import Polygon, box, MultiPolygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from .base_generator import BaseGenerator, GeneratedShape # Importações relativas corretas
from cogniticy.core.params import AppParams
from cogniticy.core.model import Building
from cogniticy.core.geometry_utils import make_geometry_valid, get_oriented_bounding_box

logger = logging.getLogger(__name__)

class CompositeGenerator(BaseGenerator):
    """
    Gera formas compostas para edificações (ex: L, U, O).
    """
    def __init__(self, params_manager: AppParams, building_model: Building):
        super().__init__(params_manager, building_model)
        self.grid_search_params = params_manager.modeling_strategy.get("grid_search_parameters", {})

    def generate_shapes(self) -> List[GeneratedShape]:
        # Implementação da função generate_shapes para CompositeGenerator (como definida anteriormente)
        generated_forms: List[GeneratedShape] = []
        if not self.base_footprint or self.base_footprint.is_empty:
            logger.warning(f"Lote {self.building_model.numlote} (CompositeGenerator): Footprint base inválido. Não pode gerar formas compostas.")
            return []

        obb_footprint = get_oriented_bounding_box(self.base_footprint)
        if not isinstance(obb_footprint, Polygon) or obb_footprint.is_empty:
            logger.warning(f"Lote {self.building_model.numlote} (CompositeGenerator): OBB inválido. Usando base_footprint.")
            obb_footprint = self.base_footprint
            if not isinstance(obb_footprint, Polygon) or obb_footprint.is_empty: return []

        minx, miny, maxx, maxy = obb_footprint.bounds
        width = maxx - minx
        height = maxy - miny
        shape_ratios_to_try = self.grid_search_params.get("shape_ratio_steps", [0.4, 0.5, 0.6])

        for ratio in shape_ratios_to_try:
            if width <= 1e-6 or height <= 1e-6 or ratio <=0 or ratio >=1: continue

            # L-Shape V1
            leg1_v_width = width * ratio
            leg1_v = box(minx, miny, minx + leg1_v_width, maxy)
            leg2_v_height = height * ratio # Para a segunda perna, poderia ser outra proporção ou fixa
            leg2_v = box(minx, miny, maxx, miny + leg2_v_height) # Perna horizontal na base
            l_shape_v1 = unary_union([leg1_v, leg2_v])
            l_shape_v1 = make_geometry_valid(l_shape_v1.intersection(self.base_footprint))
            if isinstance(l_shape_v1, Polygon) and not l_shape_v1.is_empty and l_shape_v1.area > 0.1:
                generated_forms.append(GeneratedShape(footprint=l_shape_v1, shape_name=f"L-Shape (V1, Ratio {ratio:.1f})", morphology_type=f"L_V1_R{int(ratio*10)}", generation_params={"type": "L-V1", "ratio": ratio}, parent_footprint=self.base_footprint))

            # L-Shape H1 (outra variação)
            leg1_h_height = height * ratio
            leg1_h = box(minx, miny, maxx, miny + leg1_h_height) # Barra horizontal na base
            leg2_h_width = width * ratio 
            leg2_h = box(minx, miny, minx + leg2_h_width, maxy) # Barra vertical à esquerda
            l_shape_h1 = unary_union([leg1_h, leg2_h])
            l_shape_h1 = make_geometry_valid(l_shape_h1.intersection(self.base_footprint))
            if isinstance(l_shape_h1, Polygon) and not l_shape_h1.is_empty and l_shape_h1.area > 0.1:
                generated_forms.append(GeneratedShape(footprint=l_shape_h1, shape_name=f"L-Shape (H1, Ratio {ratio:.1f})", morphology_type=f"L_H1_R{int(ratio*10)}", generation_params={"type": "L-H1", "ratio": ratio}, parent_footprint=self.base_footprint))
        
        if not generated_forms: logger.info(f"Lote {self.building_model.numlote} (CompositeGenerator): Nenhuma forma composta válida gerada.")
        return generated_forms

if __name__ == "__main__":
    # Exemplo de uso (como definido anteriormente)
    from cogniticy.core.params import AppParams
    from cogniticy.core.model import Building
    from shapely.geometry import Polygon
    logging.basicConfig(level=logging.INFO)
    logger.info("--- Testando CompositeGenerator ---")
    # MockAppParamsComposite e restante do teste como antes...
    class MockAppParamsComposite: # Mock simplificado
        def __init__(self):
            self.zoning = {"numlote": "LOTETESTE_COMP"}
            self.normative = {"min_front_setback": 1.0, "min_back_setback": 1.0, "min_side_setback": 1.0, "gf_floor_height":3, "uf_floor_height":3, "max_height":30, "max_far":2}
            self.architectural = {}
            self.simulation = {}
            self.modeling_strategy = {"grid_search_parameters": {"shape_ratio_steps": [0.4, 0.6]}}
    mock_params_comp = MockAppParamsComposite()
    lot_geom_rect = Polygon([(0,0), (50,0), (50,30), (0,30), (0,0)])
    base_building_model_comp = Building(lot_polygon=lot_geom_rect, params_manager=mock_params_comp, lot_crs="EPSG:32722")
    if base_building_model_comp.footprint_polygon and not base_building_model_comp.footprint_polygon.is_empty:
        comp_generator = CompositeGenerator(params_manager=mock_params_comp, building_model=base_building_model_comp)
        generated_composite_shapes = comp_generator.generate_shapes()
        if generated_composite_shapes: logger.info(f"Total de {len(generated_composite_shapes)} formas compostas geradas.")
        else: logger.info("Nenhuma forma composta gerada.")
    else: logger.warning("Footprint base inválido para teste do CompositeGenerator.")
    logger.info("--- Testes de CompositeGenerator Concluídos ---")

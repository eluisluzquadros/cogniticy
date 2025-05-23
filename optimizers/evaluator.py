# cogniticy/optimizers/evaluator.py

import logging
from typing import Dict, Any, Tuple

from cogniticy.core.model import Building # Importa Building
from cogniticy.core.params import AppParams # Importa AppParams

logger = logging.getLogger(__name__) # Configura logger

class BuildingEvaluator:
    """
    Avalia uma instância de Building com base em critérios de otimização.
    """
    def __init__(self, params_manager: AppParams):
        self.params_manager = params_manager
        self.optimization_objective = params_manager.modeling_strategy.get("optimization_objective", "maximize_far_within_height")

    def evaluate_building(self, building: Building) -> Tuple[float, Dict[str, Any]]:
        # Implementação da função evaluate_building (como definida anteriormente)
        if not building or not building.floors:
            logger.warning(f"Lote {building.numlote if building else 'N/A'}: Tentativa de avaliar edificação inválida ou sem pavimentos.")
            return -float('inf'), {"error": "Edificação inválida ou sem pavimentos", "numlote": building.numlote if building else "N/A"}

        is_compliant, violations = building.is_compliant()
        score = 0.0
        if not is_compliant: score -= 1000 * len(violations)

        metrics = {
            "numlote": building.numlote, "shape_name": building.shape_name,
            "morphology_type": building.morphology_type, "num_floors": building.num_floors,
            "total_height_m": building.total_height_m, "total_built_area_m2": building.total_built_area_m2,
            "achieved_far": building.achieved_far, "achieved_lot_coverage": building.achieved_lot_coverage,
            "is_compliant": is_compliant, "violations": violations,
            "slenderness_ratio_achieved": building.slenderness_ratio_achieved,
            "overall_efficiency": building.overall_efficiency
        }

        if self.optimization_objective == "maximize_far_within_height":
            if is_compliant:
                score += building.achieved_far * 100 
                height_ratio = building.total_height_m / building.max_height_param if building.max_height_param > 1e-6 else 0
                if height_ratio <= 1.0: score += height_ratio * 10
            else:
                if building.total_height_m > building.max_height_param: score -= (building.total_height_m - building.max_height_param) * 5
                if building.achieved_far > building.max_far_param: score -= (building.achieved_far - building.max_far_param) * 50
        # Adicionar outros objetivos de otimização aqui
        elif is_compliant: # Default para outros objetivos se conformes
             score += building.achieved_far * 100


        metrics["evaluation_score"] = score
        logger.debug(f"Lote {building.numlote}, Forma '{building.shape_name}': Avaliação - Score: {score:.2f}")
        return score, metrics

if __name__ == "__main__":
    # Exemplo de uso (como definido anteriormente)
    logging.basicConfig(level=logging.INFO)
    from cogniticy.core.model import Floor 
    from shapely.geometry import Polygon
    logger.info("--- Testando BuildingEvaluator ---")
    # MockAppParamsEvaluator e restante do teste como antes...
    class MockAppParamsEvaluator: # Mock simplificado
        def __init__(self, objective="maximize_far_within_height"):
            self.zoning = {"numlote": "EVAL_TEST001"}
            self.normative = {"max_height": 30.0, "max_far": 1.5, "max_lot_coverage": 0.6, "gf_floor_height":3, "uf_floor_height":3}
            self.architectural = {}
            self.simulation = {}
            self.modeling_strategy = {"optimization_objective": objective}
    params_compliant = MockAppParamsEvaluator()
    evaluator_compliant = BuildingEvaluator(params_manager=params_compliant)
    lot_geom_eval = Polygon([(0,0), (20,0), (20,20), (0,20)])
    building_ok = Building(lot_geom_eval, params_compliant, lot_crs="EPSG:32722")
    building_ok.footprint_polygon = Polygon([(1,1), (19,1), (19,19), (1,19)]) 
    building_ok.floors = [Floor(0, 0, 3, building_ok.footprint_polygon)] 
    building_ok.max_far_param = 2.5; building_ok.achieved_far = 1.0; building_ok.total_height_m = 3.0
    building_ok.is_compliant = lambda: (True, []) # Mock para ser conforme
    score_ok, _ = evaluator_compliant.evaluate_building(building_ok)
    logger.info(f"Edifício OK - Score: {score_ok:.2f}")
    assert score_ok > 0
    logger.info("--- Testes de BuildingEvaluator Concluídos ---")

# cogniticy/optimizers/optimizer.py

import logging
import itertools
from typing import List, Dict, Any, Optional, Tuple

from cogniticy.core.params import AppParams # Importa AppParams
from cogniticy.core.model import Building # Importa Building
from cogniticy.generators.base_generator import BaseGenerator, GeneratedShape # Importa BaseGenerator e GeneratedShape
from cogniticy.generators.composite_generator import CompositeGenerator # Importa CompositeGenerator
from .evaluator import BuildingEvaluator # Importa BuildingEvaluator

logger = logging.getLogger(__name__) # Configura logger

class GridSearchOptimizer:
    """
    Realiza uma busca em grade (Grid Search) para encontrar a melhor configuração.
    """
    def __init__(self, params_manager: AppParams, building_model_base: Building):
        self.params_manager = params_manager
        self.building_model_base = building_model_base
        self.evaluator = BuildingEvaluator(params_manager)
        self.shape_generators: List[BaseGenerator] = []
        self._initialize_generators()
        self.best_building_solution: Optional[Building] = None
        self.best_score: float = -float('inf')
        self.all_evaluated_solutions: List[Dict[str, Any]] = []

    def _initialize_generators(self):
        # Adiciona o CompositeGenerator. Outros geradores podem ser adicionados aqui.
        self.shape_generators.append(CompositeGenerator(self.params_manager, self.building_model_base))
        logger.info(f"Otimizador inicializado com {len(self.shape_generators)} tipo(s) de gerador(es).")

    def run_optimization(self) -> Optional[Building]:
        # Implementação da função run_optimization (como definida anteriormente)
        logger.info(f"Lote {self.building_model_base.numlote}: Iniciando Grid Search...")
        self.best_building_solution = None
        self.best_score = -float('inf')
        self.all_evaluated_solutions = []

        for generator_instance in self.shape_generators:
            logger.info(f"Lote {self.building_model_base.numlote}: Usando gerador: {type(generator_instance).__name__}")
            candidate_generated_shapes: List[GeneratedShape] = generator_instance.generate_shapes()
            
            if not candidate_generated_shapes:
                logger.info(f"Gerador {type(generator_instance).__name__} não produziu formas para o lote {self.building_model_base.numlote}.")
                continue
            logger.info(f"Gerador {type(generator_instance).__name__} produziu {len(candidate_generated_shapes)} formas candidatas.")

            for i, generated_shape_candidate in enumerate(candidate_generated_shapes):
                logger.debug(f"  Avaliando candidata {i+1}/{len(candidate_generated_shapes)}: {generated_shape_candidate.shape_name}")
                current_building = generator_instance.generate_building_from_shape(generated_shape_candidate)

                if not current_building or not current_building.floors:
                    logger.warning(f"    Lote {self.building_model_base.numlote}, Forma '{generated_shape_candidate.shape_name}': Falha ao gerar edificação/pavimentos.")
                    eval_metrics = {"error": "Falha na geração", "shape_name": generated_shape_candidate.shape_name}
                    eval_metrics.update(generated_shape_candidate.generation_params)
                    self.all_evaluated_solutions.append(eval_metrics)
                    continue
                
                score, eval_metrics = self.evaluator.evaluate_building(current_building)
                eval_metrics["generation_params"] = generated_shape_candidate.generation_params
                self.all_evaluated_solutions.append(eval_metrics)

                if score > self.best_score:
                    logger.info(f"    Lote {self.building_model_base.numlote}: Nova melhor solução! Forma: '{current_building.shape_name}', Score: {score:.2f}")
                    self.best_score = score
                    self.best_building_solution = current_building
                else:
                    logger.debug(f"    Lote {self.building_model_base.numlote}, Forma '{current_building.shape_name}': Score {score:.2f} não superou {self.best_score:.2f}.")
        
        if self.best_building_solution: logger.info(f"Lote {self.building_model_base.numlote}: Otimização Grid Search concluída. Melhor forma: '{self.best_building_solution.shape_name}', Score: {self.best_score:.2f}")
        else: logger.warning(f"Lote {self.building_model_base.numlote}: Otimização Grid Search não encontrou solução válida.")
        return self.best_building_solution

    def get_all_evaluated_solutions_summary(self) -> List[Dict[str, Any]]:
        return self.all_evaluated_solutions

if __name__ == "__main__":
    # Exemplo de uso (como definido anteriormente)
    logging.basicConfig(level=logging.INFO)
    from shapely.geometry import Polygon
    logger.info("--- Testando GridSearchOptimizer ---")
    # MockAppParamsOptimizer e restante do teste como antes...
    class MockAppParamsOptimizer: # Mock simplificado
        def __init__(self):
            self.zoning = {"numlote": "OPTIM_TEST001"}
            self.normative = {"max_height": 40.0, "max_far": 1.8, "min_front_setback":1, "min_back_setback":1, "min_side_setback":1, "gf_floor_height":3, "uf_floor_height":3}
            self.architectural = {}
            self.simulation = {}
            self.modeling_strategy = {"optimization_objective": "maximize_far_within_height", "grid_search_parameters": {"shape_ratio_steps": [0.4, 0.6]}}
    mock_params_optimizer = MockAppParamsOptimizer()
    lot_geom_opt = Polygon([(0,0), (40,0), (40,25), (0,25)])
    building_model_for_opt = Building(lot_polygon=lot_geom_opt, params_manager=mock_params_optimizer, lot_crs="EPSG:32722")
    if building_model_for_opt.footprint_polygon and not building_model_for_opt.footprint_polygon.is_empty:
        optimizer = GridSearchOptimizer(params_manager=mock_params_optimizer, building_model_base=building_model_for_opt)
        best_solution_building = optimizer.run_optimization()
        if best_solution_building: logger.info(f"Melhor Solução: Forma {best_solution_building.shape_name}, Score {optimizer.best_score:.2f}")
        else: logger.info("Otimizador não encontrou solução.")
    else: logger.error("Footprint base inválido para teste do otimizador.")
    logger.info("--- Testes de GridSearchOptimizer Concluídos ---")

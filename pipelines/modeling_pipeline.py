# cogniticy/pipelines/modeling_pipeline.py

import logging
import os
from typing import List, Dict, Any, Optional

from cogniticy.core.params import AppParams
from cogniticy.dataio.geojson_handler import GeoJSONHandler
from cogniticy.dataio.exporter import Exporter
from cogniticy.core.model import Building
from cogniticy.generators.orthogonal_generator import OrthogonalGenerator
from cogniticy.generators.composite_generator import CompositeGenerator # Importado
from cogniticy.optimizers.optimizer import GridSearchOptimizer # Importado

# Configuração básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger(__name__)

def run_modeling_pipeline(config_path: str = "config/default.yaml"):
    """
    Executa a pipeline de modelagem generativa urbana de ponta a ponta.

    Args:
        config_path (str): Caminho para o arquivo de configuração YAML principal.
    """
    logger.info("Iniciando a Pipeline de Modelagem CogniCity...")

    # 1. Carregar Configurações Globais
    try:
        global_params_manager = AppParams(default_config_path=config_path)
        logger.info(f"Configurações globais carregadas de: {config_path}")
    except Exception as e:
        logger.error(f"Falha crítica ao carregar configurações de {config_path}: {e}")
        return

    # 2. Inicializar Componentes de I/O
    default_processing_crs = global_params_manager.simulation.get("default_processing_crs", "EPSG:31982")
    
    geojson_loader = GeoJSONHandler(default_crs=default_processing_crs)
    exporter = Exporter(params_manager=global_params_manager)

    # 3. Carregar Dados dos Lotes
    input_lots_path = global_params_manager.simulation.get("input_lots_geojson")
    if not input_lots_path:
        logger.error("Caminho para o GeoJSON de lotes de entrada não definido em 'simulation_parameters.input_lots_geojson'.")
        return
    lot_id_column = global_params_manager.simulation.get("lot_id_column_name", "numlote") 

    if not geojson_loader.load_lots_geojson(geojson_path=input_lots_path, id_column=lot_id_column):
        logger.error(f"Falha ao carregar lotes de {input_lots_path}. Pipeline interrompida.")
        return
        
    # 3a. Carregar Arquivo de Faces Externas (Opcional)
    input_faces_path = global_params_manager.simulation.get("input_block_faces_geojson")
    if input_faces_path and os.path.exists(input_faces_path):
        faces_lot_id_col = global_params_manager.simulation.get("faces_lot_id_column", "numlote")
        faces_type_col = global_params_manager.simulation.get("faces_type_column", "tipo")
        
        if not geojson_loader.load_external_faces_geojson(
            face_geojson_path=input_faces_path,
            lot_id_col_in_faces=faces_lot_id_col,
            face_type_col=faces_type_col
        ):
            logger.warning(f"Não foi possível carregar o arquivo de faces externas de {input_faces_path}, mas a pipeline continuará.")
    else:
        logger.info("Nenhum arquivo de faces externas especificado ou encontrado.")

    all_lots_data = geojson_loader.get_all_lot_data(id_column=lot_id_column)
    if not all_lots_data:
        logger.info("Nenhum lote encontrado ou válido para processar.")
        return

    logger.info(f"Total de {len(all_lots_data)} lotes para processar.")
    overall_summary_data: List[Dict[str, Any]] = []

    # 4. Processar cada Lote
    for lot_geometry, lot_crs_str, lot_specific_params_dict, lot_id, lot_identified_faces in all_lots_data:
        logger.info(f"--- Iniciando processamento do Lote ID: {lot_id} ---")

        current_lot_params = AppParams(default_config_path=config_path)
        current_lot_params.update_for_lot(lot_specific_params_dict)
        if "zoning_parameters" not in current_lot_params.current_params:
            current_lot_params.current_params["zoning_parameters"] = {}
        current_lot_params.current_params["zoning_parameters"]["numlote"] = lot_id

        try:
            building_model_base = Building(
                lot_polygon=lot_geometry,
                params_manager=current_lot_params,
                lot_crs=lot_crs_str,
                shape_name="LoteBruto",
                identified_faces=lot_identified_faces # Passando as faces identificadas
            )
        except Exception as e:
            logger.error(f"Lote {lot_id}: Erro ao instanciar Building base: {e}", exc_info=True)
            overall_summary_data.append({"numlote": lot_id, "status": "Erro na criação do Building base", "error_message": str(e)})
            continue

        if not building_model_base.footprint_polygon or building_model_base.footprint_polygon.is_empty:
            logger.warning(f"Lote {lot_id}: Footprint base (após recuos iniciais) é inválido ou vazio. Pulando lote.")
            overall_summary_data.append({"numlote": lot_id, "status": "Footprint base inválido"})
            continue
        
        logger.info(f"Lote {lot_id}: Footprint base (lote com recuos) área: {building_model_base.footprint_polygon.area:.2f} m²")

        # 4c. Gerar Edificação Baseline (Ortogonal)
        baseline_building: Optional[Building] = None
        try:
            ortho_generator = OrthogonalGenerator(
                params_manager=current_lot_params,
                building_model=building_model_base
            )
            generated_ortho_shapes = ortho_generator.generate_shapes()
            if generated_ortho_shapes:
                orthogonal_shape = generated_ortho_shapes[0]
                baseline_building = ortho_generator.generate_building_from_shape(orthogonal_shape)
                if baseline_building and baseline_building.floors:
                    logger.info(f"Lote {lot_id}: Edificação Baseline Ortogonal gerada - Pav: {baseline_building.num_floors}, Alt: {baseline_building.total_height_m:.2f}m, FAR: {baseline_building.achieved_far:.3f}")
                    exporter.export_building_footprint_geojson(baseline_building, "baseline")
                    exporter.export_building_floors_geojson(baseline_building, "baseline")
                else:
                    logger.warning(f"Lote {lot_id}: Falha ao gerar pavimentos para a edificação baseline ortogonal.")
                    baseline_building = None
            else:
                logger.warning(f"Lote {lot_id}: Nenhuma forma ortogonal gerada.")
        except Exception as e:
            logger.error(f"Lote {lot_id}: Erro durante a geração da baseline ortogonal: {e}", exc_info=True)
            baseline_building = None

        # 4d. Gerar Edificação Otimizada (Best Shape)
        best_shape_building: Optional[Building] = None
        modeling_mode = current_lot_params.modeling_strategy.get("modeling_mode", "basic")

        if modeling_mode == "advanced":
            logger.info(f"Lote {lot_id}: Modo 'advanced' selecionado. Iniciando otimização de formas compostas...")
            try:
                optimizer = GridSearchOptimizer(
                    params_manager=current_lot_params,
                    building_model_base=building_model_base # Passa o mesmo building_model_base
                )
                best_shape_building = optimizer.run_optimization()

                if best_shape_building and best_shape_building.floors:
                    logger.info(f"Lote {lot_id}: Otimização concluída. Melhor forma encontrada: '{best_shape_building.shape_name}', "
                                f"Score: {optimizer.best_score:.2f}, FAR: {best_shape_building.achieved_far:.3f}, Altura: {best_shape_building.total_height_m:.2f}m")
                elif best_shape_building: # Tem forma mas não pavimentos
                     logger.warning(f"Lote {lot_id}: Melhor forma '{best_shape_building.shape_name}' encontrada, mas não gerou pavimentos.")
                     best_shape_building = None # Considerar como falha se não tem pavimentos
                else:
                    logger.warning(f"Lote {lot_id}: Otimizador não encontrou nenhuma solução 'best_shape' válida ou com pavimentos.")
            except Exception as e:
                logger.error(f"Lote {lot_id}: Erro durante a otimização Grid Search: {e}", exc_info=True)
                best_shape_building = None
        
        # Se o modo não for advanced, ou se a otimização falhou, usar baseline como best_shape
        if not best_shape_building:
            if modeling_mode == "advanced":
                logger.warning(f"Lote {lot_id}: Otimização no modo 'advanced' não produziu uma 'best_shape' válida. Usando baseline como fallback.")
            else: # Modo basic
                logger.info(f"Lote {lot_id}: Modo 'basic'. Usando baseline como 'best_shape'.")
            best_shape_building = baseline_building # Reutiliza o objeto baseline

        if best_shape_building and best_shape_building.floors : # Garante que tem pavimentos
            # Se best_shape_building é o mesmo objeto que baseline_building, precisamos
            # "renomeá-lo" para a exportação. Podemos criar uma cópia ou apenas mudar o sufixo.
            # Para evitar problemas, se for o mesmo objeto, não reexportamos os mesmos arquivos.
            if best_shape_building is baseline_building:
                logger.info(f"Lote {lot_id}: 'best_shape' é a mesma que 'baseline'. Arquivos de 'best_shape' não serão duplicados se já exportados como baseline.")
                # A lógica de exportação já nomeia os arquivos com "baseline" ou "best_shape"
                # Se quisermos arquivos separados mesmo sendo iguais, teríamos que fazer uma cópia profunda
                # do objeto Building e mudar seu shape_name/morphology_type antes de exportar.
                # Por ora, o Exporter vai gerar arquivos com sufixo "best_shape"
                exporter.export_building_footprint_geojson(best_shape_building, "best_shape")
                exporter.export_building_floors_geojson(best_shape_building, "best_shape")
            else: # Se best_shape_building é um objeto diferente (resultado real da otimização)
                exporter.export_building_footprint_geojson(best_shape_building, "best_shape")
                exporter.export_building_floors_geojson(best_shape_building, "best_shape")
        elif best_shape_building and not best_shape_building.floors:
             logger.warning(f"Lote {lot_id}: 'best_shape_building' foi definido mas não possui pavimentos. Não será exportado.")
        else: # Se best_shape_building for None (ex: baseline também falhou)
            logger.warning(f"Lote {lot_id}: Nenhuma edificação 'best_shape' (nem baseline) para exportar.")

        # 4e. Coletar dados para o resumo CSV
        lot_summary = {"numlote": lot_id, "status": "Processado"}
        if baseline_building and baseline_building.floors:
            lot_summary.update({
                "baseline_shape_name": baseline_building.shape_name,
                "baseline_morphology_type": baseline_building.morphology_type,
                "baseline_num_floors": baseline_building.num_floors,
                "baseline_total_height_m": round(baseline_building.total_height_m, 2),
                "baseline_total_built_area_m2": round(baseline_building.total_built_area_m2, 2),
                "baseline_achieved_far": round(baseline_building.achieved_far, 3),
                "baseline_achieved_lot_coverage": round(baseline_building.achieved_lot_coverage, 3),
                "baseline_is_compliant": baseline_building.is_compliant()[0],
                "baseline_violations": "; ".join(baseline_building.is_compliant()[1]),
            })
        else:
            lot_summary["status"] = "Erro na Baseline" if not lot_summary.get("error_message") else lot_summary["status"]
            lot_summary["baseline_error"] = "Baseline não gerada ou sem pavimentos"


        if best_shape_building and best_shape_building.floors:
            # Adicionar métricas da avaliação do otimizador, se disponíveis
            optimizer_metrics = next((item for item in optimizer.all_evaluated_solutions 
                                      if item.get("shape_name") == best_shape_building.shape_name and 
                                         item.get("morphology_type") == best_shape_building.morphology_type and
                                         abs(item.get("achieved_far", -1) - best_shape_building.achieved_far) < 0.001 and # Comparação de float
                                         abs(item.get("total_height_m", -1) - best_shape_building.total_height_m) < 0.01
                                     ), None) if modeling_mode == "advanced" and 'optimizer' in locals() else None

            lot_summary.update({
                "best_shape_name": best_shape_building.shape_name,
                "best_morphology_type": best_shape_building.morphology_type,
                "best_num_floors": best_shape_building.num_floors,
                "best_total_height_m": round(best_shape_building.total_height_m, 2),
                "best_total_built_area_m2": round(best_shape_building.total_built_area_m2, 2),
                "best_achieved_far": round(best_shape_building.achieved_far, 3),
                "best_achieved_lot_coverage": round(best_shape_building.achieved_lot_coverage, 3),
                "best_is_compliant": best_shape_building.is_compliant()[0],
                "best_violations": "; ".join(best_shape_building.is_compliant()[1]),
                "best_shape_score": optimizer_metrics.get("evaluation_score") if optimizer_metrics else (optimizer.best_score if 'optimizer' in locals() and best_shape_building is optimizer.best_building_solution else None),
                "best_shape_gen_params": str(optimizer_metrics.get("generation_params")) if optimizer_metrics else None,
            })
        elif modeling_mode == "advanced":
             lot_summary["best_shape_status"] = "Erro ou Nenhuma Best Shape Válida"
        # Se não for modo advanced, as colunas de best_shape podem ficar vazias ou repetir baseline

        overall_summary_data.append(lot_summary)
        logger.info(f"--- Processamento do Lote ID: {lot_id} concluído ---")

    # 5. Exportar Resumo CSV
    if overall_summary_data:
        exporter.export_summary_csv(overall_summary_data)
    else:
        logger.info("Nenhum dado de resumo para gerar CSV.")

    logger.info("Pipeline de Modelagem CogniCity concluída.")


if __name__ == "__main__":
    config_file_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "default.yaml")
    config_file_path = os.path.abspath(config_file_path)

    if not os.path.exists(config_file_path):
        alt_config_path = "config/default.yaml" 
        if os.path.exists(alt_config_path):
            config_file_path = alt_config_path
        else:
            logger.error(f"Arquivo de configuração principal não encontrado em {config_file_path} ou {alt_config_path}")
            logger.error("Verifique o caminho ou crie o arquivo 'config/default.yaml'.")
            exit()
            
    run_modeling_pipeline(config_path=config_file_path)

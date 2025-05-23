# cogniticy/dataio/exporter.py

import os
import logging
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, mapping # Importa mapping
from typing import List, Dict, Any, Optional

from cogniticy.core.model import Building, Floor # Importa Building e Floor
from cogniticy.core.params import AppParams # Importa AppParams

logger = logging.getLogger(__name__) # Configura logger

class Exporter:
    """
    Classe responsável por exportar os resultados da modelagem.
    """
    def __init__(self, params_manager: AppParams):
        self.output_dir: str = params_manager.simulation.get("output_directory", "output")
        self.project_name: str = params_manager.simulation.get("project_name", "cognicity_run")
        self.output_crs: str = params_manager.simulation.get("output_crs", "EPSG:4326")
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"Exporter inicializado. Saídas em: {self.output_dir}, CRS: {self.output_crs}")

    def _generate_filepath(self, lot_id: str, suffix: str, extension: str = "geojson") -> str:
        filename = f"{self.project_name}_{lot_id}_{suffix}.{extension}" if lot_id else f"{self.project_name}_{suffix}.{extension}"
        return os.path.join(self.output_dir, filename)

    def export_building_footprint_geojson(self, building: Building, file_type_suffix: str) -> Optional[str]:
        # Implementação de export_building_footprint_geojson (como definida anteriormente)
        if not building.footprint_polygon or building.footprint_polygon.is_empty:
            logger.warning(f"Lote {building.numlote}: Footprint '{building.shape_name}' vazio. Não exportado."); return None
        properties = building.get_building_properties_for_geojson()
        gdf = gpd.GeoDataFrame([properties], geometry=[building.footprint_polygon], crs=building.lot_crs)
        if building.lot_crs and building.lot_crs.lower() != self.output_crs.lower():
            try: gdf = gdf.to_crs(self.output_crs)
            except Exception as e: logger.error(f"Lote {building.numlote}: Falha ao reprojetar footprint: {e}. Exportando com CRS original.")
        filepath = self._generate_filepath(building.numlote, file_type_suffix)
        try: gdf.to_file(filepath, driver="GeoJSON"); logger.info(f"Lote {building.numlote}: Footprint '{building.shape_name}' exportado para {filepath}"); return filepath
        except Exception as e: logger.error(f"Lote {building.numlote}: Erro ao exportar footprint para {filepath}: {e}"); return None


    def export_building_floors_geojson(self, building: Building, file_type_suffix: str) -> Optional[str]:
        # Implementação de export_building_floors_geojson (como definida anteriormente)
        if not building.floors:
            logger.warning(f"Lote {building.numlote}: Edificação '{building.shape_name}' sem pavimentos."); return None
        features_data = []
        for floor_obj in building.floors:
            if floor_obj.geometry and not floor_obj.geometry.is_empty:
                props = floor_obj.get_properties_for_geojson()
                props['shape_name'] = building.shape_name; props['morphology_type'] = building.morphology_type
                props['achieved_far'] = round(building.achieved_far, 3) if building.achieved_far is not None else None
                props['total_height'] = round(building.total_height_m, 2) if building.total_height_m is not None else None
                props['efficiency'] = round(building.overall_efficiency, 3) if building.overall_efficiency is not None else (round(building.params_manager.architectural.get("target_efficiency",0.0),3) if building.params_manager.architectural.get("target_efficiency") is not None else None)
                features_data.append({"type": "Feature", "geometry": mapping(floor_obj.geometry), "properties": props})
        if not features_data: logger.warning(f"Lote {building.numlote}: Nenhum pavimento válido em '{building.shape_name}'."); return None
        gdf = gpd.GeoDataFrame.from_features(features_data, crs=building.lot_crs)
        if building.lot_crs and building.lot_crs.lower() != self.output_crs.lower():
            try: gdf = gdf.to_crs(self.output_crs)
            except Exception as e: logger.error(f"Lote {building.numlote}: Falha ao reprojetar pavimentos: {e}. Exportando com CRS original.")
        filepath = self._generate_filepath(building.numlote, f"{file_type_suffix}_floors")
        try: gdf.to_file(filepath, driver="GeoJSON"); logger.info(f"Lote {building.numlote}: Pavimentos de '{building.shape_name}' exportados para {filepath}"); return filepath
        except Exception as e: logger.error(f"Lote {building.numlote}: Erro ao exportar pavimentos para {filepath}: {e}"); return None

    def export_summary_csv(self, summary_data_list: List[Dict[str, Any]], filename_prefix: str = "summary_results") -> Optional[str]:
        # Implementação de export_summary_csv (como definida anteriormente)
        if not summary_data_list: logger.warning("Nenhum dado de resumo para CSV."); return None
        df = pd.DataFrame(summary_data_list)
        filepath = self._generate_filepath(lot_id="", suffix=filename_prefix, extension="csv")
        try: df.to_csv(filepath, index=False, encoding='utf-8-sig'); logger.info(f"Resumo CSV exportado para {filepath}"); return filepath
        except Exception as e: logger.error(f"Erro ao exportar resumo CSV para {filepath}: {e}"); return None

if __name__ == "__main__":
    # Exemplo de uso (como definido anteriormente)
    logging.basicConfig(level=logging.INFO)
    # MockAppParamsExporter e restante do teste como antes...
    logger.info("Executar testes do Exporter com mocks.")


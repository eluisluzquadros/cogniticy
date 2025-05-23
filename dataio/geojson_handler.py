# cogniticy/dataio/geojson_handler.py

import os
import logging
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Polygon, LineString, MultiLineString, shape
from shapely.wkt import loads as wkt_loads 
from typing import Dict, List, Tuple, Optional, Any
import json # Importa json para o exemplo

logger = logging.getLogger(__name__)

PARAMETER_COLUMN_MAPPING = {
    "numlote": ("zoning_parameters", "numlote"), "zot": ("zoning_parameters", "zot"),
    "codigo": ("zoning_parameters", "codigo"), "id_quarteirao": ("zoning_parameters", "id_quarterirao"),
    "ga": ("zoning_parameters", "ga"), "conceito": ("zoning_parameters", "conceito"),
    "max_height": ("normative_parameters", "max_height"), "max_far": ("normative_parameters", "max_far"),
    "max_lot_coverage": ("normative_parameters", "max_lot_coverage"),
    "gf_height": ("normative_parameters", "gf_floor_height"), 
    "uf_height": ("normative_parameters", "uf_floor_height"),
    "min_front_setback": ("normative_parameters", "min_front_setback"),
    "min_back_setback": ("normative_parameters", "min_back_setback"),
    "min_side_setback": ("normative_parameters", "min_side_setback"),
    "min_setback_start_floor": ("normative_parameters", "min_setback_start_floor"),
    "back_setback_percent": ("normative_parameters", "back_setback_percent"),
    "min_floor_area": ("architectural_parameters", "min_floor_area"),
    "min_unit_area": ("architectural_parameters", "min_unit_area"),
    "target_unit_area": ("architectural_parameters", "target_unit_area"),
    "core_area_fraction": ("architectural_parameters", "core_area_fraction"),
    "target_efficiency": ("architectural_parameters", "target_efficiency"),
    "parking_required": ("parking_parameters", "parking_required"),
}

LOT_EMBEDDED_FACE_GEOMETRY_COLUMNS = {
    "lados_frente_wkt": "front", "lados_fundos_wkt": "back", "lados_laterais_wkt": "side",
}

class GeoJSONHandler:
    def __init__(self, default_crs: str = "EPSG:31982", min_lot_area_m2: float = 10.0):
        # Implementação do construtor __init__ (como definida anteriormente)
        self.default_crs = default_crs
        self.min_lot_area_m2 = min_lot_area_m2
        self.lots_gdf: Optional[gpd.GeoDataFrame] = None
        self.external_faces_gdf: Optional[gpd.GeoDataFrame] = None 
        self.lot_errors: Dict[str, str] = {}

    def _parse_geometry_from_column(self, geom_data: Any) -> Optional[LineString | MultiLineString | Polygon]:
        # Implementação de _parse_geometry_from_column (como definida anteriormente)
        if isinstance(geom_data, (LineString, MultiLineString, Polygon)): return geom_data
        if isinstance(geom_data, str):
            try: return wkt_loads(geom_data)
            except Exception: pass
            try: 
                geom_dict = json.loads(geom_data)
                return shape(geom_dict)
            except Exception: return None
        if isinstance(geom_data, dict):
            try: return shape(geom_data)
            except Exception: return None
        return None

    def load_lots_geojson(self, geojson_path: str, id_column: str = "numlote") -> bool:
        # Implementação de load_lots_geojson (como definida anteriormente)
        logger.info(f"Carregando lotes de: {geojson_path}")
        try:
            lots_gdf = gpd.read_file(geojson_path)
            if lots_gdf.empty:
                logger.warning(f"Arquivo de lotes {geojson_path} está vazio."); self.lots_gdf = lots_gdf; return True
            current_crs_str = lots_gdf.crs.to_string().lower() if lots_gdf.crs else ""
            target_crs_str = self.default_crs.lower()
            if not lots_gdf.crs:
                logger.warning(f"CRS não definido para lotes, assumindo {self.default_crs}")
                lots_gdf.set_crs(self.default_crs, inplace=True, allow_override=True)
            elif current_crs_str != target_crs_str:
                logger.info(f"Convertendo CRS de lotes de {lots_gdf.crs} para {self.default_crs}")
                try: lots_gdf = lots_gdf.to_crs(self.default_crs)
                except Exception as e: logger.error(f"Falha ao converter CRS para lotes: {e}. Mantendo original.")
            try: lots_gdf['calculated_area_m2'] = lots_gdf.geometry.area
            except Exception as e: logger.error(f"Erro ao calcular área: {e}"); lots_gdf['calculated_area_m2'] = 0.0
            original_count = len(lots_gdf)
            lots_gdf = lots_gdf[lots_gdf['calculated_area_m2'] >= self.min_lot_area_m2].copy()
            if original_count - len(lots_gdf) > 0: logger.info(f"Excluídos {original_count - len(lots_gdf)} lotes pequenos.")
            if id_column not in lots_gdf.columns:
                logger.warning(f"Coluna ID '{id_column}' não encontrada. Usando índice."); lots_gdf[id_column] = lots_gdf.index.astype(str)
            else: lots_gdf[id_column] = lots_gdf[id_column].astype(str).fillna(f"ID_NULO_{pd.Series(lots_gdf.index).astype(str)}")
            self.lots_gdf = lots_gdf
            logger.info(f"Carregados {len(self.lots_gdf)} lotes válidos de {geojson_path}.")
            return True
        except Exception as e: logger.error(f"Erro crítico ao carregar lotes: {e}"); self.lots_gdf = None; return False

    def load_external_faces_geojson(self, face_geojson_path: str, lot_id_col_in_faces: str = "numlote", face_type_col: str = "tipo") -> bool:
        # Implementação de load_external_faces_geojson (como definida anteriormente)
        logger.info(f"Carregando faces externas de: {face_geojson_path}")
        if not os.path.exists(face_geojson_path):
            logger.warning(f"Arquivo de faces {face_geojson_path} não encontrado."); self.external_faces_gdf = None; return False
        try:
            faces_gdf = gpd.read_file(face_geojson_path)
            if faces_gdf.empty: logger.warning(f"Arquivo de faces {face_geojson_path} vazio."); self.external_faces_gdf = None; return True
            current_crs_str = faces_gdf.crs.to_string().lower() if faces_gdf.crs else ""
            target_crs_str = self.default_crs.lower()
            if not faces_gdf.crs:
                logger.warning(f"CRS não definido para faces, assumindo {self.default_crs}")
                faces_gdf.set_crs(self.default_crs, inplace=True, allow_override=True)
            elif current_crs_str != target_crs_str:
                logger.info(f"Convertendo CRS de faces de {faces_gdf.crs} para {self.default_crs}")
                try: faces_gdf = faces_gdf.to_crs(self.default_crs)
                except Exception as e: logger.error(f"Falha ao converter CRS para faces: {e}. Mantendo original.")
            if lot_id_col_in_faces not in faces_gdf.columns:
                logger.error(f"Coluna ID lote '{lot_id_col_in_faces}' não encontrada em faces."); self.external_faces_gdf = None; return False
            if face_type_col not in faces_gdf.columns:
                logger.error(f"Coluna tipo face '{face_type_col}' não encontrada em faces."); self.external_faces_gdf = None; return False
            faces_gdf[lot_id_col_in_faces] = faces_gdf[lot_id_col_in_faces].astype(str)
            self.external_faces_gdf = faces_gdf
            logger.info(f"Carregadas {len(self.external_faces_gdf)} faces externas de {face_geojson_path}.")
            return True
        except Exception as e: logger.error(f"Erro crítico ao carregar faces externas: {e}"); self.external_faces_gdf = None; return False
        
    def get_all_lot_data(self, id_column: str = "numlote") -> List[Tuple[Polygon, str, Dict[str, Any], str, Dict[str, List[LineString|MultiLineString]]]]:
        # Implementação de get_all_lot_data (como definida anteriormente)
        if self.lots_gdf is None or self.lots_gdf.empty: return []
        processed_lots_data = []
        lot_crs = self.lots_gdf.crs.to_string() if self.lots_gdf.crs else self.default_crs
        for index, lot_row in self.lots_gdf.iterrows():
            lot_id = str(lot_row.get(id_column, f"index_{index}"))
            lot_geometry_main = lot_row.geometry
            if not isinstance(lot_geometry_main, Polygon):
                logger.warning(f"Geometria lote {lot_id} não é Polígono: {type(lot_geometry_main)}. Pulando."); self.lot_errors[lot_id] = "Não é Polígono"; continue
            if lot_geometry_main.is_empty:
                logger.warning(f"Geometria lote {lot_id} vazia. Pulando."); self.lot_errors[lot_id] = "Geometria vazia"; continue
            lot_specific_params = self._extract_parameters_from_row(lot_row, lot_id)
            lot_faces = self._get_faces_for_lot_from_external_file(lot_id)
            if not any(lot_faces.values()):
                lot_faces_embedded = self._extract_embedded_face_geometries_from_row(lot_row, lot_id)
                if any(lot_faces_embedded.values()): lot_faces = lot_faces_embedded
                else: logger.debug(f"Lote {lot_id}: Nenhuma face (externa ou embutida) encontrada.")
            processed_lots_data.append((lot_geometry_main, lot_crs, lot_specific_params, lot_id, lot_faces))
        return processed_lots_data

    def _extract_parameters_from_row(self, lot_row: pd.Series, lot_id: str) -> Dict[str, Any]:
        # Implementação de _extract_parameters_from_row (como definida anteriormente)
        structured_params: Dict[str, Any] = {"zoning_parameters": {}, "normative_parameters": {}, "architectural_parameters": {}, "parking_parameters": {}}
        structured_params["zoning_parameters"]["numlote"] = lot_id
        for col_name, (cat, param_name) in PARAMETER_COLUMN_MAPPING.items():
            if col_name in lot_row and pd.notna(lot_row[col_name]):
                val = lot_row[col_name]
                try:
                    if param_name in ["max_height", "max_far", "max_lot_coverage", "gf_floor_height", "uf_floor_height", "min_front_setback", "min_back_setback", "min_side_setback", "back_setback_percent", "min_floor_area", "min_unit_area", "target_unit_area", "core_area_fraction", "target_efficiency"]:
                        val = float(val)
                        if param_name == "max_lot_coverage" and val > 1.0 and val <= 100.0: val /= 100.0
                    elif param_name == "min_setback_start_floor": val = int(val)
                    elif param_name == "parking_required": val = bool(val)
                except ValueError: logger.warning(f"Lote {lot_id}: Valor inválido '{val}' para '{col_name}'. Ignorando."); continue
                if cat not in structured_params: structured_params[cat] = {}
                structured_params[cat][param_name] = val
        return structured_params

    def _extract_embedded_face_geometries_from_row(self, lot_row: pd.Series, lot_id: str) -> Dict[str, List[LineString|MultiLineString]]:
        # Implementação de _extract_embedded_face_geometries_from_row (como definida anteriormente)
        extracted_faces: Dict[str, List[LineString|MultiLineString]] = {"front": [], "back": [], "side": []}
        for col_name, face_type in LOT_EMBEDDED_FACE_GEOMETRY_COLUMNS.items():
            if col_name in lot_row and pd.notna(lot_row[col_name]):
                face_geom_data = lot_row[col_name]; geoms_to_process = [face_geom_data] if not isinstance(face_geom_data, list) else face_geom_data
                for item_data in geoms_to_process:
                    parsed_geom = self._parse_geometry_from_column(item_data)
                    if parsed_geom and isinstance(parsed_geom, (LineString, MultiLineString)):
                        if face_type not in extracted_faces: extracted_faces[face_type] = []
                        if isinstance(parsed_geom, MultiLineString): extracted_faces[face_type].extend(list(parsed_geom.geoms))
                        else: extracted_faces[face_type].append(parsed_geom)
                    elif parsed_geom: logger.warning(f"Lote {lot_id}: Geometria face embutida '{col_name}' não é Linha: {type(parsed_geom)}.")
        return extracted_faces

    def _get_faces_for_lot_from_external_file(self, lot_id: str, lot_id_col: str = "numlote", type_col: str = "tipo") -> Dict[str, List[LineString|MultiLineString]]:
        # Implementação de _get_faces_for_lot_from_external_file (como definida anteriormente)
        lot_faces_map: Dict[str, List[LineString|MultiLineString]] = {"front": [], "back": [], "side": []}
        if self.external_faces_gdf is None or self.external_faces_gdf.empty: return lot_faces_map
        relevant_faces = self.external_faces_gdf[self.external_faces_gdf[lot_id_col] == str(lot_id)]
        if relevant_faces.empty: logger.debug(f"Lote {lot_id}: Nenhuma face externa."); return lot_faces_map
        for _, face_row in relevant_faces.iterrows():
            face_type_str = str(face_row.get(type_col, "")).lower().strip(); face_geom = face_row.geometry
            if not face_geom or face_geom.is_empty: continue
            cat = "front" if "frente" in face_type_str else "back" if "fundo" in face_type_str else "side" if "lateral" in face_type_str else ""
            if not cat: logger.warning(f"Lote {lot_id}: Tipo face externa desconhecido '{face_type_str}'."); continue
            if isinstance(face_geom, MultiLineString): lot_faces_map[cat].extend(list(face_geom.geoms))
            elif isinstance(face_geom, LineString): lot_faces_map[cat].append(face_geom)
        logger.debug(f"Lote {lot_id}: Faces externas: { {k: len(v) for k,v in lot_faces_map.items()} }")
        return lot_faces_map

if __name__ == "__main__":
    # Exemplo de uso (como definido anteriormente)
    logging.basicConfig(level=logging.INFO)
    # Teste com faces embutidas (criar test_lots_embedded_faces.geojson)
    # Teste com faces externas (criar test_external_faces.geojson e test_main_lots_for_external.geojson)
    logger.info("Executar testes do GeoJSONHandler com arquivos de exemplo.")


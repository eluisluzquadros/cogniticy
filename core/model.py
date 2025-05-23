# cogniticy/core/model.py

from typing import List, Optional, Dict, Any, Tuple
from shapely.geometry import Polygon, MultiPolygon, Point, LineString, MultiLineString
from shapely.validation import make_valid
import math
import logging # Importa logging

from .params import AppParams
from .geometry_utils import (
    calculate_polygon_area_m2, 
    apply_setbacks_to_polygon_with_identified_faces, 
    get_longest_edge_and_others,
    make_geometry_valid # Importa make_geometry_valid
)

logger = logging.getLogger(__name__) # Configura logger para este módulo

class Floor:
    """
    Representa um pavimento de uma edificação.
    """
    def __init__(self,
                 floor_number: int,
                 base_height: float,
                 floor_height_m: float,
                 geometry: Polygon,
                 lot_crs: Optional[str] = None,
                 has_vertical_setback: bool = False,
                 applied_back_setback_amount: float = 0.0,
                 applied_front_setback_amount: float = 0.0,
                 applied_side_setback_amount: float = 0.0):
        self.floor_number: int = floor_number
        self.floor_name: str = f"Pav. {floor_number}" if floor_number > 0 else "Térreo"
        self.base_height: float = base_height
        self.top_height: float = base_height + floor_height_m
        self.floor_height_m: float = floor_height_m
        
        self.geometry: Polygon = make_geometry_valid(geometry) if geometry and not geometry.is_empty else Polygon()
        self.lot_crs: Optional[str] = lot_crs
        
        self.floor_area_m2: float = calculate_polygon_area_m2(self.geometry, self.lot_crs) if self.geometry else 0.0
        
        self.has_vertical_setback: bool = has_vertical_setback
        self.applied_back_setback_amount: float = applied_back_setback_amount
        self.applied_front_setback_amount: float = applied_front_setback_amount
        self.applied_side_setback_amount: float = applied_side_setback_amount
        
        self.numlote: Optional[str] = None
        self.shape_name: Optional[str] = None
        self.morphology_type: Optional[str] = None
        self.efficiency: Optional[float] = None
        self.achieved_far_on_floor: Optional[float] = None # Nota: Este campo na saída final representa o FAR total do edifício
        self.building_total_height: Optional[float] = None

    def __repr__(self) -> str:
        return (f"Floor(num={self.floor_number}, name='{self.floor_name}', "
                f"base_h={self.base_height:.2f}m, top_h={self.top_height:.2f}m, "
                f"area={self.floor_area_m2:.2f}m²)")

    def get_properties_for_geojson(self) -> Dict[str, Any]:
        # Implementação da função get_properties_for_geojson (como definida anteriormente)
        return {
            "numlote": self.numlote,
            "floor_number": self.floor_number,
            "floor_name": self.floor_name,
            "base_height": round(self.base_height, 2),
            "top_height": round(self.top_height, 2),
            "floor_height": round(self.floor_height_m, 2),
            "has_setback": self.has_vertical_setback,
            "setback_amount": round(self.applied_back_setback_amount, 2), 
            "floor_area": round(self.floor_area_m2, 2),
            "shape_name": self.shape_name,
            "morphology_type": self.morphology_type,
            "efficiency": round(self.efficiency, 3) if self.efficiency is not None else None,
            "achieved_far": round(self.achieved_far_on_floor, 3) if self.achieved_far_on_floor is not None else None,
            "total_height": round(self.building_total_height, 2) if self.building_total_height is not None else None,
            "front_setback_applied": round(self.applied_front_setback_amount, 2),
            "side_setback_applied": round(self.applied_side_setback_amount, 2),
        }

class Building:
    """
    Representa uma edificação, composta por múltiplos pavimentos e sujeita a parâmetros urbanísticos.
    """
    def __init__(self,
                 lot_polygon: Polygon,
                 params_manager: AppParams,
                 lot_crs: Optional[str] = "EPSG:4326",
                 shape_name: str = "Desconhecida",
                 morphology_type: str = "CUSTOM",
                 identified_faces: Optional[Dict[str, List[LineString|MultiLineString]]] = None):
        # Implementação do construtor __init__ (como definida anteriormente, incluindo identified_faces)
        self.lot_polygon_original: Polygon = make_geometry_valid(lot_polygon) if lot_polygon and not lot_polygon.is_empty else Polygon()
        self.lot_crs: Optional[str] = lot_crs
        self.lot_area_m2: float = calculate_polygon_area_m2(self.lot_polygon_original, self.lot_crs) if self.lot_polygon_original else 0.0
        
        self.params_manager: AppParams = params_manager
        self.shape_name: str = shape_name
        self.morphology_type: str = morphology_type
        self.identified_faces: Dict[str, List[LineString|MultiLineString]] = identified_faces if identified_faces else {}

        self.floors: List[Floor] = []
        self.footprint_polygon: Optional[Polygon] = None
        
        self.total_built_area_m2: float = 0.0
        self.total_height_m: float = 0.0
        self.achieved_far: float = 0.0
        self.achieved_lot_coverage: float = 0.0
        self.num_floors: int = 0
        self.slenderness_ratio_achieved: Optional[float] = None
        self.overall_efficiency: Optional[float] = None

        self.max_height_param: float = params_manager.normative.get("max_height", 0.0)
        self.max_far_param: float = params_manager.normative.get("max_far", 0.0)
        self.max_lot_coverage_param: float = params_manager.normative.get("max_lot_coverage", 1.0)
        self.min_front_setback_param: float = params_manager.normative.get("min_front_setback", 0.0)
        self.min_back_setback_param: float = params_manager.normative.get("min_back_setback", 0.0)
        self.min_side_setback_param: float = params_manager.normative.get("min_side_setback", 0.0)
        self.gf_floor_height_param: float = params_manager.normative.get("gf_floor_height", 3.0)
        self.uf_floor_height_param: float = params_manager.normative.get("uf_floor_height", 3.0)
        self.min_setback_start_floor_param: int = params_manager.normative.get("min_setback_start_floor", 3)
        self.back_setback_percent_param: float = params_manager.normative.get("back_setback_percent", 0.0)
        self.numlote: str = params_manager.zoning.get("numlote", "LOTE_SEM_ID")
        self._initialize_base_footprint()


    def _initialize_base_footprint(self):
        # Implementação de _initialize_base_footprint (como definida anteriormente, priorizando identified_faces)
        if self.lot_polygon_original.is_empty or self.lot_area_m2 == 0:
            self.footprint_polygon = Polygon()
            return

        has_valid_identified_faces = False
        if self.identified_faces and any(self.identified_faces.values()):
            if self.identified_faces.get("front") or self.identified_faces.get("side") or self.identified_faces.get("back"): # Checa se alguma chave relevante existe
                has_valid_identified_faces = True
            else:
                logger.warning(f"Lote {self.numlote}: Faces identificadas fornecidas, mas sem tipos reconhecíveis (front, back, side). Tentando fallback.")
        
        if has_valid_identified_faces:
            logger.info(f"Lote {self.numlote}: Usando faces identificadas para aplicar recuos iniciais.")
            self.footprint_polygon = apply_setbacks_to_polygon_with_identified_faces(
                original_lot_polygon=self.lot_polygon_original,
                identified_faces=self.identified_faces,
                front_setback_val=self.min_front_setback_param,
                back_setback_val=self.min_back_setback_param,
                side_setback_val=self.min_side_setback_param
            )
            if self.footprint_polygon is None or self.footprint_polygon.is_empty:
                logger.warning(f"Lote {self.numlote}: Aplicação de recuos com faces identificadas resultou em geometria nula/vazia. Tentando fallback com buffer.")
                has_valid_identified_faces = False 

        if not has_valid_identified_faces:
            logger.warning(f"Lote {self.numlote}: Faces não identificadas ou falha ao usá-las. Usando buffer uniforme como fallback para recuos iniciais.")
            min_overall_setback = min(self.min_front_setback_param, self.min_back_setback_param, self.min_side_setback_param)
            if min_overall_setback > 1e-6: # Aplicar buffer apenas se o recuo for significativo
                self.footprint_polygon = self.lot_polygon_original.buffer(-min_overall_setback, cap_style='flat', join_style='mitre')
            else: # Se todos os recuos forem zero ou muito pequenos, usar o lote original
                self.footprint_polygon = self.lot_polygon_original
            logger.info(f"Lote {self.numlote}: Fallback - buffer uniforme de {min_overall_setback}m aplicado. Área resultante: {self.footprint_polygon.area if self.footprint_polygon else 'N/A'}")

        if self.footprint_polygon is None or self.footprint_polygon.is_empty:
            logger.error(f"Lote {self.numlote}: Footprint inicial resultou nulo ou vazio após todas as tentativas. Usando lote original sem recuos.")
            self.footprint_polygon = self.lot_polygon_original
        
        self.footprint_polygon = make_geometry_valid(self.footprint_polygon)
        if not isinstance(self.footprint_polygon, Polygon):
            logger.error(f"Lote {self.numlote}: Footprint final não é um Polígono após validação. Tipo: {type(self.footprint_polygon)}")
            self.footprint_polygon = Polygon()


    def generate_floors(self, custom_footprint: Optional[Polygon] = None) -> bool:
        # Implementação de generate_floors (como definida anteriormente, usando apply_setbacks_to_polygon_with_identified_faces para recuo vertical)
        self.floors = []
        current_height_m = 0.0
        current_built_area_m2 = 0.0
        
        base_geometry_for_floors = custom_footprint if custom_footprint and not custom_footprint.is_empty else self.footprint_polygon

        if not base_geometry_for_floors or base_geometry_for_floors.is_empty:
            logger.warning(f"Lote {self.numlote}: Geometria base para pavimentos é inválida ou vazia. Não é possível gerar pavimentos.")
            self._calculate_final_metrics()
            return False

        floor_num = 0
        
        while True:
            floor_specific_height = self.gf_floor_height_param if floor_num == 0 else self.uf_floor_height_param
            
            if current_height_m + floor_specific_height > self.max_height_param * 1.0001: # Pequena tolerância
                break

            current_floor_geometry = Polygon(base_geometry_for_floors.exterior.coords) 
            current_base_h = current_height_m
            
            has_vertical_setback_this_floor = False
            current_total_front_setback = self.min_front_setback_param
            current_total_back_setback = self.min_back_setback_param
            current_total_side_setback = self.min_side_setback_param

            if floor_num >= self.min_setback_start_floor_param and self.back_setback_percent_param > 0:
                has_vertical_setback_this_floor = True
                additional_back_setback = current_height_m * self.back_setback_percent_param
                current_total_back_setback += additional_back_setback
                
                temp_floor_geom = apply_setbacks_to_polygon_with_identified_faces(
                    original_lot_polygon=self.lot_polygon_original,
                    identified_faces=self.identified_faces,
                    front_setback_val=current_total_front_setback,
                    back_setback_val=current_total_back_setback,
                    side_setback_val=current_total_side_setback
                )
                
                if temp_floor_geom and not temp_floor_geom.is_empty:
                    current_floor_geometry = temp_floor_geom
                else:
                    logger.debug(f"Lote {self.numlote}, Pav {floor_num}: Recuo vertical resultou em geometria inválida. Parando.")
                    break 
            
            floor_area_m2 = calculate_polygon_area_m2(current_floor_geometry, self.lot_crs)

            if self.lot_area_m2 > 1e-6 and (current_built_area_m2 + floor_area_m2) / self.lot_area_m2 > self.max_far_param * 1.001:
                break
            
            min_allowed_floor_area = self.params_manager.architectural.get("min_floor_area", 1.0)
            if floor_area_m2 < min_allowed_floor_area :
                if floor_num > 0 or floor_area_m2 <= 0.01:
                    logger.debug(f"Lote {self.numlote}, Pav {floor_num}: Área ({floor_area_m2:.2f}m²) < mínima ({min_allowed_floor_area}m²). Parando.")
                    break

            new_floor = Floor(
                floor_number=floor_num, base_height=current_base_h, floor_height_m=floor_specific_height,
                geometry=current_floor_geometry, lot_crs=self.lot_crs,
                has_vertical_setback=has_vertical_setback_this_floor,
                applied_back_setback_amount=current_total_back_setback,
                applied_front_setback_amount=current_total_front_setback,
                applied_side_setback_amount=current_total_side_setback
            )
            self.floors.append(new_floor)
            current_built_area_m2 += floor_area_m2
            current_height_m += floor_specific_height
            floor_num += 1
            
        self._calculate_final_metrics()
        return len(self.floors) > 0

    def _calculate_final_metrics(self):
        # Implementação de _calculate_final_metrics (como definida anteriormente)
        if not self.floors:
            self.total_built_area_m2 = 0.0
            self.total_height_m = 0.0
            self.achieved_far = 0.0
            self.achieved_lot_coverage = 0.0
            self.num_floors = 0
            if self.footprint_polygon is None: self._initialize_base_footprint() 
            if self.footprint_polygon is None: self.footprint_polygon = Polygon()
            return

        self.total_built_area_m2 = sum(f.floor_area_m2 for f in self.floors)
        self.num_floors = len(self.floors)
        self.total_height_m = self.floors[-1].top_height if self.floors else 0.0

        if self.lot_area_m2 > 1e-6:
            self.achieved_far = self.total_built_area_m2 / self.lot_area_m2
            ground_floor_area = self.floors[0].floor_area_m2 if self.floors else 0.0
            self.achieved_lot_coverage = ground_floor_area / self.lot_area_m2
        else:
            self.achieved_far = 0.0
            self.achieved_lot_coverage = 0.0

        self.footprint_polygon = self.floors[0].geometry if self.floors and self.floors[0].geometry and not self.floors[0].geometry.is_empty else self.footprint_polygon
        if self.footprint_polygon is None: self.footprint_polygon = Polygon()

        if self.footprint_polygon and not self.footprint_polygon.is_empty and self.total_height_m > 0:
            obb = self.footprint_polygon.minimum_rotated_rectangle
            if obb and not obb.is_empty and isinstance(obb, Polygon):
                coords = list(obb.exterior.coords)
                if len(coords) > 1: 
                    edge_lengths = [Point(coords[i]).distance(Point(coords[i+1])) for i in range(len(coords)-1)]
                    if len(edge_lengths) >= 2:
                        dims = sorted(list(set(round(l, 5) for l in edge_lengths if l > 1e-6)))
                        if dims and dims[0] > 1e-6 :
                             min_dimension = dims[0]
                             self.slenderness_ratio_achieved = self.total_height_m / min_dimension
        
        target_efficiency_param = self.params_manager.architectural.get("target_efficiency")
        for floor in self.floors:
            floor.numlote = self.numlote
            floor.shape_name = self.shape_name
            floor.morphology_type = self.morphology_type
            floor.building_total_height = self.total_height_m
            if self.lot_area_m2 > 1e-6:
                 floor.achieved_far_on_floor = self.achieved_far
            if target_efficiency_param is not None: 
                floor.efficiency = target_efficiency_param
        if target_efficiency_param is not None:
            self.overall_efficiency = target_efficiency_param

    def get_building_properties_for_geojson(self) -> Dict[str, Any]:
        # Implementação da função get_building_properties_for_geojson (como definida anteriormente)
        return {
            "fid": f"{self.numlote}_{self.morphology_type}", "numlote": self.numlote,
            "zot": self.params_manager.zoning.get("zot"), "morphology_type": self.morphology_type,
            "shape_name": self.shape_name, "num_floors": self.num_floors,
            "total_height": round(self.total_height_m, 2), "achieved_far": round(self.achieved_far, 3),
            "efficiency": round(self.overall_efficiency, 3) if self.overall_efficiency is not None else None,
            "slenderness": round(self.slenderness_ratio_achieved, 2) if self.slenderness_ratio_achieved is not None else None,
            "max_far": self.max_far_param, "max_height": self.max_height_param,
            "max_lot_coverage": self.max_lot_coverage_param, "gf_height": self.gf_floor_height_param,
            "uf_height": self.uf_floor_height_param, "shape_ratio": None,
            "min_front_setback": self.min_front_setback_param, "min_back_setback": self.min_back_setback_param,
            "min_side_setback": self.min_side_setback_param, "report_url": None,
        }

    def is_compliant(self) -> Tuple[bool, List[str]]:
        # Implementação da função is_compliant (como definida anteriormente)
        violations = []
        compliant = True
        tolerance = 1.001 

        if self.total_height_m > self.max_height_param * tolerance:
            violations.append(f"Altura excedida: {self.total_height_m:.2f}m > {self.max_height_param:.2f}m")
            compliant = False
        if self.achieved_far > self.max_far_param * tolerance:
            violations.append(f"FAR excedido: {self.achieved_far:.3f} > {self.max_far_param:.3f}")
            compliant = False
        if self.achieved_lot_coverage > self.max_lot_coverage_param * tolerance :
            violations.append(f"Taxa de Ocupação excedida: {self.achieved_lot_coverage:.3f} > {self.max_lot_coverage_param:.3f}")
            compliant = False
        return compliant, violations

if __name__ == "__main__":
    # Implementação do bloco if __name__ == '__main__': (como definida anteriormente)
    logging.basicConfig(level=logging.INFO)
    
    class MockAppParamsBuilding: 
        def __init__(self):
            self.zoning = {"numlote": "TESTE001_MODEL", "zot": "ZC"}
            self.normative = {
                "max_height": 30.0, "max_far": 1.5, "max_lot_coverage": 0.6,
                "min_front_setback": 3.0, "min_back_setback": 2.0, "min_side_setback": 1.0,
                "gf_floor_height": 4.0, "uf_floor_height": 3.0,
                "min_setback_start_floor": 2, "back_setback_percent": 0.10
            }
            self.architectural = {"min_floor_area": 20.0, "target_efficiency": 0.8}
            self.simulation = {"output_crs": "EPSG:32722"}

    mock_params_building = MockAppParamsBuilding()
    lot_geom_utm = Polygon([(0,0), (20,0), (20,30), (0,30)])
    lot_crs_utm = "EPSG:32722"
    identified_lot_faces = {
        "front": [LineString([(0,30), (20,30)])], "back": [LineString([(20,0), (0,0)])],
        "side": [LineString([(0,0), (0,30)]), LineString([(20,30), (20,0)])]
    }
    logger.info("--- Testando Building com Faces Identificadas ---")
    building_with_faces = Building(lot_polygon=lot_geom_utm, params_manager=mock_params_building, lot_crs=lot_crs_utm, shape_name="OrtogonalComFaces", identified_faces=identified_lot_faces)
    logger.info(f"Footprint (com faces) área: {building_with_faces.footprint_polygon.area if building_with_faces.footprint_polygon else 'N/A'}")
    success_faces = building_with_faces.generate_floors()
    if success_faces: logger.info(f"Edifício (com faces) - Pav: {building_with_faces.num_floors}, Alt: {building_with_faces.total_height_m:.2f}m, FAR: {building_with_faces.achieved_far:.3f}")
    else: logger.warning("Falha ao gerar pavimentos para edifício com faces.")
    logger.info("\n--- Testes de Modelo (com lógica de faces) Concluídos ---")

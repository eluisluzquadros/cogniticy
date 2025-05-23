# cogniticy/core/geometry_utils.py

from typing import List, Tuple, Optional, Any, Dict
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, LineString, Point, box, MultiLineString, MultiPoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union, nearest_points, polygonize, orient
from shapely.validation import make_valid
import pyproj
import h3 # Importa a biblioteca h3
import logging # Importa logging

logger = logging.getLogger(__name__)

METRIC_CRS = "EPSG:32633" 

def ensure_geometry_crs(geometry: BaseGeometry, target_crs: str, source_crs: Optional[str] = None) -> BaseGeometry:
    # Implementação da função ensure_geometry_crs (como definida anteriormente)
    if source_crs is None:
        logger.warning("source_crs não fornecido para ensure_geometry_crs. Retornando geometria original.")
        return geometry
    if source_crs.lower() == target_crs.lower():
        return geometry
    try:
        project = pyproj.Transformer.from_crs(
            pyproj.CRS(source_crs),
            pyproj.CRS(target_crs),
            always_xy=True
        ).transform
        return transform(project, geometry)
    except Exception as e:
        logger.error(f"Erro ao transformar CRS de {source_crs} para {target_crs}: {e}")
        return geometry

def make_geometry_valid(geometry: BaseGeometry) -> BaseGeometry:
    # Implementação da função make_geometry_valid (como definida anteriormente)
    if not geometry:
        return geometry
    if geometry.is_valid:
        return geometry
    
    corrected_geometry = geometry.buffer(0)
    if not corrected_geometry.is_valid or corrected_geometry.is_empty or corrected_geometry.geom_type not in ['Polygon', 'MultiPolygon']:
        try:
            corrected_geometry = make_valid(geometry)
        except Exception as e:
            logger.warning(f"make_valid falhou após buffer(0): {e}. Retornando geometria original do buffer(0).")
            return geometry.buffer(0) if not geometry.buffer(0).is_empty else geometry

    if isinstance(geometry, (Polygon, MultiPolygon)) and not isinstance(corrected_geometry, (Polygon, MultiPolygon)):
        logger.warning(f"Validação alterou tipo de geometria de {geometry.geom_type} para {corrected_geometry.geom_type}.")
        if isinstance(make_valid(geometry), (Polygon, MultiPolygon)):
             return make_valid(geometry)
        return geometry.buffer(0) 
    return corrected_geometry

def calculate_polygon_area_m2(polygon: Optional[BaseGeometry], polygon_crs: Optional[str] = None) -> float:
    # Implementação da função calculate_polygon_area_m2 (como definida anteriormente)
    if not polygon or polygon.is_empty:
        return 0.0
    if not isinstance(polygon, (Polygon, MultiPolygon)):
        logger.warning(f"Tentando calcular área de geometria não poligonal: {polygon.geom_type}. Retornando 0.")
        return 0.0

    poly_to_calc = make_geometry_valid(polygon)
    if not isinstance(poly_to_calc, (Polygon, MultiPolygon)) or poly_to_calc.is_empty:
        return 0.0

    if polygon_crs:
        try:
            crs_obj = pyproj.CRS(polygon_crs)
            if crs_obj.is_geographic:
                centroid = poly_to_calc.centroid
                if centroid.is_empty: 
                    logger.warning("Centroide vazio para cálculo de UTM. Usando área no CRS geográfico (não em m²).")
                    return poly_to_calc.area 
                
                utm_zone_number = int((centroid.x + 180) / 6) + 1
                hemisphere_indicator = '6' if centroid.y >= 0 else '7'
                target_utm_crs_str = f"EPSG:32{hemisphere_indicator}{utm_zone_number:02d}"
                
                poly_metric = ensure_geometry_crs(poly_to_calc, target_utm_crs_str, polygon_crs)
                return poly_metric.area
            else:
                return poly_to_calc.area
        except Exception as e:
            logger.error(f"Erro ao processar CRS para cálculo de área ({polygon_crs}): {e}. Calculando área no CRS fornecido.")
            return poly_to_calc.area
    else:
        logger.warning("polygon_crs não fornecido para calculate_polygon_area_m2. Assumindo unidades métricas.")
        return poly_to_calc.area

def get_oriented_bounding_box(polygon: Polygon) -> Polygon:
    # Implementação da função get_oriented_bounding_box (como definida anteriormente)
    if not polygon or not isinstance(polygon, Polygon) or polygon.is_empty:
        return Polygon()
    valid_polygon = make_geometry_valid(polygon)
    if not isinstance(valid_polygon, Polygon) or valid_polygon.is_empty:
        return Polygon()
    return valid_polygon.minimum_rotated_rectangle

def get_polygon_edges(polygon: Polygon) -> List[LineString]:
    # Implementação da função get_polygon_edges (como definida anteriormente)
    if not isinstance(polygon, Polygon) or polygon.is_empty:
        return []
    exterior_coords = list(polygon.exterior.coords)
    edges = []
    for i in range(len(exterior_coords) - 1):
        edges.append(LineString([exterior_coords[i], exterior_coords[i+1]]))
    return edges

def get_longest_edge_and_others(polygon: Polygon) -> Tuple[Optional[LineString], int, List[LineString]]:
    # Implementação da função get_longest_edge_and_others (como definida anteriormente)
    edges = get_polygon_edges(polygon)
    if not edges:
        return None, -1, []
    longest_edge = max(edges, key=lambda edge: edge.length, default=None)
    if longest_edge is None:
        return None, -1, edges
    longest_edge_index = edges.index(longest_edge) if longest_edge in edges else -1
    return longest_edge, longest_edge_index, edges

def apply_setbacks_to_polygon_with_identified_faces(
    original_lot_polygon: Polygon,
    identified_faces: Dict[str, List[LineString|MultiLineString]],
    front_setback_val: float,
    back_setback_val: float,
    side_setback_val: float 
) -> Optional[Polygon]:
    # Implementação da função apply_setbacks_to_polygon_with_identified_faces (como definida anteriormente)
    if not original_lot_polygon or original_lot_polygon.is_empty:
        return None
    
    original_lot_polygon = make_geometry_valid(original_lot_polygon)
    if not isinstance(original_lot_polygon, Polygon): return None

    offset_lines: List[LineString] = []
    face_types_map = {"front": front_setback_val, "back": back_setback_val, "side": side_setback_val}

    for face_type, setback_value in face_types_map.items():
        if setback_value < 0: 
            logger.warning(f"Recuo negativo para {face_type} ({setback_value}). Ignorando offset.")
            continue # Não aplicar offset negativo, mas também não adicionar a linha original diretamente aqui
        
        # Se o recuo for zero, a face original define o limite.
        # Adicionamos as faces originais com recuo zero para ajudar a formar o polígono.
        if setback_value == 0.0:
            original_faces_for_type = identified_faces.get(face_type, [])
            for orig_face_geom in original_faces_for_type:
                if isinstance(orig_face_geom, LineString) and not orig_face_geom.is_empty:
                    offset_lines.append(orig_face_geom)
                elif isinstance(orig_face_geom, MultiLineString):
                    for line_part in orig_face_geom.geoms:
                        if isinstance(line_part, LineString) and not line_part.is_empty:
                            offset_lines.append(line_part)
            continue # Pula para a próxima face_type

        # Processamento para recuos > 0
        faces_list = identified_faces.get(face_type, [])
        for face_line_or_multi in faces_list:
            current_faces_to_offset = []
            if isinstance(face_line_or_multi, MultiLineString):
                current_faces_to_offset.extend(list(face_line_or_multi.geoms))
            elif isinstance(face_line_or_multi, LineString):
                current_faces_to_offset.append(face_line_or_multi)

            for face_line in current_faces_to_offset:
                if face_line.is_empty or face_line.length < 1e-6: # Pular linhas muito pequenas
                    continue
                
                try:
                    # Tenta offset para ambos os lados e escolhe o que está "dentro"
                    # O lado 'left' ou 'right' para o offset interno depende da orientação da linha da face.
                    # Uma heurística: o offset correto deve estar mais próximo do centroide do lote.
                    # Ou, um ponto no offset deve estar dentro do lote.
                    
                    # Garantir que a linha da face esteja orientada consistentemente (opcional, mas pode ajudar)
                    # face_line = orient(face_line) # orient() é para polígonos, não linhas diretamente.

                    offset_candidate_left = face_line.parallel_offset(setback_value, 'left', join_style=2)
                    offset_candidate_right = face_line.parallel_offset(setback_value, 'right', join_style=2)

                    chosen_offset_line = None
                    
                    # Testar qual offset está "dentro"
                    # Um ponto médio do offset deve estar dentro do polígono original (ou muito próximo)
                    # E o ponto médio do offset "errado" deve estar mais longe ou fora.
                    if not offset_candidate_left.is_empty:
                        pt_left = offset_candidate_left.interpolate(0.5, normalized=True)
                        if original_lot_polygon.contains(pt_left) or original_lot_polygon.touches(pt_left):
                            chosen_offset_line = offset_candidate_left
                    
                    if not chosen_offset_line and not offset_candidate_right.is_empty: # Se o esquerdo não foi escolhido
                        pt_right = offset_candidate_right.interpolate(0.5, normalized=True)
                        if original_lot_polygon.contains(pt_right) or original_lot_polygon.touches(pt_right):
                            chosen_offset_line = offset_candidate_right
                    
                    # Se ambos ou nenhum foi escolhido, pode haver um problema ou caso complexo.
                    if not chosen_offset_line and not offset_candidate_left.is_empty and not offset_candidate_right.is_empty:
                        logger.debug(f"Offset ambíguo para face {face_type}. Lote: {original_lot_polygon.centroid.wkt}. Face: {face_line.wkt}")
                        # Fallback mais simples: escolher o que está mais próximo do centroide do lote
                        pt_left = offset_candidate_left.interpolate(0.5, normalized=True)
                        pt_right = offset_candidate_right.interpolate(0.5, normalized=True)
                        lot_centroid = original_lot_polygon.centroid
                        if lot_centroid.distance(pt_left) < lot_centroid.distance(pt_right):
                            chosen_offset_line = offset_candidate_left
                        else:
                            chosen_offset_line = offset_candidate_right
                    
                    if chosen_offset_line and not chosen_offset_line.is_empty:
                        if isinstance(chosen_offset_line, LineString):
                             offset_lines.append(chosen_offset_line)
                        elif isinstance(chosen_offset_line, MultiLineString):
                             offset_lines.extend(l for l in chosen_offset_line.geoms if isinstance(l, LineString) and not l.is_empty)
                    else:
                        logger.warning(f"Offset para face {face_type} (comprimento {face_line.length:.2f}) resultou em geometria vazia ou não foi escolhido. Setback: {setback_value}")

                except Exception as e:
                    logger.error(f"Erro ao aplicar parallel_offset para face {face_type} (comprimento {face_line.length:.2f}): {e}")

    if not offset_lines:
        logger.warning("Nenhuma linha de offset foi gerada (ou todas eram recuo zero e não formaram um polígono). Não é possível criar polígono de recuo.")
        # Se todos os recuos fossem zero, o polígono original seria o resultado.
        # Isso é tratado implicitamente se offset_lines ficar vazio e polygonize falhar.
        # Se houver uma mistura de recuos zero e positivos, as linhas originais com recuo zero
        # devem ajudar a fechar o polígono com as linhas offsetadas.
        if front_setback_val == 0 and back_setback_val == 0 and side_setback_val == 0:
            return original_lot_polygon
        return None # Ou um fallback mais robusto

    try:
        list_of_polygons = list(polygonize(offset_lines))
    except Exception as e:
        logger.error(f"Erro durante polygonize: {e}")
        return None

    if not list_of_polygons:
        logger.warning("Polygonize não retornou polígonos. Verifique se as linhas de offset formam um anel fechado.")
        # Tentar unir as linhas e ver se forma um anel? unary_union(offset_lines).is_ring
        # Se as linhas não se fecham, polygonize falha.
        return None

    largest_valid_polygon: Optional[Polygon] = None
    max_area = 0.0
    for poly_candidate in list_of_polygons:
        if isinstance(poly_candidate, Polygon) and not poly_candidate.is_empty:
            # Orientar o polígono para garantir consistência (exterior anti-horário)
            poly_oriented = orient(poly_candidate, sign=1.0) # 1.0 para anti-horário
            valid_poly = make_geometry_valid(poly_oriented)
            
            if isinstance(valid_poly, Polygon) and not valid_poly.is_empty:
                # Considerar apenas polígonos que estão (principalmente) dentro do lote original
                # Uma pequena área fora pode ser aceitável devido a imprecisões do offset.
                # Usar interseção garante que o resultado final esteja dentro.
                intersected_with_lot = valid_poly.intersection(original_lot_polygon)
                
                # Se a interseção resultar em MultiPolygon, pegar o maior
                if isinstance(intersected_with_lot, MultiPolygon):
                    if not intersected_with_lot.is_empty:
                        intersected_with_lot = max(intersected_with_lot.geoms, key=lambda p: p.area)
                    else: continue # MultiPolygon vazio
                
                if isinstance(intersected_with_lot, Polygon) and not intersected_with_lot.is_empty:
                    current_area = intersected_with_lot.area
                    if current_area > max_area:
                        max_area = current_area
                        largest_valid_polygon = intersected_with_lot
    
    if largest_valid_polygon:
        return make_geometry_valid(largest_valid_polygon)
    else:
        logger.warning("Nenhum polígono válido encontrado após polygonize e interseção com o lote original.")
        return None


def polygon_to_h3_cells(polygon: Polygon, resolution: int, polygon_crs: Optional[str] = "EPSG:4326") -> List[str]:
    # Implementação da função polygon_to_h3_cells (como definida anteriormente)
    if not polygon or polygon.is_empty or not isinstance(polygon, Polygon):
        return []
    poly_for_h3 = make_geometry_valid(polygon)
    if not isinstance(poly_for_h3, Polygon) or poly_for_h3.is_empty: return []

    if polygon_crs and polygon_crs.upper() != "EPSG:4326":
        poly_for_h3 = ensure_geometry_crs(poly_for_h3, "EPSG:4326", polygon_crs)
    
    exterior_coords_lng_lat = list(poly_for_h3.exterior.coords)
    exterior_coords_lat_lng = [[pt[1], pt[0]] for pt in exterior_coords_lng_lat]
    holes_lat_lng = []
    for interior in poly_for_h3.interiors:
        interior_coords_lng_lat = list(interior.coords)
        holes_lat_lng.append([[pt[1], pt[0]] for pt in interior_coords_lng_lat])

    geojson_like_geometry = {
        "type": "Polygon",
        "coordinates": [exterior_coords_lat_lng] + holes_lat_lng
    }
    try:
        if hasattr(h3, 'polygon_to_cells'): # h3 v4+
            return list(h3.polygon_to_cells(geojson_like_geometry, resolution))
        elif hasattr(h3, 'polyfill'): # h3 v3
            return list(h3.polyfill(geojson_like_geometry, resolution, geo_json_conformant=True))
        else:
            logger.error("Nenhum método de preenchimento H3 compatível encontrado.")
            return []
    except Exception as e:
        logger.error(f"ERRO ao converter polígono para H3: {e}")
        return []

def h3_cells_to_polygon(h3_cells: List[str]) -> Optional[Polygon | MultiPolygon]:
    # Implementação da função h3_cells_to_polygon (como definida anteriormente)
    if not h3_cells: return None
    polygons = []
    for cell_id in h3_cells:
        try:
            if hasattr(h3, 'cell_to_boundary'): 
                 boundary_lat_lng = h3.cell_to_boundary(cell_id, geo_json=True)
            elif hasattr(h3, 'h3_to_geo_boundary'): 
                 boundary_lat_lng = h3.h3_to_geo_boundary(cell_id, geo_json=True)
            else:
                logger.error("Nenhum método H3 para obter limite da célula encontrado.")
                continue
            polygons.append(Polygon(boundary_lat_lng))
        except Exception as e:
            logger.error(f"Erro ao converter célula H3 {cell_id} para geometria: {e}")
            continue
            
    if not polygons: return None
    unified_geometry = unary_union(polygons)
    return make_geometry_valid(unified_geometry)

if __name__ == '__main__':
    # Implementação do bloco if __name__ == '__main__': (como definida anteriormente)
    logging.basicConfig(level=logging.DEBUG) 
    logger.info("--- Testando Funções de Geometria (com apply_setbacks_to_polygon_with_identified_faces) ---")

    example_lot_poly = Polygon([(0, 0), (0, 30), (20, 30), (20, 0), (0, 0)])
    logger.info(f"Polígono do Lote de Exemplo: {example_lot_poly.wkt}")

    identified_faces_test = {
        "front": [LineString([(0, 30), (20, 30)])],
        "back": [LineString([(20, 0), (0, 0)])], 
        "side": [LineString([(0, 0), (0, 30)]), LineString([(20, 30), (20, 0)])] 
    }
    
    front_s, back_s, side_s = 3.0, 2.0, 1.0
    logger.info(f"Aplicando recuos: Frente={front_s}, Fundos={back_s}, Lateral={side_s}")

    setback_polygon_from_faces = apply_setbacks_to_polygon_with_identified_faces(
        original_lot_polygon=example_lot_poly,
        identified_faces=identified_faces_test,
        front_setback_val=front_s,
        back_setback_val=back_s,
        side_setback_val=side_s
    )

    if setback_polygon_from_faces and not setback_polygon_from_faces.is_empty:
        logger.info(f"Polígono com recuo (de faces identificadas): {setback_polygon_from_faces.wkt}")
        logger.info(f"Área do polígono com recuo: {setback_polygon_from_faces.area:.2f} m²")
        expected_area = (20 - 2*side_s) * (30 - front_s - back_s)
        logger.info(f"Área esperada (para retângulo): {expected_area:.2f} m²")
        if abs(setback_polygon_from_faces.area - expected_area) < 1e-1: 
            logger.info("Área do recuo com faces identificadas está DENTRO da tolerância esperada.")
        else:
            logger.warning(f"Área do recuo com faces identificadas ({setback_polygon_from_faces.area:.2f}) DIFERE da esperada ({expected_area:.2f}).")
    else:
        logger.error("Falha ao aplicar recuos com faces identificadas.")
    logger.info("\n--- Testes de Geometria (com faces) Concluídos ---")

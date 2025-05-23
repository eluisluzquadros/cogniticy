from shapely.geometry import shape, Point, Polygon, mapping
from typing import List, Dict, Any, Union
import h3


class SpatialGridAllocator:
    """
    Responsável por gerar a malha H3 sobre o polígono do lote
    e fornecer pontos para alocação morfológica com formas atômicas.
    """
    
    def __init__(self, resolution: int = 10):
        """
        Args:
            resolution (int): resolução do H3 (quanto maior, menor a célula).
        """
        self.resolution = resolution
    
    def get_h3_cells(self, polygon: Union[Polygon, Dict[str, Any]]) -> List[str]:
        """
        Retorna os índices H3 que cobrem o polígono dado.
        
        Args:
            polygon (Polygon or Dict): polígono do lote (em coordenadas WGS84).
                Pode ser um objeto Polygon ou um GeoJSON dict.
        
        Returns:
            List[str]: lista de índices H3 dentro do polígono.
        """
        # Se for um dicionário GeoJSON, converter para polígono Shapely
        if isinstance(polygon, dict):
            # Processar como GeoJSON
            if 'geometry' in polygon:
                # Se for um Feature GeoJSON
                polygon = shape(polygon['geometry'])
            else:
                # Se for um Geometry GeoJSON
                polygon = shape(polygon)
        
        # Converter para formato GeoJSON aceito pelo h3
        geojson_poly = mapping(polygon)
        
        # Verificar se estamos usando h3 v3 ou v4
        if hasattr(h3, 'polygon_to_cells'):
            # h3 v4
            return h3.polygon_to_cells(geojson_poly, self.resolution)
        elif hasattr(h3, 'polyfill'):
            # h3 v3
            return h3.polyfill(geojson_poly, self.resolution)
        else:
            # Fallback para método geo_to_h3
            # Obter os vértices externos do polígono
            exterior_coords = list(polygon.exterior.coords)
            # Converter para formato esperado pelo h3
            geo_boundary = {'type': 'Polygon', 'coordinates': [exterior_coords]}
            
            # Tenta diferentes métodos, dependendo da versão do h3
            try:
                # Tenta como h3 v3 alternativo
                return h3.polyfill(geo_boundary, self.resolution)
            except (AttributeError, TypeError):
                try:
                    # Tenta como h3 v4 usando geo_to_h3shape
                    if hasattr(h3, 'geo_to_h3shape') and hasattr(h3, 'h3shape_to_cells'):
                        h3_shape = h3.geo_to_h3shape(geo_boundary)
                        return h3.h3shape_to_cells(h3_shape, self.resolution)
                except Exception:
                    raise ValueError("Não foi possível converter o polígono para células H3. Verifique a versão da biblioteca h3.")
            
            raise ValueError("Métodos polygon_to_cells ou polyfill não encontrados na biblioteca h3.")
    
    def generate_grid_centroids(self, polygon: Union[Polygon, Dict[str, Any]]) -> List[Point]:
        """
        Retorna os centroides (Point) das células H3 que estão
        dentro do polígono fornecido.
        
        Args:
            polygon (Polygon or Dict): polígono do lote.
        
        Returns:
            List[Point]: pontos centroides de células válidas.
        """
        # Converter para Shapely Polygon se for um dict
        if isinstance(polygon, dict):
            if 'geometry' in polygon:
                polygon_obj = shape(polygon['geometry'])
            else:
                polygon_obj = shape(polygon)
        else:
            polygon_obj = polygon
            
        h3_cells = self.get_h3_cells(polygon)
        centroids = []
        
        # Verificar se estamos usando h3 v3 ou v4
        h3_to_geo_func = None
        if hasattr(h3, 'h3_to_geo'):
            h3_to_geo_func = h3.h3_to_geo
        elif hasattr(h3, 'cell_to_latlng'):
            h3_to_geo_func = h3.cell_to_latlng
        else:
            raise ValueError("Função para converter H3 para coordenadas geográficas não encontrada.")
        
        for h in h3_cells:
            lat, lng = h3_to_geo_func(h)
            pt = Point(lng, lat)
            if pt.within(polygon_obj):
                centroids.append(pt)
        
        return centroids
    
    def estimate_unit_capacity(self, polygon: Union[Polygon, Dict[str, Any]], unit_area_m2: float) -> int:
        """
        Estima a quantidade de unidades que cabem no polígono com base em área mínima.
        
        Args:
            polygon (Polygon or Dict): polígono do lote.
            unit_area_m2 (float): área mínima de cada unidade (m²).
        
        Returns:
            int: número estimado de unidades.
        """
        # Converter para Shapely Polygon se for um dict
        if isinstance(polygon, dict):
            if 'geometry' in polygon:
                polygon = shape(polygon['geometry'])
            else:
                polygon = shape(polygon)
                
        total_area = polygon.area
        if unit_area_m2 <= 0:
            raise ValueError("Área mínima da unidade deve ser maior que zero.")
        
        return int(total_area // unit_area_m2)
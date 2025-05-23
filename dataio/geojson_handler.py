"""
Módulo io/geojson_handler.py
Este módulo contém funções para processamento e manipulação de arquivos GeoJSON,
leitura de lotes e faces, e preparação de dados para o sistema MORPHOMAX.
"""

import os
import logging
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Polygon, LineString, MultiLineString, GeometryCollection
from typing import Dict, List, Tuple, Optional, Any

from core.params import BuildingParameters

logger = logging.getLogger(__name__)

class GeoJSONHandler:
    """
    Classe para manipulação de arquivos GeoJSON, incluindo leitura, validação
    e agregação de lotes e faces para o MORPHOMAX.
    """
    
    def __init__(self, min_lot_area: float = 200.0, crs: str = "EPSG:31982"):
        """
        Inicializa o manipulador GeoJSON.
        
        Args:
            min_lot_area: Área mínima do lote para processamento (m²)
            crs: Sistema de coordenadas de referência para os dados
        """
        self.min_lot_area = min_lot_area
        self.crs = crs
        
        # Armazenar dados carregados
        self.lots_gdf = None
        self.faces_gdf = None
        
        # Registro de erros por lote
        self.lot_errors = {}
    
    def load_lots(self, path: str) -> gpd.GeoDataFrame:
        """
        Carrega o GeoDataFrame de lotes a partir do arquivo.
        
        Args:
            path: Caminho para o arquivo GeoJSON de lotes
            
        Returns:
            GeoDataFrame com lotes e seus parâmetros
        """
        logger.info(f"Carregando lotes de: {path}")
        
        try:
            # Carregar GeoJSON com geopandas
            lots_gdf = gpd.read_file(path)
            
            # Garantir sistema de coordenadas correto
            if lots_gdf.crs is None:
                logger.warning(f"CRS não definido para lotes, assumindo {self.crs}")
                lots_gdf.set_crs(self.crs, inplace=True)
            elif lots_gdf.crs != self.crs:
                logger.info(f"Convertendo CRS de lotes de {lots_gdf.crs} para {self.crs}")
                lots_gdf = lots_gdf.to_crs(self.crs)
            
            # Calcular área em m² para filtro
            lots_gdf['area_m2'] = lots_gdf.geometry.area
            
            # Filtrar lotes muito pequenos
            filtered_lots = lots_gdf[lots_gdf['area_m2'] >= self.min_lot_area].copy()
            
            # Registrar exclusões
            excluded_count = len(lots_gdf) - len(filtered_lots)
            if excluded_count > 0:
                logger.info(f"Excluídos {excluded_count} lotes com área < {self.min_lot_area}m²")
            
            # Armazenar o GeoDataFrame filtrado
            self.lots_gdf = filtered_lots
            
            logger.info(f"Carregados {len(filtered_lots)} lotes válidos")
            return filtered_lots
            
        except Exception as e:
            logger.error(f"Erro ao carregar lotes: {e}")
            self.lots_gdf = None
            raise
    
    def load_faces(self, path: str) -> gpd.GeoDataFrame:
        """
        Carrega o GeoDataFrame de faces a partir do arquivo.
        
        Args:
            path: Caminho para o arquivo GeoJSON de faces
            
        Returns:
            GeoDataFrame com faces dos lotes
        """
        logger.info(f"Carregando faces de: {path}")
        
        try:
            # Carregar GeoJSON com geopandas
            faces_gdf = gpd.read_file(path)
            
            # Garantir sistema de coordenadas correto
            if faces_gdf.crs is None:
                logger.warning(f"CRS não definido para faces, assumindo {self.crs}")
                faces_gdf.set_crs(self.crs, inplace=True)
            elif faces_gdf.crs != self.crs:
                logger.info(f"Convertendo CRS de faces de {faces_gdf.crs} para {self.crs}")
                faces_gdf = faces_gdf.to_crs(self.crs)
            
            # Calcular orientação das faces
            faces_gdf = self._calculate_face_orientation(faces_gdf)
            
            # Armazenar o GeoDataFrame de faces
            self.faces_gdf = faces_gdf
            
            logger.info(f"Carregadas {len(faces_gdf)} faces")
            return faces_gdf
            
        except Exception as e:
            logger.error(f"Erro ao carregar faces: {e}")
            self.faces_gdf = None
            raise
    
    def _calculate_face_orientation(self, faces_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Calcula a orientação (ângulo) para cada face.
        
        Args:
            faces_gdf: DataFrame com as faces dos lotes
            
        Returns:
            DataFrame com orientação calculada para cada face
        """
        # Criar uma cópia para evitar modificar o original durante iteração
        faces_copy = faces_gdf.copy()
        
        # Função para calcular o ângulo de orientação para uma LineString
        def get_orientation(geometry):
            if isinstance(geometry, LineString):
                x1, y1 = geometry.coords[0]
                x2, y2 = geometry.coords[-1]
                angle_rad = np.arctan2(y2 - y1, x2 - x1)
                angle_deg = np.degrees(angle_rad)
                return angle_deg
            elif isinstance(geometry, MultiLineString):
                # Usar a primeira LineString da MultiLineString
                if len(geometry.geoms) > 0:
                    line = geometry.geoms[0]
                    return get_orientation(line)
            return 0.0
        
        # Calcular orientação para cada face
        faces_copy['orientation'] = faces_copy['geometry'].apply(get_orientation)
        
        return faces_copy
    
    def process_lot(self, lot_id: str) -> Tuple[Optional[BuildingParameters], Dict]:
        """
        Processa um lote específico para criar parâmetros de construção.
        
        Args:
            lot_id: ID do lote a processar
            
        Returns:
            Tupla (building_params, lot_data) ou (None, error_dict) se falhar
        """
        try:
            # Verificar se temos dados carregados
            if self.lots_gdf is None or self.faces_gdf is None:
                raise ValueError("Lotes e faces devem ser carregados antes de processar")
            
            # Buscar lote no GeoDataFrame
            lot_rows = self.lots_gdf[self.lots_gdf['numlote'] == lot_id]
            
            if len(lot_rows) == 0:
                raise ValueError(f"Lote {lot_id} não encontrado nos dados")
            elif len(lot_rows) > 1:
                logger.warning(f"Múltiplas entradas para lote {lot_id}. Usando a primeira.")
            
            # Obter a primeira linha correspondente
            lot_row = lot_rows.iloc[0]
            
            # Extrair parâmetros do lote
            lot_data = self._extract_lot_parameters(lot_row)
            
            # Obter faces deste lote
            lot_faces = self._get_lot_faces(lot_id)
            
            # Criar objeto BuildingParameters
            building_params = BuildingParameters(
                lot_polygon=lot_row.geometry,
                faces=lot_faces,
                config=lot_data
            )
            
            # Adicionar faces_data para possível carregamento posterior
            building_params.faces_data = self.faces_gdf[self.faces_gdf['numlote'] == lot_id]
            
            return building_params, lot_data
            
        except Exception as e:
            logger.error(f"Erro ao processar lote {lot_id}: {e}")
            self.lot_errors[lot_id] = str(e)
            return None, {"error": str(e)}
    
    def _extract_lot_parameters(self, lot_row: pd.Series) -> Dict:
        """
        Extrai e valida parâmetros de um lote.
        
        Args:
            lot_row: Linha do GeoDataFrame com dados do lote
            
        Returns:
            Dicionário com parâmetros validados
        """
        # Extrair ID do lote
        lot_id = lot_row.get('numlote', str(lot_row.name))
        
        # Inicializar dicionário de configuração
        config = {}
        
        # Parâmetros básicos de identificação
        config['numlote'] = lot_id
        config['zot'] = lot_row.get('zot', None)
        config['id_quarteirao'] = lot_row.get('id_quarteirao', None)
        
        # Parâmetros urbanísticos com validação
        self._extract_numeric_param(config, lot_row, 'max_far', default=4.0)
        self._extract_numeric_param(config, lot_row, 'max_height', default=60.0)
        self._extract_numeric_param(config, lot_row, 'max_lot_coverage', default=0.8)
        
        # Parâmetros de pavimento com validação
        self._extract_numeric_param(config, lot_row, 'min_floor_ratio', default=200.0)
        self._extract_numeric_param(config, lot_row, 'gf_height', default=4.5)
        self._extract_numeric_param(config, lot_row, 'uf_height', default=3.0)
        self._extract_numeric_param(config, lot_row, 'min_setback_start_floor', default=4, as_int=True)
        
        # Parâmetros de recuo com validação
        self._extract_numeric_param(config, lot_row, 'min_front_setback', default=0.0)
        self._extract_numeric_param(config, lot_row, 'min_back_setback', default=0.0)
        self._extract_numeric_param(config, lot_row, 'min_side_setback', default=0.0)
        self._extract_numeric_param(config, lot_row, 'back_setback_percent', default=0.18)
        
        # Parâmetros de morfologia com validação
        self._extract_numeric_param(config, lot_row, 'morphology_type', default=1, as_int=True)
        self._extract_numeric_param(config, lot_row, 'shape_ratio', default=0.35)
        
        return config
    
    def _extract_numeric_param(self, config: Dict, row: pd.Series, param_name: str, 
                              default: float, as_int: bool = False) -> None:
        """
        Extrai um parâmetro numérico com validação.
        
        Args:
            config: Dicionário de configuração a atualizar
            row: Linha do DataFrame a processar
            param_name: Nome do parâmetro
            default: Valor padrão se não encontrado ou inválido
            as_int: Se True, converte para inteiro
        """
        try:
            if param_name in row and row[param_name] is not None:
                value = row[param_name]
                
                # Converter para número
                if as_int:
                    value = int(value)
                else:
                    value = float(value)
                
                # Conversão específica para max_lot_coverage (percentual para decimal)
                if param_name == 'max_lot_coverage' and value > 1:
                    value /= 100.0
                
                config[param_name] = value
            else:
                config[param_name] = default
                
        except (ValueError, TypeError):
            logger.warning(f"Valor inválido para {param_name}: {row.get(param_name)}. Usando padrão: {default}")
            config[param_name] = default
    
    def _get_lot_faces(self, lot_id: str) -> Dict:
        """
        Obtém as faces de um lote agrupadas por tipo.
        
        Args:
            lot_id: ID do lote a processar
            
        Returns:
            Dicionário com faces por tipo
        """
        # Filtrar as faces para este lote
        lot_faces = self.faces_gdf[self.faces_gdf['numlote'] == lot_id]
        
        # Criar um dicionário para armazenar faces por tipo
        faces_dict = {}
        
        # Agrupar faces por tipo
        for _, face_row in lot_faces.iterrows():
            face_type = face_row.get('tipo', None)
            if face_type:
                # Converter 'lateral' para 'laterais' para manter compatibilidade
                if face_type == 'lateral':
                    if 'laterais' not in faces_dict:
                        faces_dict['laterais'] = []
                    faces_dict['laterais'].append(face_row.geometry)
                else:
                    faces_dict[face_type] = face_row.geometry
        
        return faces_dict
    
    def get_lot_ids(self) -> List[str]:
        """
        Retorna a lista de IDs de lotes disponíveis.
        
        Returns:
            Lista de IDs de lotes
        """
        if self.lots_gdf is None:
            return []
        
        if 'numlote' in self.lots_gdf.columns:
            return self.lots_gdf['numlote'].unique().tolist()
        else:
            return [str(idx) for idx in self.lots_gdf.index]
    
    def get_face_types(self, lot_id: str) -> List[str]:
        """
        Retorna os tipos de faces disponíveis para um lote.
        
        Args:
            lot_id: ID do lote
            
        Returns:
            Lista de tipos de faces
        """
        if self.faces_gdf is None:
            return []
        
        faces = self.faces_gdf[self.faces_gdf['numlote'] == lot_id]
        
        if len(faces) > 0 and 'tipo' in faces.columns:
            return faces['tipo'].unique().tolist()
        else:
            return []
    
    def create_enriched_lots_gdf(self, results: Dict[str, Dict]) -> gpd.GeoDataFrame:
        """
        Cria um GeoDataFrame enriquecido com resultados do processamento.
        
        Args:
            results: Dicionário {lot_id: result_dict} com resultados
            
        Returns:
            GeoDataFrame enriquecido com métricas do processamento
        """
        if self.lots_gdf is None:
            raise ValueError("Lotes não foram carregados")
        
        # Criar cópia do GeoDataFrame original
        enriched_gdf = self.lots_gdf.copy()
        
        # Adicionar colunas para resultados
        enriched_gdf['processed'] = False
        enriched_gdf['processing_error'] = None
        enriched_gdf['best_morphology'] = None
        enriched_gdf['best_morphology_name'] = None
        enriched_gdf['efficiency'] = None
        enriched_gdf['buildable_area'] = None
        enriched_gdf['achieved_far'] = None
        enriched_gdf['floors'] = None
        enriched_gdf['height'] = None
        
        # Preencher resultados para cada lote processado
        for lot_id, result in results.items():
            # Verificar se o lote existe no GeoDataFrame
            mask = enriched_gdf['numlote'] == lot_id
            
            if not mask.any():
                continue
            
            # Indicar que o lote foi processado
            enriched_gdf.loc[mask, 'processed'] = True
            
            # Verificar se houve erro
            if 'error' in result:
                enriched_gdf.loc[mask, 'processing_error'] = result['error']
                continue
            
            # Adicionar dados do melhor modelo encontrado
            if 'best_morphology' in result:
                morph = result['best_morphology']
                enriched_gdf.loc[mask, 'best_morphology'] = morph.get('id', None)
                enriched_gdf.loc[mask, 'best_morphology_name'] = morph.get('name', None)
                enriched_gdf.loc[mask, 'efficiency'] = morph.get('efficiency', None)
            
            # Adicionar métricas detalhadas se disponíveis
            if 'detailed_metrics' in result:
                metrics = result['detailed_metrics']
                enriched_gdf.loc[mask, 'buildable_area'] = metrics.get('buildable_area', None)
                enriched_gdf.loc[mask, 'achieved_far'] = metrics.get('far', None)
                enriched_gdf.loc[mask, 'floors'] = metrics.get('floors', None)
                enriched_gdf.loc[mask, 'height'] = metrics.get('height', None)
        
        return enriched_gdf

from shapely.geometry import Polygon
from typing import Optional
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from shapely.geometry import Polygon, LineString

@dataclass
class BuildingParameters:
    """
    Classe que encapsula todos os parâmetros usados no processo de geração e otimização de morfologias.
    """
    lot_polygon: Polygon
    lot_id: str = ""

    # Dimensões mínimas de unidades
    min_unit_area: float = 50.0  # m²
    unit_width: float = 5.0      # largura em metros

    # Configurações de geração
    use_grid_based_generation: bool = False
    use_corner: bool = False
    corner_side_ratio: float = 0.3
    corner_thickness_ratio: float = 0.1
    h3_resolution: int = 10

    # Otimização
    use_ai_optimization: bool = False
    simplify_tolerance: float = 0.5

    # Outras propriedades opcionais
    zone_code: Optional[str] = None
    building_height_limit: Optional[float] = None
    far_limit: Optional[float] = None
    parking_type: Optional[str] = None
    parking_min_slots: Optional[int] = None

    # Dados extras (úteis para IA ou heurísticas)
    metadata: dict = field(default_factory=dict)

    faces: Optional[List[LineString]] = None
    config: Optional[Dict] = None

    def to_dict(self):
        return self.__dict__

from shapely.geometry import Polygon
from core.params import BuildingParameters
from generators.composition_generator import CompositionGenerator

class BuildingModel:
    def __init__(self, params: BuildingParameters):
        self.params = params
        self.footprint = None
        self.total_height = None
        self.morphology_type = "unknown"
        self.used_slabs = 0
        self.used_corners = 0
        self.shape_name = "composite"
        self.total_built_area = 0.0
        self.total_floors = 0

    def generate_footprint(self) -> Polygon:
        try:
            generator = CompositionGenerator(self.params)
            self.footprint = generator.generate()
            self.used_slabs = generator.used_slabs
            self.used_corners = generator.used_corners
            self.total_built_area = generator.total_built_area

            # Calcula altura total com base nos pavimentos
            if self.params.floor_height > 0:
                self.total_floors = int(self.total_built_area / self.footprint.area)
                self.total_height = self.total_floors * self.params.floor_height
            else:
                self.total_floors = 0
                self.total_height = 0.0

            self._infer_morphology_type()
            return self.footprint
        except Exception as e:
            print(f"[Erro ao gerar footprint]: {e}")
            return None

    def _infer_morphology_type(self):
        if self.used_slabs > 0 and self.used_corners == 0:
            self.morphology_type = "slab"
        elif self.used_slabs == 0 and self.used_corners > 0:
            self.morphology_type = "corner"
        elif self.used_slabs > 0 and self.used_corners > 0:
            self.morphology_type = "composite"
        else:
            self.morphology_type = "unknown"

    def get_buildable_area(self) -> float:
        if self.footprint is None:
            return 0.0
        return self.footprint.area

from shapely.geometry import Polygon
from shapely.affinity import translate, scale
from shapely.ops import unary_union
from core.spatial_grid_allocator import SpatialGridAllocator
from core.params import BuildingParameters
from shapely.geometry import box


class CompositionGenerator:
    def __init__(self, params: BuildingParameters):
        self.params = params
        self.lot_polygon = params.lot_polygon
        self.resolution = params.h3_resolution
        self.used_slabs = 0
        self.used_corners = 0
        self.total_built_area = 0.0

    def generate(self) -> Polygon:
        """
        Gera o volume escalonado da edificação usando formas atômicas distribuídas por H3,
        aplicando recuos progressivos a partir do pavimento definido.
        """
        # 1. Geração do footprint base com formas atômicas
        base = self._generate_atomic_footprint()

        # 2. Cálculo do número máximo de pavimentos possíveis
        floor_height = self.params.floor_height
        max_height = self.params.max_height
        max_floors = int(max_height // floor_height)

        # 3. Inicialização dos pavimentos
        pavimentos = []
        area_lote = self.lot_polygon.area
        far_max = self.params.max_far
        lot_coverage_max = self.params.lot_coverage_max
        min_floor_area = self.params.min_floor_area

        current_area_total = 0.0

        for floor in range(1, max_floors + 1):
            height = floor * floor_height

            # Verifica limite de FAR
            if current_area_total / area_lote >= far_max:
                break

            # Aplica recuos verticais escalonados a partir do piso definido
            if floor >= self.params.min_setback_start_floor:
                setback = height * self.params.back_setback_percent
                apply_lateral = self.params.min_side_setback > 0

                scaled = scale(
                    base,
                    xfact=1 - (2 * setback / base.bounds[2]) if apply_lateral else 1,
                    yfact=1 - (2 * setback / base.bounds[3]),
                    origin='center'
                )
            else:
                scaled = base

            area = scaled.area
            if area < min_floor_area:
                break

            pavimentos.append(scaled)
            current_area_total += area

        self.total_built_area = current_area_total
        self.used_slabs = self.params.estimated_slabs
        self.used_corners = self.params.estimated_corners

        if not pavimentos:
            return None

        return unary_union(pavimentos).intersection(self.lot_polygon)

    def _generate_atomic_footprint(self) -> Polygon:
        """
        Gera footprint 2D plano combinando formas atômicas via grid H3.
        """
        allocator = SpatialGridAllocator(self.resolution)
        centroids = allocator.generate_grid_centroids(self.lot_polygon)

        shapes = []
        for i, pt in enumerate(centroids):
            if i % 5 == 0:
                corner = box(0, 0, 8, 8)
                shape = translate(corner, xoff=pt.x, yoff=pt.y)
                self.used_corners += 1
            else:
                slab = box(-4, -12, 4, 12)
                shape = translate(slab, xoff=pt.x, yoff=pt.y)
                self.used_slabs += 1

            if shape.intersects(self.lot_polygon):
                shapes.append(shape.intersection(self.lot_polygon))

        return unary_union(shapes)

from shapely.geometry import box, Polygon
from shapely.affinity import translate, scale
from shapely.ops import unary_union
from core.spatial_grid_allocator import SpatialGridAllocator
from core.params import BuildingParameters

class GridCompositionGenerator:
    def __init__(self, params: BuildingParameters):
        self.params = params
        self.resolution = params.h3_resolution
        self.used_slabs = 0
        self.used_corners = 0
        self.total_built_area = 0.0
        self.total_floors = 0

    def generate(self) -> Polygon:
        allocator = SpatialGridAllocator(self.resolution)
        centroids = allocator.generate_grid_centroids(self.params.lot_polygon)

        base_shapes = []
        for i, pt in enumerate(centroids):
            if i % 5 == 0:
                corner = box(0, 0, 8, 8)
                shape = translate(corner, xoff=pt.x, yoff=pt.y)
                self.used_corners += 1
            else:
                slab = box(-4, -12, 4, 12)
                shape = translate(slab, xoff=pt.x, yoff=pt.y)
                self.used_slabs += 1

            if shape.intersects(self.params.lot_polygon):
                base_shapes.append(shape.intersection(self.params.lot_polygon))

        if not base_shapes:
            print("[!] Nenhuma forma atômica válida gerada.")
            return None

        base = unary_union(base_shapes)
        pavimentos = []

        max_height = self.params.max_height
        floor_height = self.params.floor_height
        max_floors = int(max_height // floor_height)

        far_max = self.params.max_far
        lot_area = self.params.lot_polygon.area
        area_total_maxima = far_max * lot_area
        min_area_piso = self.params.min_floor_area

        for floor in range(1, max_floors + 1):
            height = floor * floor_height

            if self.total_built_area >= area_total_maxima:
                break

            # Aplica recuos verticais
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
            if area < min_area_piso:
                break

            pavimentos.append(scaled)
            self.total_built_area += area
            self.total_floors += 1

        return unary_union(pavimentos).intersection(self.params.lot_polygon)

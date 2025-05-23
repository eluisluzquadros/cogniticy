from shapely.geometry import Polygon
from core.params import BuildingParameters

def test_building_parameters_defaults():
    poly = Polygon([(0,0), (0,10), (10,10), (10,0), (0,0)])
    params = BuildingParameters(lot_polygon=poly)

    assert params.min_unit_area == 50.0
    assert params.unit_width == 5.0
    assert params.use_grid_based_generation is False
    assert isinstance(params.to_dict(), dict)

def test_building_parameters_custom():
    poly = Polygon([(0,0), (0,10), (10,10), (10,0), (0,0)])
    params = BuildingParameters(
        lot_polygon=poly,
        min_unit_area=40.0,
        use_grid_based_generation=True,
        parking_type="subterraneo",
        metadata={"zone": "ZC1"}
    )

    assert params.min_unit_area == 40.0
    assert params.use_grid_based_generation is True
    assert params.parking_type == "subterraneo"
    assert params.metadata["zone"] == "ZC1"

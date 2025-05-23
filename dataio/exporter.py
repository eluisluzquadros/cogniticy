import geopandas as gpd
import json
from shapely.geometry import mapping

class BuildingExporter:
    def __init__(self, output_path):
        self.output_path = output_path

    def export_building(self, model, model_id="model_1"):
        """
        Exporta os dados do modelo gerado em formato GeoJSON com metadados.
        """
        if model.footprint is None:
            print(f"[!] Modelo {model_id} não possui footprint válido.")
            return

        data = {
            "type": "Feature",
            "geometry": mapping(model.footprint),
            "properties": {
                "model_id": model_id,
                "shape_name": model.shape_name,
                "morphology_type": model.morphology_type,
                "total_built_area": round(model.total_built_area, 2),
                "total_floors": model.total_floors,
                "total_height": round(model.total_height or 0.0, 2),
                "used_slabs": model.used_slabs,
                "used_corners": model.used_corners,
                "lot_id": getattr(model.params, "lot_id", "unknown")
            }
        }

        # Cria GeoDataFrame e salva
        gdf = gpd.GeoDataFrame.from_features([data], crs="EPSG:4326")
        output_file = f"{self.output_path}/{model_id}.geojson"
        gdf.to_file(output_file, driver="GeoJSON")

        print(f"[✓] Modelo exportado para {output_file}")

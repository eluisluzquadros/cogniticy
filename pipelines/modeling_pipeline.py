from core.model import BuildingModel
from dataio.exporter import BuildingExporter
from dataio.geojson_handler import GeoJSONHandler

def run_modeling_pipeline(lot_path: str, face_path: str, output_path: str, model_prefix="skyvidya"):
    handler = GeoJSONHandler()
    handler.load_lots(lot_path)
    handler.load_faces(face_path)

    lot_ids = handler.get_lot_ids()

    for lot_id in lot_ids:
        params, metadata = handler.process_lot(lot_id)
        if not params:
            print(f"[x] Falha no processamento do lote {lot_id}")
            continue

        model = BuildingModel(params)
        model.generate_footprint()

        exporter = BuildingExporter(output_path)
        model_id = f"{model_prefix}_{lot_id}"
        exporter.export_building(model, model_id=model_id)

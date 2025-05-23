import os
import click
from io.geojson_handler import GeoJSONHandler
from core.model import BuildingModel
from io.exporter import Exporter
from agents.llm_stub_interface import LLMStubInterface

@click.command()
@click.option('--lots', 'lots_path', required=True, help='Caminho para arquivo de lotes (GeoJSON ou Parquet)')
@click.option('--faces', 'faces_path', required=True, help='Caminho para arquivo de faces (GeoJSON ou Parquet)')
@click.option('--output_dir', default='output', help='Diretório para salvar resultados')
def main(lots_path, faces_path, output_dir):
    """
    Pipeline de modelagem: carrega lotes e faces, gera e otimiza footprints, exporta resultados.
    """
    os.makedirs(output_dir, exist_ok=True)

    handler = GeoJSONHandler()
    lots_gdf = handler.load_lots(lots_path)
    faces_gdf = handler.load_faces(faces_path)
    handler.faces_gdf = faces_gdf

    lot_ids = handler.get_lot_ids()
    click.echo(f"Processando {len(lot_ids)} lotes...")

    exporter = Exporter(output_dir)
    for lot_id in lot_ids:
        click.echo(f"- Lote: {lot_id}")
        params, config = handler.process_lot(lot_id)
        if params is None:
            click.echo(f"  > Parâmetros não encontrados, pulando.")
            continue

        # Ativa stub de AI se necessário
        llm_stub = LLMStubInterface(compacity_factor=0.95) if getattr(params, 'use_ai_optimization', False) else None
        if llm_stub: llm_stub.set_geometry(params.lot_polygon)

        model = BuildingModel(params, llm_interface=llm_stub)
        footprint = model.generate_footprint()
        optimized = model.optimize(footprint)

        filename = f"footprint_{lot_id}.geojson"
        exporter.export_footprint(optimized, filename)
        click.echo(f"  > Exportado: {filename}")

    click.echo("Pipeline concluído.")

if __name__ == '__main__':
    main()

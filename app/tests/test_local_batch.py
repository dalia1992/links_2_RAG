# test_local_batch.py
import asyncio
from app.src.core_etl import run_pipeline

async def test_batch():
    # Lista pequeña para probar la concurrencia y la lógica de deduplicación
    urls_de_prueba = [
        "https://medlineplus.gov/spanish/recetas/licuado-de-calabaza/",
        "https://retinia.mx/agudeza-visual-av/"
    ]
    
    print(f"[*] Iniciando prueba local con {len(urls_de_prueba)} URLs...")
    for url in urls_de_prueba:
        await run_pipeline(url)

if __name__ == "__main__":
    asyncio.run(test_batch())
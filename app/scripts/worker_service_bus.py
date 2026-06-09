import os
import asyncio
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import TransportType
from dotenv import load_dotenv
# Importamos tu lógica ya probada
from app.src.core_etl import run_pipeline
import logging
import csv
import time
import datetime

load_dotenv()
# 2. Configuración del Archivo CSV
CSV_FILE = 'reporte_procesamiento.csv'

# Si el archivo no existe, creamos los encabezados
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Hora_Fin', 'URL', 'Estado', 'Tiempo_Segundos', 'Detalle_Error'])

# Configuración desde el .env
CONNECTION_STR = os.getenv("SERVICEBUS_CONNECTION_STR")
QUEUE_NAME = os.getenv("SERVICEBUS_QUEUE_NAME")

async def worker():
    async with ServiceBusClient.from_connection_string(
        CONNECTION_STR,
        transport_type=TransportType.AmqpOverWebsocket
    ) as client:
        receiver = client.get_queue_receiver(queue_name=QUEUE_NAME)
        async with receiver:
            logging.info(f"[*] Worker iniciado. Esperando mensajes...")
            
            async for msg in receiver:
                url = str(msg)
                start_time = time.time()  # Empezamos el cronómetro
                
                try:
                    await run_pipeline(url)
                    await receiver.complete_message(msg)
                    estado = "EXITO"
                    detalle_error = "N/A"
                except Exception as e:
                    logging.error(f"[!] Error procesando {url}: {e}")
                    await receiver.dead_letter_message(msg)
                    estado = "FALLO"
                    detalle_error = str(e)
                
                # Detenemos el cronómetro y redondeamos a 2 decimales
                end_time = time.time()
                tiempo_procesamiento = round(end_time - start_time, 2)
                
                # 3. Guardamos silenciosamente en el CSV
                hora_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([hora_actual, url, estado, tiempo_procesamiento, detalle_error])
                
                logging.info(f"[{estado}] URL procesada en {tiempo_procesamiento} seg.")

if __name__ == "__main__":
    try:
        asyncio.run(worker())
    except KeyboardInterrupt:
        print("[*] Worker detenido por el usuario.")
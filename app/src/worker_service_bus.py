import os
import asyncio
from azure.servicebus.aio import ServiceBusClient
from dotenv import load_dotenv
# Importamos tu lógica ya probada
from app.src.core_etl import run_pipeline

load_dotenv()

# Configuración desde el .env
CONNECTION_STR = os.getenv("SERVICEBUS_CONNECTION_STR")
QUEUE_NAME = os.getenv("SERVICEBUS_QUEUE_NAME")

async def worker():
    async with ServiceBusClient.from_connection_string(CONNECTION_STR) as client:
        receiver = client.get_queue_receiver(queue_name=QUEUE_NAME)
        async with receiver:
            print(f"[*] Worker iniciado. Esperando mensajes en '{QUEUE_NAME}'...")
            
            async for msg in receiver:
                url = str(msg)
                print(f"[*] Procesando URL recibida: {url}")
                
                try:
                    # Aquí reutilizamos tu pipeline probado
                    await run_pipeline(url)
                    
                    # Si todo sale bien, borramos el mensaje de la cola
                    await receiver.complete_message(msg)
                    print(f"[+] URL completada: {url}")
                    
                except Exception as e:
                    # Si falla, dejamos el mensaje para reintento o manejo de errores
                    print(f"[!] Error procesando {url}: {e}")
                    # Opcional: await receiver.dead_letter_message(msg) si el error es fatal

if __name__ == "__main__":
    try:
        asyncio.run(worker())
    except KeyboardInterrupt:
        print("[*] Worker detenido por el usuario.")
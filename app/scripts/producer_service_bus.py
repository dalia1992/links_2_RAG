import os
import asyncio
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.servicebus import TransportType
from dotenv import load_dotenv
import pandas as pd
import numpy as np

# Cargar variables de entorno
load_dotenv()

CONNECTION_STR = os.getenv("SERVICEBUS_CONNECTION_STR")
QUEUE_NAME = os.getenv("SERVICEBUS_QUEUE_NAME")

async def fill_queue(urls):
    """
    Toma una lista de URLs y las envía todas a la cola de Service Bus.
    """
    async with ServiceBusClient.from_connection_string(CONNECTION_STR,
                                                       transport_type=TransportType.AmqpOverWebsocket) as client:
        sender = client.get_queue_sender(queue_name=QUEUE_NAME)
        async with sender:
            print(f"[*] Conectado a la cola '{QUEUE_NAME}'. Iniciando carga de {len(urls)} URLs...")
            
            for url in urls:
                message = ServiceBusMessage(url)
                # Opcional: Podrías añadir propiedades personalizadas aquí si lo necesitas
                await sender.send_messages(message)
                print(f"[+] Mensaje enviado: {url}")

if __name__ == "__main__":
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'reference_urls.csv')
    # Leer el CSV
    df = pd.read_csv(csv_path)
    urls = df['URL'].dropna().tolist()
    urls = np.random.choice(urls, 10, replace=False)
    try:
        asyncio.run(fill_queue(urls))
        print("[*] Carga finalizada exitosamente.")
    except Exception as e:
        print(f"[!] Error crítico durante la carga: {e}")
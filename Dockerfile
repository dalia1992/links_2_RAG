# 1. Usamos nuestra imagen base de siempre
FROM python:3.11-slim


# Fuerza a Azure a usar la red de Python nativa
ENV AZURE_SERVICEBUS_TRANSPORT_TYPE=pyamqp

# Evita que Python guarde buffers (bueno para ver los logs en vivo)
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .

# ==========================================
# DEPENDENCIAS PARA QUE PLAYWRIGHT FUNCIONE
# ==========================================
# Instalar dependencias de Playwright y navegadores
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1  libxfixes3 \
    libxdamage1 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# 3. Instalamos las librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# Instalamos el navegador interno que usa Playwright
RUN playwright install chromium
RUN playwright install-deps                          

# 4. Copiamos el código y ejecutamos
COPY . .
CMD ["python", "-m", "app.scripts.worker_service_bus"]
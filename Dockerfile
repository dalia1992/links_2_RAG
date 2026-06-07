# 1. Usamos nuestra imagen base de siempre
FROM python:3.11-slim

# 2. Copiamos los archivos
WORKDIR /app
COPY requirements.txt .

# 3. Instalamos las librerías de Python (incluyendo 'playwright')
RUN pip install --no-cache-dir -r requirements.txt

# ==========================================
# 4. PLAYWRIGHT
# Instalamos Chromium y le pedimos a Playwright que instale 
# las dependencias del sistema operativo (C++, fuentes, etc)
# ==========================================
RUN playwright install chromium
RUN playwright install-deps chromium

# 5. Copiamos el código y ejecutamos
COPY . .
CMD ["python", "worker.py"]
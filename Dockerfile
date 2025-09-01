FROM python:3.11-slim

WORKDIR /app

# Copia backend e requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/

# Garante a pasta de export
RUN mkdir -p /app/exports

# Variáveis padrão (podem ser sobrescritas via -e)
ENV INFLUX_HOST=influxdb \
    INFLUX_DB=estufa \
    EXPORT_PATH=/app/exports/sensores.csv \
    SIMULATE=0

EXPOSE 5000
CMD ["python", "app.py"]

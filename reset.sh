#!/bin/bash
set -e

echo "🧹 Limpando containers antigos..."
podman rm -af || true

echo "🧹 Limpando imagens antigas..."
podman rmi -af || true

echo "🔨 Rebuildando backend..."
podman build -t estufa-backend .

echo "🌐 Garantindo rede estufa-net..."
if ! podman network exists estufa-net; then
  podman network create estufa-net
fi

echo "📦 Subindo InfluxDB..."
mkdir -p ./data ./data/exports
podman run -d --name influxdb --network estufa-net \
  -p 8086:8086 \
  -v ./data:/var/lib/influxdb:Z \
  docker.io/library/influxdb:1.8

echo "📦 Subindo Backend (Flask)..."
podman run -d --name backend --network estufa-net \
  -e SIMULATE=1 \
  -e INFLUX_HOST=influxdb \
  -e INFLUX_DB=estufa \
  -e EXPORT_PATH=/app/exports/sensores.csv \
  -p 5000:5000 \
  -v ./data/exports:/app/exports:Z \
  localhost/estufa-backend:latest

echo "📦 Subindo Frontend (Nginx)..."
if [ ! -d "./frontend/dist" ]; then
  echo "⚠️  Pasta ./frontend/dist não encontrada! Rode 'npm run build' em ./frontend antes."
else
  podman run -d --name frontend --network estufa-net \
    -p 8081:80 \
    -v ./frontend/dist:/usr/share/nginx/html:Z \
    docker.io/library/nginx:alpine
fi

echo ""
echo "✅ Todos os serviços foram iniciados!"
echo "➡️  Backend:   http://localhost:5000/dados"
echo "➡️  Frontend:  http://localhost:8081"
echo "➡️  InfluxDB:  http://localhost:8086/ping"

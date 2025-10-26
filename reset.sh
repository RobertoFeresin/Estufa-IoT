#!/bin/bash
set -e

echo "🧹 Limpando containers antigos..."
podman rm -af || true

echo "🧹 Limpando imagens antigas..."
podman rmi -af || true

echo "🔪 Matando qualquer processo ocupando a porta 11434..."
if sudo lsof -t -i:11434 >/dev/null 2>&1; then
  sudo fuser -k 11434/tcp || true
  echo "✅ Porta 11434 liberada!"
else
  echo "ℹ️ Nenhum processo usando a porta 11434."
fi


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

echo "🤖 Subindo Ollama (IA local)..."

if podman ps -a --format '{{.Names}}' | grep -q '^ollama$'; then
  podman stop ollama >/dev/null 2>&1 || true
  podman rm ollama >/dev/null 2>&1 || true
fi
if podman volume exists ollama; then
  echo "🧨 Removendo volume antigo do Ollama..."
  podman volume rm ollama >/dev/null 2>&1 || true
fi

podman pull docker.io/ollama/ollama:latest

podman run -d \
  --name ollama \
  --network estufa-net \
  -p 11434:11434 \
  -e HOME=/root \
  -v ollama:/root/.ollama \
  docker.io/ollama/ollama:latest

echo "⏳ Aguardando Ollama iniciar..."
sleep 6

if curl -s http://localhost:11434 | grep -q "Ollama is running"; then
  echo "✅ Ollama está rodando corretamente."
else
  echo "❌ Falha ao iniciar Ollama. Verifique o Podman."
  exit 1
fi

echo "📦 Baixando modelo leve 'qwen2:1.5b'..."
podman exec -it ollama ollama pull qwen2:1.5b || {
  echo "⚠️ Falha ao puxar modelo automaticamente. Tente manualmente depois com:"
  echo "   podman exec -it ollama ollama pull qwen2:1.5b"
}

echo "📋 Modelos disponíveis:"
podman exec -it ollama ollama list || true

echo ""
echo "✅ Todos os serviços foram iniciados com sucesso!"
echo "➡️  Backend:   http://localhost:5000/dados"
echo "➡️  Frontend:  http://localhost:8081"
echo "➡️  InfluxDB:  http://localhost:8086/ping"
echo "➡️  IA (Ollama): http://localhost:11434"
echo ""
echo "🎯 Modelo 'qwen2:1.5b' instalado e pronto pra responder no chat!"

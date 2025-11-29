#!/bin/bash
set -e

echo "=================================================="
echo "🚀 INICIANDO SISTEMA ESTUFA IoT"
echo "=================================================="

echo ""
echo "🛠️  Preparando ambiente..."
echo "=================================================="

echo "Limpando containers antigos..."
podman rm -af || true

echo "Limpando imagens antigas..."
podman rmi -af || true

echo "Matando qualquer processo ocupando a porta 11434..."
if sudo lsof -t -i:11434 >/dev/null 2>&1; then
  sudo fuser -k 11434/tcp || true
  echo "✅ Porta 11434 liberada!"
else
  echo "ℹ Nenhum processo usando a porta 11434."
fi

echo "Matando qualquer processo ocupando a porta 5000..."
if sudo lsof -t -i:5000 >/dev/null 2>&1; then
  sudo fuser -k 5000/tcp || true
  echo "✅ Porta 5000 liberada!"
else
  echo "ℹ Nenhum processo usando a porta 5000."
fi

echo "Matando qualquer processo ocupando a porta 8081..."
if sudo lsof -t -i:8081 >/dev/null 2>&1; then
  sudo fuser -k 8081/tcp || true
  echo "✅ Porta 8081 liberada!"
else
  echo "ℹ Nenhum processo usando a porta 8081."
fi

echo ""
echo "🔨 Construindo e iniciando serviços..."
echo "=================================================="

echo "Rebuildando backend..."
podman build -t estufa-backend .

echo "Garantindo rede estufa-net..."
if ! podman network exists estufa-net; then
  podman network create estufa-net
  echo "✅ Rede estufa-net criada"
else
  echo "✅ Rede estufa-net já existe"
fi

echo "Criando diretório para exports..."
mkdir -p ./data/exports
echo "✅ Diretório ./data/exports criado"

echo ""
echo "📦 Subindo Backend (Flask)..."
podman run -d --name backend --network estufa-net \
  -e OLLAMA_URL=http://ollama:11434/api/chat \
  -p 5000:5000 \
  -v ./data/exports:/app/exports:Z \
  localhost/estufa-backend:latest

echo "⏳ Aguardando Backend iniciar..."
for i in {1..10}; do
  if curl -s http://localhost:5000/health >/dev/null 2>&1; then
    echo "✅ Backend ativo!"
    break
  fi
  echo "Aguardando Backend ($i/10)..."
  sleep 2
done

echo ""
echo "⏳ Aguardando Backend inicializar completamente (carregando dados iniciais)..."
for i in {1..20}; do
  health_response=$(curl -s http://localhost:5000/health)
  if echo "$health_response" | grep -q '"ok":true'; then
    dados_carregados=$(echo "$health_response" | grep -o '"dados_carregados":[0-9]*' | cut -d: -f2)
    echo "✅ Backend completamente inicializado com $dados_carregados dados carregados!"
    break
  elif echo "$health_response" | grep -q '"ok":false'; then
    echo "🔄 Backend inicializando... ($i/20)"
  else
    echo "⏳ Conectando ao Backend... ($i/20)"
  fi
  sleep 3
done

# Verificação final do backend
if curl -s http://localhost:5000/health | grep -q '"ok":true'; then
  echo "🎉 Backend pronto para uso!"
else
  echo "⚠️  Backend pode não ter inicializado completamente, mas continuando..."
fi

echo ""
echo "🌐 Subindo Frontend (Nginx)..."
if [ ! -d "./frontend/dist" ]; then
  echo "⚠️  Pasta ./frontend/dist não encontrada! Construindo frontend..."
  # Tenta construir se a pasta não existe
  if [ -d "./frontend" ]; then
    cd ./frontend
    npm run build || echo "⚠️  Falha ao construir frontend. Verifique se npm está instalado."
    cd ..
  else
    echo "❌ Pasta frontend não encontrada!"
    exit 1
  fi
fi

if [ -d "./frontend/dist" ]; then
  podman run -d --name frontend --network estufa-net \
    -p 8081:80 \
    -v ./frontend/dist:/usr/share/nginx/html:Z \
    docker.io/library/nginx:alpine
  echo "✅ Frontend iniciado na porta 8081"
else
  echo "❌ Não foi possível iniciar o frontend - pasta dist não encontrada"
fi

echo ""
echo "🤖 Subindo Ollama (IA local)..."

# Limpeza do Ollama se existir
if podman ps -a --format '{{.Names}}' | grep -q '^ollama$'; then
  podman stop ollama >/dev/null 2>&1 || true
  podman rm ollama >/dev/null 2>&1 || true
  echo "✅ Containers antigos do Ollama removidos"
fi

if podman volume exists ollama; then
  echo "Removendo volume antigo do Ollama..."
  podman volume rm ollama >/dev/null 2>&1 || true
  echo "✅ Volume antigo do Ollama removido"
fi

echo "Baixando imagem do Ollama..."
podman pull docker.io/ollama/ollama:latest
echo "✅ Imagem do Ollama baixada"

echo "Iniciando Ollama..."
podman run -d \
  --name ollama \
  --network estufa-net \
  -p 11434:11434 \
  -e HOME=/root \
  -v ollama:/root/.ollama \
  docker.io/ollama/ollama:latest
echo "✅ Ollama iniciado"

echo "⏳ Aguardando Ollama iniciar completamente..."
for i in {1..15}; do
  if curl -s http://localhost:11434 >/dev/null 2>&1; then
    echo "✅ Ollama ativo!"
    break
  fi
  echo "Aguardando Ollama ($i/15)..."
  sleep 3
done

# Verifica se Ollama está respondendo
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "✅ Ollama está rodando corretamente."
else
  echo "⚠️  Ollama pode não estar respondendo corretamente. Continuando..."
fi

echo ""
echo "📥 Configurando modelo de IA..."
echo "Baixando modelo 'llama3.2:1b' (mais rápido e estável)..."
if podman exec ollama ollama list 2>/dev/null | grep -q "llama3.2:1b"; then
  echo "✅ Modelo llama3.2:1b já está instalado."
else
  echo "⏳ Baixando modelo llama3.2:1b (pode demorar alguns minutos)..."
  if podman exec ollama ollama pull llama3.2:1b; then
    echo "✅ Modelo llama3.2:1b baixado com sucesso!"
  else
    echo "⚠️  Falha ao baixar modelo automaticamente. Tentando qwen2:1.5b..."
    if podman exec ollama ollama pull qwen2:1.5b; then
      echo "✅ Modelo qwen2:1.5b baixado com sucesso!"
    else
      echo "❌ Falha ao baixar modelos. O chat pode não funcionar corretamente."
      echo "💡 Tente manualmente depois com:"
      echo "   podman exec -it ollama ollama pull llama3.2:1b"
    fi
  fi
fi

echo ""
echo "📋 Modelos disponíveis no Ollama:"
podman exec ollama ollama list 2>/dev/null || echo "⚠️  Não foi possível listar modelos"

echo ""
echo "🔍 Verificando conexão com servidor externo..."
if curl -s http://localhost:5000/health | grep -q '"ok":true'; then
  echo "✅ Conexão com servidor externo estabelecida"
  dados_info=$(curl -s http://localhost:5000/debug | grep -o '"quantidade":[0-9]*' | cut -d: -f2)
  if [ -n "$dados_info" ]; then
    echo "📊 Dados disponíveis: $dados_info registros"
  fi
else
  echo "⚠️  Possível problema na conexão com servidor externo"
fi

echo ""
echo "=================================================="
echo "🎉 SISTEMA ESTUFA IoT INICIADO COM SUCESSO!"
echo "=================================================="
echo ""
echo "🌐 FRONTEND (Aplicação Principal):"
echo "   http://localhost:8081"
echo ""
echo "🔧 BACKEND (API):"
echo "   http://localhost:5000"
echo "   - Health:    http://localhost:5000/health"
echo "   - Dados:     http://localhost:5000/registros?limit=20"
echo "   - Análise:   http://localhost:5000/analise?limit=20"
echo "   - Debug:     http://localhost:5000/debug"
echo ""
echo "🤖 IA (Ollama):"
echo "   http://localhost:11434"
echo ""
echo "📊 CONFIGURAÇÃO:"
echo "   - Servidor externo: http://192.168.68.111:5000/registros"
echo "   - Dados na tabela: 20 registros em tempo real"
echo "   - Atualização: a cada 5 segundos"
echo "   - Chat: com persistência de conversa"
echo ""
echo "💡 TESTES RÁPIDOS:"
echo "   curl http://localhost:5000/health"
echo "   curl http://localhost:5000/registros?limit=5"
echo "   curl http://localhost:5000/analise?limit=10"
echo ""
echo "🚀 ACESSE AGORA: http://localhost:8081"
echo ""
echo "⚠️  IMPORTANTE:"
echo "   - O sistema carrega 20 dados iniciais durante a inicialização"
echo "   - A tabela mostra sempre os 20 registros mais recentes"
echo "   - O gráfico é atualizado em tempo real"
echo "   - O chatbot só funciona após completa inicialização"
echo ""
echo "=================================================="
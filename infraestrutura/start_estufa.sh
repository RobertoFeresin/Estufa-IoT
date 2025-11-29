#!/bin/bash
# start_estufa.sh
# Script interativo para iniciar o sistema da Estufa IoT (modo real ou simulado + servidor HTTP Flask)
# Compatível com Raspberry Pi OS Bookworm (PEP 668)

clear
echo "==============================================="
echo "   🌱  SISTEMA ESTUFA IOT - GERENCIADOR DE MODOS  "
echo "==============================================="
echo ""
echo "Escolha o modo de operação:"
echo ""
echo "  1️⃣  MODO REAL"
echo "      ➜ Usa sensores físicos conectados via MQTT (ex: NodeMCU, ESP32)."
echo "      ➜ O script 'estufa_opcua.py' receberá os dados reais publicados no tópico MQTT."
echo ""
echo "  2️⃣  MODO SIMULADO"
echo "      ➜ Gera dados aleatórios com 'estufa_opcua_simulate.py'."
echo "      ➜ Permite testar o sistema sem precisar de sensores conectados."
echo ""
read -p "Digite o número do modo desejado [1 ou 2]: " modo

echo ""
echo "==============================================="
echo "🛠️  Preparando ambiente..."
echo "==============================================="

# 1. Dependências do sistema
sudo apt update -y
sudo apt install -y python3 python3-venv python3-pip mosquitto mosquitto-clients net-tools

# 2. Criar venv se não existir
if [ ! -d "venv" ]; then
  echo "🐍 Criando ambiente virtual..."
  python3 -m venv venv
else
  echo "✅ Ambiente virtual já existe."
fi

# 3. Ativar venv e instalar libs (compatível com Raspberry Pi Bookworm)
source venv/bin/activate
pip install --upgrade pip --break-system-packages
pip install paho-mqtt opcua pandas influxdb-client flask asyncua --break-system-packages

# Verificação final das libs CORRIGIDA
missing_libs=$(python3 - <<'EOF'
import importlib.util
libs = ["paho.mqtt.client", "opcua", "pandas", "influxdb_client", "flask"]
missing = [lib for lib in libs if importlib.util.find_spec(lib) is None]
if missing: print(" ".join(missing))
EOF
)

if [ ! -z "$missing_libs" ]; then
  echo "⚠️  Algumas bibliotecas ainda faltam: $missing_libs"
  echo "Tentando reinstalar..."
  pip install $missing_libs --break-system-packages
fi

# 4. Iniciar Mosquitto
echo ""
echo "🛰️  Iniciando broker MQTT (Mosquitto)..."
sudo systemctl enable --now mosquitto
sleep 2

# 5. Detectar IP local automaticamente
IP_LOCAL=$(hostname -I | awk '{print $1}')
OPC_PORT=4840
BROKER_PORT=1883
HTTP_PORT=5000

if [[ -z "$IP_LOCAL" ]]; then
  IP_LOCAL="127.0.0.1"
fi

# 6. Função de limpeza
cleanup() {
  echo ""
  echo "🧹 Encerrando processos..."
  pkill -f "estufa_opcua_simulate.py" >/dev/null 2>&1
  pkill -f "estufa_opcua.py" >/dev/null 2>&1
  pkill -f "http_server.py" >/dev/null 2>&1
  deactivate >/dev/null 2>&1
  echo "✅ Todos os processos encerrados. Até a próxima!"
  exit 0
}
trap cleanup SIGINT SIGTERM

# 7. Exibir informações de rede
echo ""
echo "==============================================="
echo "🌐  ENDEREÇOS DE ACESSO NA REDE LOCAL"
echo "==============================================="
echo "🔌 MQTT Broker (Mosquitto): tcp://${IP_LOCAL}:${BROKER_PORT}"
echo "🛰️  Servidor OPC UA:        opc.tcp://${IP_LOCAL}:${OPC_PORT}/estufa/server/"
echo "🌍  API HTTP Flask:          http://${IP_LOCAL}:${HTTP_PORT}"
echo ""
echo "📱  Acesse a API a partir de outro dispositivo na MESMA REDE Wi-Fi."
echo ""

# 8. Iniciar servidor HTTP Flask
echo "🚀 Iniciando servidor HTTP Flask em segundo plano..."
python3 http_server.py &
HTTP_PID=$!
sleep 2

# 9. Escolha do modo
if [ "$modo" == "1" ]; then
  echo "🌡️  INICIANDO MODO REAL"
  echo "==============================================="
  echo "📡 Aguardando dados dos sensores MQTT no tópico 'estufa/sensores'..."
  echo "📊 Arquivos de dados: ./data/estado.json e ./data/registros.csv"
  echo ""
  python3 estufa_opcua.py

elif [ "$modo" == "2" ]; then
  echo "🌱  INICIANDO MODO SIMULADO"
  echo "==============================================="
  echo "📊 Gerando dados simulados via MQTT e salvando em ./data/"
  echo ""

  python3 estufa_opcua.py &
  SIM_PID=$!
  sleep 3
  python3 estufa_opcua_simulate.py
  kill $SIM_PID >/dev/null 2>&1

else
  echo "❌ Opção inválida. Saindo..."
  cleanup
fi

cleanup

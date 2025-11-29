Estufa OPC UA System - Development package
=========================================

Conteúdo do pacote:
- setup_env.py       -> Cria venv, instala dependências e registra serviço systemd (modo desenvolvimento)
- estufa_opcua.py    -> Script principal (MQTT subscriber, CSV/JSON logger, OPC UA server, relay decision)
- estufa.service     -> sample systemd unit (não habilita por padrão; usado para produção)
- config/mosquitto.conf -> configuração básica do broker (opcional)
- config/mapping.csv -> mapeamento de tags OPC UA gerado a partir da planilha
- data/estado.json   -> arquivo com o estado atual (inicial)
- data/registros.csv -> arquivo CSV de histórico (inicial)

Instruções rápidas (modo desenvolvimento):
1) Extraia o pacote em /home/pi/estufa_opcua_system_dev ou pasta de sua preferência.
2) Abra um terminal e rode (somente uma vez):
   cd /home/pi/estufa_opcua_system_dev
   sudo python3 setup_env.py
   # o script cria o ambiente virtual em ./venv e instala dependências, mas NÃO modifica o sistema de forma destrutiva.
3) Para desenvolvimento, execute o servidor diretamente (logs no console):
   source venv/bin/activate
   python3 estufa_opcua.py
4) Para parar, interrompa com Ctrl+C.
5) Se quiser habilitar o serviço systemd (produção), execute:
   sudo cp estufa.service /etc/systemd/system/estufa.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now estufa.service

Notas:
- Este pacote foi gerado para Raspberry Pi OS Bookworm.
- Ajuste os pinos dos relés no arquivo estufa_opcua.py se necessário.
- O NodeMCU deve publicar em 'estufa/sensores' e escutar comandos em 'estufa/acionamentos'.

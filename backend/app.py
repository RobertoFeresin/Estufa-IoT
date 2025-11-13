import os
import threading
import time
from flask import Flask, jsonify, send_file, request, send_from_directory
from flask_cors import CORS
import analyzer
import requests
import json
import base64
import uuid
from datetime import datetime, timedelta

# Configurações do servidor externo
EXTERNAL_SERVER_URL = "http://192.168.68.111:5000"
USERNAME = "admin"
PASSWORD = "12345"

# Codificar credenciais para Basic Auth
credentials = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
AUTH_HEADER = {"Authorization": f"Basic {credentials}"}

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434/api/chat")

app = Flask(__name__)
# CORS corrigido para permitir todas as origens
CORS(app, origins=["*"], methods=["GET", "POST"], allow_headers=["Content-Type"])

# Dicionário para armazenar históricos de conversa
conversation_histories = {}

# Cache para dados
data_cache = {
    'last_update': 0,
    'dados': [],
    'series': {'time': [], 'temperatura': [], 'umidade': []},
    'analise': {}
}

# Flag para verificar se o sistema está pronto
system_ready = False

def initialize_system():
    """Inicializa o sistema carregando dados iniciais - VERSÃO CORRIGIDA"""
    global system_ready
    
    print("🔄 Inicializando sistema...")
    print("⏳ AGUARDANDO 20 DADOS REAIS DO SERVIDOR EXTERNO...")
    
    max_retries = 30  # Aumentei para 30 tentativas
    dados_coletados = 0
    
    for attempt in range(max_retries):
        try:
            print(f"📊 Tentativa {attempt + 1}/{max_retries} - Buscando 20 dados reais...")
            
            # Busca EXATAMENTE 20 registros
            initial_data = fetch_external_data("/registros", {"limit": 20})
            
            if initial_data and len(initial_data) >= 20:  # EXIGE 20 REGISTROS
                # Verifica se os dados são válidos (não zeros)
                dados_validos = [p for p in initial_data if 
                               float(p.get('temperatura', 0)) > 0 and 
                               float(p.get('umidade', 0)) > 0]
                
                if len(dados_validos) >= 20:
                    # Processa os dados
                    process_initial_data(initial_data)
                    system_ready = True
                    dados_coletados = len(initial_data)
                    print("✅ SISTEMA INICIALIZADO COM SUCESSO!")
                    print(f"📊 Carregados {dados_coletados} registros reais")
                    break
                else:
                    print(f"⚠️ Dados insuficientes válidos: {len(dados_validos)}/20")
            else:
                print(f"⚠️ Dados insuficientes recebidos: {len(initial_data) if initial_data else 0}/20 registros")
                
        except Exception as e:
            print(f"❌ Erro na tentativa {attempt + 1}: {e}")
        
        if attempt < max_retries - 1:
            time.sleep(3)  # Aguarda 3 segundos antes da próxima tentativa
    
    if not system_ready:
        print("❌ SISTEMA NÃO INICIALIZADO - Não foi possível coletar 20 dados reais")
        print("💡 Verifique:")
        print("   - Conexão com servidor externo")
        print("   - Servidor externo tem dados suficientes")
        print("   - Credenciais de acesso")
    else:
        print(f"🎉 Sistema pronto com {dados_coletados} dados reais!")

# Thread de inicialização
init_thread = threading.Thread(target=initialize_system, daemon=True)
init_thread.start()

# Limpeza periódica de conversas antigas
def cleanup_old_conversations():
    """Remove conversas com mais de 1 hora"""
    now = datetime.now()
    expired_sessions = []
    for session_id, data in conversation_histories.items():
        if now - data['last_activity'] > timedelta(hours=1):
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        del conversation_histories[session_id]
    print(f"DEBUG: Limpas {len(expired_sessions)} conversas expiradas")

# Agendando limpeza a cada 30 minutos
def schedule_cleanup():
    while True:
        threading.Event().wait(1800)  # 30 minutos
        cleanup_old_conversations()

# Inicia thread de limpeza em background
cleanup_thread = threading.Thread(target=schedule_cleanup, daemon=True)
cleanup_thread.start()

def fetch_external_data(endpoint="/registros", params=None):
    """Função auxiliar para buscar dados do servidor externo com autenticação"""
    try:
        url = f"{EXTERNAL_SERVER_URL}{endpoint}"
        response = requests.get(
            url, 
            headers=AUTH_HEADER,
            params=params,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"DEBUG: Erro HTTP: {response.status_code}")
            return None
    except Exception as e:
        print(f"DEBUG: Exceção ao buscar dados: {e}")
        return None

def process_initial_data(data):
    """Processa dados iniciais para o cache"""
    if not data:
        return
    
    # Processa dados para a tabela
    processed_data = []
    for item in data:
        try:
            temp = float(item.get("temperatura", 0))
            umid = float(item.get("umidade", 0))
            processed_data.append({
                "time": item.get("timestamp", ""),
                "temperatura": temp,
                "umidade": umid
            })
        except (ValueError, TypeError):
            continue
    
    data_cache['dados'] = processed_data
    
    # Processa dados para séries (gráfico)
    if data:
        data_sorted = sorted(data, key=lambda x: x.get("timestamp", ""), reverse=True)
        data_sorted.reverse()  # Ordem cronológica
        
        times = []
        temps = []
        umids = []
        
        for item in data_sorted:
            timestamp = item.get("timestamp", "")
            if len(timestamp) > 16:
                times.append(timestamp[11:16])
            else:
                times.append(timestamp)
            
            try:
                temp = float(item.get("temperatura", 0))
                umid = float(item.get("umidade", 0))
                temps.append(temp)
                umids.append(umid)
            except (ValueError, TypeError):
                continue
        
        data_cache['series'] = {
            'time': times,
            'temperatura': temps,
            'umidade': umids
        }
    
    # Processa análise
    pts = []
    for item in data:
        try:
            pts.append({
                "temperatura": float(item.get("temperatura", 0)),
                "umidade": float(item.get("umidade", 0))
            })
        except (ValueError, TypeError):
            continue
    
    if pts:
        data_cache['analise'] = analyzer.analisar(pts)
    
    data_cache['last_update'] = time.time()

def get_or_create_session(session_id=None):
    """Obtém ou cria uma sessão de conversa"""
    if session_id and session_id in conversation_histories:
        conversation_histories[session_id]['last_activity'] = datetime.now()
        return session_id, conversation_histories[session_id]['history']
    else:
        new_session_id = str(uuid.uuid4())
        conversation_histories[new_session_id] = {
            'history': [],
            'last_activity': datetime.now(),
            'created_at': datetime.now()
        }
        return new_session_id, []

def add_to_history(session_id, role, content):
    """Adiciona mensagem ao histórico"""
    if session_id in conversation_histories:
        conversation_histories[session_id]['history'].append({
            'role': role,
            'content': content,
            'timestamp': datetime.now()
        })
        # Mantém apenas as últimas 20 mensagens para não ficar muito grande
        if len(conversation_histories[session_id]['history']) > 20:
            conversation_histories[session_id]['history'] = conversation_histories[session_id]['history'][-10:]
        conversation_histories[session_id]['last_activity'] = datetime.now()

def get_estufa_parameters():
    """Retorna os parâmetros ideais para cultivo"""
    return {
        "temperatura": {
            "ideal_min": 18,
            "ideal_max": 25,
            "limiar_inferior": 15,
            "limiar_superior": 28,
            "acao_inferior": "Ligar aquecedor",
            "acao_superior": "Ativar ventilação/exaustor"
        },
        "umidade": {
            "ideal_min": 60,
            "ideal_max": 80,
            "limiar_inferior": 50,
            "limiar_superior": 85,
            "acao_inferior": "Ligar umidificador",
            "acao_superior": "Ventilação forçada"
        },
        "co2": {
            "ideal_min": 800,
            "ideal_max": 1200,
            "limiar_inferior": 800,
            "limiar_superior": 1200,
            "acao_inferior": "Injetar CO₂ (se disponível)",
            "acao_superior": "Ventilar"
        },
        "luminosidade": {
            "ideal_min": 200,
            "ideal_max": 400,
            "limiar_inferior": 200,
            "limiar_superior": 600,
            "acao_inferior": "Ligar LEDs",
            "acao_superior": "Sombrear plantas"
        },
        "umidade_solo": {
            "ideal_min": 20,
            "ideal_max": 30,
            "limiar_inferior": 20,
            "limiar_superior": 35,
            "acao_inferior": "Acionar irrigação",
            "acao_superior": "Parar irrigação"
        },
        "ph_solo": {
            "ideal_min": 5.5,
            "ideal_max": 6.5,
            "limiar_inferior": 5.5,
            "limiar_superior": 6.8,
            "acao_inferior": "Aplicar calcário",
            "acao_superior": "Adicionar enxofre"
        },
        "ec_solo": {
            "ideal_min": 1.5,
            "ideal_max": 3.5,
            "limiar_inferior": 1.5,
            "limiar_superior": 3.5,
            "acao_inferior": "Adubar",
            "acao_superior": "Lavar solo com água"
        }
    }

def analisar_condicoes_estufa(temperatura_atual, umidade_atual):
    """Analisa as condições atuais da estufa e fornece recomendações"""
    params = get_estufa_parameters()
    
    analise = []
    recomendacoes = []
    
    # Análise de temperatura
    temp_info = params["temperatura"]
    if temperatura_atual < temp_info["limiar_inferior"]:
        status = "❌ BAIXA"
        recomendacoes.append(f"🌡️ {temp_info['acao_inferior']}")
    elif temperatura_atual > temp_info["limiar_superior"]:
        status = "❌ ALTA"
        recomendacoes.append(f"🌡️ {temp_info['acao_superior']}")
    elif temp_info["ideal_min"] <= temperatura_atual <= temp_info["ideal_max"]:
        status = "✅ IDEAL"
    else:
        status = "⚠️ ACEITÁVEL"
    
    analise.append(f"**Temperatura**: {temperatura_atual:.1f}°C ({status})")
    analise.append(f"   Faixa ideal: {temp_info['ideal_min']}-{temp_info['ideal_max']}°C")
    
    # Análise de umidade
    umid_info = params["umidade"]
    if umidade_atual < umid_info["limiar_inferior"]:
        status = "❌ BAIXA"
        recomendacoes.append(f"💧 {umid_info['acao_inferior']}")
    elif umidade_atual > umid_info["limiar_superior"]:
        status = "❌ ALTA"
        recomendacoes.append(f"💧 {umid_info['acao_superior']}")
    elif umid_info["ideal_min"] <= umidade_atual <= umid_info["ideal_max"]:
        status = "✅ IDEAL"
    else:
        status = "⚠️ ACEITÁVEL"
    
    analise.append(f"**Umidade**: {umidade_atual:.1f}% ({status})")
    analise.append(f"   Faixa ideal: {umid_info['ideal_min']}-{umid_info['ideal_max']}%")
    
    return analise, recomendacoes

def gerar_resposta_inteligente(mensagem, dados_estufa=None):
    """Gera respostas inteligentes baseadas no contexto da conversa"""
    mensagem_lower = mensagem.lower()
    
    # Respostas para saudações
    if any(palavra in mensagem_lower for palavra in ['oi', 'olá', 'ola', 'hey', 'hello']):
        return "Olá! Sou seu assistente especializado em estufas inteligentes. Posso ajudar você com informações sobre temperatura, umidade, condições ideais para cultivo e recomendações para suas plantas. O que gostaria de saber?"
    
    # Perguntas sobre temperatura
    if any(palavra in mensagem_lower for palavra in ['temperatura', 'calor', 'frio', 'quente']):
        if dados_estufa and dados_estufa.get('mediaTemperatura'):
            temp = dados_estufa['mediaTemperatura']
            params = get_estufa_parameters()
            temp_info = params["temperatura"]
            
            if temp < temp_info["limiar_inferior"]:
                status = "muito baixa"
                acao = f"Recomendo {temp_info['acao_inferior'].lower()}"
            elif temp > temp_info["limiar_superior"]:
                status = "muito alta"
                acao = f"Recomendo {temp_info['acao_superior'].lower()}"
            elif temp_info["ideal_min"] <= temp <= temp_info["ideal_max"]:
                status = "ideal"
                acao = "Condição perfeita para o cultivo!"
            else:
                status = "dentro dos limites aceitáveis"
                acao = "Monitorar regularmente"
            
            return f"🌡️ A temperatura atual da estufa é {temp:.1f}°C, o que está {status} para a maioria das plantas. {acao}\n\nFaixa ideal: {temp_info['ideal_min']}-{temp_info['ideal_max']}°C\nLimites críticos: abaixo de {temp_info['limiar_inferior']}°C ou acima de {temp_info['limiar_superior']}°C"
        else:
            return "Não tenho dados de temperatura disponíveis no momento."
    
    # Perguntas sobre umidade
    if any(palavra in mensagem_lower for palavra in ['umidade', 'úmido', 'umido', 'humidade']):
        if dados_estufa and dados_estufa.get('mediaUmidade'):
            umid = dados_estufa['mediaUmidade']
            params = get_estufa_parameters()
            umid_info = params["umidade"]
            
            if umid < umid_info["limiar_inferior"]:
                status = "muito baixa"
                acao = f"Recomendo {umid_info['acao_inferior'].lower()}"
            elif umid > umid_info["limiar_superior"]:
                status = "muito alta"
                acao = f"Recomendo {umid_info['acao_superior'].lower()}"
            elif umid_info["ideal_min"] <= umid <= umid_info["ideal_max"]:
                status = "ideal"
                acao = "Condição perfeita para o cultivo!"
            else:
                status = "dentro dos limites aceitáveis"
                acao = "Monitorar regularmente"
            
            return f"💧 A umidade atual da estufa é {umid:.1f}%, o que está {status} para a maioria das plantas. {acao}\n\nFaixa ideal: {umid_info['ideal_min']}-{umid_info['ideal_max']}%\nLimites críticos: abaixo de {umid_info['limiar_inferior']}% ou acima de {umid_info['limiar_superior']}%"
        else:
            return "Não tenho dados de umidade disponíveis no momento."
    
    # Perguntas sobre condições gerais
    if any(palavra in mensagem_lower for palavra in ['condições', 'como está', 'situação', 'status', 'estado']):
        if dados_estufa and dados_estufa.get('mediaTemperatura') and dados_estufa.get('mediaUmidade'):
            temp = dados_estufa['mediaTemperatura']
            umid = dados_estufa['mediaUmidade']
            
            analise, recomendacoes = analisar_condicoes_estufa(temp, umid)
            
            resposta = "📊 **CONDIÇÕES ATUAIS DA ESTUFA**\n\n"
            resposta += "\n".join(analise)
            
            if recomendacoes:
                resposta += "\n\n🔧 **RECOMENDAÇÕES:**\n• " + "\n• ".join(recomendacoes)
            else:
                resposta += "\n\n✅ Todas as condições estão dentro das faixas aceitáveis!"
            
            return resposta
        else:
            return "Não tenho dados suficientes para analisar as condições atuais."
    
    # Perguntas sobre recomendações
    if any(palavra in mensagem_lower for palavra in ['recomendação', 'sugestão', 'conselho', 'dica', 'devo fazer']):
        if dados_estufa and dados_estufa.get('mediaTemperatura') and dados_estufa.get('mediaUmidade'):
            temp = dados_estufa['mediaTemperatura']
            umid = dados_estufa['mediaUmidade']
            
            _, recomendacoes = analisar_condicoes_estufa(temp, umid)
            
            if recomendacoes:
                return "🔧 **AÇÕES RECOMENDADAS:**\n• " + "\n• ".join(recomendacoes)
            else:
                return "✅ Todas as condições estão ótimas! Não são necessárias ações no momento."
        else:
            return "Não tenho dados suficientes para fornecer recomendações específicas."
    
    # Perguntas sobre plantas específicas
    if any(palavra in mensagem_lower for palavra in ['tomate', 'alface', 'couve', 'rúcula', 'manjericão']):
        if 'tomate' in mensagem_lower:
            return "🍅 **Cultivo de Tomate:**\n• Temperatura ideal: 18-25°C (noturna: 15-18°C)\n• Umidade ideal: 60-70%\n• Luminosidade: 200-400 µmol/m²/s\n• pH solo: 5.5-6.5\n• EC solo: 1.5-3.5 mS/cm\n\nTemperaturas acima de 30°C reduzem a floração!"
        
        if 'alface' in mensagem_lower:
            return "🥬 **Cultivo de Alface:**\n• Temperatura ideal: 15-20°C\n• Umidade ideal: 60-80%\n• Luminosidade: 150-300 µmol/m²/s\n• pH solo: 6.0-7.0\n• EC solo: 1.0-2.0 mS/cm\n\nPrefere temperaturas mais amenas!"
        
        return "Posso dar informações específicas sobre tomate, alface, couve, rúcula ou manjericão. Sobre qual planta gostaria de saber?"
    
    # Resposta padrão para outras perguntas sobre plantas/estufa
    if any(palavra in mensagem_lower for palavra in ['planta', 'cultivo', 'estufa', 'horta', 'jardim']):
        return "Sou especialista em condições de estufa! Posso ajudar com:\n• Temperatura e umidade atual\n• Análise das condições\n• Recomendações específicas\n• Informações sobre cultivo de plantas\n\nO que gostaria de saber especificamente?"
    
    # Resposta para perguntas fora do tema
    return "Sou especializado em estufas e cultivo de plantas. Posso ajudar você com informações sobre temperatura, umidade, condições ideais para cultivo e recomendações para suas plantas. Tem alguma pergunta sobre isso?"

@app.route("/health")
def health():
    # Verifica conexão com servidor externo
    try:
        test_response = fetch_external_data("/registros", {"limit": 1})
        conexao_externa = test_response is not None
    except:
        conexao_externa = False
    
    status = {
        "ok": system_ready,
        "msg": "Sistema pronto" if system_ready else "Sistema inicializando",
        "dados_carregados": len(data_cache['dados']) if system_ready else 0,
        "conexao_externa": conexao_externa
    }
    return jsonify(status)

@app.route("/init-status")
def init_status():
    """Retorna o status detalhado da inicialização"""
    status = {
        "system_ready": system_ready,
        "dados_carregados": len(data_cache['dados']),
        "exige_20_dados": True,
        "mensagem": "Sistema pronto com 20 dados reais" if system_ready else "Aguardando 20 dados reais do servidor externo"
    }
    return jsonify(status)

@app.route("/debug")
def debug():
    """Rota para debug - mostra dados brutos do servidor externo"""
    data = fetch_external_data("/registros", {"limit": 5})
    return jsonify({
        "dados_brutos": data,
        "quantidade": len(data) if data else 0,
        "system_ready": system_ready,
        "cache_size": len(data_cache['dados'])
    })

@app.route("/dados")
def dados():
    limit = int(request.args.get("limit", 20))
    try:
        # Se o sistema não está pronto, retorna vazio
        if not system_ready:
            return jsonify([])
        
        # Sistema pronto - busca dados atualizados
        data = fetch_external_data("/registros", {"limit": limit})
        if data is not None and data:
            processed_data = []
            for item in data:
                try:
                    temp = float(item.get("temperatura", 0))
                    umid = float(item.get("umidade", 0))
                    processed_data.append({
                        "time": item.get("timestamp", ""),
                        "temperatura": temp,
                        "umidade": umid
                    })
                except (ValueError, TypeError):
                    continue
            
            # Atualiza cache apenas se tiver dados suficientes
            if len(processed_data) >= 20:
                data_cache['dados'] = processed_data
                data_cache['last_update'] = time.time()
            
            return jsonify(processed_data)
        
        # Se não conseguir dados novos, retorna cache apenas se tiver 20+
        if len(data_cache['dados']) >= 20:
            return jsonify(data_cache['dados'][-limit:])
        else:
            return jsonify([])
        
    except Exception as e:
        print(f"DEBUG: Erro em /dados: {e}")
        # Retorna vazio em caso de erro
        return jsonify([])

@app.route("/series")
def series():
    limit = int(request.args.get("limit", 20))
    try:
        # Se o sistema não está pronto, retorna estrutura vazia
        if not system_ready:
            return jsonify({'time': [], 'temperatura': [], 'umidade': []})
        
        # Sistema pronto - busca dados atualizados
        data = fetch_external_data("/registros", {"limit": limit})
        if data is not None and data:
            data_sorted = sorted(data, key=lambda x: x.get("timestamp", ""), reverse=True)
            if limit and len(data_sorted) > limit:
                data_sorted = data_sorted[:limit]
            
            data_sorted.reverse()
            
            times = []
            temps = []
            umids = []
            
            for item in data_sorted:
                timestamp = item.get("timestamp", "")
                if len(timestamp) > 16:
                    times.append(timestamp[11:16])
                else:
                    times.append(timestamp)
                
                try:
                    temp = float(item.get("temperatura", 0))
                    umid = float(item.get("umidade", 0))
                    temps.append(temp)
                    umids.append(umid)
                except (ValueError, TypeError):
                    continue
            
            series_data = {
                "time": times,
                "temperatura": temps,
                "umidade": umids,
            }
            
            # Atualiza cache apenas se tiver dados suficientes
            if len(temps) >= 20 and len(umids) >= 20:
                data_cache['series'] = series_data
                data_cache['last_update'] = time.time()
            
            return jsonify(series_data)
        
        # Fallback para cache apenas se tiver dados
        if len(data_cache['series']['temperatura']) >= 20:
            return jsonify(data_cache['series'])
        else:
            return jsonify({'time': [], 'temperatura': [], 'umidade': []})
        
    except Exception as e:
        print(f"DEBUG: Erro em /series: {e}")
        return jsonify({'time': [], 'temperatura': [], 'umidade': []})

@app.route("/analise")
def analise():
    limit = int(request.args.get("limit", 20))
    try:
        # Se o sistema não está pronto, retorna estrutura vazia
        if not system_ready:
            return jsonify({})
        
        # Sistema pronto - busca dados atualizados
        data = fetch_external_data("/registros", {"limit": limit})
        if data is not None and data:
            pts = []
            for item in data:
                try:
                    pts.append({
                        "temperatura": float(item.get("temperatura", 0)),
                        "umidade": float(item.get("umidade", 0))
                    })
                except (ValueError, TypeError):
                    continue
            
            if pts and len(pts) >= 20:
                result = analyzer.analisar(pts)
                # Atualiza cache
                data_cache['analise'] = result
                data_cache['last_update'] = time.time()
                return jsonify(result)
        
        # Fallback para cache apenas se tiver análise válida
        if data_cache['analise'] and data_cache['analise'].get('temperatura', {}).get('media', 0) > 0:
            return jsonify(data_cache['analise'])
        else:
            return jsonify({})
        
    except Exception as e:
        print(f"DEBUG: Erro em /analise: {e}")
        return jsonify({})

@app.route("/dados_completos")
def dados_completos():
    """Rota para ver todos os campos dos dados (para debug)"""
    limit = int(request.args.get("limit", 10))
    try:
        data = fetch_external_data("/registros", {"limit": limit})
        if data is not None and data:
            return jsonify(data)
        return jsonify({"erro": "Sem dados disponíveis"})
    except Exception as e:
        return jsonify({"erro": f"Falha ao buscar dados: {e}"}), 500

@app.route("/export.csv")
def export_csv():
    try:
        data = fetch_external_data("/registros")
        if data is not None and data:
            # Cria arquivo CSV
            export_path = "/app/exports/sensores.csv"
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            
            with open(export_path, "w", newline="", encoding="utf-8") as f:
                import csv
                w = csv.writer(f)
                # Inclui todos os campos
                w.writerow(["timestamp", "temperatura", "umidade", "luminosidade", "nivel_reservatorio", "bomba_agua", "exaustor", "ventilador", "luminaria", "emergencia"])
                for p in data:
                    w.writerow([
                        p.get("timestamp", ""),
                        p.get("temperatura", 0),
                        p.get("umidade", 0),
                        p.get("luminosidade", 0),
                        p.get("nivel_reservatorio", 0),
                        p.get("bomba_agua", 0),
                        p.get("exaustor", 0),
                        p.get("ventilador", 0),
                        p.get("luminaria", 0),
                        p.get("emergencia", 0)
                    ])
            
            return send_file(
                export_path, 
                mimetype="text/csv", 
                as_attachment=True, 
                download_name="sensores_completos.csv"
            )
        
        return jsonify({"erro": "Falha ao exportar dados"}), 500
    except Exception as e:
        return jsonify({"erro": f"Falha na exportação: {e}"}), 500

@app.route("/chat", methods=["POST"])
def chat():
    """
    Chat inteligente para estufas - VERSÃO MELHORADA
    """
    try:
        data = request.get_json(force=True)
        raw_msg = data.get("mensagem", "").strip()
        session_id = data.get("session_id")
        
        if not raw_msg:
            return jsonify({"erro": "mensagem vazia"}), 400

        # Obtém ou cria sessão
        session_id, conversation_history = get_or_create_session(session_id)
        
        # Busca dados atuais da estufa para contexto
        dados_estufa = {}
        try:
            analise_data = data_cache['analise']
            if analise_data and analise_data.get('temperatura') and analise_data.get('umidade'):
                dados_estufa = {
                    'mediaTemperatura': analise_data['temperatura'].get('media', 0),
                    'mediaUmidade': analise_data['umidade'].get('media', 0),
                    'minTemperatura': analise_data['temperatura'].get('min', 0),
                    'maxTemperatura': analise_data['temperatura'].get('max', 0),
                    'minUmidade': analise_data['umidade'].get('min', 0),
                    'maxUmidade': analise_data['umidade'].get('max', 0)
                }
        except:
            pass

        # Gera resposta inteligente
        resposta = gerar_resposta_inteligente(raw_msg, dados_estufa)
        
        # Adiciona ao histórico
        add_to_history(session_id, "user", raw_msg)
        add_to_history(session_id, "assistant", resposta)
        
        return jsonify({
            "resposta": resposta,
            "session_id": session_id
        })

    except Exception as e:
        print(f"DEBUG: Erro geral em /chat: {e}")
        return jsonify({"resposta": "Desculpe, estou com problemas técnicos no momento. Tente novamente em alguns instantes!"})

@app.route("/test-ollama")
def test_ollama():
    """Testa conexão com Ollama"""
    try:
        test_payload = {
            "model": "llama3.2:1b",
            "prompt": "Responda em uma palavra: OK",
            "stream": False
        }
        
        r = requests.post("http://ollama:11434/api/generate", 
                         json=test_payload, 
                         timeout=10)
        
        if r.status_code == 200:
            return jsonify({"status": "conectado", "resposta": r.json()})
        else:
            return jsonify({"status": "erro", "code": r.status_code})
            
    except Exception as e:
        return jsonify({"status": "erro", "details": str(e)})

@app.route("/conversations")
def list_conversations():
    """Lista conversas ativas (apenas para debug)"""
    active_sessions = {}
    for session_id, data in conversation_histories.items():
        active_sessions[session_id] = {
            'message_count': len(data['history']),
            'last_activity': data['last_activity'].isoformat(),
            'created_at': data['created_at'].isoformat()
        }
    return jsonify(active_sessions)

@app.route("/")
def index():
    return send_from_directory("../frontend", "index.html")

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory("../frontend", path)

if __name__ == "__main__":
    print(f"Backend iniciado - Conectando ao servidor externo: {EXTERNAL_SERVER_URL}")
    print(f"Usuário: {USERNAME}")
    print(f"Ollama URL: {OLLAMA_URL}")
    print("🔄 Sistema de inicialização ativado...")
    print("⏳ AGUARDANDO 20 DADOS REAIS PARA INICIAR...")
    app.run(host="0.0.0.0", port=5000)
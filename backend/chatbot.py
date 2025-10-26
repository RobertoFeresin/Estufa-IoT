import requests
import json
import logging

# Endereço do Ollama local
OLLAMA_URL = "http://localhost:11434/api/chat"

def responder(mensagem: str) -> str:
    """
    Tenta responder via Ollama (tinyllama/gemma/phi3:mini).
    Se falhar, usa respostas padrão.
    """
    try:
        payload = {
            "model": "qwen2:1.5b",  # ou "gemma2:2b" se houver memória suficiente
            "stream": False,
            "options": {"num_predict": 128, "temperature": 0.6},
            "messages": [
                {"role": "system", "content": "Responda sempre em português do Brasil."},
                {"role": "user", "content": mensagem}
            ]
        }

        r = requests.post(OLLAMA_URL, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=60)

        if r.status_code == 200:
            data = r.json()
            resposta = data.get("message", {}).get("content") or data.get("response")
            if resposta:
                return resposta.strip()

        logging.warning(f"⚠️ Falha na IA: {r.status_code} - {r.text}")
        return resposta_padrao(mensagem)

    except Exception as e:
        logging.error(f"❌ Erro ao conectar com Ollama: {e}")
        return resposta_padrao(mensagem)


def resposta_padrao(mensagem: str) -> str:
    """
    Fallback local simples, caso a IA falhe.
    """
    m = mensagem.lower()
    if "temperatura" in m:
        return "A temperatura é atualizada a cada poucos segundos e você pode ver a média na seção de análise."
    if "umidade" in m:
        return "A umidade está sob controle; veja o gráfico em tempo real no painel."
    if "csv" in m or "export" in m or "baixar" in m:
        return "Você pode exportar os dados acessando o link /export.csv."
    return "Sou o assistente da Estufa IoT 🌱. Posso responder sobre temperatura, umidade ou exportação de dados."

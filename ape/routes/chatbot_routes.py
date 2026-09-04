from flask import Blueprint, request, jsonify
import requests

chatbot_bp = Blueprint('chatbot', __name__)

# URL do Webhook do n8n (Cole aqui a URL de produção do seu nó Webhook do n8n)
N8N_WEBHOOK_URL = 'https://seu-n8n.webhook.url/webhook/chat'

@chatbot_bp.route('/api/chat', methods=['POST'])
def receber_mensagem_chat():
    dados = request.get_json()
    mensagem_usuario = dados.get('message')

    if not mensagem_usuario:
        return jsonify({'error': 'Mensagem vazia'}), 400

    try:
        # Repassa a mensagem do usuário para o n8n processar (com IA, banco, etc.)
        resposta_n8n = requests.post(N8N_WEBHOOK_URL, json={
            'message': mensagem_usuario,
            'origem': 'site_lumenarch'
        })
        
        # Pega a resposta que o n8n devolveu
        dados_n8n = resposta_n8n.json()
        
        # Extrai o texto da resposta do n8n (ajuste a chave conforme o seu fluxo)
        texto_resposta = dados_n8n.get('output', 'Recebido com sucesso!')

        return jsonify({'output': texto_resposta})

    except Exception as e:
        print(f"Erro ao comunicar com o n8n: {e}")
        return jsonify({'output': 'Desculpe, estou enfrentando instabilidades no momento.'}), 500
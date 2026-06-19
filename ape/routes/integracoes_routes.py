from flask import Blueprint, request, jsonify
from modules.integracoes.ifood.service_ifood import processar_webhook_ifood
from utils.logger import log_erro
import traceback

integracoes_bp = Blueprint("integracoes", __name__)


@integracoes_bp.route("/integracoes/ifood/webhook/<int:id_empresa>", methods=["POST"])
def webhook_ifood(id_empresa):

    try:
        payload = request.get_json()

        if not payload:
            return jsonify({"erro": "Payload inválido"}), 400

        sucesso = processar_webhook_ifood(id_empresa, payload)

        if sucesso:
            return jsonify({"status": "ok"}), 200

        return jsonify({
            "status": "erro",
            "mensagem": "Falha ao processar evento"
        }), 500

    except Exception as e:

        erro_detalhado = traceback.format_exc()

        log_erro(
            f"""
Erro: {str(e)}

Traceback:
{erro_detalhado}
"""
        )

        traceback.print_exc()

        return jsonify({
            "status": "erro",
            "mensagem": "Erro interno"
        }), 500
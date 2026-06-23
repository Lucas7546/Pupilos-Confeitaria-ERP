from flask import Blueprint, request, jsonify, render_template
from modules.tenant_db import db_admin_conn
import traceback

billing_bp = Blueprint("billing", __name__)


@billing_bp.route("/conta-bloqueada")
def conta_bloqueada():
    return render_template("conta_bloqueada.html")


@billing_bp.route("/billing/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()

        print(f"WEBHOOK RECEBIDO: {data}")

        id_empresa = data.get("id_empresa")
        status = data.get("status")

        if not id_empresa:
            return jsonify({"erro": "id_empresa ausente"}), 400

        with db_admin_conn() as conn:
            with conn.cursor() as cur:

                if status == "paid":
                    cur.execute("""
                        UPDATE empresa_planos
                        SET status_assinatura = 'active',
                            dias_atraso = 0,
                            bloqueado = FALSE,
                            ultimo_pagamento = NOW()
                        WHERE id_empresa = %s
                    """, (id_empresa,))

                    print(f"Pagamento confirmado empresa {id_empresa}")

                elif status == "overdue":
                    cur.execute("""
                        UPDATE empresa_planos
                        SET status_assinatura = 'overdue'
                        WHERE id_empresa = %s
                    """, (id_empresa,))

                    print(f"Empresa {id_empresa} em overdue")

                else:
                    return jsonify({"erro": "status inválido"}), 400

        return jsonify({"ok": True}), 200

    except Exception as e:
        erro_detalhado = traceback.format_exc()
        print(f"Erro webhook billing: {erro_detalhado}")
        traceback.print_exc()
        return jsonify({"erro": str(e)}), 500